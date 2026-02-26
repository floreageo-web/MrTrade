import os
import json
import yfinance as yf
import pandas as pd
import numpy as np
import telebot
import subprocess
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

        df['ma20']  = df['Close'].rolling(window=20).mean()
        df['ma50']  = df['Close'].rolling(window=50).mean()
        df['ma200'] = df['Close'].rolling(window=200).mean()
        df['ma200_rising'] = df['ma200'] > df['ma200'].shift(5)

        delta    = df['Close'].diff()
        gain     = delta.where(delta > 0, 0.0)
        loss     = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs       = avg_gain / avg_loss.replace(0, 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))

        high_low   = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close  = (df['Low']  - df['Close'].shift()).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr']  = true_range.ewm(com=13, adjust=False).mean()

        # vol_ma = media pe 120 lumânări 4H ≈ 20 zile calendaristice
        df['vol_ma'] = df['Volume'].rolling(window=120).mean()

        return df
    except Exception as e:
        print(f"[EROARE indicatori]: {e}")
        return df


# ═══════════════════════════════════════════════════════════════════════
# 3. DETECTARE PULLBACK
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

        # 4. RSI (40 – 58)
        if not (40 <= rsi <= 58):
            return None

        # 5. VOLUM
        #    a) Mai mic decât breakout-ul (max din 120 lumânări)
        #    b) Între 0.7x și 1.2x față de media 20 zile (120 lumânări 4H)
        if volume >= vol_breakout:
            return None
        vol_ratio = volume / vol_ma
        if not (0.7 <= vol_ratio <= 1.2):
            return None

        # 6. ATR% (1% – 2.8%)
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
#    - close curent < MA de referință recalculată LIVE
#    - SAU close curent ≤ SL salvat
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
            df = yf.Ticker(s['simbol']).history(period="60d", interval="4h")

            if df.empty or len(df) < 55:
                valid_setups.append(s)
                continue

            last_close = df['Close'].iloc[-1]
            sl         = s['sl_anticipat']

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
#    Citește din linia de comandă argumentul --prima-rulare
#    dacă e prezent → lookback 30 lumânări (5 zile)
#    dacă nu        → doar lumânarea curentă (idx = -1)
# ═══════════════════════════════════════════════════════════════════════
def main():
    import sys

    # GitHub Actions pasează --prima-rulare doar la primul workflow
    prima_rulare = '--prima-rulare' in sys.argv

    now_ro = datetime.now(TIMEZONE_RO).strftime('%d-%m-%Y %H:%M')
    print("=" * 55)
    print(f"  TRADING BOT 4H — {now_ro} (ora Romaniei)")
    print(f"  Mod: {'PRIMA RULARE (30 lum.)' if prima_rulare else 'SCANARE CURENTA (idx=-1)'}")
    print("=" * 55 + "\n")

    if not os.path.exists('baza_de_date.json'):
        print("[EROARE] baza_de_date.json nu exista!")
        exit(1)

    with open('baza_de_date.json', 'r') as f:
        db = json.load(f)

    # ── Pasul 1: Curățare setupuri invalide ───────────────────────────
    db = curata_setupuri_invalide(db)

    # ── Pasul 2: Re-extragere liste din db-ul curățat ─────────────────
    watchlist       = db.get('watchlist_trend_ascendent', [])
    setupuri_active = db.get('setupuri_active', [])
    existente       = set(s['simbol'] for s in setupuri_active)

    # ── Pasul 3: Determinare lookback ─────────────────────────────────
    # Prima rulare  → range(-30, 0) = [-30, -29, ..., -1] (cel mai vechi primul)
    # Rulări normale → [-1] (doar lumânarea curentă)
    lookback_idxs = list(range(-30, 0)) if prima_rulare else [-1]
    print(f"[INFO] Scanare {len(watchlist)} simboluri | lookback: {'30 lum. (5 zile)' if prima_rulare else '1 lum. (curenta)'}...")

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
            vol_breakout = df['Volume'].iloc[-120:].max()

            for idx in lookback_idxs:
                res = detecteaza_pullback(df, simbol, idx, vol_breakout)
                if res:
                    setupuri_active.append(res)
                    semnale_noi.append(res)
                    existente.add(simbol)
                    print(f"✅ Gasit: {simbol} pe {res['data_setup']}")
                    break

        except Exception as e:
            print(f"[EROARE] {simbol}: {e}")
            continue

    # ── Pasul 5: Trimitere Telegram + salvare ─────────────────────────
    if semnale_noi:
        print(f"\n[INFO] Trimitere {len(semnale_noi)} semnal(e) pe Telegram...")
        for s in semnale_noi:
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
                print(f"[INFO] Trimis: {s['simbol']}")
            except Exception as e:
                print(f"[EROARE Telegram {s['simbol']}]: {e}")

        db['setupuri_active'] = setupuri_active
        salveaza_si_commit(db, f"Scan 4H {now_ro}")
    else:
        print("[INFO] Niciun semnal nou conform filtrelor.")

    print(f"\n[INFO] ===== Bot finalizat =====")


if __name__ == "__main__":
    main()
