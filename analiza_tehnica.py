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
    try:
        requests.post(url, json=payload)
    except:
        pass

def calculeaza_indicatori(df):
    # RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    # ATR (14) Procentual
    tr = pd.concat([df['High']-df['Low'], 
                    abs(df['High']-df['Close'].shift()), 
                    abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)
    df['ATR_PCT'] = (tr.rolling(14).mean() / df['Close']) * 100
    
    # Trend EMA
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    
    return df.dropna()

def ruleaza_test_60_zile():
    try:
        with open("baza_de_date.json", "r") as f:
            db = json.load(f)
    except:
        print("❌ Nu am gasit fisierul JSON.")
        return

    tickers = db.get("watchlist_trend_ascendent", [])
    print(f"🧪 TEST 60 ZILE: Analizam cele {len(tickers)} actiuni...")

    for symbol in tickers:
        try:
            ticker = yf.Ticker(symbol)
            # Luam 180 de zile ca sa avem destule date pentru EMA/RSI istorice
            df = ticker.history(period="180d") 
            if len(df) < 80: continue
            
            df = calculeaza_indicatori(df)
            
            # --- MODIFICARE: Verificam ultimele 60 de zile bursiere ---
            limit = max(len(df) - 60, 0)
            
            for i in range(len(df) - 1, limit - 1, -1):
                row = df.iloc[i]
                price = row['Close']
                
                # Volum mediu 20z la momentul zilei i
                vol_avg_20z = df['Volume'].iloc[max(0, i-20):i].mean()
                vol_ratio = row['Volume'] / vol_avg_20z if vol_avg_20z > 0 else 0
                
                # --- FILTRELE TALE STRICTE ---
                if (35 <= price <= 150 and 
                    vol_avg_20z >= 500000 and 
                    vol_ratio >= 1.3 and 
                    row['ATR_PCT'] >= 1.2 and 
                    40 <= row['RSI'] <= 70 and 
                    price > row['EMA20'] > row['EMA50']):
                    
                    data_s = df.index[i].strftime('%d-%m-%Y')
                    ora_s = df.index[i].strftime('%H:%M')
                    
                    # Trimitem semnalul gasit in istoric
                    mesaj = f"🚀 `{symbol}` - {data_s} - `{ora_s}` - `{round(price, 2)}` $"
                    trimite_mesaj(mesaj)
                    
                    # Punem break aici daca vrei DOAR ultimul breakout din cele 60 de zile.
                    # Daca vrei TOATE breakout-urile din 60 zile pentru o actiune, sterge 'break'.
                    break 
                    
        except Exception as e:
            print(f"Eroare la {symbol}: {e}")
            continue

if __name__ == "__main__":
    ruleaza_test_60_zile()
