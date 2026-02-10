import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
import json
from datetime import datetime
import pytz

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
    tr = pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift()), abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(14).mean()
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    return df

def find_resistances(df):
    peaks = []
    data_len = len(df)
    for i in range(20, data_len - 3):
        close = df.iloc[i]['Close']
        if (df.iloc[i-20:i]['Close'].max() < close and df.iloc[i+1:i+4]['Close'].max() < close):
            peaks.append(i)
    
    resistances = []
    peaks_sorted = sorted(peaks, key=lambda p: df.iloc[p]['Close'])
    for base_peak in peaks_sorted:
        base_val = df.iloc[base_peak]['Close']
        zona_peaks = [p for p in peaks_sorted if abs(df.iloc[p]['Close'] - base_val) / base_val <= 0.012]
        if len(zona_peaks) < 4: continue
        zona_peaks.sort()
        if any(np.diff(zona_peaks) < 10): continue
        zona_prices = df.iloc[zona_peaks]['Close']
        resistances.append({'high': zona_prices.max(), 'last_touch': max(zona_peaks)})
    return resistances

def ruleaza_scanare_test():
    try:
        with open("baza_de_date.json", "r") as f:
            db = json.load(f)
    except: return

    tickers = db.get("watchlist_trend_ascendent", [])
    print(f"🚀 TEST: Scanăm ultimele 20 de zile pentru {len(tickers)} acțiuni...")

    for symbol in tickers:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="360d") 
            if len(df) < 200: continue
            
            df = calculeaza_indicatori(df)
            resistances = find_resistances(df)
            
            # --- SCANĂM ULTIMELE 20 DE ZILE PENTRU TEST ---
            for i in range(len(df)-20, len(df)):
                row = df.iloc[i]
                price = row['Close']
                vol_avg = df.iloc[max(0, i-20):i]['Volume'].mean()
                
                for r in resistances:
                    if r['last_touch'] >= i: continue
                    
                    # FILTRU CER CURAT (20 zile sub linie înainte de spargere)
                    fereastra_pre = df.iloc[max(0, i-20):i]
                    if any(fereastra_pre['Close'] > r['high']):
                        continue 

                    distanta_pct = (price / r['high'] - 1) * 100
                    
                    # Filtre Tehnice: Gap (1-5%), Volum (1.5x), RSI, ATR, Trend
                    if (1.0 <= distanta_pct <= 5.0 and row['Volume'] > 1.5 * vol_avg and 
                        45 <= row['RSI'] <= 65 and (row['ATR']/price)*100 >= 1.0 and
                        price > row['EMA20'] > row['EMA50']):
                        
                        # Verificare Hold (Confirmare de 2 zile peste, dacă există date)
                        hold_ok = True
                        for k in range(1, 3):
                            if i + k < len(df):
                                if df.iloc[i + k]['Close'] <= r['high']:
                                    hold_ok = False; break
                        
                        if hold_ok:
                            data_brk = df.index[i].strftime('%d-%m-%Y')
                            
                            # Trimitem mesajul pentru fiecare spargere găsită în cele 20 de zile
                            trimite_mesaj(f"🧪 *TEST BREAKOUT (Istoric 20z)*\n\n"
                                         f"📈 *Ticker:* `{symbol}`\n"
                                         f"📅 *Data:* `{data_brk}`\n"
                                         f"📏 *Rezistență:* `{round(r['high'], 2)}` $\n"
                                         f"💰 *Preț Spargere:* `{round(price, 2)}` $")
                            
                            # NU salvăm în DB pentru acest test, doar observăm alertele
                            break 
        except:
            continue

if __name__ == "__main__":
    ruleaza_scanare_test()
