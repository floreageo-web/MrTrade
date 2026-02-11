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
    requests.post(url, json=payload)

def calculeaza_indicatori(df):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    tr = pd.concat([df['High']-df['Low'], 
                    abs(df['High']-df['Close'].shift()), 
                    abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)
    df['ATR_PCT'] = (tr.rolling(14).mean() / df['Close']) * 100
    
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    return df.dropna()

def ruleaza_screener():
    try:
        with open("baza_de_date.json", "r") as f:
            db = json.load(f)
    except: return

    # Verificăm ce listă folosim
    tickers = db.get("watchlist_trend_ascendent", [])
    print(f"DEBUG: Incepem scanarea pe {len(tickers)} actiuni...")

    for symbol in tickers:
        try:
            # Tipărim în log-ul GitHub ca să vedem că lucrează
            print(f"Analizam: {symbol}...", end="\r") 
            
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="100d") 
            if len(df) < 50: continue
            
            df = calculeaza_indicatori(df)
            
            limit = max(len(df) - 20, 0)
            for i in range(len(df) - 1, limit - 1, -1):
                row = df.iloc[i]
                vol_avg_20z = df['Volume'].iloc[max(0, i-20):i].mean()
                vol_ratio = row['Volume'] / vol_avg_20z if vol_avg_20z > 0 else 0
                
                # --- FILTRE MAI PERMISIVE PENTRU TEST ---
                cond_vol_abs = vol_avg_20z >= 500000
                cond_atr = row['ATR_PCT'] >= 1.2          # Scazut de la 1.5
                cond_vol_rel = vol_ratio >= 1.2          # Scazut de la 1.5
                cond_rsi = 40 <= row['RSI'] <= 70        # Lărgit un pic
                cond_trend = row['Close'] > row['EMA20'] # Doar peste EMA20 momentan
                
                if cond_vol_abs and cond_atr and cond_vol_rel and cond_rsi and cond_trend:
                    data_semnal = df.index[i].strftime('%d-%m-%Y')
                    ora_semnal = df.index[i].strftime('%H:%M')
                    mesaj = f"🚀 `{symbol}` - {data_semnal} - `{ora_semnal}` - `{round(row['Close'], 2)}` $"
                    trimite_mesaj(mesaj)
                    break 
        except: continue

if __name__ == "__main__":
    ruleaza_screener()
