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
    requests.post(url, json={"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"})

def verifica_piata_verde():
    # Criteriul 1: SPY sau QQQ sa fie verzi (azi > ieri)
    for ticker in ['SPY', 'QQQ']:
        df = yf.download(ticker, period="2d", progress=False)
        if len(df) < 2: continue
        if df['Close'].iloc[-1] > df['Close'].iloc[-2]:
            return True
    return False

def check_earnings(simbol):
    # Criteriul 2: Earnings calendar
    try:
        t = yf.Ticker(simbol)
        calendar = t.calendar
        if calendar is not None and 'Earnings Date' in calendar:
            data_e = calendar['Earnings Date'][0].date()
            azi = datetime.now().date()
            # Fereastra: -7 zile si +3 zile
            if (azi >= data_e - timedelta(days=7)) and (azi <= data_e + timedelta(days=3)):
                return "STOP", data_e
            return "OK", data_e
    except:
        pass
    return "UNKNOWN", None

def gaseste_rezistenta(df):
    # Criteriul 8: Zona de rezistenta (5 puncte de maxim in ultimele 60 zile)
    df_recent = df.iloc[-60:]
    highs = df_recent['High'].values
    # Cautam un plafon unde pretul a batut de minim 5 ori (abatere 1.5%)
    for i in range(len(highs)-1, 10, -1):
        nivel_testat = highs[i]
        atingeri = 0
        for h in highs:
            if abs(h - nivel_testat) / nivel_testat <= 0.015:
                atingeri += 1
        if atingeri >= 5:
            return nivel_testat
    return None

def ruleaza_pasul_3():
    if not verifica_piata_verde():
        trimite_telegram("⚠️ Piata (SPY/QQQ) este pe ROȘU. Analiza Watchlist_Long a fost anulată.")
        return

    try:
        with open('baza_de_date.json', 'r') as f:
            baza_date = json.load(f)
        lista_321 = baza_date.get('watchlist_trend_ascendent', [])
    except: return

    watchlist_long = []
    
    for i, simbol in enumerate(lista_321):
        try:
            # Pauza la fiecare 50 de tickere (20 secunde conform cerintei)
            if i > 0 and i % 50 == 0:
                time.sleep(20)

            t = yf.Ticker(simbol)
            df = t.history(period="100d")
            if len(df) < 60: continue

            # Date necesare
            pret_azi = df['Close'].iloc[-1]
            volum_azi = df['Volume'].iloc[-1]
            volum_mediu_20 = df['Volume'].iloc[-20:].mean()
            
            # 3. Trend 3 luni: EMA20 > EMA50 si EMA50 slope pozitiv
            ema20 = df['Close'].ewm(span=20).mean()
            ema50 = df['Close'].ewm(span=50).mean()
            if not (ema20.iloc[-1] > ema50.iloc[-1] and ema50.iloc[-1] > ema50.iloc[-5]): continue

            # 4. Volum Mediu > 1M
            if volum_mediu_20 < 1000000: continue

            # 5. Volum azi > 150% din media 20
            if volum_azi < (volum_mediu_20 * 1.5): continue

            # 6. ATR14 > 1%
            high_low = df['High'] - df['Low']
            atr14 = high_low.rolling(window=14).mean().iloc[-1]
            if (atr14 / pret_azi) < 0.01: continue

            # 7. RSI 45-65
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs.iloc[-1]))
            if not (45 <= rsi <= 65): continue

            # 8. Rezistenta sparta recent (ultimele 2 zile)
            rezistenta = gaseste_rezistenta(df)
            if rezistenta:
                spargere_azi = pret_azi > rezistenta
                spargere_ieri = df['Close'].iloc[-2] > rezistenta and df['Close'].iloc[-3] <= rezistenta
                if not (spargere_azi or spargere_ieri): continue
            else: continue

            # Verificare Earnings la final
            status_e, data_e = check_earnings(simbol)
            if status_e == "STOP": continue
            
            nume_final = simbol if status_e == "OK" else f"{simbol} (E?)"
            watchlist_long.append(nume_final)

        except: continue

    baza_date['watchlist_long'] = watchlist_long
    with open('baza_date.json', 'w') as f:
        json.dump(baza_date, f, indent=4)

    trimite_telegram(f"🎯 S-au gasit {len(watchlist_long)} tickere care au intrat in lista watchlist_long")

if __name__ == "__main__":
    # Aici robotul decide ce sa faca in functie de ora
    ora_acum = datetime.now().hour
    minut_acum = datetime.now().minute
    
    # Daca e ora de trend (Pasul 2) - o pastram pe cea veche aici
    # Daca e ora de semnale (15:05 sau 23:10)
    ruleaza_pasul_3()
