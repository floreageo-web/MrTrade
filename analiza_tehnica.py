import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
import json
from datetime import datetime

# --- CONFIGURARE ---
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

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

def ruleaza_test_7_zile():
    try:
        with open("baza_de_date.json", "r") as f:
            db = json.load(f)
    except:
        print("Eroare: Nu am gasit baza_de_date.json")
        return

    tickers = db.get("watchlist_trend_ascendent", [])
    print(f"🧪 START TEST: Verificam ultimele 7 zile pentru {len(tickers)} actiuni...")

    for symbol in tickers:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="360d") 
            if len(df) < 200: continue
            
            df = calculeaza_indicatori(df)
            resistances = find_resistances(df)
            
            # --- SCANAM INTERVALUL DE 7 ZILE ---
            for i in range(len(df)-7, len(df)):
                row = df.iloc[i]
                price = row['Close']
                vol_avg = df.iloc[i-20:i]['Volume'].mean()
                
                for r in resistances:
                    if r['last_touch'] >= i: continue
                    
                    # FILTRU CER CURAT (20 zile sub linie)
                    fereastra_pre = df.iloc[i-20:i]
                    if any(fereastra_pre['Close'] > r['high']):
                        continue

                    distanta_pct = (price / r['high'] - 1) * 100
                    
                    # Filtre Tehnice: Gap (1-5%), Volum (1.5x), RSI, ATR, Trend
                    if (1.0 <= distanta_pct <= 5.0 and row['Volume'] > 1.5 * vol_avg and 
                        45 <= row['RSI'] <= 65 and (row['ATR']/price)*100 >= 1.0 and
                        price > row['EMA20'] > row['EMA50']):
                        
                        # Verificare Hold 2 zile (daca avem date disponibile in viitorul punctului i)
                        hold_ok = True
                        for k in range(1, 3):
                            if i + k < len(df):
                                if df.iloc[i + k]['Close'] <= r['high']:
                                    hold_ok = False; break
                        
                        if hold_ok:
                            data_brk = df.index[i].strftime('%d-%m-%Y')
                            trimite_mesaj(f"🧪 *TEST 7 ZILE*\n\n📈 Ticker: `{symbol}`\n📅 Data: `{data_brk}`\n📏 Rezistență: `{round(r['high'], 2)}` $\n💰 Preț Spargere: `{round(price, 2)}` $")
                            # NU salvam in baza_de_date.json pentru acest test
                            break 
        except:
            continue
    
    print("✅ Test finalizat. Verifica Telegram.")

if __name__ == "__main__":
    ruleaza_test_7_zile()
