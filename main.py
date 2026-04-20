# ============================================================
# main.py — Orchestrator principal (BACKTEST LOCAL SAU FULL)
# ============================================================

import logging
import argparse
import os
import yfinance as yf
import time
from datetime import datetime
from config import TICKERS 

# Configurare Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("swing_trader.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

def update_data_bulk():
    """Descarcă datele în loturi mici pentru a evita block-ul Yahoo."""
    log.info(f"📥 Actualizare bază de date locală ({len(TICKERS)} acțiuni)...")
    if not os.path.exists('data'):
        os.makedirs('data')

    # Folosim loturi de 20 pentru a fi mai "discreți"
    batch_size = 20
    count = 0
    
    for i in range(0, len(TICKERS), batch_size):
        batch = TICKERS[i:i+batch_size]
        try:
            # threads=False este mai sigur împotriva ban-ului pe IP
            data = yf.download(batch, period="2y", interval="1d", group_by='ticker', threads=False, progress=False)
            
            for ticker in batch:
                try:
                    df = data[ticker].dropna(how='all')
                    if not df.empty:
                        df.to_csv(f'data/{ticker}.csv')
                        count += 1
                except:
                    continue
            
            log.info(f"✅ Lotul {i//batch_size + 1} procesat. Pauză de siguranță...")
            time.sleep(5) # Pauză de 5 secunde între loturi
        except Exception as e:
            log.error(f"❌ Eroare la lotul {i}: {e}")
            continue

    log.info(f"🚀 Sincronizare terminată: {count} fișiere în /data.")

def run_full_cycle(skip_download=False):
    """Execută Backtest-ul complet, apoi Screener-ul zilnic."""
    log.info("=" * 60)
    log.info(f"🚀 PORNIRE CICLU — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 60)

    # 1. ACTUALIZARE DATE (Doar dacă nu sărim peste)
    if not skip_download:
        update_data_bulk()
    else:
        log.info("⏭️ Skip Download: Folosim datele existente în folderul /data.")

    # 2. ETAPA DE BACKTESTING
    log.info("📊 ETAPA 1: Analiză istorică (Backtesting)...")
    try:
        from backtester import backtest_all, format_backtest_summary
        from telegram_bot import send_telegram_message
        
        backtest_summary = backtest_all(TICKERS)
        if backtest_summary:
            report_text = format_backtest_summary(backtest_summary)
            send_telegram_message(report_text) 
            log.info("✅ Raport Backtest trimis pe Telegram.")
    except Exception as e:
        log.error(f"❌ Eroare la backtesting: {e}")

    # 3. ETAPA DE SCANARE ZILNICĂ
    log.info("🔍 ETAPA 2: Căutare semnale...")
    try:
        from screener import run_screener
        from telegram_bot import send_daily_summary
        signals = run_screener(TICKERS)
        send_daily_summary(signals)
        log.info(f"✅ Misiune finalizată. {len(signals)} semnale găsite.")
    except Exception as e:
        log.error(f"❌ Eroare la scanare: {e}")

# ─── CLI / START ──────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Swing Trader Bot")
    parser.add_argument("--mode", choices=["scan", "backtest", "full", "test"], default="full")
    parser.add_argument("--skip-download", action="store_true", help="Rulează fără să descarce date noi")
    args = parser.parse_args()

    # Dacă rulăm modul backtest, sărim implicit peste download pentru a folosi ce avem deja
    if args.mode == "backtest":
        log.info("⚙️ Mod BACKTEST selectat. Se folosesc datele locale.")
        from backtester import backtest_all, format_backtest_summary
        summary = backtest_all(TICKERS)
        if summary: 
            print(format_backtest_summary(summary))

    elif args.mode == "full":
        # Dacă vrei să rulezi tot dar FĂRĂ download, pui flag-ul --skip-download
        run_full_cycle(skip_download=args.skip_download)

    elif args.mode == "scan":
        if not args.skip_download:
            update_data_bulk()
        from screener import run_screener
        run_screener(TICKERS)

    elif args.mode == "test":
        from telegram_bot import test_connection
        test_connection()
