import os
import pandas as pd
import yfinance as yf
import telebot
from datetime import datetime
import pytz  # Adăugat pentru gestionarea orei României

# 1. Validare si Oprire Fortata
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

if not TOKEN or not CHAT_ID:
    print("❌ EROARE CRITICA: Lipsesc variabilele de mediu.")
    exit(1)

bot = telebot.TeleBot(TOKEN)

def calculeaza_indicatori_pro(df, window=14):
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # Wilder Smoothing corect
    avg_gain = gain.ewm(com=window-1, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(com=window-1, min_periods=window, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # ATR corect
    high_low = df['High'] - df['Low']
    high_cp = abs(df['High'] - df['Close'].shift())
    low_cp = abs(df['Low'] - df['Close'].shift())
    df['TR'] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    df['ATR'] = df['TR'].rolling(window=window).mean()
    return df

def ruleaza_strategia_finala():
    file_path = 'watchlist_manual.csv'
    semnale_gasite_acum = False # Indicator pentru a ști dacă am trimis vreun semnal
    
    if not os.path.exists(file_path): 
        print("Fisierul watchlist_manual.csv nu exista.")
    else:
        df_manual = pd.read_csv(file_path)
        acum = datetime.now()

        for index, row in df_manual.iterrows():
            ticker_symbol = str(row['ticker']).strip().upper() if 'ticker' in row.index else 'UNKNOWN'
            
            try:
                r_min_orig = float(row['rezistenta_min'])
                r_max_orig = float(row['rezistenta_max'])
                
                data_str = str(row['data_breakout'])
                if len(data_str.split('-')) == 2: data_str += f"-{acum.year}"
                data_brk = datetime.strptime(data_str, "%d-%m-%Y")
                
                zile_trecute = (acum - data_brk).days
                if not (3 <= zile_trecute <= 10): continue

                ticker = yf.Ticker(ticker_symbol)
                
                # Context Daily
                df_d = ticker.history(period="100d", interval="1d")
                if len(df_d) < 50: continue
                df_d = calculeaza_indicatori_pro(df_d)
                atr_daily = df_d['ATR'].iloc[-1]
                ma50_d = df_d['Close'].rolling(50).mean().iloc[-1]
                
                if pd.isna(ma50_d) or df_d['Close'].iloc[-1] < ma50_d: continue

                # Context 1H
                df_1h = ticker.history(period="30d", interval="1h")
                if len(df_1h) < 25: continue
                
                if df_1h.index.tz is not None:
                    df_1h.index = df_1h.index.tz_convert(None)
                
                df_1h = calculeaza_indicatori_pro(df_1h)
                df_after_brk = df_1h[df_1h.index > data_brk]
                
                if not df_after_brk.empty:
                    if df_after_brk['High'].max() > (r_max_orig * 1.04):
