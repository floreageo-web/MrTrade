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

def detecteaza_breakout_istoric(df, simbol):
    # Analizam ultimele 120 de zile pentru rezistenta
    highs = df['High'].values.flatten()
    closes = df['Close'].values.flatten()
    volumes = df['Volume'].values.flatten()
    dates = df.index
    
    # Calculam indicatorii pentru toata perioada ca sa ii avem la zi
    ema20 = df['Close'].ewm(span=20).mean().values.flatten()
    ema50 = df['Close'].ewm(span=50).mean().values.flatten()
    
    # RSI (calculat pe toata seria)
    delta = df['Close'].diff()
    up = delta.clip(lower=0).rolling(14).mean()
    down = -delta.clip(upper=0).rolling(14).mean()
    rsi_series = (100 - (100 / (1 + (up / down)))).values.flatten()

    # 1. Cautam Nivelul de Rezistenta (inainte de ultimele 20 de zile)
    # Ne uitam in segmentul 120 -> 20 zile in urma
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
            # 2. Am gasit rezistenta la 'nivel'. 
            # Verificam daca a fost sparta in ultimele 20 de zile
            for k in range(len(df)-20, len(df)):
                # Ziua spargerii: Azi peste nivel, Ieri sub nivel
                if closes[k] > nivel and closes[k-1] <= nivel:
                    
                    # 3. Verificam conditiile EXACT in acea zi (k)
                    vol_mediu_atunci = volumes[k-21:k-1].mean()
                    vol_zi_spargere = volumes[k]
                    rsi_atunci = rsi_series[k]
                    ema20_atunci = ema20[k]
                    ema50_atunci = ema50[k]
                    
                    if (vol_zi_spargere > vol_mediu_atunci * 1.3 and 
                        45 <= rsi_atunci <= 65 and 
                        ema20_atunci > ema50_atunci):
                        
                        data_spargere = dates[k].strftime('%d-%m')
                        return True, nivel, data_spargere, rsi_atunci
                        
    return False, None, None, None

def ruleaza_pasul_3_semnale():
    try:
        with open('baza_de_date.json', 'r') as f:
            baza_date = json.load(f)
        lista_321 = baza_date.get('watchlist_trend_ascendent', [])
        print(f"Cautam spargeri calificate in ultimele 20 de zile...")
    except: return

    watchlist_long = []
    
    for i, simbol in enumerate(lista_321):
        if i > 0 and i % 50 == 0: time.sleep(10)
        print(f"Analizăm {i+1}/{len(lista_321)}: {simbol}", end="\r")
        
        try:
            t = yf.Ticker(simbol)
            df = t.history(period="160d")
            if len(df) < 130: continue

            gasit, pret, data, rsi_val = detecteaza_breakout_istoric(df, simbol)
            
            if gasit:
                # Verificam totusi daca pretul actual nu s-a prabusit inapoi sub rezistenta
                pret_actual = df['Close'].values.flatten()[-1]
                if pret_actual >= pret * 0.98: # Permitem o mica retestare de 2% sub nivel
                    watchlist_long.append(f"{simbol} | Spargere: {data} | La: {pret:.2f} | RSI: {int(rsi_val)}")
                    print(f"\n[+] {simbol} a avut breakout valid pe {data}")
        except: continue

    baza_date['watchlist_long'] = watchlist_long
    with open('baza_de_date.json', 'w') as f:
        json.dump(baza_date, f, indent=4)
    
    header = "🎯 *Breakouts Confirmate (Ultimele 20 zile)*\n_Filtre aplicate la data spargerii (Vol 130%, RSI 45-65)_\n\n"
    mesaj = header + ("\n".join(watchlist_long) if watchlist_long else "Nicio acțiune găsită.")
    trimite_telegram(mesaj)

if __name__ == "__main__":
    ruleaza_pasul_3_semnale()
