import os
import json
import yfinance as yf
import pandas as pd
import numpy as np
import telebot
import subprocess
from datetime import datetime

TOKEN   = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

if not TOKEN or not CHAT_ID:
    print("❌ EROARE CRITICA: Lipsesc variabilele de mediu.")
    exit(1)

bot = telebot.TeleBot(TOKEN)

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

def calculate_indicators(df):
    try:
        df = df.copy()

        df['ma20']  = df['Close'].rolling(window=20).mean()
        df['ma50']  = df['Close'].rolling(window=50).mean()
        df['ma200'] = df['Close'].rolling(window=200).mean()

        # MA200 rising — verifica daca MA200 a crescut in ultimele 5 zile
        df['ma200_rising'] = df['ma200'] > df['ma200'].shift(5)

        # RSI 14
        delta    = df['Close'].diff()
        gain     = delta.where(delta > 0, 0.0)
        loss     = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs       = avg_gain / avg_loss.replace(0, 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))

        # ATR 14
        high_low   = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close  = (df['Low']  - df['Close'].shift()).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr']  = true_range.ewm(com=13, adjust=False).mean()

        # Volume MA 20
        df['vol_ma'] = df['Volume'].rolling(window=20).mean()

        return df
    except Exception as e:
        print(f"[EROARE indicatori]: {e}")
        return df


def detecteaza_pullback(df, simbol):
    try:
        if len(df) < 210:
            return None

        # i = -1 deoarece botul ruleaza la 21:00 UTC
        # adica dupa inchiderea bursei (16:00 EST)
        # lumânarea de azi e complet inchisa
        i    = -1
        c    = df.iloc[i]    # lumânarea de azi — inchisa complet
        prev = df.iloc[i-1]  # lumânarea de ieri

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

        # ==========================================
        # 1. TREND PUTERNIC
        # MA20 > MA50 > MA200 si MA200 in crestere
        # ==========================================
        trend_ok = (
            close > ma200 and
            ma50  > ma200 and
            ma20  > ma50  and
            c['ma200_rising'] == True
        )
        if not trend_ok:
            return None

        # ==========================================
        # 2. PULLBACK LA MA20 SAU MA50
        # Low-ul a atins zona MA cu toleranta 1.5%
        # ==========================================
        pullback_ma20 = low <= ma20 * 1.015 and close > ma50
        pullback_ma50 = low <= ma50 * 1.015 and close > ma200

        if not (pullback_ma20 or pullback_ma50):
            return None

        # ==========================================
        # 3. RSI INTRE 40-55
        # Zona de racire — nu supracumparat
        # ==========================================
        if not (40 <= rsi <= 55):
            return None

        # ==========================================
        # 4. VOLUM MIC LA PULLBACK
        # Pullback sanatos = volum scazut
        # Panic sale = volum mare — ignoram
        # ==========================================
        if volume > vol_ma * 0.8:
            return None

        # ==========================================
        # 5. LUMANARE DE CONFIRMARE
        # Engulfing, Inside Bar sau Respingere
        # ==========================================
        engulfing  = (
            close > open_ and
            close > prev['High'] and
            open_ < prev['Close']
        )
        wick_jos   = open_ - low if close > open_ else close - low
        corp       = abs(close - open_)
        respingere = (
            close > open_ and
            wick_jos > corp * 1.5 and
            close > prev['Close']
        )
        inside_bar = (
            high > prev['High'] and
            low  > prev['Low']  and
            close > prev['High']
        )
        is_bullish = close > open_

        confirmare = engulfing or respingere or inside_bar or is_bullish
        if not confirmare:
            return None

        # Tip lumânare detectat
        if engulfing:    tip_lumanare = "ENGULFING 💪"
        elif inside_bar: tip_lumanare = "INSIDE BREAK 📊"
        elif respingere: tip_lumanare = "RESPINGERE 🔄"
        else:            tip_lumanare = "BULLISH ✅"

        # Zona de pullback
        zona = "MA20 🎯" if pullback_ma20 else "MA50 🎯"

        # ==========================================
        # SL ANTICIPAT
        # Sub swing low sau MA50 — orientativ
        # Va fi recalculat in Bot 2 dupa entry real
        # ==========================================
        swing_low    = df['Low'].iloc[i-6:i-1].min()
        sl_anticipat = round(min(swing_low, ma50) - (atr * 0.1), 2)
        sl_pct       = round((sl_anticipat - close) / close * 100, 2)

        return {
            'simbol':        simbol,
            'zona':          zona,
            'tip_lumanare':  tip_lumanare,
            'close_azi':     round(close, 2),
            'sl_anticipat':  sl_anticipat,
            'sl_pct':        sl_pct,
            'rsi':           round(rsi, 1),
            'vol_ratio':     round(volume / vol_ma, 2),
            'ma20':          round(ma20, 2),
            'ma50':          round(ma50, 2),
            'atr':           round(atr, 2),
            'swing_low':     round(swing_low, 2),
            'data_setup':    datetime.now().strftime('%Y-%m-%d'),
            'status':        'asteapta_confirmare',
            'tp1_atins':     False
        }

    except Exception as e:
        print(f"[EROARE semnal {simbol}]: {e}")
        return None


