import os
import pandas as pd
import json
import yfinance as yf
import telebot
import time

# Configurare
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
bot = telebot.TeleBot(TOKEN)

def ruleaza_reset_total():
    # 1. Citim sursa sigura (CSV-ul tau)
    try:
        df = pd.read_csv('nasdaq_screener_1770486054910.csv')
        toate_simbolurile = df['Symbol'].dropna().tolist()
        bot.send_message(CHAT_ID, f"♻️ Reset Total: Incep scanarea de la zero pentru {len(toate_simbolurile)} actiuni...")
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ Eroare la citirea CSV-ului: {e}")
        return

    lista_reparata = []
    
    # 2. Scanarea (Filtrele tale: 35-150$ si 2-50B Cap)
    for i, simbol in enumerate(toate_simbolurile):
        # Curatam simbolul de caractere speciale
        if not isinstance(simbol, str) or any(c in simbol for c in ['^', '.', '$']):
            continue

        try:
            t = yf.Ticker(simbol)
            info = t.fast_info
            pret = info.last_price
            mcap = info.market_cap / 1_000_000_000

            if 35 <= pret <= 150 and 2 <= mcap <= 50:
                lista_reparata.append(simbol)
                print(f"✅ Gasit si salvat: {simbol}")
        except:
            continue
        
        # O mica pauza la fiecare 100 ca sa nu ne taie Yahoo macaroana
        if i % 100 == 0:
            time.sleep(2)

    # 3. SALVAREA FINALA (FARA STR, FARA PUNCTE-PUNCTE)
    baza_noua = {
        "watchlist_trend_ascendent": sorted(list(set(lista_reparata))),
        "watchlist_long": []
    }

    with open('baza_de_date.json', 'w') as f:
        # indent=4 e cel care asigura ca fiecare ticker e scris clar pe randul lui
        json.dump(baza_noua, f, indent=4)

    bot.send_message(CHAT_ID, f"🏁 RESET COMPLET!\n\nAcum ai {len(lista_reparata)} actiuni REALE in baza de date.\nPoti rula Analiza Tehnica.")

if __name__ == "__main__":
    ruleaza_reset_total()
