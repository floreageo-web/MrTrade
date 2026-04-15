# ============================================================
# screener.py — Scanare 317 acțiuni + detectare semnale
# ============================================================

import yfinance as yf
import pandas as pd
import time
import logging
import requests
from datetime import datetime
from indicators import add_indicators, is_bullish_candle, is_engulfing, is_pin_bar
from config import (TICKERS, EMA_FAST, EMA_MID, EMA_SLOW, RSI_MIN, RSI_MAX,
                    PRICE_MIN, PRICE_MAX, CAPITAL, RISK_PER_TRADE, RR_TP1, RR_TP2)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# --- CONFIGURARE SESIUNE PENTRU ANTI-BLOCARE ---
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
})

def fetch_data(ticker: str, period: str = "1y") -> pd.DataFrame | None:
    """Descarcă date zilnice pentru un ticker folosind sesiune mascată."""
    try:
        # Descarcă datele folosind sesiunea de browser simulată
        df = yf.download(
            ticker, 
            period=period, 
            interval="1d", 
            progress=False, 
            auto_adjust=True, 
            session=session,  # Folosim header-ul de browser
            timeout=15        # Evităm blocarea infinită
        )
        
        if df is None or df.empty or len(df) < 200:
            return None
            
        df.dropna(inplace=True)
        return df
    except Exception as e:
        # Nu logăm erorile de timeout ca fiind critice pentru a nu umple log-ul
        return None

def check_signal(df: pd.DataFrame) -> dict | None:
    """Verifică dacă ultima lumânare îndeplinește condițiile de intrare."""
    try:
        df = add_indicators(df)
        if len(df) < 5:
            return None

        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Extragere preț (asigurăm format float)
        price = float(last["Close"])

        # FILTRU 1: Preț
        if not (PRICE_MIN <= price <= PRICE_MAX):
            return None

        # FILTRU 2: Trend (Preț > EMA50 > EMA200)
        ema21 = float(last["EMA21"])
        ema50 = float(last["EMA50"])
        ema200 = float(last["EMA200"])

        if not (ema50 > ema200 and price > ema50):
            return None

        # FILTRU 3: RSI zona de retragere
        rsi = float(last["RSI"])
        if not (RSI_MIN <= rsi <= RSI_MAX):
            return None

        # FILTRU 4: Distanța față de EMA21 (maxim 2%)
        dist_ema21 = abs(price - ema21) / ema21
        if dist_ema21 > 0.02:
            return None

        # FILTRU 5: Lumânare confirmare
        candle_ok = (
            is_bullish_candle(last) or
            is_engulfing(prev, last) or
            is_pin_bar(last)
        )
        if not candle_ok:
            return None

        # Calcule SL/TP
        atr = float(last["ATR"])
        sl = round(price - 1.5 * atr, 2)
        risk = price - sl
        if risk <= 0.01: return None
        
        tp1 = round(price + risk * RR_TP1, 2)
        tp2 = round(price + risk * RR_TP2, 2)

        # Calcul Shares
        risk_amount = CAPITAL * RISK_PER_TRADE
        shares = int(risk_amount / risk) if risk > 0 else 0

        # Scor
        score = 3
        if is_engulfing(prev, last): score += 1
        if is_pin_bar(last): score += 1
        score = min(score, 5)

        return {
            "ticker": "",
            "price": round(price, 2),
            "rsi": round(rsi, 1),
            "dist_ema21": round(dist_ema21 * 100, 2),
            "sl": sl, "tp1": tp1, "tp2": tp2,
            "shares": shares,
            "risk_$": round(shares * risk, 2),
            "score": score,
            "candle_type": _candle_type(prev, last),
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
    except:
        return None

def _candle_type(prev, curr) -> str:
    if is_engulfing(prev, curr): return "Bullish Engulfing"
    if is_pin_bar(curr): return "Pin Bar"
    return "Bullish Candle"

def run_screener(batch_size: int = 5, delay: float = 1.2) -> list[dict]:
    """Rulează scanarea cu pauze pentru a evita blocarea IP-ului."""
    signals = []
    total = len(TICKERS)
    
    log.info(f"🔍 Start scanare — {total} tickere...")

    for i, ticker in enumerate(TICKERS):
        df = fetch_data(ticker)
        
        if df is not None:
            signal = check_signal(df)
            if signal:
                signal["ticker"] = ticker
                signals.append(signal)
                log.info(f"✅ SEMNAL: {ticker} (Scor: {signal['score']}/5)")
        
        # Log progres rar (la 20 tickere) pentru a păstra log-ul curat
        if (i + 1) % 20 == 0:
            log.info(f"📊 Progres: {i+1}/{total} | Semnale: {len(signals)}")
        
        # PAUZA ANTI-BAN (Creștem la 1.2 secunde)
        time.sleep(delay) 

    signals.sort(key=lambda x: x["score"], reverse=True)
    log.info(f"✨ Finalizat! {len(signals)} semnale găsite.")
    return signals
