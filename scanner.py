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
            return json.load(f)
    except:
        return {"lista_generala_long": [], "watchlist_trend_ascendent": [], "watchlist_long": [], "watchlist_retest_long": [], "signal_list_long": []}

def salveaza_baza_date(date):
    with open('baza_de_date.json', 'w') as f:
        json.dump(date, f, indent=4)

def ruleaza_scanner_complet():
    db = incarca_baza_date()
    
    # Citim lista din fisierul tau CSV
    try:
        df_screener = pd.read_csv('nasdaq_screener_1770486054910.csv')
        toate_simbolurile = df_screener['Symbol'].tolist()
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ Eroare la citirea fisierului CSV: {e}")
        return

    gasite_noi = []
    total = len(toate_simbolurile)
    bot.send_message(CHAT_ID, f"🚀 Incep scanarea gigant pentru {total} actiuni din lista ta...")

    for i, simbol in enumerate(toate_simbolurile):
        # Evitam erori de formatare in CSV
        if not isinstance(simbol, str) or '^' in simbol or '.' in simbol:
            continue

        # Regula ta de pauza (ajustata la 1 minut pentru a nu depasi limita GitHub)
        if i > 0 and i % 50 == 0:
            print(f"Scanat {i}/{total}. Pauza 60 secunde...")
            time.sleep(60) 

        try:
            # Luam datele esentiale
            t = yf.Ticker(simbol)
            info = t.fast_info # Mai rapid decat t.info
            
            pret = info.last_price
            mcap = info.market_cap / 1_000_000_000

            # FILTRELE TALE: 35-150$ si 2-50B Market Cap
            if 35 <= pret <= 150 and 2 <= mcap <= 50:
                if simbol not in db['lista_generala_long']:
                    gasite_noi.append(simbol)
                    print(f"✅ Gasit: {simbol}")
        except:
            continue

    # Salvam rezultatele
    db['lista_generala_long'] = list(set(db['lista_generala_long'] + gasite_noi))
    salveaza_baza_date(db)
    
    bot.send_message(CHAT_ID, f"✅ Scanare finalizata! Din {total} actiuni, am gasit {len(gasite_noi)} care respecta criteriile tale (35-150$, 2-50B Cap).")

if __name__ == "__main__":
    ruleaza_scanner_complet()
