# ============================================================
# risk_manager.py — Management risc + Jurnal tranzacții
# ============================================================

import json
import os
import logging
from datetime import datetime
from config import CAPITAL, RISK_PER_TRADE, RR_TP1, RR_TP2

log = logging.getLogger(__name__)
JOURNAL_FILE = "trade_journal.json"


def calc_position(entry: float, sl: float, capital: float = CAPITAL,
                  risk_pct: float = RISK_PER_TRADE) -> dict:
    """Calculează dimensiunea poziției și nivelurile de ieșire."""
    risk_per_share = entry - sl
    if risk_per_share <= 0:
        return {"error": "Stop loss trebuie să fie sub prețul de intrare"}

    risk_amount = capital * risk_pct
    shares      = int(risk_amount / risk_per_share)
    tp1         = round(entry + risk_per_share * RR_TP1, 2)
    tp2         = round(entry + risk_per_share * RR_TP2, 2)
    position_val= round(shares * entry, 2)
    pct_capital = round(position_val / capital * 100, 1)

    return {
        "entry":          round(entry, 2),
        "sl":             round(sl, 2),
        "tp1":            tp1,
        "tp2":            tp2,
        "risk_per_share": round(risk_per_share, 2),
        "risk_amount_$":  round(risk_amount, 2),
        "shares":         shares,
        "position_value": position_val,
        "pct_of_capital": pct_capital,
        "rr_tp1":         RR_TP1,
        "rr_tp2":         RR_TP2,
    }


def load_journal() -> list:
    """Încarcă jurnalul de tranzacții."""
    if os.path.exists(JOURNAL_FILE):
        with open(JOURNAL_FILE, "r") as f:
            return json.load(f)
    return []


def save_journal(journal: list):
    """Salvează jurnalul de tranzacții."""
    with open(JOURNAL_FILE, "w") as f:
        json.dump(journal, f, indent=2, default=str)


def add_trade(ticker: str, entry: float, sl: float, shares: int,
              tp1: float, tp2: float, notes: str = "") -> dict:
    """Adaugă o nouă tranzacție în jurnal."""
    journal = load_journal()
    trade = {
        "id":         len(journal) + 1,
        "ticker":     ticker,
        "entry":      entry,
        "sl":         sl,
        "tp1":        tp1,
        "tp2":        tp2,
        "shares":     shares,
        "status":     "OPEN",
        "exit_price": None,
        "exit_type":  None,
        "r":          None,
        "pnl_$":      None,
        "notes":      notes,
        "open_date":  datetime.now().strftime("%Y-%m-%d"),
        "close_date": None,
    }
    journal.append(trade)
    save_journal(journal)
    log.info(f"📝 Tranzacție adăugată: {ticker} @ ${entry}")
    return trade


def close_trade(trade_id: int, exit_price: float, exit_type: str = "MANUAL") -> dict | None:
    """Închide o tranzacție și calculează P&L."""
    journal = load_journal()
    for trade in journal:
        if trade["id"] == trade_id and trade["status"] == "OPEN":
            risk  = trade["entry"] - trade["sl"]
            pnl   = (exit_price - trade["entry"]) * trade["shares"]
            r     = (exit_price - trade["entry"]) / risk if risk > 0 else 0

            trade["exit_price"] = round(exit_price, 2)
            trade["exit_type"]  = exit_type
            trade["r"]          = round(r, 2)
            trade["pnl_$"]      = round(pnl, 2)
            trade["status"]     = "CLOSED"
            trade["close_date"] = datetime.now().strftime("%Y-%m-%d")

            save_journal(journal)
            log.info(f"✅ Tranzacție închisă: {trade['ticker']} | R: {trade['r']} | P&L: ${trade['pnl_$']}")
            return trade
    return None


def get_journal_stats() -> dict:
    """Calculează statistici din jurnalul de tranzacții."""
    journal = load_journal()
    closed  = [t for t in journal if t["status"] == "CLOSED"]
    open_t  = [t for t in journal if t["status"] == "OPEN"]

    if not closed:
        return {
            "total_closed": 0,
            "open_trades":  len(open_t),
            "message":      "Nu există tranzacții închise încă"
        }

    wins   = [t for t in closed if t["r"] and t["r"] > 0]
    losses = [t for t in closed if t["r"] and t["r"] <= 0]
    total_pnl = sum(t["pnl_$"] for t in closed if t["pnl_$"])
    total_r   = sum(t["r"]     for t in closed if t["r"])

    return {
        "total_closed":  len(closed),
        "open_trades":   len(open_t),
        "wins":          len(wins),
        "losses":        len(losses),
        "win_rate":      round(len(wins) / len(closed) * 100, 1),
        "total_r":       round(total_r, 2),
        "total_pnl_$":   round(total_pnl, 2),
        "avg_r":         round(total_r / len(closed), 2),
        "best_trade":    max(closed, key=lambda x: x.get("r", 0)),
        "worst_trade":   min(closed, key=lambda x: x.get("r", 0)),
    }


def format_stats_message(stats: dict) -> str:
    """Formatează statisticile pentru Telegram."""
    if stats.get("total_closed", 0) == 0:
        return "📊 *Jurnal gol* — nu există tranzacții închise încă."

    best  = stats["best_trade"]
    worst = stats["worst_trade"]
    emoji = "🟢" if stats["total_pnl_$"] >= 0 else "🔴"

    return (
        f"📊 *STATISTICI JURNAL*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 *Tranzacții închise:* `{stats['total_closed']}`\n"
        f"🔓 *Tranzacții deschise:* `{stats['open_trades']}`\n"
        f"✅ *Win Rate:* `{stats['win_rate']}%`\n"
        f"💹 *Total R:* `{stats['total_r']}R`\n"
        f"{emoji} *P&L total:* `${stats['total_pnl_$']}`\n"
        f"📈 *R mediu/tranzacție:* `{stats['avg_r']}R`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 *Cea mai bună:* `{best['ticker']}` +{best['r']}R\n"
        f"💀 *Cea mai proastă:* `{worst['ticker']}` {worst['r']}R"
    )
