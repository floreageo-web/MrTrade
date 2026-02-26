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

        # 1. LICHIDITATE
        if (close * volume) < 500_000:
            return None

        # 2. TREND PUTERNIC
        trend_ok = (close > ma200 and ma50 > ma200 and ma20 > ma50 and c.get('ma200_rising', False))
        if not trend_ok:
            return None

        # 3. PULLBACK (Toleranță 1.5% față de MA20/MA50)
        pullback_ma20 = low <= ma20 * 1.015 and close >= ma20 * 0.98
        pullback_ma50 = low <= ma50 * 1.015 and close >= ma50 * 0.98
        if not (pullback_ma20 or pullback_ma50):
            return None

        # 4. RSI (40 - 58)
        if not (40 <= rsi <= 58):
            return None

        # 5. VOLUM (să nu fie vârf de panică, acceptăm până la 1.1x medie)
        vol_ratio = volume / vol_ma
        if vol_ratio > 1.1:
            return None

        # 6. ATR PCT (1% - 2.8%)
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

        if engulfing: tip = "ENGULFING 💪"
        elif inside_break: tip = "INSIDE BREAK 📊"
        elif respingere: tip = "REJECTION PIN 🔄"
        else: tip = "BULLISH SOLID ✅"

        zona = "MA20 🎯" if pullback_ma20 else "MA50 🎯"

        # 8. MANAGEMENT RISC
        lookback_sl  = min(6, len(df) + idx - 1)
        swing_low    = df['Low'].iloc[idx - lookback_sl:idx].min()
        sl_anticipat = round(min(swing_low, ma50) - (atr * 0.2), 2)

        risc = close - sl_anticipat
        if risc <= 0: return None

        tp1    = round(close + (risc * 1.5), 2)
        tp2    = round(close + (risc * 3.0), 2)
        sl_pct = round((risc / close) * 100, 2)
        data_lumanare = df.index[idx].strftime('%Y-%m-%d')

        return {
            'simbol': simbol, 'zona': zona, 'tip_lumanare': tip,
            'close_azi': round(close, 2), 'sl_anticipat': sl_anticipat,
            'tp1': tp1, 'tp2': tp2, 'sl_pct': sl_pct, 'rsi': round(rsi, 1),
            'vol_ratio': round(vol_ratio, 2), 'atr_pct': round(atr_pct, 2),
            'ma20': round(ma20, 2), 'ma50': round(ma50, 2), 'atr': round(atr, 2),
            'data_setup': data_lumanare, 'status': 'asteapta_confirmare', 'tp1_atins': False
        }
    except:
        return None

def main():
    if not os.path.exists('baza_de_date.json'): return
    with open('baza_de_date.json', 'r') as f: db = json.load(f)

    watchlist       = db.get('watchlist_trend_ascendent', [])
    setupuri_active = db.get('setupuri_active', [])

    # Verificare doar dupa simbol — un ticker primeste mesaj o singura data
    existente = set(s['simbol'] for s in setupuri_active)

    semnale_noi = []
    print(f"[INFO] Incepere scanare (10 zile back-check) pentru {len(watchlist)} simboluri...")

    for simbol in watchlist:
        if simbol in existente:
            print(f"[SKIP] {simbol} — semnal deja existent.")
            continue
        try:
            df = yf.Ticker(simbol).history(period="2y")
            if len(df) < 210: continue
            df = calculate_indicators(df)

            for zile_inapoi in range(10, 0, -1):
                res = detecteaza_pullback(df, simbol, idx=-zile_inapoi)
                if res:
                    setupuri_active.append(res)
                    semnale_noi.append(res)
                    existente.add(simbol)
                    print(f"✅ Gasit: {simbol} pe {res['data_setup']}")
                    break  # opreste la primul semnal gasit pentru acest ticker
        except: continue

    if semnale_noi:
        for s in semnale_noi:
            msg = (f"🔍 *SETUP IDENTIFICAT*\n"
                   f"📊 *Ticker:* `{s['simbol']}` | {s['data_setup']}\n"
                   f"💰 *Preț:* ${s['close_azi']}\n"
                   f"🎯 *Zona:* {s['zona']} | {s['tip_lumanare']}\n"
                   f"🛑 *SL:* ${s['sl_anticipat']} ({s['sl_pct']}%)\n"
                   f"🎯 *TP1:* ${s['tp1']} | *TP2:* ${s['tp2']}\n"
                   f"📈 *RSI:* {s['rsi']} | *ATR:* {s['atr_pct']}%")
            bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

        db['setupuri_active'] = setupuri_active
        salveaza_si_commit(db, f"Scan {datetime.now().strftime('%d-%m %H:%M')}")
    else:
        print("[INFO] Niciun rezultat conform filtrelor.")

if __name__ == "__main__":
    main()
