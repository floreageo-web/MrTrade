import yfinance as yf
import pandas as pd
import json
import requests
import os
import time
from datetime import datetime, timedelta

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def trimite_telegram(mesaj):
    if not TOKEN: 
        print("Eroare: Lipseste TOKEN-ul Telegram.")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": mesaj})
        if r.status_code != 200:
            print(f"Eroare Telegram: {r.text}")
    except Exception as e:
        print(f"Eroare la trimiterea mesajului: {e}")

def detecteaza_breakout_istoric(df, simbol):
    highs = df['High'].values.flatten()
    closes = df['Close'].values.flatten()
    volumes = df['Volume'].values.flatten()
    dates = df.index
    
    ema20 = df['Close'].ewm(span=20).mean().values.flatten()
    ema50 = df['Close'].ewm(span=50).mean().values.flatten()
    
    delta = df['Close'].diff()
    up = delta.clip(lower=0).rolling(14).mean()
    down = -delta.clip(upper=0).rolling(14).mean()
    rsi_series = (100 - (100 / (1 + (up / down)))).values.flatten()

    # 1. Cautam Rezistenta in segmentul 120 -> 20 zile in urma
    h_lookback = highs[:-20]
    d_lookback = dates[:-20]
    
    for i in range(len(h_lookback)-1, 40, -1):
        nivel = h_lookback[i]
        puncte = []
        for j in range(len(h_lookback)):
            if abs(h_lookback[j] - nivel) / nivel <= 0.02:
                if not puncte or (d_lookback[j] - puncte[-1]).days >= 15:
                    puncte.append(d_lookback[j])
        
        if len(puncte) >= 4:
            # 2. Verificam daca a fost sparta in ultimele 20 de zile
            for k in range(len(df)-20, len(df)):
                if closes[k] > nivel and closes[k-1] <= nivel:
                    
                    # 3. Filtre la momentul spargerii (k)
                    vol_mediu_atunci = volumes[k-21:k-1].mean()
                    vol_zi_spargere = volumes[k]
                    rsi_atunci = rsi_series[k]
                    
                    if (vol_zi_spargere > vol_mediu_atunci * 1.3 and 
                        45 <= rsi_atunci <= 65 and 
                        ema20[k] > ema50[k]):
                        
                        data_spargere = dates[k].strftime('%d-%m')
                        return True, nivel, data_spargere
                        
    return False, None, None

def ruleaza_pasul_3_semnale():
    try:
        with open('baza_de_date.json', 'r') as f:
            baza_date = json.load(f)
        lista_321 = baza_date.get('watchlist_trend_ascendent', [])
        print(f"Cautam spargeri in ultimele 20 zile pe {len(lista_321)} tickere...")
    except Exception as e:
        print(f"Eroare la citirea bazei de date: {e}")
        return

    watchlist_long = []
    
    for i, simbol in enumerate(lista_321):
        if i > 0 and i % 50 == 0: time.sleep(10)
        print(f"Analizăm {i+1}/{len(lista_321)}: {simbol}", end="\r")
        
        try:
            t = yf.Ticker(simbol)
            df = t.history(period="160d")
            if len(df) < 130: continue

            gasit, pret, data = detecteaza_breakout_istoric(df, simbol)
            
            if gasit:
                pret_actual = df['Close'].values.flatten()[-1]
                # Sa nu fi cazut prea mult sub nivelul de breakout intre timp
                if pret_actual >= pret * 0.98:
                    watchlist_long.append(
