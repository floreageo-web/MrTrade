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
            
            # Calculăm vechimea (folosim 2026 conform contextului tau)
            full_date_str = f"{data_breakout_str}-2026"
            data_breakout_dt = datetime.strptime(full_date_str, "%d-%m-%Y")
            zile_trecute = (datetime.now() - data_breakout_dt).days
            
            # FILTRU TIMP: intre 3 si 45 de zile (am extins putin sa fim siguri)
            if 3 <= zile_trecute <= 45:
                ticker = yf.Ticker(ticker_symbol)
                hist = ticker.history(period="2d")
                if hist.empty: continue
                
                pret_curent = hist['Close'].iloc[-1]
                
                # FILTRU PRET: Marja de 2% fata de breakout
                limita_superioara = pret_breakout * 1.02
                limita_inferioara = pret_breakout * 0.98
                
                if limita_inferioara <= pret_curent <= limita_superioara:
                    mesaj = (f"🔄 *RETEST CONFIRMAT*\n\n"
                             f"📈 Simbol: `{ticker_symbol}`\n"
                             f"📅 Data Breakout: `{full_date_str}`\n"
                             f"📍 Preț Intrare (Breakout): `{pret_breakout}`\n"
                             f"--- \n"
                             f"🕒 Data Revenire Suport: `{data_azi}`\n"
                             f"💰 Preț Actual: `{round(pret_curent, 2)}`\n"
                             f"⏳ Vechime: `{zile_trecute} zile`\n\n"
                             f"✅ *Prețul este în zona de buy!*")
                    trimite_mesaj_telegram(mesaj)
                    mesaje_trimise += 1
        except Exception as e:
            print(f"Eroare la {entry}: {e}")

    if mesaje_trimise == 0:
        print("Nicio acțiune nu este în zona de retest.")
    else:
        print(f"S-au trimis {mesaje_trimise} alerte.")

if __name__ == "__main__":
    ruleaza_analiza_retest()
