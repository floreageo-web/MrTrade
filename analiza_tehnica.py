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
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, 1e-10)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    tr = pd.concat([df['High']-df['Low'], 
                    abs(df['High']-df['Close'].shift()), 
                    abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)
    df['ATR_PCT'] = (tr.rolling(14).mean() / df['Close']) * 100
    
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    return df.dropna()

def ruleaza_analiza():
    try:
        with open("baza_de_date.json", "r") as f:
            db = json.load(f)
    except:
        print("❌ Fisierul baza_de_date.json nu a fost gasit!")
        return

    tickers = db.get("watchlist_trend_ascendent", [])
    print(f"🔍 Incepem scanarea pentru {len(tickers)} actiuni (Istoric 60 zile)...")
    
    for symbol in tickers:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="180d")
            if len(df) < 80:
                print(f"⚠️ {symbol}: Date insuficiente.")
                continue
            
            df = calculeaza_indicatori(df)
            limit = max(len(df) - 60, 0)
            
            gasit_pentru_ticker = False
            for i in range(len(df) - 1, limit - 1, -1):
                row = df.iloc[i]
                price = row['Close']
                vol_slice = df['Volume'].iloc[max(0, i-20):i]
                vol_avg = vol_slice.mean()
                vol_ratio = row['Volume'] / vol_avg if vol_avg > 0 else 0

                # Conditii
                c_pret = 35 <= price <= 150
                c_vol_avg = vol_avg >= 500000
                c_vol_rel = vol_ratio >= 1.3
                c_atr = row['ATR_PCT'] >= 1.2
                c_rsi = 40 <= row['RSI'] <= 70
                c_trend = price > row['EMA20'] > row['EMA50']

                if c_pret and c_vol_avg and c_vol_rel and c_atr and c_rsi and c_trend:
                    data_s = df.index[i].strftime('%d-%m-%Y')
                    trimite_mesaj(f"🚀 `{symbol}` - {data_s} - `{round(price, 2)}` $")
                    gasit_pentru_ticker = True
                    break # Trecem la urmatoarea actiune dupa primul semnal gasit
            
            if not gasit_pentru_ticker:
                # Printam in log-ul GitHub de ce nu a iesit nimic pentru acest ticker
                print(f"ℹ️ {symbol}: Nu a indeplinit toate conditiile in ultimele 60 de zile.")

        except Exception as e:
            print(f"❌ Eroare la {symbol}: {e}")

if __name__ == "__main__":
    ruleaza_analiza()
