import os
import json
import yfinance as yf
import pandas as pd
import numpy as np
import telebot

# Configurare Bot
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
bot = telebot.TeleBot(TOKEN)

def calculeaza_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    # Evităm împărțirea la zero
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calculeaza_atr(df, window=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(window=window).mean()

def ruleaza_analiza_noutati():
    try:
        # 1. Incarcam baza de date
        if not os.path.exists('baza_de_date.json'):
            print("Baza de date nu exista.")
            return
            
        with open('baza_de_date.json', 'r') as f:
            db = json.load(f)
        
        simboluri = db.get('watchlist_trend_ascendent', [])
        # Luăm lista anterioară pentru a vedea ce e NOU
        semnale_anterioare = set(db.get('signal_list_long', []))
        
        print(f"Scanare inceputa. Avem {len(semnale_anterioare)} semnale in memorie.")
        
        gasite_azi = []
        mesaje_noi = []

        # 2. Scanam actiunile
        for simbol in simboluri:
            try:
                ticker = yf.Ticker(simbol)
                df = ticker.history(period="1y")
                if len(df) < 200: continue

                # Indicatori
                close = df['Close']
                ema20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
                ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
                ema50_prev = close.ewm(span=50, adjust=False).mean().iloc[-2]
                ema200 = close.ewm(span=200, adjust=False).mean().iloc[-1]
                
                v_rsi = calculeaza_rsi(close).iloc[-1]
                v_atr = calculeaza_atr(df).iloc[-1]
                
                v_vol_azi = df['Volume'].iloc[-1]
                v_vol_m = df['Volume'].rolling(window=20).mean().iloc[-2]
                
                pret
