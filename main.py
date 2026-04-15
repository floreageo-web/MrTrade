# ============================================================
# main.py — Orchestrator principal
# Rulează zilnic după închiderea bursei (ex: 17:00 ET)
# ============================================================

import logging
import argparse
import threading
from datetime import datetime

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

    from screener import run_screener
    from telegram_bot import send_daily_summary
    from risk_manager import get_journal_stats

    # 1. Rulează screener-ul
    signals = run_screener()

    # 2. Obține statistici jurnal
    stats = get_journal_stats()

    # 3. Trimite pe Telegram
    send_daily_summary(signals, stats)

    log.info(f"✅ Scanare zilnică finalizată — {len(signals)} semnale trimise pe Telegram")


def run_backtest_all():
    """Rulează backtesting complet și trimite raport pe Telegram."""
    log.info("🔄 Start backtesting complet...")
    from backtester import backtest_all
    from telegram_bot import send_backtest_report
    from config import TICKERS

    summary = backtest_all(TICKERS)
    send_backtest_report(summary)
    log.info("✅ Backtesting complet finalizat!")
    return summary


def run_dashboard_only():
    """Pornește doar dashboard-ul web."""
    from dashboard import run_dashboard
    run_dashboard(debug=True)


def run_full():
    """Pornește dashboard-ul + planificatorul zilnic."""
    import schedule
    import time
    from dashboard import run_dashboard

    # Pornește dashboard-ul în thread separat
    dash_thread = threading.Thread(target=run_dashboard, daemon=True)
    dash_thread.start()
    log.info("🌐 Dashboard pornit la http://localhost:5000")

    # Planifică scanarea zilnică la 17:30 ET (după închidere bursă)
    schedule.every().monday.at("17:30").do(run_daily_scan)
    schedule.every().tuesday.at("17:30").do(run_daily_scan)
    schedule.every().wednesday.at("17:30").do(run_daily_scan)
    schedule.every().thursday.at("17:30").do(run_daily_scan)
    schedule.every().friday.at("17:30").do(run_daily_scan)

    # Backtesting complet în fiecare duminică
    schedule.every().sunday.at("10:00").do(run_backtest_all)

    log.info("⏰ Scheduler activ — scanare zilnică la 17:30 (Luni-Vineri)")
    log.info("📊 Backtesting complet în fiecare Duminică la 10:00")

    while True:
        schedule.run_pending()
        time.sleep(60)


# ─── CLI ───────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Swing Trader Bot")
    parser.add_argument("--mode", choices=["scan", "backtest", "dashboard", "full", "test"],
                        default="full", help="Modul de rulare")
    args = parser.parse_args()

    if args.mode == "scan":
        # python main.py --mode scan
        run_daily_scan()

    elif args.mode == "backtest":
        # python main.py --mode backtest
        run_backtest_all()

    elif args.mode == "dashboard":
        # python main.py --mode dashboard
        run_dashboard_only()

    elif args.mode == "test":
        # python main.py --mode test  (testează conexiunea Telegram)
        from telegram_bot import test_connection
        test_connection()

    elif args.mode == "full":
        # python main.py  (mod implicit — dashboard + scheduler)
        run_full()
