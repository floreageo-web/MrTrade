import pandas as pd
import numpy as np
import json
import logging
import time
import random
import warnings
from datetime import datetime
from yahooquery import Ticker
from indicators import add_indicators, is_bullish_candle, is_engulfing, is_pin_bar
from config import (RSI_MIN, RSI_MAX, PRICE_MIN, PRICE_MAX, RR_TP1, RR_TP2,
                    CAPITAL, RISK_PER_TRADE, TICKERS)

# Dezactivăm avertismentele care poluează log-ul
warnings.simplefilter(action='ignore', category=FutureWarning)
log = logging.getLogger(__name__)

def backtest_ticker(ticker_symbol: str, period: str = "2y") -> dict | None:
    """Rulează backtesting pentru un singur ticker folosind yahooquery."""
    try:
        t = Ticker(ticker_symbol, asynchronous=False, formatted=False)
        df = t.history(period=period, interval="1d")

        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            return None
            
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(ticker_symbol, level='symbol')

        if len(df) < 250:
            return None

        df.rename(columns={
            'open': 'Open', 'high': 'High', 'low': 'Low', 
            'close': 'Close', 'volume': 'Volume'
        }, inplace=True)

        df.dropna(inplace=True)
        df = add_indicators(df)
        
    except Exception as e:
        log.warning(f"⚠️ Eroare la descărcare/indicatori pentru {ticker_symbol}: {e}")
        return None

    trades = []
    in_trade = False
    entry_price = sl = tp1 = tp2 = 0.0
    entry_date = ""

    # Începem de la 210 pentru a avea date istorice suficiente pentru indicatori și comparații RSI
    for i in range(210, len(df) - 1):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        price = float(row["Close"])

        if not (PRICE_MIN <= price <= PRICE_MAX):
            continue

        # --- LOGICA DE IEȘIRE ---
        if in_trade:
            high = float(row["High"])
            low = float(row["Low"])
            result = None

            if low <= sl:
                result = {"exit": sl, "type": "SL", "r": -1.0}
            elif high >= tp2:
                result = {"exit": tp2, "type": "TP2", "r": RR_TP2}
            elif high >= tp1:
                result = {"exit": tp1, "type": "TP1", "r": RR_TP1}

            if result:
                trades.append({
                    "entry_date": entry_date,
                    "exit_date": row.name.strftime("%Y-%m-%d") if hasattr(row.name, 'strftime') else str(row.name),
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(result["exit"], 2),
                    "exit_type": result["type"],
                    "r": result["r"],
                    "profit_$": round(result["r"] * CAPITAL * RISK_PER_TRADE, 2),
                })
                in_trade = False
            continue

        # --- CONDIȚII DE INTRARE (RAFINTATE CU LOGICĂ DE PULLBACK) ---
        ema21 = float(row["EMA21"])
        ema50 = float(row["EMA50"])
        ema200 = float(row["EMA200"])
        rsi_acum = float(row["RSI"])
        atr = float(row["ATR"])
        
        # Luăm RSI-ul de acum 4 zile pentru a verifica dacă prețul s-a "răcit"
        rsi_acum_4_zile = float(df.iloc[i-4]["RSI"])

        # 1. Trendul principal (Tauri)
        trend_ok = (ema50 > ema200) and (price > ema50)
        
        # 2. Zona de RSI (Pullback)
        rsi_zona_ok = (RSI_MIN <= rsi_acum <= RSI_MAX)
        
        # 3. FILTRU PULLBACK: RSI actual trebuie să fie mai mic decât acum 4 zile
        # (Asta elimină situațiile în care prețul vine de jos, de la RSI 30 în sus)
        este_pullback = rsi_acum < rsi_acum_4_zile
        
        # 4. Apropierea de EMA21 (Suport)
        ema21_ok = abs(price - ema21) / ema21 <= 0.02
        
        # 5. Candlestick de confirmare
        candle_ok = is_bullish_candle(row) or is_engulfing(prev, row) or is_pin_bar(row)

        if trend_ok and rsi_zona_ok and este_pullback and ema21_ok and candle_ok:
            in_trade = True
            entry_price = price
            entry_date = row.name.strftime("%Y-%m-%d") if hasattr(row.name, 'strftime') else str(row.name)
            
            risk = 1.5 * atr
            sl = price - risk
            tp1 = price + risk * RR_TP1
            tp2 = price + risk * RR_TP2

    return _calc_stats(ticker_symbol, trades)

