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
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    # ATR & EMA
    tr = pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift()), abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(14).mean()
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    return df

def find_resistances_v_final(df):
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
        zona_peaks = [p for p in peaks_sorted if abs(df.iloc[p]['Close'] - base_val) / base_val <= 0.01]
        
        if len(zona_peaks) < 4: continue
        
        zona_prices = df.iloc[zona_peaks]['Close']
        zona_low, zona_high = zona_prices.min(), zona_prices.max()
        
        # Logica de "Comasare" (Punctul 4 din discutie): Permitem suprapunerea pentru forta
        first_touch_idx, last_touch_idx = min(zona_peaks), max(zona_peaks)
        
        resistances.append({
            'points_indices': zona_peaks,
            'low': zona_low,
            'high': zona_high,
            'strength': len(zona_peaks),
            'last_touch': last_touch_idx,
            'first_touch_date': df.index[first_touch_idx].strftime("%d-%m-%Y"),
            'age_days': data_len - first_touch_idx
        })
    return resistances

def ruleaza_scanare():
    try:
        with open("baza_de_date.json", "r") as f:
            db = json.load(f)
    except: return

    tickers = db.get("watchlist_trend_ascendent", [])
    tz_ro = pytz.timezone('Europe/Bucharest')
    data_scanare = datetime.now(tz_ro).strftime("%d-%m-%Y %H:%M")

    for symbol in tickers:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="360d") # 1 an de date
            if len(df) < 200: continue
            
            df = calculeaza_indicatori(df)
            resistances = find_resistances_v_final(df)
            
            # Verificam ultimele 10 zile pentru a gasi breakout-ul
            for i in range(len(df)-10, len(df)):
                row = df.iloc[i]
                price = row['Close']
                vol_avg = df.iloc[i-20:i]['Volume'].mean()
                
                for r in resistances:
                    if r['last_touch'] >= i: continue # Rezistenta trebuie sa fie in trecut
                    
                    gap_pct = (price / r['high'] - 1) * 100
                    
                    # FILTRE: Breakout (min 1%), Gap (max 5%), Volum (1.5x), RSI, ATR, Trend
                    if (1.0 <= gap_pct <= 5.0 and row['Volume'] > 1.5 * vol_avg and 
                        45 <= row['RSI'] <= 65 and (row['ATR']/price)*100 >= 1.0 and
                        price > row['EMA20'] > row['EMA50']):
                        
                        # Verificare Hold (doar daca exista date in viitor)
                        hold_ok = True
                        status = "✅ CONFIRMAT"
                        for k in range(1, 3):
                            if i + k < len(df):
                                if df.iloc[i + k]['Close'] <= r['high']:
                                    hold_ok = False; break
                            else:
                                status = "⏳ ÎN CURS" # Inca nu avem 2 zile de istoric
                        
                        if hold_ok:
                            trimite_mesaj(f"🔔 *BREAKOUT DETECTAT*\n\n"
                                         f"📊 Ticker: `{symbol}`\n"
                                         f"💰 Preț: `{round(price, 2)}` $\n"
                                         f"📏 Rezistență: `{round(r['high'], 2)}`\n"
                                         f"🔢 Forță (Puncte): `{r['strength']}`\n"
                                         f"📈 Gap: `{round(gap_pct, 1)}%`\n"
                                         f"⏳ Vârstă Rez.: `{r['age_days']} zile`\n"
                                         f"--- \n"
                                         f"🛡️ Status: {status}\n"
                                         f"📅 Dată: `{df.index[i].strftime('%d-%m-%Y')}`")
                            
                            # Salvare in watchlist_long
                            entry = f"{symbol}, {df.index[i].strftime('%d-%m')}, {round(price, 2)}"
                            if entry not in db.get("watchlist_long", []):
                                db.setdefault("watchlist_long", []).append(entry)
                            break # O singura alerta per ticker
        except: continue

    with open("baza_de_date.json", "w") as f:
        json.dump(db, f, indent=2)

if __name__ == "__main__":
    ruleaza_scanare()
