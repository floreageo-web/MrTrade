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
    # RSI 14
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    # ATR 14
    tr = pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift()), abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(14).mean()
    # EMA 20 & 50
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    return df

def find_resistances(df):
    peaks = []
    data_len = len(df)
    # Detectare varfuri locale
    for i in range(20, data_len - 3):
        close = df.iloc[i]['Close']
        if (df.iloc[i-20:i]['Close'].max() < close and df.iloc[i+1:i+4]['Close'].max() < close):
            peaks.append(i)
    
    resistances = []
    peaks_sorted = sorted(peaks, key=lambda p: df.iloc[p]['Close'])
    
    for base_peak in peaks_sorted:
        base_val = df.iloc[base_peak]['Close']
        # Zona de rezistenta +/- 1.2%
        zona_peaks = [p for p in peaks_sorted if abs(df.iloc[p]['Close'] - base_val) / base_val <= 0.012]
        
        if len(zona_peaks) < 4: continue
        
        # Distantare minima 10 zile intre puncte
        zona_peaks.sort()
        if any(np.diff(zona_peaks) < 10): continue
            
        zona_prices = df.iloc[zona_peaks]['Close']
        resistances.append({
            'high': zona_prices.max(),
            'last_touch': max(zona_peaks)
        })
    return resistances

def ruleaza_scanare():
    try:
        with open("baza_de_date.json", "r") as f:
            db = json.load(f)
    except: return

    tickers = db.get("watchlist_trend_ascendent", [])
    
    # Prevenire duplicate: vedem ce simboluri avem deja in watchlist_long
    simboluri_existente = [entry.split(",")[0].strip() for entry in db.get("watchlist_long", [])]

    for symbol in tickers:
        try:
            if symbol in simboluri_existente:
                continue

            ticker = yf.Ticker(symbol)
            df = ticker.history(period="360d") 
            if len(df) < 200: continue
            
            df = calculeaza_indicatori(df)
            resistances = find_resistances(df)
            
            # Scanam ultimele 20 de zile pentru breakout (dupa cum ai cerut)
            for i in range(len(df)-20, len(df)):
                row = df.iloc[i]
                price = row['Close']
                vol_avg = df.iloc[max(0, i-20):i]['Volume'].mean()
                
                for r in resistances:
                    # Rezistenta trebuie sa fie finalizata inainte de ziua analizei
                    if r['last_touch'] >= i: continue
                    
                    # FILTRU CER CURAT (Toate cele 20 de zile anterioare SUB rezistenta)
                    fereastra_pre = df.iloc[max(0, i-20):i]
                    if any(fereastra_pre['Close'] > r['high']):
                        continue 

                    # Distanta fata de rezistenta (intre 1% si 5%)
                    distanta_pct = (price / r['high'] - 1) * 100
                    
                    if (1.0 <= distanta_pct <= 5.0 and row['Volume'] > 1.5 * vol_avg and 
                        45 <= row['RSI'] <= 65 and (row['ATR']/price)*100 >= 1.0 and
                        price > row['EMA20'] > row['EMA50']):
                        
                        # Confirmare Hold 2 zile (pretul ramane peste)
                        hold_ok = True
                        for k in range(1, 3):
                            if i + k < len(df):
                                if df.iloc[i + k]['Close'] <= r['high']:
                                    hold_ok = False; break
                        
                        if hold_ok:
                            data_brk = df.index[i].strftime('%d-%m-%Y')
                            
                            # MESAJ FINAL (Ticker, Data, Rezistenta, Pret Spargere)
                            trimite_mesaj(f"🔔 *BREAKOUT DETECTAT*\n\n"
                                         f"📈 *Ticker:* `{symbol}`\n"
                                         f"📅 *Data:* `{data_brk}`\n"
                                         f"📏 *Rezistență:* `{round(r['high'], 2)}` $\n"
                                         f"💰 *Preț Spargere:* `{round(price, 2)}` $")
                            
                            # Salvare in DB pentru Retest
                            entry = f"{symbol}, {df.index[i].strftime('%d-%m')}, {round(price, 2)}"
                            db.setdefault("watchlist_long", []).append(entry)
                            simboluri_existente.append(symbol) 
                            break 

        except Exception:
            continue

    with open("baza_de_date.json", "w") as f:
        json.dump(db, f, indent=2)

if __name__ == "__main__":
    ruleaza_scanare()
