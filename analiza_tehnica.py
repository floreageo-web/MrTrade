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
    
    # ATR % (Volatilitate relativa la pret)
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
        print(f"Eroare: Nu s-a putut citi baza_de_date.json: {e}")
        return

    tickers = db.get("watchlist_trend_ascendent", [])
    print(f"🧪 Incepem scanarea pentru {len(tickers)} actiuni (ATR 1.5%)...")

    for symbol in tickers:
        try:
            ticker = yf.Ticker(symbol)
            # Luam date pentru ultimele luni ca sa calculam corect mediile
            df = ticker.history(period="100d") 
            if len(df) < 50: continue
            
            df = calculeaza_indicatori(df)
            
            # Verificam ultimele 20 de zile, incepand cu cea mai recenta
            limit = max(len(df) - 20, 0)
            for i in range(len(df) - 1, limit - 1, -1):
                row = df.iloc[i]
                
                # Volum mediu pe 20 de zile (pana in ziua i)
                vol_avg_20z = df['Volume'].iloc[max(0, i-20):i].mean()
                vol_ratio = row['Volume'] / vol_avg_20z if vol_avg_20z > 0 else 0
                
                # --- FILTRELE TALE ---
                if (vol_avg_20z >= 500000 and           # Lichiditate 0.5M
                    row['ATR_PCT'] >= 1.5 and           # Energie ATR
                    vol_ratio >= 1.5 and                # Explozie Volum
                    45 <= row['RSI'] <= 65 and          # Momentum sanatos
                    row['Close'] > row['EMA20'] > row['EMA50']): # Trend ascendent
                    
                    data_semnal = df.index[i].strftime('%d-%m-%Y')
                    
                    # FORMAT MESAJ: Ticker - Data - Pret
                    mesaj = f"🚀 `{symbol}` - {data_semnal} - `{round(row['Close'], 2)}` $"
                    trimite_mesaj(mesaj)
                    
                    # Daca am gasit cel mai recent semnal, trecem la urmatorul ticker
                    break 
            
        except Exception as e:
            print(f"Eroare la {symbol}: {e}")
            continue

if __name__ == "__main__":
    ruleaza_screener()
