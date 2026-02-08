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
        
        # Luăm datele din pasul anterior
        watchlist_long = baza_date.get('watchlist_long', [])
        watchlist_trend = baza_date.get('watchlist_trend_ascendent', [])
        
        if not watchlist_long:
            print("Lista watchlist_long este goală.")
            return

        retest_signals = []
        noi_watchlist_long = []
        
        print(f"Analizăm {len(watchlist_long)} acțiuni pentru Retest (4h)...")

        for entry in watchlist_long:
            # Parsăm entry-ul (Simbol, Data, Pret)
            # Exemplu entry: "AAPL, 05-02, 185.20"
            parts = [p.strip() for p in entry.split(',')]
            if len(parts) < 3: continue
            
            simbol = parts[0]
            data_spargere_str = parts[1]
            pret_spargere = float(parts[2])
            
            # 1. Verificăm vechimea (3-30 zile)
            try:
                data_spargere = datetime.strptime(f"{data_spargere_str}-2026", "%d-%m-%Y")
                zile_trecute = (datetime.now() - data_spargere).days
            except: continue

            if zile_trecute > 30:
                # Retrogradăm pentru că e prea veche
                if simbol not in watchlist_trend: watchlist_trend.append(simbol)
                continue
            
            # 2. Analiză tehnică pe 4h
            try:
                t = yf.Ticker(simbol)
                df_4h = t.history(interval="4h", period="60d")
                df_1d = t.history(period="40d") # Pentru volum mediu 20z
                
                if len(df_4h) < 20 or len(df_1d) < 20:
                    noi_watchlist_long.append(entry)
                    continue

                pret_actual = df_4h['Close'].iloc[-1]
                rsi_4h = calculeaza_rsi(df_4h['Close']).iloc[-1]
                
                # ATR 14 pe 1d (peste 1%)
                high_low = df_1d['High'] - df_1d['Low']
                atr = high_low.rolling(14).mean().iloc[-1]
                atr_procent = (atr / pret_actual) * 100
                
                # Volum (70-110% din media 20z)
                vol_mediu_20z = df_1d['Volume'].iloc[-21:-1].mean()
                vol_azi = df_1d['Volume'].iloc[-1]
                raport_volum = vol_azi / vol_mediu_20z

                # VERIFICARE CRITERII
                # Marja pret: 0.2% - 1.7% peste breakout
                limita_inf = pret_spargere * 1.002
                limita_sup = pret_spargere * 1.017
                
                # Retrogradare la -3% sub breakout
                if pret_actual < pret_spargere * 0.97:
                    if simbol not in watchlist_trend: watchlist_trend.append(simbol)
                    continue

                # Condiție de Retest Valid
                if (zile_trecute >= 3 and 
                    limita_inf <= pret_actual <= limita_sup and 
                    0.7 <= raport_volum <= 1.1 and 
                    45 <= rsi_4h <= 65 and 
                    atr_procent > 1.0):
                    
                    retest_signals.append(f"🎯 RETEST: {simbol} la {pret_actual:.2f} (Breakout: {pret_spargere})")
                
                # Păstrăm în listă dacă nu a expirat și nu s-a prăbușit
                noi_watchlist_long.append(entry)
                
            except Exception as e:
                print(f"Eroare la {simbol}: {e}")
                noi_watchlist_long.append(entry)

        # Update Bază de date
        baza_date['watchlist_long'] = noi_watchlist_long
        baza_date['watchlist_trend_ascendent'] = watchlist_trend
        baza_date['watchlist_retest_long'] = retest_signals
        
        with open('baza_de_date.json', 'w') as f:
            json.dump(baza_date, f, indent=4)

        # Trimitem semnalele
        if retest_signals:
            header = "💎 *RETEST CONFIRMAT (4h)*\n_Zona: +0.2% - 1.7% deasupra liniei_\n\n"
            trimite_telegram(header + "\n".join(retest_signals))
            
    except Exception as e:
        print(f"Eroare generală: {e}")

if __name__ == "__main__":
    ruleaza_pasul_4_retest()
