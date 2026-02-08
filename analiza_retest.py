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
    except:
        return {}

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
                ticker = yf.Ticker(ticker_symbol)
                hist = ticker.history(start=dt_breakout.strftime('%Y-%m-%d'))
                
                if len(hist) < 4: continue

                limita_sup = pret_breakout * 1.02
                limita_inf = pret_breakout * 0.98
                pret_curent = hist['Close'].iloc[-1]

                # 1. Identificăm prima atingere (retest 1)
                zona_atinsa = (hist['Low'].iloc[1:-1] >= limita_inf) & (hist['Low'].iloc[1:-1] <= limita_sup)
                
                if zona_atinsa.any():
                    idx_primul_retest = zona_atinsa.values.argmax()
                    data_primul_retest = hist.index[idx_primul_retest + 1].strftime("%d-%m-%Y")
                    
                    # 2. Verificăm respingerea (bounce de min 2% după primul retest)
                    preturi_dupa = hist['High'].iloc[idx_primul_retest+1:-1]
                    a_avut_respingere = any(preturi_dupa > pret_breakout * 1.02)

                    # 3. Verificăm a doua revenire (retest 2 - azi)
                    if a_avut_respingere and (limita_inf <= pret_curent <= limita_sup):
                        mesaj = (f"🎯 *DUBLU RETEST DETECTAT*\n\n"
                                 f"📈 *Simbol:* `{ticker_symbol}`\n"
                                 f"💥 *Breakout:* `{full_date_brk}` | Preț: `{pret_breakout}`\n"
                                 f"--- \n"
                                 f"1️⃣ *Primul Retest:* `{data_primul_retest}` (confirmat cu bounce)\n"
                                 f"2️⃣ *Al Doilea Retest:* `{data_azi}` (ACUM)\n"
                                 f"--- \n"
                                 f"💰 *Preț Actual:* `{round(pret_curent, 2)}`\n"
                                 f"⏳ *Vechime:* `{zile_trecute} zile`\n\n"
                                 f"🚀 *Semnal: Suport confirmat a doua oară!*")
                        trimite_mesaj_telegram(mesaj)
                        mesaje_trimise += 1
                    
        except Exception as e:
            print(f"Eroare la {entry}: {e}")

    if mesaje_trimise == 0:
        print("Nicio acțiune cu dublu retest găsită.")

if __name__ == "__main__":
    ruleaza_analiza_retest()