def _calc_stats(ticker: str, trades: list) -> dict:
    # ... (Această funcție rămâne identică cu cea originală) ...
    if not trades:
        return {"ticker": ticker, "trades": 0, "message": "Fără tranzacții"}
    total = len(trades)
    wins = [t for t in trades if t["r"] > 0]
    losses = [t for t in trades if t["r"] <= 0]
    win_rate = len(wins) / total * 100
    total_r = sum(t["r"] for t in trades)
    total_pnl = sum(t["profit_$"] for t in trades)
    equity = [CAPITAL]
    running = CAPITAL
    for t in trades:
        running += t["profit_$"]
        equity.append(running)
    peak = CAPITAL
    max_dd = 0
    for e in equity:
        if e > peak: peak = e
        dd = (peak - e) / peak * 100
        if dd > max_dd: max_dd = dd
    gross_win = sum(t["profit_$"] for t in wins)
    gross_loss = abs(sum(t["profit_$"] for t in losses)) or 1
    pf = round(gross_win / gross_loss, 2)
    return {
        "ticker": ticker, "trades": total, "wins": len(wins), "losses": len(losses),
        "win_rate": round(win_rate, 1), "total_r": round(total_r, 2), "total_pnl_$": round(total_pnl, 2),
        "profit_factor": pf, "max_drawdown": round(max_dd, 1), "final_capital": round(equity[-1], 2),
        "trade_list": trades, "equity_curve": equity,
    }

def backtest_all(tickers: list = None, top_n: int = 20) -> dict:
    # ... (Rămâne identică cu cea originală, asigură pauzele între cereri) ...
    tickers = tickers or TICKERS
    results = []
    processed = 0
    log.info(f"🔄 Start backtesting pentru {len(tickers)} tickere...")
    for ticker in tickers:
        result = backtest_ticker(ticker)
        if result and result.get("trades", 0) >= 3:
            results.append(result)
        processed += 1
        time.sleep(random.uniform(1.5, 3.5))
        if processed % 20 == 0:
            log.info(f"📊 Progres: {processed}/{len(tickers)}")
    if not results:
        return {"error": "Nu s-au găsit date suficiente pentru backtest"}
    results.sort(key=lambda x: x.get("total_r", 0), reverse=True)
    all_trades = [t for r in results for t in r.get("trade_list", [])]
    all_wins = [t for t in all_trades if t["r"] > 0]
    summary = {
        "total_tickers_tested": len(results),
        "total_trades": len(all_trades),
        "aggregate_win_rate": round(len(all_wins)/len(all_trades)*100, 1) if all_trades else 0,
        "aggregate_total_r": round(sum(t["r"] for t in all_trades), 2),
        "aggregate_pnl_$": round(sum(t["profit_$"] for t in all_trades), 2),
        "top_performers": results[:top_n],
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    with open("backtest_results.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)
    return summary

def format_backtest_summary(summary: dict) -> str:
    # ... (Rămâne identică cu cea originală) ...
    if "error" in summary:
        return f"❌ Backtest eșuat: {summary['error']}"
    top = summary.get("top_performers", [])[:5]
    top_text = ""
    for r in top:
        top_text += f"  • `{r['ticker']}`: {r['win_rate']}% WR | {r['total_r']}R\n"
    return (
        f"📊 *RAPORT BACKTESTING (12 luni)*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔢 *Acțiuni analizate:* `{summary['total_tickers_tested']}`\n"
        f"📋 *Tranzacții totale:* `{summary['total_trades']}`\n"
        f"✅ *Win Rate global:* `{summary['aggregate_win_rate']}%`\n"
        f"💹 *Total R profit:* `{summary['aggregate_total_r']}R`\n"
        f"💰 *P&L estimat:* `${summary['aggregate_pnl_$']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 *Top Performeri:*\n{top_text}\n"
        f"📅 *Generat:* `{summary['generated_at']}`"
    )
