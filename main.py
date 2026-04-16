import logging
import argparse
import os
import warnings
from datetime import datetime

# 1. Blocăm avertismentele de tip FutureWarning global pentru log curat
warnings.simplefilter(action='ignore', category=FutureWarning)

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

def run_daily_scan():
    """Rulează procesul complet: Scanare semnale + Backtesting strategie."""
    log.info("=" * 60)
    log.info(f"🚀 START PROCES COMPLET — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 60)

    try:
        # Importuri din fișierele tale
        from screener import run_screener
        from backtester import backtest_all
        from telegram_bot import send_daily_summary, send_backtest_report, send_message
        from config import TICKERS

        # --- PASUL 1: SCANARE PENTRU SEMNALE AZI ---
        # Folosește yahooquery (codul nou)
        signals = run_screener(TICKERS)

        # --- PASUL 2: BACKTESTING (Performanța pe 12 luni) ---
        # Rulează calculele istorice
        backtest_results = backtest_all(TICKERS)

        # --- PASUL 3: STATISTICI JURNAL ---
        stats = None
        try:
            from risk_manager import get_journal_stats
            stats = get_journal_stats()
        except Exception as e:
            log.warning(f"⚠️ Nu s-au putut încărca statisticile jurnalului: {e}")

        # --- PASUL 4: TRIMITERE TELEGRAM ---
        # Trimite semnalele și stats jurnal (funcția ta existentă)
        send_daily_summary(signals, stats)
        
        # Trimite raportul de backtesting (folosind funcția ta din telegram_bot.py)
        if backtest_results and "error" not in backtest_results:
            send_backtest_report(backtest_results)
        else:
            send_message("⚠️ Raportul de backtest nu a putut fi generat (date insuficiente).")

        log.info(f"✅ Proces finalizat cu succes!")

    except Exception as e:
        log.error(f"❌ Eroare critică în main.py: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Swing Trader Bot")
    parser.add_argument("--mode", choices=["scan", "backtest", "test"],
                        default="scan", help="Modul de rulare")
    args = parser.parse_args()

    is_github = os.getenv('GITHUB_ACTIONS') == 'true'
    
    if is_github:
        log.info("🤖 Rulare detectată pe GitHub Actions. Forțăm SCAN + BACKTEST.")
        run_daily_scan()
    else:
        if args.mode == "scan":
            run_daily_scan()
        elif args.mode == "test":
            from telegram_bot import test_connection
            test_connection()
