import yfinance as yf
import pandas as pd
import requests
import os
import json

# --- CONFIGURARE TELEGRAM ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def trimite_mesaj(mesaj):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Eroare trimitere Telegram: {e}")

def calculeaza_indicatori(df):
    # RSI 14
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    # ATR %
    tr = pd.concat([df['High']-df['Low'], 
                    abs(df['High']-df['Close'].shift()), 
                    abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)
    df['ATR_PCT'] = (tr.rolling(14).mean() / df['Close']) * 100
    
    # Trend EMA
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    
    return df.dropna()

def ruleaza_screener():
    try:
        with open("baza_de_date.json", "r") as f:
            db = json.load(f)
    except Exception as e:
        print(f"Eroare baza de date: {e}")
        return

    tickers = db.get("watchlist_trend_ascendent", [])
    print(f"🧪 Scanare pornita (ATR 1.5%, Vol 0.5M)...")

    for symbol in tickers:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="100d") 
            if len(df) < 50: continue
            
            df = calculeaza_indicatori(df)
            
            # Verificam ultimele 20 de zile
            limit = max(len(df) - 20, 0)
            for i in range(len(df) - 1, limit - 1, -1):
                row = df.iloc[i]
                
                vol_avg_20z = df['Volume'].iloc[max(0, i-20):i].mean()
                vol_ratio = row['Volume'] / vol_avg_20z if vol_avg_20z > 0 else 0
                
                if (vol_avg_20z >= 500000 and 
                    row['ATR_PCT'] >= 1.5 and 
                    vol_ratio >= 1.5 and 
                    45 <= row['RSI'] <= 65 and 
                    row['Close'] > row['EMA20'] > row['EMA50']):
                    
                    # Convertim timpul la ora Romaniei (UTC+2 sau UTC+3)
                    # yfinance returneaza timestamp-ul in ora locala a bursei
                    data_semnal = df.index[i].strftime('%d-%m-%Y')
                    ora_semnal = df.index[i].strftime('%H:%M')
                    
                    # FORMAT MESAJ: Ticker - Data - Ora - Pret
                    mesaj = f"🚀 `{symbol}` - {data_semnal} - `{ora_semnal}` - `{round(row['Close'], 2)}` $"
                    trimite_mes
