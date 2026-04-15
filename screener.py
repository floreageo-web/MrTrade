import yfinance as yf
import pandas as pd
import requests
import time
import random
import logging

logger = logging.getLogger(__name__)

def get_yahoo_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Connection': 'keep-alive'
    })
    return session

def run_screener(tickers_list):
    # Reducem lotul la doar 5 acțiuni. Mai puține date per cerere = risc mai mic.
    batch_size = 5 
    all_signals = []
    session = get_yahoo_session()
    
    batches = [tickers_list[i:i + batch_size] for i in range(0, len(tickers_list), batch_size)]
    
    logger.info(f"🐢 Mod Ultra-Safe activat. Scanăm {len(tickers_list)} acțiuni în {len(batches)} loturi.")
    logger.info("⏳ Această operațiune va dura aproximativ 15-20 minute.")

    for idx, group in enumerate(batches):
        logger.info(f"📦 Procesare lot {idx + 1}/{len(batches)}: {group}")
        
        try:
            # Descarcă datele unul câte unul (fără threading) pentru discreție maximă
            data = yf.download(
                tickers=group,
                period="1y",
                interval="1d",
                group_by='ticker',
                progress=False,
                threads=False, 
                auto_adjust=True,
                session=session
            )
            
            if not data.empty:
                for ticker in group:
                    try:
                        # Verificăm dacă ticker-ul există în rezultate
                        ticker_data = None
                        if len(group) > 1:
                            if ticker in data.columns.get_level_values(0):
                                ticker_data = data[ticker].dropna()
                        else:
                            ticker_data = data.dropna()

                        if ticker_data is not None and len(ticker_data) > 20:
                            # --- LOGICA TA DE ANALIZĂ ---
                            # Exemplu: Breakout peste maximul de ieri
                            if ticker_data['Close'].iloc[-1] > ticker_data['High'].iloc[-2]:
                                all_signals.append(ticker)
                            # ----------------------------
                    except Exception as e:
                        continue

        except Exception as e:
            logger.error(f"❌ Eroare la lotul {idx + 1}: {e}")
        
        # --- PAUZĂ LUNGĂ ȘI RANDOM ---
        # Între 15 și 30 de secunde după FIECARE lot de 5 acțiuni
        pauza = random.uniform(15, 30)
        logger.info(f"☕ Pauză tactică: {pauza:.1f} secunde...")
        time.sleep(pauza)

    return all_signals
