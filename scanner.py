import os
import yfinance as yf
import json
import time
import telebot

# Configurare Telegram
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
bot = telebot.TeleBot(TOKEN)

# LISTA EXTINSA (Exemplu cu peste 100 de tickere, poti adauga oricate in acest format)
TICKERS_DE_SCANAT = [
    "AAPL", "AMD", "MSFT", "TSLA", "PLTR", "BAC", "INTC", "F", "NIO", "PFE", "UBER", "SNAP", "SQ", "DKNG", "HOOD",
    "AAL", "DAL", "UAL", "XOM", "CVX", "JPM", "WFC", "V", "MA", "T", "VZ", "ORCL", "CRM", "ADBE", "ABT", "MRK", 
    "KO", "PEP", "GM", "COIN", "PYPL", "NET", "SNOW", "PLUG", "LCID", "RIVN", "MARA", "RIOT", "LCID", "XPEV", 
    "LI", "BABA", "JD", "PDD", "BIDU", "TME", "IQ", "Z", "OPEN", "RDFN", "PTON", "ROKU", "TDOC", "ZM", "DOCU", 
    "MSTR", "COIN", "MARA", "RIOT", "CLSK", "HIVE", "CAN", "BITF", " Hut8", "WATT", "FCEL", "BE", "RUN", "SPWR", 
    "ENPH", "SEDG", "FSLR", "PLUG", "BLDP", "NKLA", "QS", "CHPT", "EVGO", "BLNK", "BEEM", "HYLN", "WKHS", "RIDE", 
    "GOEV", "FSR", "PSNY", "PTRA", "ARVL", "MULN", "CEI", "VKIN", "IMPP", "SHIP", "TOPS", "PSHG", "SBLK", "GOGL"
]

def incarca_baza_date():
    try:
        with open('baza_de_date.json', 'r') as f:
            return json.load(f)
    except:
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
    gasite_acum = 0
    
    # Trimitem un mesaj de start ca sa stii ca a inceput procesul lung
    bot.send_message(CHAT_ID, f"🚀 Am pornit scanarea completa pentru {len(TICKERS_DE_SCANAT)} actiuni...")
    
    for i, simbol in enumerate(TICKERS_DE_SCANAT):
        # Regula ta: Pauza 10 minute la fiecare 50 actiuni
        if i > 0 and i % 50 == 0:
            print(f"S-au scanat {i} actiuni. Pauza 10 minute...")
            time.sleep(600) 
            
        try:
            t = yf.Ticker(simbol)
            info = t.info
            
            pret = info.get('currentPrice', info.get('regularMarketPrice', 0))
            market_cap = info.get('marketCap', 0) / 1_000_000_000 
            exchange = info.get('exchange', '')

            # FILTRELE TALE
            if exchange in ['NYQ', 'NMS', 'NGM'] and 35 <= pret <= 150 and 2 <= market_cap <= 50:
                if simbol not in db['lista_generala_long']:
                    db['lista_generala_long'].append(simbol)
                    gasite_acum += 1
                    print(f"Gasit si adaugat: {simbol}")
        except:
            continue

    salveaza_baza_date(db)
    
    # Mesaj final
    bot.send_message(CHAT_ID, f"✅ Scanare finalizata. Au fost gasite un numar de {gasite_acum} actiuni noi.")

if __name__ == "__main__":
    ruleaza_filtru_initial()
