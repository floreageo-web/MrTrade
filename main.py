# ============================================================
# main.py — Orchestrator principal (CICLU COMPLET: BACKTEST + SCAN)
# ============================================================

import logging
import argparse
import os
import yfinance as yf
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
    """Descarcă datele masiv pentru a evita block-ul Yahoo."""
    log.info(f"📥 Actualizare bază de date locală ({len(TICKERS)} acțiuni)...")
    if not os.path.exists('data'):
        os.makedirs('data')

    try:
        # Descărcăm 2 ani pentru a avea date suficiente pentru EMA200 în Backtest
        data = yf.download(TICKERS, period="2y", interval="1d", group_by='ticker', threads=True)
        
        count = 0
        for ticker in TICKERS:
            try:
                df = data[ticker].dropna(how='all')
                if not df.empty:
                    df.to_csv(f'data/{ticker}.csv')
                    count += 1
            except Exception:
                continue
        log.info(f"✅ Date pregătite: {count} fișiere în /data.")
    except Exception as e:
        log.error(f"❌ Eroare critică la descărcare: {e}")

def run_full_cycle():
    """Execută Backtest-ul complet, apoi Screener-ul zilnic."""
    log.info("=" * 60)
    log.info(f"🚀 PORNIRE CICLU COMPLET — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 60)

    # 1. ACTUALIZARE DATE
    update_data_bulk()

    # 2. ETAPA DE BACKTESTING (Trecutul)
    log.info("📊 ETAPA 1: Analiză istorică (Backtesting)...")
    backtest_summary = None
    try:
        from backtester import backtest_all, format_backtest_summary
        from telegram_bot import send_telegram_message # Asigură-te că ai această funcție
        
        backtest_summary = backtest_all(TICKERS)
        
        if backtest_summary:
            report_text = format_backtest_summary(backtest_summary)
            # Trimitem raportul de winrate pe Telegram înainte de semnale
            send_telegram_message(report_text) 
            log.info("✅ Raport Backtest trimis pe Telegram.")
    except Exception as e:
        log.error(f"❌ Eroare la backtesting: {e}")

    # 3. ETAPA DE SCANARE ZILNICĂ (Prezentul)
    log.info("🔍 ETAPA 2: Căutare semnale pentru azi...")
    try:
        from screener import run_screener
        from telegram_bot import send_daily_summary
        
        # Rulăm screener-ul pe datele proaspete din /data
        signals = run_screener(TICKERS)

        # Trimitem semnalele pe Telegram
        # Dacă vrei, poți include backtest_summary în send_daily_summary dacă funcția suportă
        send_daily_summary(signals)
        
        log.info(f"✅ Misiune finalizată. {len(signals)} semnale găsite.")
    except Exception as e:
        log.error(f"❌ Eroare la scanarea zilnică: {e}")

# ─── CLI / START ──────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Swing Trader Bot")
    parser.add_argument("--mode", choices=["scan", "backtest", "full", "test"], default="full")
    args = parser.parse_args()

    # Identificăm dacă rulăm pe GitHub Actions
    is_github = os.getenv('GITHUB_ACTIONS') == 'true'
    
    # Dacă e pe GitHub sau modul e "full", executăm tot ciclul
    if is_github or args.mode == "full":
        run_full_cycle()
    elif args.mode == "backtest":
        update_data_bulk()
        from backtester import backtest_all, format_backtest_summary
        summary = backtest_all(TICKERS)
        if summary: print(format_backtest_summary(summary))
    elif args.mode == "scan":
        update_data_bulk()
        from screener import run_screener
        run_screener(TICKERS)
    elif args.mode == "test":
        from telegram_bot import test_connection
        test_connection()
