# ============================================================
# backtester.py — Versiune optimizată (Citire locală)
# ============================================================

import pandas as pd
import numpy as np
import json
import logging
import os
from datetime import datetime
from indicators import add_indicators, is_bullish_candle, is_engulfing, is_pin_bar
from config import (RSI_MIN, RSI_MAX, PRICE_MIN, PRICE_MAX, RR_TP1, RR_TP2,
                    CAPITAL, RISK_PER_TRADE, TICKERS)

log = logging.getLogger(__name__)

def backtest_ticker(ticker: str) -> dict | None:
    """Rulează backtesting folosind datele salvate local în folderul /data."""
    try:
        # --- MODIFICARE CHEIE: Citim din CSV-ul local, nu de pe Yahoo ---
        file_path = f"data/{ticker}.csv"
        
        if not os.path.exists(file_path):
            # Nu dăm warning aici pentru a nu polua log-urile dacă e normal să lipsească
            return None
            
        df = pd.read_csv(file_path, index_col=0, parse_dates=True)
        
        if df is None or len(df) < 100: # Minim de date pentru indicatori
            return None
            
        df.dropna(inplace=True)
        # Recalculăm indicatorii pe datele istorice
        df = add_indicators(df)
        
    except Exception as e:
        log.warning(f"⚠️ Eroare citire date locale pentru {ticker}: {e}")
        return None

    trades  = []
    in_trade = False
    entry_price = sl = tp1 = tp2 = 0.0
    entry_date = ""

    # Începem de la 200 pentru a lăsa EMA200 să se calculeze corect
    for i in range(200, len(df) - 1):
        row  = df.iloc[i]
        prev = df.iloc[i - 1]
        price = float(row["Close"])

        # Verificare filtru preț (opțional în backtest)
        if not (PRICE_MIN <= price <= PRICE_MAX):
            continue

        # --- LOGICĂ IEȘIRE ---
        if in_trade:
            high = float(row["High"])
            low  = float(row["Low"])
            result = None

            if low <= sl:
                result = {"exit": sl, "type": "SL", "r": -1.0}
            elif high >= tp2:
                result = {"exit": tp2, "type": "TP2", "r": RR_TP2}
            elif high >= tp1:
                # Strategie simplificată: ieșim la TP1 sau ținem până la TP2/SL
                # Poți adăuga aici logică de Break Even
                result = {"exit": tp1, "type": "TP1", "r": RR_TP1}

            if result:
                trades.append({
                    "entry_date":  entry_date,
                    "exit_date":   row.name.strftime("%Y-%m-%d") if hasattr(row.name, 'strftime') else str(row.name),
                    "entry_price": round(entry_price, 2),
                    "exit_price":  round(result["exit"], 2),
                    "exit_type":   result["type"],
                    "r":           result["r"],
                    "profit_$":    round(result["r"] * CAPITAL * RISK_PER_TRADE, 2),
                })
                in_trade = False
            continue

        # --- CONDIȚII DE INTRARE ---
        # Folosim .get() pentru siguranță în cazul în care coloana lipsește
        ema21  = float(row.get("EMA21", 0))
        ema50  = float(row.get("EMA50", 0))
        ema200 = float(row.get("EMA200", 0))
        rsi    = float(row.get("RSI", 50))
        atr    = float(row.get("ATR", 0))

        if atr == 0: continue

        trend_ok   = (ema50 > ema200) and (price > ema50)
        rsi_ok     = (RSI_MIN <= rsi <= RSI_MAX)
        # Distanța față de EMA21 să fie mică (Pullback)
        ema21_ok   = abs(price - ema21) / ema21 <= 0.03 
        candle_ok  = is_bullish_candle(row) or is_engulfing(prev, row) or is_pin_bar(row)

        if trend_ok and rsi_ok and ema21_ok and candle_ok:
            in_trade    = True
            entry_price = price
            entry_date  = row.name.strftime("%Y-%m-%d") if hasattr(row.name, 'strftime') else str(row.name)
            risk        = 1.5 * atr
            sl          = price - risk
            tp1         = price + risk * RR_TP1
            tp2         = price + risk * RR_TP2

    return _calc_stats(ticker, trades)

def _calc_stats(ticker: str, trades: list) -> dict:
    """Calculează statisticile (rămâne neschimbat, dar curățat)."""
    if not trades:
        return {"ticker": ticker, "trades": 0, "total_r": 0}

    total = len(trades)
    wins = [t for t in trades if t["r"] > 0]
    losses = [t for t in trades if t["r"] <= 0]
    
    win_rate = (len(wins) / total * 100) if total > 0 else 0
    total_r = sum(t["r"] for t in trades)
    total_pnl = sum(t["profit_$"] for t in trades)

    # Profit Factor
    gross_win = sum(t["profit_$"] for t in wins)
    gross_loss = abs(sum(t["profit_$"] for t in losses)) or 1
    pf = round(gross_win / gross_loss, 2)

    return {
        "ticker": ticker,
        "trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 1),
        "total_r": round(total_r, 2),
        "total_pnl_$": round(total_pnl, 2),
        "profit_factor": pf,
        "trade_list": trades
    }

def backtest_all(tickers: list = None, top_n: int = 15) -> dict:
    """Rulează procesul peste tot ce există local."""
    tickers = tickers or TICKERS
    results = []

    log.info(f"🔄 Start backtesting LOCAL pe {len(tickers)} tickere...")

    for ticker in tickers:
        result = backtest_ticker(ticker)
        # Luăm doar tickerele care au avut măcar o tranzacție
        if result and result.get("trades", 0) > 0:
            results.append(result)

    if not results:
        log.warning("❌ Nu s-au găsit tranzacții în backtest.")
        return {}

    # Sortare după performanță
    results.sort(key=lambda x: x.get("total_r", 0), reverse=True)

    summary = {
        "total_tickers_tested": len(results),
        "total_trades": sum(r["trades"] for r in results),
        "aggregate_total_r": round(sum(r["total_r"] for r in results), 2),
        "top_performers": results[:top_n],
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    with open("backtest_results.json", "w") as f:
        json.dump(summary, f, indent=2)
        
    return summary
