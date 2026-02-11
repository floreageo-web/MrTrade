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
    # RSI (14) - Varianta sigura (fara diviziune la zero)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, 1e-10) # FIX: Prevenire NaN
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # ATR (14) Procentual
    tr = pd.concat([df['High']-df['Low'], 
                    abs(df['High']-df['Close'].shift()), 
                    abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)
    df['ATR_PCT'] = (tr.rolling(14).mean() / df['Close']) * 100
    
    # Trend EMA
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    
    return df.dropna()

def ruleaza_test_60z_pro():
    try:
        with open("baza_de_date.json", "r") as f:
            db = json.load(f)
    except:
        return

    tickers = db.get("watchlist_trend_ascendent", [])
    print(f"🧪 TEST 60 ZILE (Bulletproof): Analizam {len(tickers)} actiuni...")

    for symbol in tickers:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="180d") 
            if len(df) < 80: continue
            
            df = calculeaza_indicatori(df)
            
            # Verificam ultimele 60 de zile
            limit = max(len(df) - 60, 0)
            for i in range(len(df) - 1, limit - 1, -1):
                row = df.iloc[i]
                price = row['Close']
                
                # Volum Safe (FIX: Verificam lungimea slice-ului)
                vol_slice = df['Volume'].iloc[max(0, i-20):i]
                if len(vol_slice) < 20: continue
                vol_avg_20z = vol_slice.mean()
                vol_ratio = row['Volume'] / vol_avg_20z if vol_avg_20z > 0 else 0
                
                # --- FILTRELE TALE (Varianta stabila) ---
                if (35 <= price <= 150 and 
                    vol_avg_20z >= 500000 and 
                    vol_ratio >= 1.3 and 
                    row['ATR_PCT'] >= 1.2 and 
                    40 <= row['RSI'] <= 70 and 
                    price > row['EMA20'] > row['EMA50']):
                    
                    data_s = df.index[i].strftime('%d-%m-%Y')
                    
                    # Mesaj curat: Ticker - Data - Pret
                    mesaj = f"🚀 `{symbol}` - {data_s} - `{round(price, 2)}` $"
                    trimite_mesaj(mesaj)
                    break 
                    
        except:
            continue

if __name__ == "__main__":
    ruleaza_test_60z_pro()
