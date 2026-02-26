import os
import json
import yfinance as yf
import pandas as pd
import numpy as np
import telebot
import subprocess
from datetime import datetime

# ===============================
# CONFIGURARE
# ===============================
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

def detecteaza_pullback(df, simbol, idx=-1):
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

        # 1. FILTRU LICHIDITATE (Minim 1M $ rulați azi)
        if (close * volume) < 1_000_000:
            return None

        # 2. TREND PUTERNIC
        trend_ok = (
            close > ma200 and
            ma50  > ma200 and
            ma20  > ma50  and
            c.get('ma200_rising', False) is True
        )
        if not trend_ok:
            return None

        # 3. PULLBACK CONTROLAT (Max 1.5% de medie)
        pullback_ma20 = low <= ma20 * 1.015 and close >= ma20 * 0.98
        pullback_ma50 = low <= ma50 * 1.015 and close >= ma50 * 0.98

        if not (pullback_ma20 or pullback_ma50):
            return None

        # 4. RSI GOLDILOCKS (45 - 65)
        if not (45 <= rsi <= 65):
            return None

        # 5. VOLUM PULLBACK (Sănătos: >50% din medie, dar nu vârf de panică)
        vol_ratio = volume / vol_ma
        if vol_ratio < 0.50:
            return None

        lookback_vol = min(20, len(df) + idx - 1)
        vol_breakout = df['Volume'].iloc[idx - lookback_vol:idx].max()
        if volume >= vol_breakout:
            return None

        # 6. FILTRU ATR (Volatilitate normală 1% - 2.5%)
        atr_pct = (atr / close) * 100
        if not (1.0 <= atr_pct <= 2.5):
            return None

        # 7. CONFIRMARE PRICE ACTION
        engulfing = (close > open_ and close > prev['Close'] and open_ < prev['Open'])

        corp     = abs(close - open_)
        wick_jos = min(open_, close) - low
        respingere = (close > open_ and wick_jos >= corp * 2)

        inside_bar   = (prev['High'] < prev2['High'] and prev['Low'] > prev2['Low'])
        inside_break = inside_bar and close > prev['High']

        if not (engulfing or respingere or inside_break):
            return None

        tip_lumanare = "ENGULFING 💪" if engulfing else ("INSIDE BREAK 📊" if inside_break else "REJECTION PIN 🔄")
        zona = "MA20 🎯" if pullback_ma20 else "MA50 🎯"

        # 8. MANAGEMENT RISC (SL & TP)
        lookback_sl  = min(6, len(df) + idx - 1)
        swing_low    = df['Low'].iloc[idx - lookback_sl:idx].min()
        sl_anticipat = round(min(swing_low, ma50) - (atr * 0.2), 2)

        risc_per_actiune = close - sl_anticipat
        if risc_per_actiune <= 0:
            return None

        tp1    = round(close + (risc_per_actiune * 1.5), 2)
        tp2    = round(close + (risc_per_actiune * 3.0), 2)
        sl_pct = round((risc_per_actiune / close) * 100, 2)

        # Data reala a lumânării analizate
        data_lumanare = df.index[idx].strftime('%Y-%m-%d')

        return {
            'simbol': simbol, 'zona': zona, 'tip_lumanare': tip_lumanare,
            'close_azi': round(close, 2), 'sl_anticipat': sl_anticipat,
            'tp1': tp1, 'tp2': tp2, 'sl_pct': sl_pct, 'rsi': round(rsi, 1),
            'vol_ratio': round(vol_ratio, 2), 'atr_pct': round(atr_pct, 2),
            'ma20': round(ma20, 2), 'ma50': round(ma50, 2), 'atr': round(atr, 2),
            'swing_low': round(swing_low, 2), 'data_setup': data_lumanare,
            'status': 'asteapta_confirmare', 'tp1_atins': False
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

    # Cheie unica simbol + data ca sa nu duplicam semnale
    existente = set(f"{s['simbol']}_{s['data_setup']}" for s in setupuri_active)

    semnale_noi = []

    for simbol in watchlist:
        try:
            df = yf.Ticker(simbol).history(period="2y")
            if len(df) < 210:
                continue
            df = calculate_indicators(df)

            # Scanam ultimele 10 zile (de la -10 la -1)
            for zile_inapoi in range(10, 0, -1):
                idx = -zile_inapoi
                res = detecteaza_pullback(df, simbol, idx=idx)
                if res:
                    cheie = f"{res['simbol']}_{res['data_setup']}"
                    if cheie in existente:
                        continue  # semnal deja salvat, sarim peste
                    setupuri_active.append(res)
                    semnale_noi.append(res)
                    existente.add(cheie)
                    print(f"[SEMNAL] {simbol} — {res['data_setup']} identificat.")
        except Exception as e:
            print(f"[EROARE {simbol}]: {e}")
            continue

    if semnale_noi:
        for s in semnale_noi:
            msg = (
                f"🔍 *SETUP IDENTIFICAT — Daily*\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 *Ticker:* `{s['simbol']}`\n"
                f"📅 *Data setup:* {s['data_setup']}\n"
                f"🎯 *Pullback la:* {s['zona']}\n"
                f"🕯️ *Lumânare:* {s['tip_lumanare']}\n\n"
                f"📈 *Niveluri Teoretice:*\n"
                f"• Close: ${s['close_azi']}\n"
                f"🛑 *SL:* ${s['sl_anticipat']} ({s['sl_pct']}%)\n"
                f"🎯 *TP1:* ${s['tp1']} (1.5R)\n"
                f"🚀 *TP2:* ${s['tp2']} (3R)\n\n"
                f"🔍 *Filtre:* RSI: {s['rsi']} | Vol: {s['vol_ratio']}x | ATR: {s['atr_pct']}%\n"
                f"━━━━━━━━━━━━━━━━━━━━━"
            )
            bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

        db['setupuri_active'] = setupuri_active
        salveaza_si_commit(db, f"Scanner Daily {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    else:
        print("[INFO] Niciun setup nou in ultimele 10 zile conform filtrelor stricte.")

if __name__ == "__main__":
    main()
