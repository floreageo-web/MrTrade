import os
import yfinance as yf
import json
import time
import telebot

# Configurare Telegram
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
bot = telebot.TeleBot(TOKEN)

# Lista de start (Vom începe cu o listă extinsă de ticker-e pentru a găsi ce ceri)
TICKERS_DE_SCANAT = ["AAPL", "AMD", "MSFT", "TSLA", "PLTR", "BAC", "INTC", "F", "NIO", "PFE", "UBER", "SNAP", "SQ", "DKNG", "HOOD", "AAL", "DAL", "UAL", "XOM", "CVX", "JPM", "WFC", "V", "MA", "T", "VZ", "ORCL", "CRM", "ADBE", "ABT", "MRK", "KO", "PEP"]

def incarca_baza_date():
    with open('baza_de_date.json', 'r') as f:
        return json.load(f)

def salveaza_baza_date(date):
    with open('baza_de_date.json', 'w') as f:
        json.dump(date, f, indent=4)

def ruleaza_filtru_initial():
    db = incarca_baza_date()
    gasite_noi = []
    
    print(f"Încep scanarea pentru {len(TICKERS_DE_SCANAT)} acțiuni...")
    
    for i, simbol in enumerate(TICKERS_DE_SCANAT):
        # Regula ta: Grupuri de 50 cu pauză de 10 minute
        if i > 0 and i % 50 == 0:
            print("Pauză de 10 minute conform instrucțiunilor tale...")
            time.sleep(600) 
            
        try:
            t = yf.Ticker(simbol)
            info = t.info
            
            pret = info.get('currentPrice', 0)
            market_cap = info.get('marketCap', 0) / 1_000_000_000 # Billions
            exchange = info.get('exchange', '')

            # 1. Doar Nasdaq si NYSE
            # 2. Pret intre 35-150 dolari
            # 3. Market cap 2-50 B
            if exchange in ['NYQ', 'NMS', 'NGM'] and 35 <= pret <= 150 and 2 <= market_cap <= 50:
                if simbol not in db['lista_generala_long']:
                    gasite_noi.append(simbol)
                    print(f"Găsit: {simbol}")
        except:
            continue

    # Copiază denumirea acțiunii în listă: lista_generala_long
    db['lista_generala_long'].extend(gasite_noi)
    salveaza_baza_date(db)
    
    # Mesaj Telegram exact cum ai cerut
    bot.send_message(CHAT_ID, f"Au fost gasite un numar de {len(gasite_noi)} actiuni.")

if __name__ == "__main__":
    ruleaza_filtru_initial()
