import yfinance as yf
import pandas as pd
import requests
import time
import logging

# Configurare logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def get_yahoo_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    })
    return session

def run_screener(tickers_list):
    batch_size = 15
    all_results = []
    session = get_yahoo_session()
    
    batches = [tickers_list[i:i + batch_size] for i in range(0, len(tickers_list), batch_size)]
    
    for idx, group in enumerate(batches):
        logger.info(f"📦 Procesare lot {idx + 1}/{len(batches)}: {group}")
        
        try:
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
                # Verificăm dacă avem date pentru ticker-ul curent în lot
                if ticker not in data.columns.get_level_values(0):
                    continue
                
                df = data[ticker].dropna()
                if df.empty:
                    continue
                
                # --- AICI ADAUGI LOGICA TA DE ANALIZĂ ---
                # Exemplu rapid:
                # last_close = df['Close'].iloc[-1]
                # if conditie_breakout(df):
                #     all_results.append(ticker)
                # ----------------------------------------

        except Exception as e:
            logger.error(f"❌ Eroare la lotul {idx + 1}: {e}")
        
        time.sleep(2) # Pauză necesară între loturi

    return all_results
