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

# --- FUNCTII CALCUL TEHNIC ---
def calculeaza_indicatori(df):
    # RSI 14
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # ATR 14
    high_low = df['High'] - df['Low']
    high_close = abs(df['High'] - df['Close'].shift())
    low_close = abs(df['Low'] - df['Close'].shift())
    df['TR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = df['TR'].rolling(14).mean()
    
    # EMA 20 & 50
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    return df

# --- FILTRUL "ULTRA-PERFECT" (GEOMETRIE SI INACTIVITATE) ---
def valideaza_zona_ultra_perfect(df):
    cp = df['Close'].iloc[-1]
    atr_val = df['ATR'].iloc[-1]
    # Delta conform formulei tale: max(0.8% din pret sau ATR)
    delta = max(0.008 * cp, atr_val)
    
    # Gasim maxime locale folosind o fereastra de 21 de zile (centrat)
    maxime = df[df['High'] == df['High'].rolling(window=21, center=True).max()]
    
    if len(maxime) < 4: 
        return None, "INACTIV"
    
    # Verificam ultima zona formata
    potentiala_zona = maxime['High'].iloc[-1]
    puncte_in_zona = maxime[(maxime['High'] >= potentiala_zona - delta) & 
                            (maxime['High'] <= potentiala_zona + delta)]
    
    if len(puncte_in_zona) >= 4:
        # Regula 1b: Separare minim 10 zile intre puncte
        distante = puncte_in_zona.index.to_series().diff().dt.days
        if not (distante.dropna() >= 10).all():
            return None, "INACTIV"
            
        zona_z = puncte_in_zona['High'].mean()
        
        # Regula 3: Stare de INACTIVITATE (30-50 zile)
        # Daca pretul a inchis sub Z - delta in ultimele 50 de zile, zona e "moarta"
        istoric_50 = df.iloc[-50:-1]
        a_fost_sparta_jos = (istoric_50['Close'] < zona_z - delta).any()
        
        if a_fost_sparta_jos:
            return zona_z, "INACTIV"
            
        return zona_z, "ACTIV"
        
    return None, "INACTIV"

# --- SCANAREA PRINCIPALA (PE CELE 312 ACTIUNI) ---
def ruleaza_scanare():
    try:
        with open("baza_de_date.json", "r") as f:
            db = json.load(f)
    except:
        print("Eroare: Nu s-a putut incarca baza_de_date.json")
        return

    # Luam lista de 312 din Trend Ascendent
    tickers = db.get("watchlist_trend_ascendent", [])
    total_tickers = len(tickers)
    noi_breakouturi = []
    
    # Seteaza ora Romaniei
    tz_ro = pytz.timezone('Europe/Bucharest')
    acum_ro = datetime.now(tz_ro)
    data_ora_str = acum_ro.strftime("%d-%m-%Y %H:%M")

    print(f"Incepem scanarea pentru {total_tickers} actiuni...")

    for index, symbol in enumerate(tickers, start=1):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="250d") # Date pe 1 an pentru structura
            if len(df) < 150: continue

            df = calculeaza_indicatori(df)
            cp = df['Close'].iloc[-1]
            
            # --- FILTRELE TALE TEHNICE ---
            # 1. Trend 3 luni (EMA20 > EMA50 si EMA50 Slope +)
            slope_ema50 = df['EMA50'].iloc[-1] > df['EMA50'].iloc[-10]
            cond_trend = (df['EMA20'].iloc[-1] > df['EMA50'].iloc[-1]) and slope_ema50
            
            # 2. Volum (Mediu > 1M, Azi > 150%)
            vol_mediu_20 = df['Volume'].tail(20).mean()
            cond_vol = (vol_mediu_20 >= 1000000) and (df['Volume'].iloc[-1] >= vol_mediu_20 * 1.5)
            
            # 3. ATR > 1% si RSI 45-65
            atr_proc = (df['ATR'].iloc[-1] / cp) * 100
            cond_tehnic = (atr_proc > 1.0) and (45 <= df['RSI'].iloc[-1] <= 65)
            
            # --- FILTRU GEOMETRIC (ULTRA-PERFECT) ---
            zona_z, status = valideaza_zona_ultra_perfect(df)
            
            # --- VALIDARE FINALA ---
            if zona_z and status == "ACTIV":
                delta = max(0.008 * cp, df['ATR'].iloc[-1])
                # Pretul trebuie sa sparga Z + delta
                if cp > (zona_z + delta) and cond_trend and cond_vol and cond_tehnic:
                    
                    data_salvare = acum_ro.strftime("%d-%m")
                    noi_breakouturi.append(f"{symbol}, {data_salvare}, {round(cp, 2)}")
                    
                    # Trimite alerta detaliata
                    trimite_mesaj(f"🏆 *BREAKOUT ULTRA-CONFIRMAT*\n\n"
                                 f"📊 *Ticker:* `{symbol}` (#{index}/{total_tickers})\n"
                                 f"💰 *Preț Spargere:* `{round(cp, 2)}` $\n"
                                 f"📅 *Data & Ora:* `{data_ora_str}` (RO)\n"
                                 f"📏 *Rezistență (Z):* `{round(zona_z, 2)}` (4 puncte)\n"
                                 f"--- \n"
                                 f"🔊 *Volum:* `{round(df['Volume'].iloc[-1]/vol_mediu_20*100)}%` 🚀\n"
                                 f"📈 *Trend:* EMA 20/50 Ascendent\n"
                                 f"🎯 *Status:* Zonă ACTIVĂ & CURATĂ")

        except Exception as e:
            print(f"Eroare la {symbol}: {e}")

    # Salvare in watchlist_long (pentru analiza de retest ulterioara)
    if noi_breakouturi:
        existing = db.get("watchlist_long", [])
        # Folosim set pentru a evita duplicatele, dar pastram formatul string
        db["watchlist_long"] = list(set(existing + noi_breakouturi))
        with open("baza_de_date.json", "w") as f:
            json.dump(db, f, indent=2)
        print(f"Scanare finalizata. Am gasit {len(noi_breakouturi)} oportunitati.")
    else:
        print("Scanare finalizata. Niciun breakout valid gasit.")

if __name__ == "__main__":
    ruleaza_scanare()
