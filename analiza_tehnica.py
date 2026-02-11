import yfinance as yf
import pandas as pd
import requests
import os
import json

# --- CONFIGURARE ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def trimite_mesaj(mesaj):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

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
    return df

def ruleaza_test_scurt_20z():
    try:
        with open("baza_de_date.json", "r") as f:
            db = json.load(f)
    except: return

    tickers = db.get("watchlist_trend_ascendent", [])
    print(f"🧪 TEST 20 ZILE: Incepe scanarea...")

    for symbol in tickers:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="150d") 
            if len(df) < 60: continue
            
            df = calculeaza_indicatori(df)
            
            start_index = len(df) - 20
            for i in range(start_index, len(df)):
                row = df.iloc[i]
                
                # Volum mediu 20z
                vol_avg_20z = df['Volume'].iloc[i-20:i].mean()
                vol_ratio = row['Volume'] / vol_avg_20z if vol_avg_20z > 0 else 0
                
                # Filtre: Volum > 500k, ATR > 2%, Vol Zi > 1.5x, RSI 45-65, Trend ok
                if (vol_avg_20z >= 500000 and 
                    row['ATR_PCT'] >= 2.0 and 
                    vol_ratio >= 1.5 and 
                    45 <= row['RSI'] <= 65 and 
                    row['Close'] > row['EMA20'] > row['EMA50']):
                    
                    data_semnal = df.index[i].strftime('%d-%m-%Y')
                    
                    # FORMATUL CERUT: Ticker - Data si Pretul
                    mesaj = f"🚀 `{symbol}` - {data_semnal} - `{round(row['Close'], 2)}` $"
                    
                    trimite_mesaj(mesaj)
        except: continue

if __name__ == "__main__":
    ruleaza_test_scurt_20z()
