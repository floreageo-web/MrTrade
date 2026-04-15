import logging
import argparse
import threading
import time
import os
from datetime import datetime

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
    """Rulează scanarea zilnică completă."""
    log.info("=" * 60)
    log.info(f"🚀 START SCANARE ZILNICĂ — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 60)

    try:
        from screener import run_screener
        from telegram_bot import send_daily_summary
        from config import TICKERS  # Lista ta de acțiuni

        # 1. Rulează screener-ul (ACUM TRANSMITEM TICKERS CORECT)
        signals = run_screener(TICKERS)

        # 2. Obține statistici jurnal (Opțional)
        stats = None
        try:
            from risk_manager import get_journal_stats
            stats = get_journal_stats()
        except Exception as e:
            log.warning(f"⚠️ Nu am putut încărca statisticile jurnalului: {e}")

        # 3. Trimite pe Telegram
        send_daily_summary(signals, stats)

        log.info(f"✅ Scanare zilnică finalizată — {len(signals) if signals else 0} semnale găsite.")
    except Exception as e:
        log.error(f"❌ Eroare critică în timpul scanării: {e}")

# ... (restul funcțiilor run_backtest_all, run_dashboard_only rămân neschimbate) ...

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Swing Trader Bot")
    parser.add_argument("--mode", choices=["scan", "backtest", "dashboard", "full", "test"],
                        default="scan", help="Modul de rulare")
    args = parser.parse_args()

    is_github = os.getenv('GITHUB_ACTIONS') == 'true'
    
    if is_github:
        log.info("🤖 Rulare detectată pe GitHub Actions. Forțăm modul SCAN.")
        run_daily_scan()
    else:
        if args.mode == "scan":
            run_daily_scan()
        elif args.mode == "backtest":
            # Dacă ai nevoie, implementează run_backtest_all() similar
            pass
        elif args.mode == "test":
            from telegram_bot import test_connection
            test_connection()
        # Adaugă restul modurilor dacă le folosești local
