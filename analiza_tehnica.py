import yfinance as yf
import pandas as pd
import json
import requests
import os
import time

# Datele de conectare (GitHub le ia automat din Secrets)
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def trimite_telegram(mesaj):
    if not TOKEN: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"})
    except:
        pass

def verifica_structura_anuala(df):
    """
    Imparte istoricul in 6 ferestre de 40 de zile.
    Cauta minim 3 confirmari de Higher High si Higher Low.
    """
    ferestre = []
    # Luam ultimele 240 de zile lucratoare (aprox. 1 an)
    df_recent = df.iloc[-240:] if len(df) >= 240 else df
    
    # Cream ferestrele
    for i in range(6):
        start = i * 40
        end = (i + 1) * 40
        segment = df_recent.iloc[start:end]
        if not segment.empty:
            ferestre.append({
                'high': float(segment['High'].max()),
                'low': float(segment['Low'].min())
            })
    
    hh_count = 0
    hl_count = 0
    marja = 1.02 # Marja de 2% stabilita de tine

    # Comparam ferestrele intre ele
    for j in range(1, len(ferestre)):
        if ferestre[j]['high'] > ferestre[j-1]['high'] * marja:
            hh_count += 1
        if ferestre[j]['low'] > ferestre[j-1]['low'] * marja:
            hl_count += 1
            
    # Trebuie sa avem minim 3 trepte urcate
    return hh_count >= 3 and hl_count >= 3

def ruleaza_analiza_trend():
    # 1. Citim lista celor 816 din JSON
    try:
        with open('baza_de_date.json', 'r') as f:
            baza_date = json.load(f)
        lista_816 = baza_date.get('lista_generala_long', [])
    except Exception as e:
        print(f"Eroare JSON: {e}")
        return

    watchlist_trend = []
    total = len(lista_816)
    
    if total == 0:
        trimite_telegram("⚠️ Lista 'lista_generala_long' este goala!")
        return

    trimite_telegram(f"🚀 Incepem Pasul 2: Analiza de Trend 1 An pentru {total} actiuni.")

    # 2. Analizam fiecare simbol
    for i, simbol in enumerate(lista_816):
        try:
            df = yf.download(simbol, period="1y", interval="1d", progress=False)
            if len(df) < 200: continue

            # Calculam EMA 50 si 200
            ema50 = df['Close'].ewm(span=50, adjust=False).mean()
            ema200 = df['Close'].ewm(span=200, adjust=False).mean()

            pret_azi = float(df['Close'].iloc[-1])
            e50_azi = float(ema50.iloc[-1])
            e200_azi = float(ema200.iloc[-1])
            e200_vechi = float(ema200.iloc[-20]) # Acum o luna

            # FILTRELE TALE:
            # A. Pret > EMA 50 > EMA 200
            if pret_azi > e50_azi > e200_azi:
                # B. EMA 200 in urcare
                if e200_azi > e200_vechi:
                    # C. Cele 3 trepte (HH/HL)
                    if verifica_structura_anuala(df):
                        watchlist_trend.append(simbol)

            # Pauza la fiecare 50 actiuni ca sa fim safe
            if (i + 1) % 50 == 0:
                print(f"Verificat: {i+1}/{total}")
                time.sleep(10)

        except:
            continue

    # 3. Salvam rezultatul
    baza_date['watchlist_trend_ascendent'] = watchlist_trend
    with open('baza_de_date.json', 'w') as f:
        json.dump(baza_date, f, indent=4)

    # 4. Finalizare
    mesaj = (f"✅ **Pasul 2 Gata!**\n\n"
             f"Am gasit **{len(watchlist_trend)}** actiuni care au trecut testul de trend ascendent.\n"
             f"Univers initial: {total} actiuni.")
    trimite_telegram(mesaj)

if __name__ == "__main__":
    ruleaza_analiza_trend()
