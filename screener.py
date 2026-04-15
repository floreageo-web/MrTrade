import pandas as pd
import logging
import time
import random
from yahooquery import Ticker
from pathlib import Path

# Configurare Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def run_screener(tickers_list):
    """
    Scanează lista de acțiuni folosind yahooquery.
    Grupăm acțiunile în loturi mici pentru a evita blocarea IP-ului de către Yahoo.
    """
    all_signals = []
    total = len(tickers_list)
    
    # Loturi de 10 acțiuni - siguranță maximă pe GitHub Actions
    batch_size = 10
    batches = [tickers_list[i:i + batch_size] for i in range(0, total, batch_size)]
    
    logger.info(f"🚀 Start Scanare: {total} acțiuni în {len(batches)} loturi.")

    for idx, batch in enumerate(batches):
        try:
            logger.info(f"📦 Procesare lot {idx + 1}/{len(batches)}: {batch}")
            
            # Inițializăm Ticker
            # asynchronous=True trimite cererile în paralel în interiorul lotului
            t = Ticker(batch, asynchronous=True, formatted=False, retry=3, status_forcelist=[429, 500, 502, 503, 504])
            
            # Preluăm datele istorice (avem nevoie de minim 21 de zile pentru media de volum)
            data = t.history(period='1y', interval='1d')

            if data is None or (isinstance(data, dict) and not data) or data.empty:
                logger.warning(f"⚠️ Lotul {idx + 1} nu a returnat date valide.")
                continue

            # Procesăm fiecare ticker din rezultatul lotului
            # YahooQuery returnează un MultiIndex (symbol, date)
            symbols_returned = data.index.get_level_values('symbol').unique()

            for ticker in batch:
                if ticker not in symbols_returned:
                    continue
                    
                try:
                    ticker_data = data.loc[ticker].copy()
                    
                    if len(ticker_data) < 22:
                        continue

                    # --- LOGICA DE ANALIZĂ ---
                    # Notă: YahooQuery returnează coloanele cu litere mici
                    close_today = ticker_data['close'].iloc[-1]
                    high_yesterday = ticker_data['high'].iloc[-2]
                    
                    volume_today = ticker_data['volume'].iloc[-1]
                    avg_volume_20 = ticker_data['volume'].rolling(window=20).mean().iloc[-1]

                    # Strategia: 
                    # 1. Preț închidere azi este peste maximul de ieri
                    # 2. Volumul de azi este peste media ultimelor 20 de zile
                    if close_today > high_yesterday and volume_today > avg_volume_20:
                        logger.info(f"✅ SEMNAL DETECTAT: {ticker} (Preț: {close_today:.2f}, Volum: {int(volume_today)})")
                        all_signals.append(ticker)
                        
                except Exception as e:
                    logger.debug(f"Eroare la analiza individuală pentru {ticker}: {e}")
                    continue

        except Exception as e:
            logger.error(f"❌ Eroare critică la lotul {idx + 1}: {e}")
        
        # Pauză între loturi (obligatorie pentru GitHub Actions)
        # O pauză mai lungă scade riscul de a fi detectat ca bot
        pause_time = random.uniform(12, 22)
        logger.info(f"☕ Pauză tactică: {pause_time:.1f} secunde...")
        time.sleep(pause_time)

    logger.info(f"🎯 Scanare finalizată. Total semnale găsite: {len(all_signals)}")
    return all_signals

# Bloc de testare locală
if __name__ == "__main__":
    test_list = ["AAPL", "TSLA", "NVDA", "AMD", "MSFT"]
    results = run_screener(test_list)
    print(f"Rezultate test: {results}")
