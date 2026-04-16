import pandas as pd
import logging
import time
import random
import warnings
from yahooquery import Ticker
from pathlib import Path

# 1. Ignorăm avertismentele de tip FutureWarning și altele care poluează log-ul GitHub
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore", message="A value is trying to be set on a copy of a slice from a DataFrame")

# Configurare Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def run_screener(tickers_list):
    """
    Scanează acțiunile folosind yahooquery cu protecție anti-429 și log-uri curate.
    """
    all_signals = []
    total = len(tickers_list)
    
    # Loturi de 10 acțiuni pentru a nu supraîncărca conexiunea
    batch_size = 10
    batches = [tickers_list[i:i + batch_size] for i in range(0, total, batch_size)]
    
    logger.info(f"🚀 Start Scanare: {total} acțiuni în {len(batches)} loturi.")
    logger.info("⏳ Așteptăm 10 secunde pentru inițializarea sesiunii...")
    time.sleep(10) # Pauză inițială pentru a evita blocajul la "getcrumb"

    for idx, batch in enumerate(batches):
        try:
            logger.info(f"📦 Procesare lot {idx + 1}/{len(batches)}: {batch}")
            
            # Configurare Ticker cu retry-uri mai agresive pentru erori 429
            t = Ticker(
                batch, 
                asynchronous=True, 
                formatted=False, 
                retry=5, 
                timeout=30
            )
            
            # Preluăm datele (1 an pentru a avea context de medie mobilă)
            data = t.history(period='1y', interval='1d')

            # Verificăm dacă am primit date valide
            if data is None or (isinstance(data, dict) and not data) or (isinstance(data, pd.DataFrame) and data.empty):
                logger.warning(f"⚠️ Lotul {idx + 1} nu a returnat date. Yahoo a respins cererea.")
                continue

            # YahooQuery returnează un MultiIndex (symbol, date)
            # Ne asigurăm că avem indexul 'symbol' disponibil
            try:
                available_symbols = data.index.get_level_values('symbol').unique()
            except:
                # Dacă datele vin sub alt format din cauza unei erori Yahoo
                continue

            for ticker in batch:
                if ticker not in available_symbols:
                    continue
                    
                try:
                    # Extragem datele pentru ticker-ul curent
                    ticker_data = data.loc[ticker].copy()
                    
                    if len(ticker_data) < 22:
                        continue

                    # --- LOGICA DE ANALIZĂ (Litere mici pentru yahooquery) ---
                    close_today = ticker_data['close'].iloc[-1]
                    high_yesterday = ticker_data['high'].iloc[-2]
                    
                    volume_today = ticker_data['volume'].iloc[-1]
                    avg_volume_20 = ticker_data['volume'].rolling(window=20).mean().iloc[-1]

                    # Strategia: Breakout Preț + Confirmare Volum
                    if close_today > high_yesterday and volume_today > avg_volume_20:
                        logger.info(f"✅ SEMNAL DETECTAT: {ticker}")
                        all_signals.append(ticker)
                        
                except Exception:
                    continue

        except Exception as e:
            logger.error(f"❌ Eroare la lotul {idx + 1}: {str(e)[:100]}")
        
        # Pauză random între loturi pentru a simula comportamentul uman
        pause_time = random.uniform(15, 25)
        logger.info(f"☕ Lot finalizat. Pauză {pause_time:.1f}s...")
        time.sleep(pause_time)

    logger.info(f"🎯 Scanare terminată. Semnale găsite: {len(all_signals)}")
    return all_signals

if __name__ == "__main__":
    # Test rapid pentru validare
    test_list = ["AAPL", "BBU", "TSLA"]
    results = run_screener(test_list)
    print(f"Rezultate: {results}")
