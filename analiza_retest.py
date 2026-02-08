import yfinance as yf
import pandas as pd
import requests
import os
import json
from datetime import datetime, timedelta

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
    
    if not watchlist_long:
        print("Watchlist-ul este gol.")
        return

    mesaje_trimise = 0
    
    for entry in watchlist_long:
        try:
            # Format entry: "TICKER, DD-MM, PRET"
            parts = entry.split(", ")
            ticker_symbol = parts[0]
            data_breakout_str = parts[1]
            pret_breakout = float(parts[2])
            
            # Calculăm vechimea breakout-ului (anul curent 2026)
            data_breakout = datetime.strptime(f"{data_breakout_str}-2026", "%d-%m-%Y")
            zile_trecute = (datetime.now() - data_breakout).days
            
            # FILTRU TIMP: intre 3 si 30 de zile
            if 3 <= zile_trecute <= 30:
                ticker = yf.Ticker(ticker_symbol)
                hist = ticker.history(period="5d")
                if hist.empty: continue
                
                pret_curent = hist['Close'].iloc[-1]
                
                # FILTRU PRET: Sa fie intre pret_breakout si pret_breakout + 2%
                limita_superioara = pret_breakout * 1.02
                limita_inferioara = pret_breakout * 0.99 # mică marjă sub pentru siguranță
                
                if limita_inferioara <= pret_curent <= limita_superioara:
                    mesaj = (f"🔄 *RETEST DETECTAT*\n\n"
                             f"Acțiune: `{ticker_symbol}`\n"
                             f"Preț Breakout: `{pret_breakout}`\n"
                             f"Preț Curent: `{round(pret_curent, 2)}`\n"
                             f"Vechime: `{zile_trecute} zile`\n"
                             f"Status: Prețul a revenit la zona de suport!")
                    trimite_mesaj_telegram(mesaj)
                    mesaje_trimise += 1
        except Exception as e:
            print(f"Eroare la {entry}: {e}")

    if mesaje_trimise == 0:
        print("Nicio acțiune nu îndeplinește condițiile de retest acum.")
    else:
        print(f"S-au trimis {mesaje_trimise} alerte de retest.")

if __name__ == "__main__":
    ruleaza_analiza_retest()
