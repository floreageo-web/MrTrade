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
    print("Verificăm starea pieței (SPY/QQQ)...")
    for ticker_symbol in ['SPY', 'QQQ']:
        try:
            df = yf.download(ticker_symbol, period="5d", progress=False)
            if df.empty or len(df) < 2: continue
            close = df['Close'].values.flatten()
            if close[-1] > close[-2]:
                print(f"Piața este VERDE conform {ticker_symbol}")
                return True
        except: continue
    return False

def detecteaza_rezistenta_si_breakout(df, simbol):
    highs = df['High'].values.flatten()
    dates = df.index
    h_60 = highs[-60:]
    d_60 = dates[-60:]
    
    for i in range(len(h_60)-1, 20, -1):
        nivel = h_60[i]
        puncte = []
        for j in range(len(h_60)):
            if abs(h_60[j] - nivel) / nivel <= 0.02:
                if not puncte or (d_60[j] - puncte[-1]).days >= 5:
                    puncte.append(d_60[j])
        
        if len(puncte) >= 5:
            close = df['Close'].values.flatten()
            if close[-1] > nivel or (close[-2] > nivel and close[-3] <= nivel):
                print(f"  [!] Breakout detectat pentru {simbol} la nivelul {nivel:.2f}")
                return True
    return False

def ruleaza_pasul_3_semnale():
    if not verifica_piata_verde():
        trimite_telegram("🟡 Analiză anulată: Piața este pe ROȘU.")
        return

    try:
        with open('baza_de_date.json', 'r') as f:
            baza_date = json.load(f)
        lista_321 = baza_date.get('watchlist_trend_ascendent', [])
        print(f"Am încărcat {len(lista_321)} tickere din baza de date.")
    except Exception as e:
        print(f"EROARE la încărcarea bazei de date: {e}")
        return

    watchlist_long = []
    
    for i, simbol in enumerate(lista_321):
        if i > 0 and i % 50 == 0:
            print("Pauză de 20 secunde pentru a evita blocarea...")
            time.sleep(20)
        
        print(f"Analizăm {i+1}/{len(lista_321)}: {simbol}...", end="\r")
        try:
            t = yf.Ticker(simbol)
            df = t.history(period="100d")
            if df.empty or len(df) < 60: continue

            close = df['Close'].values.flatten()
            vol = df['Volume'].values.flatten()
            vol_mediu_20 = vol[-20:].mean()
            
            # Criterii rapide pentru a nu pierde timp
            if vol_mediu_20 < 1000000 or vol[-1] < (vol_mediu_20 * 1.5): continue
            
            # Restul criteriilor
            ema20 = df['Close'].ewm(span=20).mean().values.flatten()
            ema50 = df['Close'].ewm(span=50).mean().values.flatten()
            if not (ema20[-1] > ema50[-1]): continue
            
            delta = df['Close'].diff()
            up = delta.clip(lower=0).rolling(14).mean()
            down = -delta.clip(upper=0).rolling(14).mean()
            rsi = (100 - (100 / (1 + (up.iloc[-1] / down.iloc[-1])))) if down.iloc[-1] != 0 else 50
            if not (45 <= rsi <= 65): continue
            
            if detecteaza_rezistenta_si_breakout(df, simbol):
                watchlist_long.append(simbol)
                print(f"\n[+] {simbol} adăugat în watchlist_long!")

        except Exception as e:
            continue

    baza_date['watchlist_long'] = watchlist_long
    with open('baza_de_date.json', 'w') as f:
        json.dump(baza_date, f, indent=4)
    
    trimite_telegram(f"🎯 Analiză finalizată. S-au găsit {len(watchlist_long)} tickere.")

if __name__ == "__main__":
    ruleaza_pasul_3_semnale()
