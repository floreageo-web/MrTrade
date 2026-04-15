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
    """Scanare hibridă: pachete mici pentru a evita blocajele GitHub/Yahoo."""
    signals = []
    # Împărțim lista de 320 în bucăți de câte 15
    batch_size = 15 
    ticker_groups = [TICKERS[i:i + batch_size] for i in range(0, len(TICKERS), batch_size)]
    
    log.info(f"🚀 Start scanare hibridă: {len(TICKERS)} acțiuni în {len(ticker_groups)} loturi.")

    for idx, group in enumerate(ticker_groups):
        log.info(f"📦 Procesare lot {idx+1}/{len(ticker_groups)}...")
        
        try:
            # Descărcăm lotul curent
            data = yf.download(
                tickers=group,
                period="1y",
                interval="1d",
                group_by='ticker',
                progress=False,
                threads=True,
                auto_adjust=True
            )
            
            # Procesăm fiecare ticker din lot
            for ticker in group:
                try:
                    df = data[ticker].copy() if len(group) > 1 else data.copy()
                    df.dropna(inplace=True)
                    
                    if len(df) < 200: continue
                    
                    signal = check_signal_logic(df, ticker)
                    if signal:
                        signals.append(signal)
                        log.info(f"✅ SEMNAL: {ticker}")
                except:
                    continue
                    
        except Exception as e:
            log.warning(f"⚠️ Eroare la lotul {idx+1}: {e}")
        
        # PAUZA CRUCIALĂ între loturi pentru a nu fi detectat ca bot
        time.sleep(2) 

    signals.sort(key=lambda x: x["score"], reverse=True)
    return signals

def check_signal_logic(df, ticker):
    """Strategia ta matematică (rămâne neschimbată)."""
    try:
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

        return {
            "ticker": ticker, "price": round(price, 2), "rsi": round(rsi, 1),
            "dist_ema21": round(dist_ema21 * 100, 2), "sl": sl, "tp1": tp1, "tp2": tp2,
            "shares": shares, "risk_$": round(shares * risk, 2), "score": 3,
            "candle_type": "Signal", "date": datetime.now().strftime("%Y-%m-%d")
        }
    except:
        return None
