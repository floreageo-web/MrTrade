# ============================================================
# backtester.py — Backtesting strategie pe 12 luni
# ============================================================

import yfinance as yf
import pandas as pd
import numpy as np
import json
import logging
from datetime import datetime
from indicators import add_indicators, is_bullish_candle, is_engulfing, is_pin_bar
from config import (RSI_MIN, RSI_MAX, PRICE_MIN, PRICE_MAX, RR_TP1, RR_TP2,
                    CAPITAL, RISK_PER_TRADE, TICKERS)

log = logging.getLogger(__name__)


def backtest_ticker(ticker: str, period: str = "2y") -> dict | None:
    """Rulează backtesting pentru un singur ticker."""
    try:
        df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
        if df is None or len(df) < 250:
            return None
        df.dropna(inplace=True)
        df = add_indicators(df)
    except Exception as e:
        log.warning(f"Eroare backtesting {ticker}: {e}")
        return None

    trades  = []
    in_trade = False
    entry_price = sl = tp1 = tp2 = 0.0

    for i in range(210, len(df) - 1):
        row  = df.iloc[i]
        prev = df.iloc[i - 1]
        price = float(row["Close"])

        if not (PRICE_MIN <= price <= PRICE_MAX):
            continue

        # --- IEȘIRE din tranzacție activă ---
        if in_trade:
            high  = float(row["High"])
            low   = float(row["Low"])
            result = None

            if low <= sl:
                result = {"exit": sl, "type": "SL", "r": -1.0}
            elif high >= tp2:
                result = {"exit": tp2, "type": "TP2", "r": RR_TP2}
            elif high >= tp1:
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
        ema21  = float(row["EMA21"])
        ema50  = float(row["EMA50"])
        ema200 = float(row["EMA200"])
        rsi    = float(row["RSI"])
        atr    = float(row["ATR"])

        trend_ok   = (ema50 > ema200) and (price > ema50)
        rsi_ok     = (RSI_MIN <= rsi <= RSI_MAX)
        ema21_ok   = abs(price - ema21) / ema21 <= 0.02
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
    """Calculează statisticile pentru un set de tranzacții."""
    if not trades:
        return {"ticker": ticker, "trades": 0, "message": "Nu s-au găsit tranzacții"}

    total     = len(trades)
    wins      = [t for t in trades if t["r"] > 0]
    losses    = [t for t in trades if t["r"] <= 0]
    win_rate  = len(wins) / total * 100
    total_r   = sum(t["r"] for t in trades)
    total_pnl = sum(t["profit_$"] for t in trades)

    # Calcul Drawdown maxim
    equity    = [CAPITAL]
    running   = CAPITAL
    for t in trades:
        running += t["profit_$"]
        equity.append(running)
    peak      = CAPITAL
    max_dd    = 0
    for e in equity:
        if e > peak:
            peak = e
        dd = (peak - e) / peak * 100
        if dd > max_dd:
            max_dd = dd

    # Profit Factor
    gross_win  = sum(t["profit_$"] for t in wins)
    gross_loss = abs(sum(t["profit_$"] for t in losses)) or 1
    pf         = round(gross_win / gross_loss, 2)

    # Avg R
    avg_win_r  = round(sum(t["r"] for t in wins) / len(wins), 2)  if wins   else 0
    avg_loss_r = round(sum(t["r"] for t in losses) / len(losses), 2) if losses else 0

    return {
        "ticker":       ticker,
        "trades":       total,
        "wins":         len(wins),
        "losses":       len(losses),
        "win_rate":     round(win_rate, 1),
        "total_r":      round(total_r, 2),
        "total_pnl_$":  round(total_pnl, 2),
        "avg_win_r":    avg_win_r,
        "avg_loss_r":   avg_loss_r,
        "profit_factor":pf,
        "max_drawdown": round(max_dd, 1),
        "final_capital":round(equity[-1], 2),
        "trade_list":   trades,
        "equity_curve": equity,
    }


def backtest_all(tickers: list = None, top_n: int = 20) -> dict:
    """
    Rulează backtesting pe toate tickerele sau primele N.
    Returnează statistici agregate + top performeri.
    """
    tickers   = tickers or TICKERS
    results   = []
    processed = 0

    log.info(f"🔄 Start backtesting pentru {len(tickers)} tickere...")

    for ticker in tickers:
        result = backtest_ticker(ticker)
        if result and result.get("trades", 0) >= 3:
            results.append(result)
        processed += 1
        if processed % 20 == 0:
            log.info(f"📊 Progres backtesting: {processed}/{len(tickers)}")

    if not results:
        return {"error": "Nu s-au găsit date suficiente"}

    # Sortează după Total R
    results.sort(key=lambda x: x.get("total_r", 0), reverse=True)

    # Statistici agregate
    all_trades    = [t for r in results for t in r.get("trade_list", [])]
    all_wins      = [t for t in all_trades if t["r"] > 0]
    aggregate_wr  = round(len(all_wins) / len(all_trades) * 100, 1) if all_trades else 0
    aggregate_r   = round(sum(t["r"] for t in all_trades), 2)
    aggregate_pnl = round(sum(t["profit_$"] for t in all_trades), 2)

    summary = {
        "total_tickers_tested": len(results),
        "total_trades":         len(all_trades),
        "aggregate_win_rate":   aggregate_wr,
        "aggregate_total_r":    aggregate_r,
        "aggregate_pnl_$":      aggregate_pnl,
        "top_performers":       results[:top_n],
        "all_results":          results,
        "generated_at":         datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    # Salvează rezultatele
    with open("backtest_results.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)
    log.info(f"✅ Backtesting finalizat! Rezultate salvate în backtest_results.json")

    return summary


def format_backtest_summary(summary: dict) -> str:
    """Formatează sumar backtesting pentru Telegram."""
    top = summary.get("top_performers", [])[:5]
    top_text = ""
    for r in top:
        top_text += f"  • `{r['ticker']}` — {r['win_rate']}% WR | {r['total_r']}R | PF: {r['profit_factor']}\n"

    return (
        f"📊 *RAPORT BACKTESTING* (12 luni)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔢 *Tickere testate:* `{summary['total_tickers_tested']}`\n"
        f"📋 *Total tranzacții:* `{summary['total_trades']}`\n"
        f"✅ *Win Rate global:* `{summary['aggregate_win_rate']}%`\n"
        f"💹 *Total R câștigat:* `{summary['aggregate_total_r']}R`\n"
        f"💰 *P&L total:* `${summary['aggregate_pnl_$']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 *Top 5 acțiuni:*\n{top_text}"
        f"📅 *Generat:* `{summary['generated_at']}`"
    )
