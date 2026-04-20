# ============================================================
# screener.py — Scanare LOCALĂ (fără Yahoo) + detectare semnale
# ============================================================

import pandas as pd
import os
import logging
from datetime import datetime
from indicators import add_indicators, is_bullish_candle, is_engulfing, is_pin_bar
from config import (TICKERS, EMA_FAST, EMA_MID, EMA_SLOW, RSI_MIN, RSI_MAX,
                    PRICE_MIN, PRICE_MAX, CAPITAL, RISK_PER_TRADE, RR_TP1, RR_TP2)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

def fetch_data(ticker: str) -> pd.DataFrame | None:
    """
    Citește datele din folderul local /data în loc să descarce de pe Yahoo.
    """
    try:
        file_path = f"data/{ticker}.csv"
        if not os.path.exists(file_path):
            # Dacă totuși vrei să încerci download dacă lipsește fișierul, 
            # poți lăsa yf.download aici, dar pentru siguranță acum returnăm None
            return None
            
        df = pd.read_csv(file_path, index_col=0, parse_dates=True)
        
        if df is None or len(df) < 200: 
            return None
            
        df.dropna(inplace=True)
        return df
    except Exception as e:
        log.warning(f"Eroare la citirea locală pentru {ticker}: {e}")
        return None

def check_signal(df: pd.DataFrame) -> dict | None:
    """Verifică dacă ultima lumânare îndeplinește condițiile."""
    df = add_indicators(df)
    if len(df) < 5:
        return None

    last  = df.iloc[-1]
    prev  = df.iloc[-2]
    
    price = float(last["Close"])

    if not (PRICE_MIN <= price <= PRICE_MAX):
        return None

    ema21  = float(last["EMA21"])
    ema50  = float(last["EMA50"])
    ema200 = float(last["EMA200"])

    trend_ok = (ema50 > ema200) and (price > ema50)
    if not trend_ok:
        return None

    rsi = float(last["RSI"])
    if not (RSI_MIN <= rsi <= RSI_MAX):
        return None

    dist_ema21 = abs(price - ema21) / ema21
    if dist_ema21 > 0.02:
        return None

    candle_ok = (
        is_bullish_candle(last) or
        is_engulfing(prev, last) or
        is_pin_bar(last)
    )
    if not candle_ok:
        return None

    atr   = float(last["ATR"])
    sl    = round(price - 1.5 * atr, 2)
    risk  = price - sl
    if risk <= 0: return None 
    
    tp1   = round(price + risk * RR_TP1, 2)
    tp2   = round(price + risk * RR_TP2, 2)

    risk_amount = CAPITAL * RISK_PER_TRADE
    shares      = int(risk_amount / risk) if risk > 0 else 0

    score = 3
    if is_engulfing(prev, last): score += 1
    if is_pin_bar(last): score += 1
    score = min(score, 5)

    return {
        "ticker":       "", 
        "price":        round(price, 2),
        "ema21":        round(ema21, 2),
        "ema50":        round(ema50, 2),
        "ema200":       round(ema200, 2),
        "rsi":          round(rsi, 1),
        "dist_ema21":   round(dist_ema21 * 100, 2),
        "sl":           sl,
        "tp1":          tp1,
        "tp2":          tp2,
        "risk_per_share": round(risk, 2),
        "shares":       shares,
        "risk_$":       round(shares * risk, 2),
        "score":        score,
        "candle_type": _candle_type(prev, last),
        "date":         datetime.now().strftime("%Y-%m-%d"),
    }

def _candle_type(prev, curr) -> str:
    from indicators import is_engulfing, is_pin_bar # Import local pentru siguranță
    if is_engulfing(prev, curr): return "Bullish Engulfing"
    if is_pin_bar(curr): return "Pin Bar"
    return "Bullish Candle"

def run_screener(tickers_list: list = None) -> list[dict]:
    """
    Rulează screener-ul folosind EXCLUSIV datele din folderul /data.
    """
    if tickers_list is None:
        tickers_list = TICKERS

    signals   = []
    total     = len(tickers_list)
    processed = 0

    log.info(f"🔍 Start screener LOCAL — {total} tickere de verificat...")

    for ticker in tickers_list:
        df = fetch_data(ticker)
        
        if df is not None:
            signal = check_signal(df)
            if signal:
                signal["ticker"] = ticker
                signals.append(signal)
                log.info(f"✅ SEMNAL: {ticker} | Preț: {signal['price']} | Scor: {signal['score']}/5")
        
        processed += 1
        if processed % 50 == 0:
            log.info(f"📊 Progres: {processed}/{total} acțiuni verificate...")

    signals.sort(key=lambda x: x["score"], reverse=True)
    log.info(f"✅ Screener finalizat — {len(signals)} semnale găsite.")
    return signals

def format_signal_message(signal: dict) -> str:
    stars = "⭐" * signal["score"]
    return (
        f"📈 *SEMNAL SWING TRADING* {stars}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷️ *Ticker:* `{signal['ticker']}`\n"
        f"💰 *Preț intrare:* `${signal['price']}`\n"
        f"📊 *RSI:* `{signal['rsi']}`\n"
        f"📍 *Dist. EMA21:* `{signal['dist_ema21']}%`\n"
        f"🕯️ *Lumânare:* `{signal['candle_type']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛑 *Stop Loss:* `${signal['sl']}`\n"
        f"🎯 *TP1:* `${signal['tp1']}`\n"
        f"🚀 *TP2:* `${signal['tp2']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 *Shares:* `{signal['shares']}`\n"
        f"⚠️ *Risc:* `${signal['risk_$']}`\n"
        f"📅 *Data:* `{signal['date']}`"
    )
