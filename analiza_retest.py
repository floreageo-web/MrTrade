import yfinance as yf
import pandas as pd
import requests
import os
import json
from datetime import datetime

# Configurare Telegram
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def trimite_mesaj_telegram(mesaj):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def incarca_baza_de_date():
    try:
        with open("baza_de_date.json", "r") as f:
            return json.load(f)
    except: return {}

def calculeaza_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def ruleaza_analiza_retest():
    data = incarca_baza_de_date()
    watchlist_long = data.get("watchlist_long", [])
    data_azi = datetime.now().strftime("%d-%m-%Y")
    
    if not watchlist_long: return

    mesaje_trimise = 0
    
    for entry in watchlist_long:
        try:
            parts = entry.split(", ")
            ticker_symbol, data_brk_str, pret_breakout = parts[0], parts[1], float(parts[2])
            
            full_date_brk = f"{data_brk_str}-2026"
            dt_breakout = datetime.strptime(full_date_brk, "%d-%m-%Y")
            zile_trecute = (datetime.now() - dt_breakout).days
            
            # FILTRU TIMP: 5 - 25 zile
            if 5 <= zile_trecute <= 25:
                # Luăm date suficiente pentru indicatori (60 zile pentru EMA/RSI/ATR)
                ticker = yf.Ticker(ticker_symbol)
                hist = ticker.history(period="60d")
                
                if len(hist) < 30: continue

                # --- CALCUL INDICATORI ---
                pret_curent = hist['Close'].iloc[-1]
                volum_curent = hist['Volume'].iloc[-1]
                
                # EMA 20
                ema20 = hist['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
                
                # Volum Mediu (20 zile)
                vol_mediu_20 = hist['Volume'].tail(20).mean()
                procent_volum = (volum_curent / vol_mediu_20) * 100
                
                # ATR 14 (Aproximare rapidă)
                high_low = hist['High'] - hist['Low']
                high_close = abs(hist['High'] - hist['Close'].shift())
                low_close = abs(hist['Low'] - hist['Close'].shift())
                tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                atr14 = tr.rolling(14).mean().iloc[-1]
                atr_procent = (atr14 / pret_curent) * 100
                
                # RSI 14
                rsi_val = calculeaza_rsi(hist['Close']).iloc[-1]

                # --- FILTRE TEHNICE ---
                cond_ema = pret_curent >= ema20
                cond_vol_abs = vol_mediu_20 >= 1000000
                cond_vol_rel = 70 <= procent_volum <= 150 # Nu parabolic (>150%), Nu mort (<70%)
                cond_atr = atr_procent >= 1.0
                cond_rsi = 45 <= rsi_val <= 65

                # Zona de Retest (marja 2%)
                limita_sup = pret_breakout * 1.02
                limita_inf = pret_breakout * 0.98

                # Logica de Dublu Retest (folosim ultimele 20 zile din hist)
                zona_atinsa = (hist['Low'].iloc[-zile_trecute:-1] >= limita_inf) & (hist['Low'].iloc[-zile_trecute:-1] <= limita_sup)
                
                if zona_atinsa.any() and cond_ema and cond_vol_abs and cond_vol_rel and cond_atr and cond_rsi:
                    idx_primul = zona_atinsa.values.argmax()
                    data_retest1 = hist.index[-zile_trecute + idx_primul].strftime("%d-%m-%Y")
                    
                    if limita_inf <= pret_curent <= limita_sup:
                        mesaj = (f"🎯 *SETUP DUBLU RETEST FILTRAT*\n\n"
                                 f"📈 *Simbol:* `{ticker_symbol}`\n"
                                 f"💥 *Breakout:* `{full_date_brk}` | Preț: `{pret_breakout}`\n"
                                 f"--- \n"
                                 f"1️⃣ *Primul Retest:* `{data_retest1}`\n"
                                 f"2️⃣ *Al Doilea Retest:* `{data_azi}`\n"
                                 f"--- \n"
                                 f"📊 *Indicatori la Retest 2:*\n"
                                 f"🔹 EMA 20: `Preț >= EMA20` ✅\n"
                                 f"🔹 Volum: `{round(procent_volum)}%` din medie ✅\n"
                                 f"🔹 RSI (14): `{round(rsi_val, 1)}` ✅\n"
                                 f"🔹 ATR (14): `{round(atr_procent, 2)}%` ✅\n\n"
                                 f"🚀 *Zonă de cumpărare confirmată tehnic!*")
                        trimite_mesaj_telegram(mesaj)
                        mesaje_trimise += 1
                    
        except Exception as e:
            print(f"Eroare la {entry}: {e}")

    if mesaje_trimise == 0:
        print("Nicio acțiune nu îndeplinește toate criteriile stricte.")

if __name__ == "__main__":
    ruleaza_analiza_retest()
