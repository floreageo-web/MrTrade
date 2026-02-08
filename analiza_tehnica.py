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
    if not TOKEN: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"})
    except: pass

def verifica_piata_verde():
    # Criteriul 1: SPY sau QQQ verde (azi > ieri)
    for ticker_symbol in ['SPY', 'QQQ']:
        try:
            df = yf.download(ticker_symbol, period="5d", progress=False)
            if df.empty or len(df) < 2: continue
            
            # Luam ultimele doua preturi de inchidere, indiferent de formatul coloanelor
            close = df['Close'].values.flatten()
            if close[-1] > close[-2]:
                return True
        except: continue
    return False

def check_earnings(simbol):
    # Criteriul 2: Earnings calendar
    try:
        t = yf.Ticker(simbol)
        cal = t.calendar
        if cal is not None and not cal.empty:
            data_e = cal.iloc[0, 0].date()
            azi = datetime.now().date()
            if (azi >= data_e - timedelta(days=7)) and (azi <= data_e + timedelta(days=3)):
                return "STOP", data_e
            return "OK", data_e
    except: pass
    return "UNKNOWN", None

def detecteaza_rezistenta_si_breakout(df):
    # Criteriul 8: Rezistenta cu minim 5 puncte, intre 5-15 zile distanta
    highs = df['High'].values.flatten()
    dates = df.index
    # Ne uitam in ultimele 60 de zile
    h_60 = highs[-60:]
    d_60 = dates[-60:]
    
    for i in range(len(h_60)-1, 20, -1):
        nivel = h_60[i]
        puncte = []
        for j in range(len(h_60)):
            if abs(h_60[j] - nivel) / nivel <= 0.02: # Abatere 2%
                if not puncte or (d_60[j] - puncte[-1]).days >= 5:
                    puncte.append(d_60[j])
        
        if len(puncte) >= 5:
            close = df['Close'].values.flatten()
            # Verificam spargerea azi sau ieri
            if close[-1] > nivel or (close[-2] > nivel and close[-3] <= nivel):
                return True
    return False

def ruleaza_pasul_2_trend():
    try:
        with open('baza_de_date.json', 'r') as f:
            baza_date = json.load(f)
        lista_816 = baza_date.get('lista_generala_long', [])
    except: return

    watchlist_trend = []
    trimite_telegram(f"🔍 [Pasul 2] Analizăm trendul pentru {len(lista_816)} acțiuni...")

    for i, simbol in enumerate(lista_816):
        try:
            df = yf.download(simbol, period="1y", progress=False)
            if df.empty or len(df) < 200: continue
            close = df['Close'].values.flatten()
            ema50 = df['Close'].ewm(span=50, adjust=False).mean().values.flatten()
            ema200 = df['Close'].ewm(span=200, adjust=False).mean().values.flatten()
            
            if close[-1] > ema50[-1] > ema200[-1] and ema200[-1] > ema200[-10]:
                watchlist_trend.append(simbol)
        except: continue
    
    baza_date['watchlist_trend_ascendent'] = watchlist_trend
    with open('baza_de_date.json', 'w') as f:
        json.dump(baza_date, f, indent=4)
    trimite_telegram(f"✅ Pasul 2 finalizat. {len(watchlist_trend)} acțiuni rămân în trend ascendent.")

def ruleaza_pasul_3_semnale():
    if not verifica_piata_verde():
        trimite_telegram("🟡 Analiză watchlist_long: Piața (SPY/QQQ) este pe roșu. Așteptăm o zi mai bună.")
        return

    try:
        with open('baza_de_date.json', 'r') as f:
            baza_date = json.load(f)
        lista_321 = baza_date.get('watchlist_trend_ascendent', [])
    except: return

    watchlist_long = []
    
    for i, simbol in enumerate(lista_321):
        if i > 0 and i % 50 == 0: time.sleep(20)
        try:
            t = yf.Ticker(simbol)
            df = t.history(period="100d")
            if df.empty or len(df) < 60: continue

            # Filtre Tehnice
            close = df['Close'].values.flatten()
            vol = df['Volume'].values.flatten()
            vol_mediu_20 = vol[-20:].mean()
            
            # Trend 3 luni (EMA20 > EMA50)
            ema20 = df['Close'].ewm(span=20).mean().values.flatten()
            ema50 = df['Close'].ewm(span=50).mean().values.flatten()
            if not (ema20[-1] > ema50[-1]): continue
            
            # Volum > 1M si Volum azi > 150%
            if vol_mediu_20 < 1000000 or vol[-1] < (vol_mediu_20 * 1.5): continue
            
            # RSI 45-65
            delta = df['Close'].diff()
            up = delta.clip(lower=0).rolling(14).mean(); down = -delta.clip(upper=0).rolling(14).mean()
            rsi = (100 - (100 / (1 + (up.iloc[-1] / down.iloc[-1])))) if down.iloc[-1] != 0 else 50
            if not (45 <= rsi <= 65): continue
            
            # Rezistenta (Criteriul 8)
            if detecteaza_rezistenta_si_breakout(df):
                status_e, _ = check_earnings(simbol)
                if status_e == "STOP": continue
                watchlist_long.append(simbol if status_e == "OK" else f"{simbol} (E?)")
        except: continue

    baza_date['watchlist_long'] = watchlist_long
    with open('baza_de_date.json', 'w') as f:
        json.dump(baza_date, f, indent=4)
    trimite_telegram(f"🎯 S-au gasit {len(watchlist_long)} tickere care au intrat in lista watchlist_long")

if __name__ == "__main__":
    # Verificam ora Romaniei (UTC + 2h)
    ora_ro = (datetime.utcnow() + timedelta(hours=2)).hour
    
    if ora_ro == 12:
        ruleaza_pasul_2_trend()
    else:
        ruleaza_pasul_3_semnale()