def main():
    if not os.path.exists('baza_de_date.json'):
        print("[EROARE] baza_de_date.json nu exista!")
        return

    with open('baza_de_date.json', 'r') as f:
        db = json.load(f)

    watchlist       = db.get('watchlist_trend_ascendent', [])
    setupuri_active = db.get('setupuri_active', [])
    existente       = [s['simbol'] for s in setupuri_active]

    ora = datetime.now().strftime('%H:%M')
    print(f"[INFO] Scanner Daily | {len(watchlist)} simboluri | {ora} UTC")

    semnale_noi = []

    for simbol in watchlist:
        # Skip daca avem deja pozitie activa pe acest simbol
        if simbol in existente:
            print(f"[SKIP] {simbol} — pozitie activa deja")
            continue

        try:
            df = yf.Ticker(simbol).history(period="2y")
            if len(df) < 210:
                continue

            df  = calculate_indicators(df)
            res = detecteaza_pullback(df, simbol)

            if res:
                setupuri_active.append(res)
                semnale_noi.append(res)
                print(f"[SEMNAL] {simbol} | {res['zona']} | {res['tip_lumanare']} | RSI: {res['rsi']}")

        except Exception as e:
            print(f"[EROARE] {simbol}: {e}")
            continue

    # Trimite semnale noi pe Telegram
    if semnale_noi:
        print(f"[INFO] {len(semnale_noi)} semnale noi gasite")
        for s in semnale_noi:
            msg = (
                f"🔍 *SETUP IDENTIFICAT — Daily*\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 *Ticker:* `{s['simbol']}`\n"
                f"🎯 *Pullback la:* {s['zona']}\n"
                f"🕯️ *Lumânare:* {s['tip_lumanare']}\n\n"
                f"📈 *Detalii setup:*\n"
                f"• Close azi: ${s['close_azi']}\n"
                f"• RSI: {s['rsi']} ✅\n"
                f"• Volum pullback: {s['vol_ratio']}x (MIC ✅)\n"
                f"• MA20: ${s['ma20']}\n"
                f"• MA50: ${s['ma50']}\n"
                f"• ATR: ${s['atr']}\n"
                f"• Swing Low: ${s['swing_low']}\n\n"
                f"🛑 *SL anticipat:* ${s['sl_anticipat']} ({s['sl_pct']}%)\n\n"
                f"⏳ *Așteaptă confirmare mâine pe 1H*\n"
                f"📌 *Entry + SL + TP1 + TP2 se calculează*\n"
                f"   *mâine la prețul real de intrare*\n\n"
                f"⚠️ _DYOR - Analiza Automata_\n"
                f"━━━━━━━━━━━━━━━━━━━━━"
            )
            bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

        # Salveaza si commit
        db['setupuri_active'] = setupuri_active
        salveaza_si_commit(
            db,
            f"Scanner Daily {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
    else:
        print("[INFO] Niciun setup nou astazi")


if __name__ == "__main__":
    main()
