import os
import json
import yfinance as yf
import pandas as pd
import numpy as np
import telebot
import subprocess
import schedule
import time
import pytz
from datetime import datetime

# ===============================
# CONFIGURARE
# ===============================
TOKEN   = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

if not TOKEN or not CHAT_ID:
    print("❌ EROARE CRITICA: Lipsesc variabilele de mediu TELEGRAM_TOKEN si TELEGRAM_CHAT_ID.")
    exit(1)

bot         = telebot.TeleBot(TOKEN)
TIMEZONE_RO = pytz.timezone('Europe/Bucharest')

# -----------------------------------------------------------------------
# Globale
#   coada_semnale  — semnalele găsite la scanare, trimise 5 min mai târziu
#   prima_rulare   — True doar la prima execuție (lookback 5 zile / 30 lumânări)
# -----------------------------------------------------------------------
coada_semnale = []
prima_rulare  = True


# ═══════════════════════════════════════════════════════════════════════
# 1. SALVARE + GIT COMMIT
# ═══════════════════════════════════════════════════════════════════════
def salveaza_si_commit(db, mesaj_commit):
    try:
        with open('baza_de_date.json', 'w') as f:
            json.dump(db, f, indent=4)
        subprocess.run(['git', 'config', '--global', 'user.email', 'bot@github.com'])
        subprocess.run(['git', 'config', '--global', 'user.name', 'Trading Bot'])
        subprocess.run(['git', 'add', 'baza_de_date.json'])
        subprocess.run(['git', 'commit', '-m', mesaj_commit])
        subprocess.run(['git', 'push'])
        print(f"[INFO] Commit reusit: {mesaj_commit}")
    except Exception as e:
        print(f"[EROARE commit]: {e}")


# ═══════════════════════════════════════════════════════════════════════
# 2. CALCUL INDICATORI TEHNICI
#    vol_ma = media pe 120 lumânări 4H ≈ 20 zile calendaristice
# ═══════════════════════════════════════════════════════════════════════
def calculate_indicators(df):
    try:
        df = df.copy()

        # Mobile Averages
        df['ma20']  = df['Close'].rolling(window=20).mean()
        df['ma50']  = df['Close'].rolling(window=50).mean()
        df['ma200'] = df['Close'].rolling(window=200).mean()
        df['ma200_rising'] = df['ma200'] > df['ma200'].shift(5)

        # RSI (14 perioadă cu EWM)
        delta    = df['Close'].diff()
        gain     = delta.where(delta > 0, 0.0)
        loss     = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs       = avg_gain / avg_loss.replace(0, 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))

        # ATR
        high_low   = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close  = (df['Low']  - df['Close'].shift()).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr']  = true_range.ewm(com=13, adjust=False).mean()

        # Volum mediu pe 120 lumânări 4H = ~20 zile
        df['vol_ma'] = df['Volume'].rolling(window=120).mean()

        return df
    except Exception as e:
        print(f"[EROARE indicatori]: {e}")
        return df


