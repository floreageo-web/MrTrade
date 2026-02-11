import os
import pandas as pd
import json
import time
import telebot
import yfinance as yf

# Configurare Telegram
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
bot = telebot.TeleBot(TOKEN)

def incarca_baza_date():
    try:
        with open('baza_de_date.json', 'r') as f:
            content = json.load(f)
            # Ne asiguram ca structura exista
            if "watchlist_trend_ascendent" not in content:
                content["watchlist_trend_ascendent"] = []
            return content
    except:
        return {"watchlist_trend_ascendent": [], "watchlist_long": []}

def salveaza_baza_date(date):
    with open('baza_de_date.json', 'w') as f:
        # indent=4 este CRUCIAL pentru a vedea toate simbolurile clar
        json.dump(date, f, indent=4)

def ruleaza_scanner_complet():
    db = incarca_baza_date()
    
    try:
        df_screener = pd.read_csv('nasdaq_screener_1770486054910.csv')
        toate_simbolurile = df_screener['Symbol'].tolist()
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ Eroare la citirea fisierului CSV: {e}")
        return

    gasite_noi = []
    total = len(toate_simbolurile)
    bot.send_message(CHAT_ID, f"🚀 Incep scanarea pentru {total} actiuni...")

    for i, simbol in enumerate(toate_simbolurile):
        if not isinstance(simbol, str) or '^' in simbol or '.' in simbol:
            continue

        # Pauza la fiecare 50 de actiuni pentru a evita blocarea de catre Yahoo
        if i > 0 and i % 50 == 0:
            print(f"Progres: {i}/{total}...")
            time.sleep(5) # Redus la 5 secunde, 60 era prea mult pentru GitHub Actions

        try:
            t = yf.Ticker(simbol)
            info = t.fast_info 
            
            pret = info.last_price
            mcap = info.market_cap / 1_000_000_000

            # FILTRELE TALE: 35-150$ si 2-50B Market Cap
            if 35 <= pret <= 150 and 2 <= mcap <= 50:
                gasite_noi.append(simbol)
                print(f"✅ Adaugat: {simbol}")
        except:
            continue

    # --- AICI E CHEIA: ACTUALIZAM WATCHLIST-UL PE CARE IL CITESTE ANALIZA TEHNICA ---
    # Stergem ce era vechi si punem lista proaspata (fara duplicate)
    db['watchlist_trend_ascendent'] = sorted(list(set(gasite_noi)))
    salveaza_baza_date(db)
    
    bot.send_message(CHAT_ID, f"✅ Scanare finalizata! Am gasit {len(gasite_noi)} actiuni pentru analiza tehnica.")

if __name__ == "__main__":
    ruleaza_scanner_complet()
