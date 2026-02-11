import os
import pandas as pd
import json
import yfinance as yf
import telebot

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
bot = telebot.TeleBot(TOKEN)

def ruleaza_scanner_final():
    # 1. Citim CSV-ul
    try:
        df_screener = pd.read_csv('nasdaq_screener_1770486054910.csv')
        simboluri_de_verificat = df_screener['Symbol'].dropna().tolist()
        bot.send_message(CHAT_ID, f"🚀 Start recuperare! Verific {len(simboluri_de_verificat)} actiuni...")
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ Eroare citire CSV: {e}")
        return

    gasite_noi = []
    
    # 2. Scanarea rapida
    for i, simbol in enumerate(simboluri_de_verificat):
        if not isinstance(simbol, str) or any(c in simbol for c in ['^', '.', '$']):
            continue

        try:
            t = yf.Ticker(simbol)
            # .fast_info e mult mai rapid, nu consuma timp
            info = t.fast_info
            p = info.last_price
            mcap = info.market_cap / 1_000_000_000

            # FILTRELE TALE: 35-150$ si 2-50B Cap
            if 35 <= p <= 150 and 2 <= mcap <= 50:
                gasite_noi.append(simbol)
                print(f"Adaugat: {simbol}")
        except:
            continue

    # 3. SALVAREA - Aici e toata magia
    # Citim ce mai era in baza de date ca sa nu stricam restul
    try:
        with open('baza_de_date.json', 'r') as f:
            db = json.load(f)
    except:
        db = {}

    # REPARAM WATCHLIST-UL: Inlocuim tot cu lista noua si curata
    db['watchlist_trend_ascendent'] = sorted(list(set(gasite_noi)))
    
    # Stergem cheile vechi care ar putea incurca (daca exista)
    if 'lista_generala_long' in db: del db['lista_generala_long']

    with open('baza_de_date.json', 'w') as f:
        # INDENT=4 este cel care ne scapa de puncte-puncte!
        json.dump(db, f, indent=4)

    bot.send_message(CHAT_ID, f"✅ RECUPERARE REUSITA!\n\nAm gasit {len(gasite_noi)} actiuni.\nAcum poti rula Analiza Tehnica!")

if __name__ == "__main__":
    ruleaza_scanner_final()
