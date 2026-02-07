import os
import yfinance as yf
import json
import time
import telebot

# Configurare Telegram
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
bot = telebot.TeleBot(TOKEN)

# Lista de test extinsa pentru a asigura rezultate la prima rulare
TICKERS_DE_SCANAT = ["AAPL", "AMD", "MSFT", "TSLA", "PLTR", "BAC", "INTC", "F", "NIO", "PFE", "UBER", "SNAP", "SQ", "DKNG", "HOOD", "AAL", "DAL", "UAL", "XOM", "CVX", "JPM", "WFC", "V", "MA", "T", "VZ", "ORCL", "CRM", "ADBE", "ABT", "MRK", "KO", "PEP", "GM", "COIN", "PYPL", "NET", "SNOW", "PLUG", "LCID", "RIVN", "MARA", "RIOT"]

def incarca_baza_date():
    try:
        with open('baza_de_date.json', 'r') as f:
            return json.load(f)
    except:
        # Daca fisierul nu exista, il cream cu structura ceruta de tine
        return {
            "lista_generala_long": [],
            "watchlist_trend_ascendent": [],
            "watchlist_long": [],
            "watchlist_retest_long": [],
            "signal_list_long": []
        }

def salveaza_baza_date(date):
    with open('baza_de_date.json', 'w') as f:
        json.dump(date, f, indent=4)

def ruleaza_filtru_initial():
    db = incarca_baza_date()
    gasite_noi = []
    
    print(f"Incep scanarea pentru {len(TICKERS_DE_SCANAT)} actiuni...")
    
    for i, simbol in enumerate(TICKERS_DE_SCANAT):
        # Regula ta: Analiza in grupuri de 50 cu distanta de 10 minute
        if i > 0 and i % 50 == 0:
            print("Pauza 10 minute conform instructiunilor...")
            time.sleep(600) 
            
        try:
            t = yf.Ticker(simbol)
            info = t.info
            
            # Preluam datele pentru filtrele tale
            pret = info.get('currentPrice', info.get('regularMarketPrice', 0))
            market_cap = info.get('marketCap', 0) / 1_000_000_000 # Convertit in Billions
            exchange = info.get('exchange', '')

            # CRITERIILE TALE:
            # 1. Doar Piata Nasdaq si NYSE
            # 2. Pret intre 35-150 dolari
            # 3. Market cap 2-50 B
            if exchange in ['NYQ', 'NMS', 'NGM'] and 35 <= pret <= 150 and 2 <= market_cap <= 50:
                if simbol not in db['lista_generala_long']:
                    gasite_noi.append(simbol)
                    print(f"Gasit: {simbol}")
        except Exception as e:
            print(f"Eroare la {simbol}: {e}")
            continue

    # Cand termini vei copia doar denumirea aciunii in lista: lista_generala_long
    db['lista_generala_long'] = list(set(db['lista_generala_long'] + gasite_noi))
    salveaza_baza_date(db)
    
    # Mesaj Telegram exact cum ai cerut: "Au fost gasite un numar de x actiuni."
    bot.send_message(CHAT_ID, f"Au fost gasite un numar de {len(gasite_noi)} actiuni.")

if __name__ == "__main__":
    ruleaza_filtru_initial()
