import logging
import argparse
import os
import warnings
from datetime import datetime

# 1. Blocăm avertismentele pentru un log curat
warnings.simplefilter(action='ignore', category=FutureWarning)

# Configurare Logging (Scrie și în fișier și pe ecran)
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
    """Rulează procesul complet: Scanare semnale + Backtesting + Telegram."""
    log.info("=" * 60)
    log.info(f"🚀 START PROCES COMPLET — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 60)

    try:
        # Importuri din modulele noastre
        from screener import run_screener
        # Importăm ALL_SYMBOLS din db_manager pentru a fi siguri că scanăm tot ce am descărcat
        from db_manager import ALL_SYMBOLS 
        
        # Importuri opționale (dacă fișierele există deja)
        try:
            from telegram_bot import send_daily_summary, send_backtest_report, send_message
        except ImportError:
            log.warning("⚠️ telegram_bot.py nu a fost găsit. Rezultatele vor fi doar afișate aici.")
            send_daily_summary = lambda s, st: print(f"Semnale: {s}")
            send_message = lambda m: print(m)

        # --- PASUL 1: SCANARE PENTRU SEMNALE AZI ---
        # Folosim datele locale din folderul /data
        signals = run_screener(ALL_SYMBOLS)

        # --- PASUL 2: BACKTESTING (Opțional) ---
        backtest_results = None
        try:
            from backtester import backtest_all
            backtest_results = backtest_all(ALL_SYMBOLS)
        except ImportError:
            log.info("ℹ️ Modulul backtester.py lipsește. Sărim peste backtest.")

        # --- PASUL 3: STATISTICI JURNAL ---
        stats = None
        try:
            from risk_manager import get_journal_stats
            stats = get_journal_stats()
        except Exception:
            log.warning("⚠️ Nu s-au putut încărca statisticile jurnalului (risk_manager.py lipsește).")

        # --- PASUL 4: TRIMITERE TELEGRAM ---
        if signals:
            log.info(f"✅ S-au găsit {len(signals)} semnale. Trimitem pe Telegram...")
            send_daily_summary(signals, stats)
        else:
            log.info("ℹ️ Nu sunt semnale azi. Trimitem notificare de status.")
            send_message("☕ Scanare finalizată: Niciun semnal Pullback confirmat azi.")
        
        # Raport Backtest
        if backtest_results:
            send_backtest_report(backtest_results)

        log.info(f"✅ Proces finalizat cu succes!")

    except Exception as e:
        log.error(f"❌ Eroare critică în main.py: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Swing Trader Bot")
    parser.add_argument("--mode", choices=["scan", "test"], default="scan")
    args = parser.parse_args()

    # Detectăm dacă suntem pe GitHub Actions
    is_github = os.getenv('GITHUB_ACTIONS') == 'true'
    
    if is_github or args.mode == "scan":
        run_daily_scan()
    elif args.mode == "test":
        try:
            from telegram_bot import test_connection
            test_connection()
        except ImportError:
            print("❌ telegram_bot.py nu este configurat.")
