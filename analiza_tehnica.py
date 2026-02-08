import yfinance as yf
import pandas as pd
import json
import requests
import time

# --- CONFIGURARE TELEGRAM ---
TOKEN = "AICI_PUNE_TOKENUL_TAU"
CHAT_ID = "AICI_PUNE_CHAT_ID_TAU"

def trimite_telegram(mesaj):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Eroare trimitere Telegram: {e}")

def calculeaza_ema(data, period):
    return data['Close'].ewm(span=period, adjust=False).mean()

def verifica_structura_hh_hl(data):
    # Verificam daca ultimele minime sunt in crestere (Higher Lows)
    # Ne uitam la ultimele 20 de zile
    recent_lows = data['Low'].tail(20).rolling(window=5).min()
    if recent_lows.iloc[-1] >= recent_lows.iloc[-10]:
        return True
    return False

def ruleaza_analiza():
    # 1. Incarcam cele 816 actiuni gasite de scanner
    try:
        with open('baza_de_date.json', 'r') as f:
            date_brute = json.load(f)
        lista_actiuni = date_brute['lista_generala_long']
    except Exception as e:
        print(f"Nu am putut citi baza_de_date.json: {e}")
        return

    print(f"Incepem analiza tehnica pentru {len(lista_actiuni)} actiuni...")
    trimite_telegram(f"🔍 Incep analiza tehnica pe cele {len(lista_actiuni)} actiuni filtrate...")

    oportunitati = []

    for simbol in lista_actiuni:
        try:
            # Descarcam datele pentru 1 an (necesar pentru EMA 200)
            df = yf.download(simbol, period="1y", interval="1d", progress=False)
            
            if len(df) < 200:
                continue

            # Calculam indicatorii
            ema50 = calculeaza_ema(df, 50)
            ema200 = calculeaza_ema(df, 200)
            pret_actual = float(df['Close'].iloc[-1])

            # --- FILTRU 1: TREND (EMA 50 > EMA 200) ---
            if ema50.iloc[-1] > ema200.iloc[-1]:
                
                # --- FILTRU 2: STRUCTURA (Higher Lows) ---
                if verifica_structura_hh_hl(df):
                    
                    # --- FILTRU 3: ZONA DE CUMPARARE (Aproape de EMA 50) ---
                    # Calculam distanta procentuala fata de EMA 50
                    valoare_ema50 = float(ema50.iloc[-1])
                    distanta_ema50 = (pret_actual - valoare_ema50) / valoare_ema50
                    
                    # Daca pretul este deasupra EMA 50, dar la mai putin de 2% distanta
                    if 0 <= distanta_ema50 <= 0.02:
                        msg = (f"⭐ **SEMNAL GASIT: {simbol}**\n"
                               f"💰 Pret: ${pret_actual:.2f}\n"
                               f"📈 Distanta EMA 50: {distanta_ema50*100:.2f}%\n"
                               f"📍 Strategie: Retest pe Trend crescator")
                        
                        print(f"Gasit: {simbol}")
                        trimite_telegram(msg)
                        oportunitati.append({"simbol": simbol, "pret": pret_actual})
            
            # Mica pauza sa nu blocam Yahoo Finance
            time.sleep(0.1)

        except Exception as e:
            print(f"Eroare la {simbol}: {e}")
            continue

    trimite_telegram(f"✅ Analiza finalizata! Am gasit {len(oportunitati)} oportunitati care respecta toate criteriile tale.")

if __name__ == "__main__":
    ruleaza_analiza()
