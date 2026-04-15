# ============================================================
# telegram_bot.py — Trimitere semnale și rapoarte pe Telegram
# ============================================================

import requests
import logging
import time
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

log = logging.getLogger(__name__)
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def send_message(text: str, chat_id: str = TELEGRAM_CHAT_ID,
                 parse_mode: str = "Markdown") -> bool:
    """Trimite un mesaj text pe Telegram."""
    url     = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        log.error(f"Eroare Telegram sendMessage: {e}")
        return False


def send_signals(signals: list) -> None:
    """Trimite toate semnalele găsite pe Telegram."""
    from screener import format_signal_message

    if not signals:
        send_message("🔍 *Screener zilnic finalizat*\n\nNu au fost găsite semnale de intrare astăzi.")
        return

    # Header
    send_message(
        f"🚀 *SCREENER ZILNIC — {len(signals)} SEMNALE GĂSITE*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Strategia: EMA21 + RSI(40-55) + Lumânare confirmare\n"
        f"⚡ Sortate după scor (cel mai bun primul)"
    )
    time.sleep(0.5)

    # Fiecare semnal separat
    for i, signal in enumerate(signals, 1):
        msg = f"*{i}/{len(signals)}*\n" + format_signal_message(signal)
        success = send_message(msg)
        if not success:
            log.warning(f"Nu s-a putut trimite semnalul pentru {signal['ticker']}")
        time.sleep(0.3)  # Anti-rate-limit Telegram


def send_backtest_report(summary: dict) -> None:
    """Trimite raportul de backtesting pe Telegram."""
    from backtester import format_backtest_summary
    msg = format_backtest_summary(summary)
    send_message(msg)


def send_journal_stats(stats: dict) -> None:
    """Trimite statisticile jurnalului pe Telegram."""
    from risk_manager import format_stats_message
    msg = format_stats_message(stats)
    send_message(msg)


def send_daily_summary(signals: list, stats: dict) -> None:
    """Trimite sumar zilnic complet."""
    send_signals(signals)
    time.sleep(1)
    send_message("━━━━━━━━━━━━━━━━━━━━\n📊 *STATISTICI JURNAL PERSONAL*")
    send_journal_stats(stats)


def test_connection() -> bool:
    """Testează conexiunea la Telegram."""
    url = f"{BASE_URL}/getMe"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get("ok"):
            bot_name = data["result"]["username"]
            log.info(f"✅ Telegram conectat: @{bot_name}")
            send_message(f"✅ *Bot activ!* @{bot_name} este conectat și funcțional.")
            return True
    except Exception as e:
        log.error(f"Eroare conexiune Telegram: {e}")
    return False
