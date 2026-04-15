# ============================================================
# main.py — Orchestrator principal (Optimizat GitHub Actions)
# ============================================================

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
        
        # 1. Rulează screener-ul
        signals = run_screener()

        # 2. Obține statistici jurnal (Opțional - tratăm eroarea dacă fișierul nu există)
        stats = None
        try:
            from risk_manager import get_journal_stats
            stats = get_journal_stats()
        except Exception as e:
            log.warning(f"⚠️ Nu am putut încărca statisticile jurnalului: {e}")

        # 3. Trimite pe Telegram
        send_daily_summary(signals, stats)

        log.info(f"✅ Scanare zilnică finalizată — {len(signals)} semnale procesate.")
    except Exception as e:
        log.error(f"❌ Eroare critică în timpul scanării: {e}")


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
    log.info("🌐 Dashboard pornit la http://localhost:5000")
    run_dashboard(debug=False) # debug=False e mai stabil


def run_full():
    """Modul pentru PC/Server: Dashboard + Scheduler."""
    import schedule
    from dashboard import run_dashboard

    # Pornește dashboard-ul în thread separat
    dash_thread = threading.Thread(target=run_dashboard, kwargs={'debug': False}, daemon=True)
    dash_thread.start()
    log.info("🌐 Dashboard activ în fundal...")

    # Planifică scanările (Ora este în funcție de serverul unde rulează)
    # Dacă e pe GitHub, ignorăm asta și folosim workflow-ul .yml
    schedule.every().monday.at("23:30").do(run_daily_scan) # Aproximativ ora închiderii bursei în RO
    schedule.every().tuesday.at("23:30").do(run_daily_scan)
    schedule.every().wednesday.at("23:30").do(run_daily_scan)
    schedule.every().thursday.at("23:30").do(run_daily_scan)
    schedule.every().friday.at("23:30").do(run_daily_scan)

    log.info("⏰ Scheduler activ pentru mod local.")

    while True:
        schedule.run_pending()
        time.sleep(60)


# ─── CLI / START ──────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Swing Trader Bot")
    parser.add_argument("--mode", choices=["scan", "backtest", "dashboard", "full", "test"],
                        default="scan", help="Modul de rulare") # Schimbat default pe 'scan'
    args = parser.parse_args()

    # Detectăm dacă suntem pe GitHub Actions
    is_github = os.getenv('GITHUB_ACTIONS') == 'true'
    
    if is_github:
        log.info("🤖 Rulare detectată pe GitHub Actions. Forțăm modul SCAN.")
        run_daily_scan()
    else:
        if args.mode == "scan":
            run_daily_scan()
        elif args.mode == "backtest":
            run_backtest_all()
        elif args.mode == "dashboard":
            run_dashboard_only()
        elif args.mode == "test":
            from telegram_bot import test_connection
            test_connection()
        elif args.mode == "full":
            run_full()
