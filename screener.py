import yfinance as yf
import pandas as pd
import requests
import time
import logging

# Configurare logging pentru screener
logger = logging.getLogger(__name__)

def get_yahoo_session():
    """Creează o sesiune care imită un browser real."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
    })
    return session

def run_screener(tickers_list):
    """
    Primește lista de tickers și returnează acțiunile care au breakout.
    """
    batch_size = 15
    all_signals = []
    session = get_yahoo_session()
    
    # Împărțim lista în loturi (batches)
    batches = [tickers_list[i:i + batch_size] for i in range(0, len(tickers_list), batch_size)]
    
    logger.info(f"🚀 Start scanare hibridă: {len(tickers_list)} acțiuni în {len(batches)} loturi.")

    for idx, group in enumerate(batches):
        logger.info(f"📦 Procesare lot {idx + 1}/{len(batches)}...")
        
        try:
            # Descărcare date cu sesiunea de browser
            data = yf.download(
                tickers=group,
                period="1y",
                interval="1d",
                group_by='ticker',
                progress=False,
                threads=True,
                auto_adjust=True,
                session=session
            )
            
            if data.empty:
                continue

            for ticker in group:
                try:
                    # Verificăm dacă avem date pentru ticker-ul respectiv
                    if ticker not in data.columns.get_level_values(0):
                        continue
                    
                    df = data[ticker].dropna()
                    if df.empty or len(df) < 20:
                        continue
                    
                    # --- LOGICA TA DE ANALIZĂ (EXEMPLU) ---
                    # Aici pui condițiile tale (RSI, MACD, etc.)
                    # Daca e semnal: all_signals.append(ticker)
                    # --------------------------------------
                    
                except Exception as ticker_err:
                    continue

        except Exception as batch_err:
            logger.error(f"❌ Eroare la lotul {idx + 1}: {batch_err}")
        
        # Pauză mică între loturi ca să fim "politicoși" cu Yahoo
        time.sleep(2)

    return all_signals
