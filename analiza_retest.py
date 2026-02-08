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
            ticker_symbol, data_breakout_str, pret_breakout = parts[0], parts[1], float(parts[2])
            
            full_date_str = f"{data_breakout_str}-2026"
            data_breakout_dt = datetime.strptime(full_date_str, "%d-%m-%Y")
            zile_trecute = (datetime.now() - data_breakout_dt).days
            
            # FILTRU TIMP: 5 - 25 zile
            if 5 <= zile_trecute <= 25:
                ticker = yf.Ticker(ticker_symbol)
                hist = ticker.history(start=data_breakout_dt.strftime('%Y-%m-%d'))
                
                if len(hist) < 4: continue # Avem nevoie de cateva zile pentru "miscare"

                limita_sup = pret_breakout * 1.02
                limita_inf = pret_breakout * 0.98
                pret_curent = hist['Close'].iloc[-1]

                # --- LOGICA DE RESPINGERE (BOUNCE) ---
                # 1. Identificam daca in trecut (intre breakout si azi) a atins zona
                zona_atinsa = (hist['Low'].iloc[1:-1] >= limita_inf) & (hist['Low'].iloc[1:-1] <= limita_sup)
                
                if zona_atinsa.any():
                    # Gasim indexul primei atingeri
                    idx_atingere = zona_atinsa.values.argmax()
                    # 2. Verificam daca DUPA acea atingere, pretul a urcat (confirmand respingerea)
                    # Verificam daca maximul atins dupa prima vizita a fost cu cel putin 2% peste breakout
                    preturi_dupa_prima_vizita = hist['High'].iloc[idx_atingere+1:-1]
                    a_avut_respingere = any(preturi_dupa_prima_vizita > pret_breakout * 1.02)

                    # 3. Daca a avut respingere si ACUM e inapoi in zona
                    if a_avut_respingere and (limita_inf <= pret_curent <= limita_sup):
                        mesaj = (f"🔄 *DUBLU RETEST (Respingere Confirmată)*\n\n"
                                 f"📈 Simbol: `{ticker_symbol}`\n"
                                 f"📅 Breakout: `{full_date_str}` (`{pret_breakout}`)\n"
                                 f"--- \n"
                                 f"✅ Prima respingere detectată în istoric.\n"
                                 f"🕒 A doua revenire: `{data_azi}`\n"
                                 f"💰 Preț Actual: `{round(pret_curent, 2)}`\n"
                                 f"⏳ Vechime: `{zile_trecute} zile`\n\n"
                                 f"🚀 *Zonă de suport testată a doua oară!*")
                        trimite_mesaj_telegram(mesaj)
                        mesaje_trimise += 1
                    
        except Exception as e:
            print(f"Eroare la {entry}: {e}")

    if mesaje_trimise == 0:
        print("Nicio acțiune cu dublu retest și respingere găsită.")

if __name__ == "__main__":
    ruleaza_analiza_retest()
