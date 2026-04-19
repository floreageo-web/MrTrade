import pandas as pd
import logging
import time
import random
import warnings
import numpy as np
import os
from datetime import datetime
from indicators import add_indicators, is_bullish_candle, is_engulfing, is_pin_bar

# 1. Ignorăm avertismentele
warnings.simplefilter(action='ignore', category=FutureWarning)

# Configurare Logging
logger = logging.getLogger(__name__)

def run_screener(tickers_list):
    """
    Scanează acțiunile căutând PULLBACK-uri reale folosind datele locale.
    """
    all_signals = []
    DATA_DIR = 'data'
    
    logger.info(f"🚀 Start Scanare Pullback pe {len(tickers_list)} acțiuni (Date locale).")

    for ticker in tickers_list:
        file_path = os.path.join(DATA_DIR, f"{ticker}.csv")
        
        if not os.path.exists(file_path):
            continue

        try:
            # Încărcăm datele din CSV-ul descărcat anterior
            df = pd.read_csv(file_path)
            
            if len(df) < 200: 
                continue

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
            atr = row["ATR"]
            
            # Verificăm RSI-ul de acum 4 zile pentru a confirma PULLBACK-ul
            rsi_acum_4_zile = df.iloc[-5]["RSI"]

            # --- LOGICA DE FILTRARE ---
            # 1. Trend Ascendent
            trend_ok = (ema50 > ema200) and (price > ema50)
            
            # 2. Zona de Pullback (RSI între 40 și 57)
            rsi_zona_ok = (40 <= rsi_acum <= 57)
            
            # 3. Confirmare Pullback (Prețul s-a "răcit")
            este_pullback = rsi_acum < rsi_acum_4_zile
            
            # 4. Apropierea de suport (EMA21) - Max 2.5% distanță
            distanta_ema21 = abs(price - ema21) / ema21
            ema21_ok = distanta_ema21 <= 0.025
            
            # 5. Candlestick de confirmare
            candle_ok = is_bullish_candle(row) or is_engulfing(prev, row) or is_pin_bar(row)

            if trend_ok and rsi_zona_ok and este_pullback and ema21_ok and candle_ok:
                
                # --- CALCUL MANAGEMENT RISC ---
                # Stop Loss la 2x ATR sub prețul de intrare
                stop_loss = round(price - (2 * atr), 2)
                # Take Profit la un raport de 1.5x riscul (Risk/Reward 1.5)
                risc = price - stop_loss
                take_profit = round(price + (1.5 * risc), 2)
                
                signal_data = {
                    'ticker': ticker,
                    'price': round(price, 2),
                    'rsi': round(rsi_acum, 1),
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'date': datetime.now().strftime('%Y-%m-%d')
                }
                
                logger.info(f"✅ SEMNAL GĂSIT: {ticker} la ${price:.2f}")
                all_signals.append(signal_data)
                        
        except Exception as e:
            logger.error(f"❌ Eroare la procesarea {ticker}: {e}")
            continue

    return all_signals

def format_signal_message(signal):
    """
    Transformă dicționarul de semnal într-un text frumos pentru Telegram.
    """
    return (
        f"💎 *TICKER: ${signal['ticker']}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 *Intrare:* `${signal['price']}`\n"
        f"📉 *Stop Loss:* `{signal['stop_loss']}`\n"
        f"🎯 *Take Profit:* `{signal['take_profit']}`\n\n"
        f"📊 *Indicatori:*\n"
        f"└ RSI: {signal['rsi']}\n"
        f"└ Semnal generat la: {signal['date']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 [Deschide Graficul TradingView](https://www.tradingview.com/chart/?symbol={signal['ticker']})"
    )
