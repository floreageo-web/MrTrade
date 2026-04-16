import pandas as pd
import logging
import time
import random
import warnings
import numpy as np
from yahooquery import Ticker
from indicators import add_indicators, is_bullish_candle, is_engulfing, is_pin_bar

# 1. Ignorăm avertismentele de tip FutureWarning
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore", message="A value is trying to be set on a copy of a slice from a DataFrame")

# Configurare Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def run_screener(tickers_list):
    """
    Scanează acțiunile căutând PULLBACK-uri reale (RSI în scădere + aproape de EMA21).
    """
    all_signals = []
    total = len(tickers_list)
    
    batch_size = 10
    batches = [tickers_list[i:i + batch_size] for i in range(0, total, batch_size)]
    
    logger.info(f"🚀 Start Scanare Pullback: {total} acțiuni.")
    time.sleep(5) 

    for idx, batch in enumerate(batches):
        try:
            t = Ticker(batch, asynchronous=True, formatted=False, retry=5, timeout=30)
            # Luăm datele istorice
            data = t.history(period='1y', interval='1d')

            if data is None or (isinstance(data, pd.DataFrame) and data.empty):
                continue

            # YahooQuery returnează MultiIndex (symbol, date)
            available_symbols = data.index.get_level_values('symbol').unique()

            for ticker in batch:
                if ticker not in available_symbols:
                    continue
                    
                try:
                    # Extragem și curățăm datele pentru ticker
                    df = data.loc[ticker].copy()
                    
                    # Redenumim coloanele pentru a fi compatibile cu indicators.py
                    df.rename(columns={
                        'open': 'Open', 'high': 'High', 'low': 'Low', 
                        'close': 'Close', 'volume': 'Volume'
                    }, inplace=True)

                    if len(df) < 250: continue

                    # Adăugăm indicatorii (EMA, RSI, ATR)
                    df = add_indicators(df)
                    
                    row = df.iloc[-1]
                    prev = df.iloc[-2]
                    
                    # --- PARAMETRI ANALIZĂ ---
                    price = row["Close"]
                    ema21 = row["EMA21"]
                    ema50 = row["EMA50"]
                    ema200 = row["EMA200"]
                    rsi_acum = row["RSI"]
                    
                    # Verificăm RSI-ul de acum 4 zile pentru a confirma PULLBACK-ul
                    rsi_acum_4_zile = df.iloc[-5]["RSI"]

                    # --- LOGICA DE FILTRARE ---
                    
                    # 1. Trend Ascendent (Să nu fie "cădere liberă")
                    trend_ok = (ema50 > ema200) and (price > ema50)
                    
                    # 2. Zona de Pullback (RSI între 40 și 57)
                    rsi_zona_ok = (40 <= rsi_acum <= 57)
                    
                    # 3. Confirmare Pullback (RSI a scăzut, deci prețul s-a răcit, nu vine de jos)
                    # Dacă RSI-ul e mai mic acum decât acum 4 zile = PULLBACK
                    este_pullback = rsi_acum < rsi_acum_4_zile
                    
                    # 4. Apropierea de suport (EMA21) - Max 2% distanță
                    distanta_ema21 = abs(price - ema21) / ema21
                    ema21_ok = distanta_ema21 <= 0.02
                    
                    # 5. Candlestick de confirmare (Price Action)
                    candle_ok = is_bullish_candle(row) or is_engulfing(prev, row) or is_pin_bar(row)

                    if trend_ok and rsi_zona_ok and este_pullback and ema21_ok and candle_ok:
                        logger.info(f"✅ PULLBACK CONFIRMAT: {ticker} (RSI: {rsi_acum:.1f})")
                        all_signals.append(ticker)
                        
                except Exception as e:
                    continue

        except Exception as e:
            logger.error(f"❌ Eroare lot {idx + 1}: {str(e)[:50]}")
        
        # Pauză pentru a evita blocarea IP-ului
        time.sleep(random.uniform(10, 15))

    logger.info(f"🎯 Scanare terminată. Semnale găsite: {len(all_signals)}")
    return all_signals
