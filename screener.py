import yfinance as yf
import pandas as pd
import requests
import time
import random
import logging
from pathlib import Path

# Configurare logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
# CONFIG
# =========================
MAX_RETRIES = 2 # Redus, pentru că dacă e block, e block
CACHE_FOLDER = "cache"
Path(CACHE_FOLDER).mkdir(exist_ok=True)

# =========================
# SESSION (Simulăm un browser real de Mac)
# =========================
def get_yahoo_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive"
    })
    return session

# =========================
# ANALIZĂ STRATEGIE (Breakout + Volum)
# =========================
def analyze_ticker(ticker, ticker_data):
    if len(ticker_data) < 30:
        return False
    try:
        # Pret inchidere azi vs Maxim ieri
        close_today = ticker_data["Close"].iloc[-1]
        high_yesterday = ticker_data["High"].iloc[-2]

        # Volum azi vs Media ultimelor 20 zile
        volume_today = ticker_data["Volume"].iloc[-1]
        avg_volume = ticker_data["Volume"].rolling(20).mean().iloc[-1]

        # Conditie: Breakout pe pret SI Volum peste medie
        if close_today > high_yesterday and volume_today > avg_volume:
            return True
    except:
        return False
    return False

# =========================
# MAIN SCREENER
# =========================
def run_screener(tickers_list):
    all_signals = []
    session = get_yahoo_session()
    total = len(tickers_list)

    logger.info(f"🚀 Start Scanare: {total} acțiuni (Mod Ticker-by-Ticker)")

    for idx, ticker in enumerate(tickers_list):
        ticker_data = None
        success = False
        
        # Încercăm să descărcăm datele pentru ticker-ul curent
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Folosim Ticker individual pentru discretie maxima
                t = yf.Ticker(ticker, session=session)
                ticker_data = t.history(period="1y", interval="1d")
                
                if not ticker_data.empty:
                    success = True
                    break
            except Exception as e:
                if attempt == MAX_RETRIES:
                    logger.warning(f"❌ Eșuat definitiv {ticker} după {attempt} încercări")
                else:
                    time.sleep(random.uniform(10, 20)) # Pauză lungă la eroare

        if success and ticker_data is not None:
            # Analizăm strategia
            if analyze_ticker(ticker, ticker_data):
                logger.info(f"✅ Semnal găsit: {ticker} ({idx+1}/{total})")
                all_signals.append(ticker)
            
            # Salvăm în cache (opțional)
            ticker_data.to_csv(Path(CACHE_FOLDER) / f"{ticker}.csv")
        
        # --- PAUZĂ CRITICĂ ---
        # Între 4 și 8 secunde după FIECARE acțiune
        # Asta va face ca scanarea să dureze ~40 min, exact cum ai zis că e ok.
        time.sleep(random.uniform(4, 8))
        
        if (idx + 1) % 10 == 0:
            logger.info(f"☕ Progres: {idx + 1}/{total} verificat...")

    logger.info(f"🎯 Finalizat. Semnale găsite: {all_signals}")
    return all_signals
