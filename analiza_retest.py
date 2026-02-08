import yfinance as yf
import pandas as pd
import json
import requests
import os
import time
from datetime import datetime

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def trimite_telegram(mesaj):
    if not TOKEN: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": mesaj})
    except: pass

def calculeaza_rsi(series, periods=14):
    delta = series.diff()
    up = delta.clip(lower=0).rolling(window=periods).mean()
    down = -delta.clip(upper=0).rolling(window=periods).mean()
    rs = up / down
    return 100 - (100 / (1 + rs))

def ruleaza_pasul_4_retest():
    try:
        with open('baza_de_date.json', 'r') as f:
            baza_date = json.load(f)
        
        watchlist_long = baza_date.get('watchlist_long', [])
        watchlist_trend = baza_date.get('watchlist_trend_ascendent', [])
        
        if not watchlist_long:
            return

        retest_signals = []
        noi_watchlist_long = []
        
        for entry in watchlist_long:
            parts = [p.strip() for p in entry.split(',')]
            if len(parts) < 3: continue
            
            simbol = parts[0]
            data_spargere_str = parts[1]
            pret_spargere = float(parts[2])
            
            # Verificare vechime
            try:
                data_spargere = datetime.strptime(f"{data_spargere_str}-2026", "%d-%m-%Y")
                zile_trecute = (datetime.now() - data_spargere).days
            except: zile_trecute = 0

            # 1. Daca e mai vechi de 30 zile, muta inapoi in trend
            if zile_trecute > 30:
                if simbol not in watchlist_trend: watchlist_trend.append(simbol)
                continue
            
            try:
                t = yf.Ticker(simbol)
                df_4h = t.history(interval="4h", period="60d")
                df_1d = t.history(period="40d")
                
                if len(df_4h) < 20: 
                    noi_watchlist_long.append(entry)
                    continue

                pret_actual = df_4h['Close'].iloc[-1]
                rsi_4h = calculeaza_rsi(df_4h['Close']).iloc[-1]
                
                # ATR 14 zile
                high_low = df_1d['High'] - df_1d['Low']
                atr = high_low.rolling(14).mean().iloc[-1]
                atr_procent = (atr / pret_actual) * 100
                
                # Volum (70-110%)
                vol_mediu_20z = df_1d['Volume'].iloc[-21:-1].mean()
                vol_azi = df_1d['Volume'].iloc[-1]
                raport_volum = vol_azi / vol_mediu_20z

                # Marje pret stabilite de tine
                limita_inf = pret_spargere * 1.002
                limita_sup = pret_spargere * 1.017
                
                # 2. Retrogradare daca scade sub -3%
                if pret_actual < pret_spargere * 0.97:
                    if simbol not in watchlist_trend: watchlist_trend.append(simbol)
                    continue

                # 3. Conditie Semnal Retest
                if (zile_trecute >= 3 and 
                    limita_inf <= pret_actual <= limita_sup and 
                    0.7 <= raport_volum <= 1.1 and 
                    45 <= rsi_4h <= 65 and 
                    atr_procent > 1.0):
                    
                    retest_signals.append(f"🎯 RETEST: {simbol} la {pret_actual:.2f} (Breakout: {pret_spargere})")
                
                noi_watchlist_long.append(entry)
            except:
                noi_watchlist_long.append(entry)

        # Salvare date
        baza_date['watchlist_long'] = noi_watchlist_long
        baza_date['watchlist_trend_ascendent'] = watchlist_trend
        baza_date['watchlist_retest_long'] = retest_signals
        
        with open('baza_de_date.json', 'w') as f:
            json.dump(baza_date, f, indent=4)

        if retest_signals:
            trimite_telegram("🎯 SEMNALE RETEST (4h):\n\n" + "\n".join(retest_signals))
            
    except Exception as e:
        print(f"Eroare: {e}")

if __name__ == "__main__":
    ruleaza_pasul_4_retest()
