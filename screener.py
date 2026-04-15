import yfinance as yf
import pandas as pd
import time
import logging
from datetime import datetime
from indicators import add_indicators, is_bullish_candle, is_engulfing, is_pin_bar
from config import (TICKERS, EMA_FAST, EMA_MID, EMA_SLOW, RSI_MIN, RSI_MAX,
                    PRICE_MIN, PRICE_MAX, CAPITAL, RISK_PER_TRADE, RR_TP1, RR_TP2)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

def run_screener():
    """Rulează scanarea prin descărcarea acțiunilor în grupuri mari (Bulk)."""
    signals = []
    total = len(TICKERS)
    
    log.info(f"🚀 Start scanare BULK — {total} tickere...")

    # 1. Descarcă TOATE datele într-o singură cerere (sau grupuri mari)
    # yfinance gestionează mult mai bine descărcarea listelor lungi
    try:
        all_data = yf.download(
            tickers=TICKERS,
            period="1y",
            interval="1d",
            group_by='ticker',
            progress=True,
            threads=True, # Descarcă în paralel pentru viteză
            auto_adjust=True
        )
    except Exception as e:
        log.error(f"❌ Eroare la descărcarea datelor bulk: {e}")
        return []

    # 2. Procesează datele pentru fiecare ticker
    for ticker in TICKERS:
        try:
            # Extrage dataframe-ul pentru ticker-ul curent
            if total > 1:
                df = all_data[ticker].copy()
            else:
                df = all_data.copy()

            df.dropna(inplace=True)
            
            if len(df) < 200:
                continue

            # Verifică semnalul folosind strategia ta
            signal = check_signal_logic(df, ticker)
            if signal:
                signals.append(signal)
                log.info(f"✅ SEMNAL GĂSIT: {ticker}")

        except Exception as e:
            continue

    signals.sort(key=lambda x: x["score"], reverse=True)
    log.info(f"✨ Finalizat! {len(signals)} semnale găsite.")
    return signals

def check_signal_logic(df, ticker):
    """Logica de strategie aplicată pe datele descărcate."""
    df = add_indicators(df)
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    price = float(last["Close"])
    if not (PRICE_MIN <= price <= PRICE_MAX): return None

    ema21, ema50, ema200 = float(last["EMA21"]), float(last["EMA50"]), float(last["EMA200"])
    if not (ema50 > ema200 and price > ema50): return None

    rsi = float(last["RSI"])
    if not (RSI_MIN <= rsi <= RSI_MAX): return None

    dist_ema21 = abs(price - ema21) / ema21
    if dist_ema21 > 0.02: return None

    if not (is_bullish_candle(last) or is_engulfing(prev, last) or is_pin_bar(last)):
        return None

    atr = float(last["ATR"])
    sl = round(price - 1.5 * atr, 2)
    risk = price - sl
    if risk <= 0.01: return None
    
    tp1, tp2 = round(price + risk * RR_TP1, 2), round(price + risk * RR_TP2, 2)
    shares = int((CAPITAL * RISK_PER_TRADE) / risk)

    score = 3
    if is_engulfing(prev, last): score += 1
    if is_pin_bar(last): score += 1

    return {
        "ticker": ticker, "price": round(price, 2), "rsi": round(rsi, 1),
        "dist_ema21": round(dist_ema21 * 100, 2), "sl": sl, "tp1": tp1, "tp2": tp2,
        "shares": shares, "risk_$": round(shares * risk, 2), "score": min(score, 5),
        "candle_type": "Engulfing" if is_engulfing(prev, last) else "Pin Bar" if is_pin_bar(last) else "Bullish",
        "date": datetime.now().strftime("%Y-%m-%d")
    }