# ═══════════════════════════════════════════════════════════════════════
# 3. DETECTARE PULLBACK
#
#    Filtre aplicate în ordine:
#      1. Lichiditate minimă ($500k/lumânare)
#      2. Trend puternic: close > MA200 > MA50 > MA20, MA200 în creștere
#      3. Pullback la MA20 sau MA50 cu toleranță ±0.2 ATR
#      4. RSI între 40 și 58
#      5. Volum pullback < volum breakout (max din 120 lumânări)
#         și între 0.7x–1.2x din media 20 zile (120 lumânări 4H)
#      6. ATR% între 1% și 2.8%
#      7. Confirmare price action (engulfing / rejection pin /
#         inside break / bullish solid)
#      8. Management risc: SL, TP1, TP2
# ═══════════════════════════════════════════════════════════════════════
def detecteaza_pullback(df, simbol, idx, vol_breakout):
    try:
        if len(df) < 210:
            return None

        c     = df.iloc[idx]
        prev  = df.iloc[idx - 1]
        prev2 = df.iloc[idx - 2]

        close  = c['Close']
        open_  = c['Open']
        high   = c['High']
        low    = c['Low']
        ma20   = c['ma20']
        ma50   = c['ma50']
        ma200  = c['ma200']
        rsi    = c['rsi']
        volume = c['Volume']
        vol_ma = c['vol_ma']
        atr    = c['atr']

        # Verificare NaN (warmup insuficient)
        if any(pd.isna(x) for x in [ma20, ma50, ma200, rsi, vol_ma, atr]):
            return None

        # 1. LICHIDITATE
        if (close * volume) < 500_000:
            return None

        # 2. TREND PUTERNIC
        if not (close > ma200 and ma50 > ma200 and ma20 > ma50 and bool(c.get('ma200_rising', False))):
            return None

        # 3. PULLBACK ±0.2 ATR față de MA20 sau MA50
        atr_margin    = 0.2 * atr
        pullback_ma20 = (low <= ma20 + atr_margin) and (close >= ma20 - atr_margin)
        pullback_ma50 = (low <= ma50 + atr_margin) and (close >= ma50 - atr_margin)
        if not (pullback_ma20 or pullback_ma50):
            return None

        # 4. RSI
        if not (40 <= rsi <= 58):
            return None

        # 5. VOLUM
        #    a) Mai mic decât breakout-ul (max absolut din 120 lumânări)
        #    b) Între 0.7x și 1.2x față de media 20 zile (120 lumânări 4H)
        if volume >= vol_breakout:
            return None
        vol_ratio = volume / vol_ma
        if not (0.7 <= vol_ratio <= 1.2):
            return None

        # 6. ATR%
        atr_pct = (atr / close) * 100
        if not (1.0 <= atr_pct <= 2.8):
            return None

        # 7. CONFIRMARE PRICE ACTION
        engulfing     = (close > open_ and close > prev['Close'] and open_ < prev['Open'])
        respingere    = (close > open_ and (min(open_, close) - low) >= abs(close - open_) * 1.8)
        inside_break  = (prev['High'] < prev2['High'] and prev['Low'] > prev2['Low'] and close > prev['High'])
        bullish_solid = (close > open_) and (close > prev['Close']) and (close > (high + low) / 2)

        if not (engulfing or respingere or inside_break or bullish_solid):
            return None

        if   engulfing:    tip = "ENGULFING 💪"
        elif inside_break: tip = "INSIDE BREAK 📊"
        elif respingere:   tip = "REJECTION PIN 🔄"
        else:              tip = "BULLISH SOLID ✅"

        zona = "MA20 🎯" if pullback_ma20 else "MA50 🎯"

        # 8. MANAGEMENT RISC
        lookback_sl  = min(6, len(df) + idx - 1)
        swing_low    = df['Low'].iloc[idx - lookback_sl : idx].min()
        sl_anticipat = round(min(swing_low, ma50) - (atr * 0.2), 2)
        risc         = close - sl_anticipat
        if risc <= 0:
            return None

        tp1    = round(close + (risc * 1.5), 2)
        tp2    = round(close + (risc * 3.0), 2)
        sl_pct = round((risc / close) * 100, 2)

        return {
            'simbol':       simbol,
            'zona':         zona,
            'tip_lumanare': tip,
            'close_azi':    round(close, 2),
            'sl_anticipat': sl_anticipat,
            'tp1':          tp1,
            'tp2':          tp2,
            'sl_pct':       sl_pct,
            'rsi':          round(rsi, 1),
            'vol_ratio':    round(vol_ratio, 2),
            'atr_pct':      round(atr_pct, 2),
            'ma20':         round(ma20, 2),
            'ma50':         round(ma50, 2),
            'atr':          round(atr, 2),
            'data_setup':   df.index[idx].strftime('%Y-%m-%d %H:%M'),
            'status':       'asteapta_confirmare',
            'tp1_atins':    False
        }
    except Exception as e:
        print(f"[EROARE detectare {simbol} idx={idx}]: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════
# 4. CURĂȚARE SETUPURI INVALIDE
#
#    Un setup este eliminat dacă:
#      - close curent < MA de referință (recalculată LIVE, nu cea salvată)
#      - SAU close curent ≤ SL salvat
#
#    Dacă un ticker e eliminat, dispare din `existente` și poate fi
#    re-detectat la scanarea următoare dacă face un nou setup valid.
# ═══════════════════════════════════════════════════════════════════════
def curata_setupuri_invalide(db):
    active        = db.get('setupuri_active', [])
    initial_count = len(active)
    valid_setups  = []

    if not active:
        return db

    print(f"[INFO] Verificare invalidare pentru {initial_count} setupuri active...")

    for s in active:
        try:
            # 60 zile date 4H — suficient pentru a recalcula MA50 live
            df = yf.Ticker(s['simbol']).history(period="60d", interval="4h")

            if df.empty or len(df) < 55:
                # Date insuficiente → păstrăm setup-ul ca să nu-l pierdem
                valid_setups.append(s)
                continue

            last_close = df['Close'].iloc[-1]
            sl         = s['sl_anticipat']

            # MA recalculate LIVE pe datele proaspete
            ma20_live = df['Close'].rolling(window=20).mean().iloc[-1]
            ma50_live = df['Close'].rolling(window=50).mean().iloc[-1]
            ma_ref    = ma50_live if "MA50" in s['zona'] else ma20_live

            sub_medie = last_close < ma_ref
            atins_sl  = last_close <= sl

            if sub_medie or atins_sl:
                motive = []
                if sub_medie: motive.append(f"close ${last_close:.2f} < MA_ref ${ma_ref:.2f}")
                if atins_sl:  motive.append(f"SL atins (${sl})")
                print(f"❌ [INVALIDARE] {s['simbol']}: {' | '.join(motive)}")
            else:
                valid_setups.append(s)

        except Exception as e:
            # Eroare de rețea sau date lipsă → păstrăm setup-ul
            print(f"[WARN] {s['simbol']} — eroare la validare, setup pastrat: {e}")
            valid_setups.append(s)

    eliminate = initial_count - len(valid_setups)
    if eliminate:
        print(f"[INFO] Curatare: {eliminate} setup(uri) eliminate, {len(valid_setups)} ramase.")
    else:
        print(f"[INFO] Niciun setup invalidat. Active: {len(valid_setups)}.")

    db['setupuri_active'] = valid_setups
    return db


# ═══════════════════════════════════════════════════════════════════════
# 5. SCANARE PRINCIPALĂ
#
#    Prima rulare  → lookback 5 zile (30 lumânări 4H), semnal cel mai vechi
#    Rulări normale → doar lumânarea curentă (idx = -1)
# ═══════════════════════════════════════════════════════════════════════
def ruleaza_scanare():
    global prima_rulare, coada_semnale

    now_ro = datetime.now(TIMEZONE_RO).strftime('%d-%m-%Y %H:%M')
    print(f"\n[INFO] ===== Scanare pornita la {now_ro} (ora Romaniei) =====")

    if not os.path.exists('baza_de_date.json'):
        print("[EROARE] baza_de_date.json nu exista!")
        return

    with open('baza_de_date.json', 'r') as f:
        db = json.load(f)

    # ── Pasul 1: Curățare setupuri invalide ───────────────────────────
    db = curata_setupuri_invalide(db)

    # ── Pasul 2: Re-extragere liste DIN DB-UL CURĂȚAT ─────────────────
    watchlist       = db.get('watchlist_trend_ascendent', [])
    setupuri_active = db.get('setupuri_active', [])
    existente       = set(s['simbol'] for s in setupuri_active)

    # ── Pasul 3: Determinare lookback ─────────────────────────────────
    if prima_rulare:
        # 5 zile × 6 lumânări/zi = 30 lumânări 4H
        # range(-30, 0) → [-30, -29, ..., -1] → cel mai vechi primul
        lookback_idxs = list(range(-30, 0))
        print(f"[INFO] PRIMA RULARE — lookback 5 zile (30 lum. 4H) | {len(watchlist)} simboluri...")
    else:
        lookback_idxs = [-1]
        print(f"[INFO] Scanare curenta (idx=-1) | {len(watchlist)} simboluri...")

    # ── Pasul 4: Scanare watchlist ────────────────────────────────────
    semnale_noi = []

    for simbol in watchlist:
        if simbol in existente:
            print(f"[SKIP] {simbol} — semnal deja activ.")
            continue
        try:
            df = yf.Ticker(simbol).history(period="2y", interval="4h")
            if len(df) < 210:
                print(f"[SKIP] {simbol} — date insuficiente ({len(df)} lum.).")
                continue

            df = calculate_indicators(df)

            # Volumul breakout = maximul absolut din ultimele 120 lumânări (~20 zile)
            vol_breakout = df['Volume'].iloc[-120:].max()

            for idx in lookback_idxs:
                res = detecteaza_pullback(df, simbol, idx, vol_breakout)
                if res:
                    setupuri_active.append(res)
                    semnale_noi.append(res)
                    existente.add(simbol)
                    print(f"✅ Gasit: {simbol} pe {res['data_setup']}")
                    break  # Primul semnal (cel mai vechi) — oprim pentru acest ticker

        except Exception as e:
            print(f"[EROARE] {simbol}: {e}")
            continue

    # ── Pasul 5: Salvare + adăugare în coadă ─────────────────────────
    if semnale_noi:
        coada_semnale.extend(semnale_noi)
        db['setupuri_active'] = setupuri_active
        salveaza_si_commit(db, f"Scan 4H {now_ro}")
        print(f"[INFO] {len(semnale_noi)} semnal(e) in coada — trimitere in 5 min.")
    else:
        print("[INFO] Niciun semnal nou conform filtrelor.")

    prima_rulare = False
    print(f"[INFO] ===== Scanare finalizata =====\n")


# ═══════════════════════════════════════════════════════════════════════
# 6. TRIMITERE MESAJE TELEGRAM
#    Apelată la 5 minute după fiecare scanare.
#    Consumă și golește coada globală.
# ═══════════════════════════════════════════════════════════════════════
def trimite_semnale():
    global coada_semnale

    if not coada_semnale:
        return

    now_ro = datetime.now(TIMEZONE_RO).strftime('%d-%m-%Y %H:%M')
    print(f"[INFO] Trimitere {len(coada_semnale)} semnal(e) la {now_ro}...")

    for s in coada_semnale:
        try:
            msg = (
                f"🔍 *SETUP IDENTIFICAT (4H)*\n"
                f"📊 *Ticker:* `{s['simbol']}` | {s['data_setup']}\n"
                f"💰 *Preț:* ${s['close_azi']}\n"
                f"🎯 *Zona:* {s['zona']} | {s['tip_lumanare']}\n"
                f"🛑 *SL:* ${s['sl_anticipat']} ({s['sl_pct']}%)\n"
                f"🎯 *TP1:* ${s['tp1']} | *TP2:* ${s['tp2']}\n"
                f"📈 *RSI:* {s['rsi']} | *Vol ratio:* {s['vol_ratio']}x | *ATR:* {s['atr_pct']}%\n"
                f"🕐 *Timeframe:* 4H"
            )
            bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
        except Exception as e:
            print(f"[EROARE Telegram {s['simbol']}]: {e}")

    coada_semnale.clear()
    print("[INFO] Toate semnalele au fost trimise.")


# ═══════════════════════════════════════════════════════════════════════
# 7. MAIN — SCHEDULER
#    Scanări:  16:45 | 20:35 | 23:00  (ora României)
#    Mesaje:   16:50 | 20:40 | 23:05  (ora României, +5 min)
#
#    ⚠️  Asigură-te că serverul rulează cu TZ=Europe/Bucharest
#        (ex: export TZ=Europe/Bucharest înainte de pornire)
#        sau că schedule este setat pe UTC și orele sunt ajustate.
# ═══════════════════════════════════════════════════════════════════════
def main():
    print("=" * 55)
    print("  TRADING BOT 4H — PORNIT")
    print("=" * 55)
    print("  Scanări:  16:45 | 20:35 | 23:00  (ora României)")
    print("  Mesaje:   16:50 | 20:40 | 23:05  (ora României)")
    print("  Prima rulare: lookback 5 zile (30 lumânări 4H)")
    print("  Rulări normale: doar lumânarea curentă (idx=-1)")
    print("=" * 55 + "\n")

    # Scanări
    schedule.every().day.at("16:45").do(ruleaza_scanare)
    schedule.every().day.at("20:35").do(ruleaza_scanare)
    schedule.every().day.at("23:00").do(ruleaza_scanare)

    # Trimitere mesaje (+5 min)
    schedule.every().day.at("16:50").do(trimite_semnale)
    schedule.every().day.at("20:40").do(trimite_semnale)
    schedule.every().day.at("23:05").do(trimite_semnale)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
