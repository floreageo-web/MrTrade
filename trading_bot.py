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
    print("❌ EROARE: Lipsesc variabilele de mediu.")
    exit(1)

bot = telebot.TeleBot(TOKEN)
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
        result = subprocess.run(['git', 'commit', '-m', mesaj_commit], capture_output=True, text=True)
        if "nothing to commit" not in result.stdout:
            subprocess.run(['git', 'push'])
            print(f"[INFO] Commit reusit: {mesaj_commit}")
        else:
            print("[INFO] Nimic de salvat pe GitHub.")
    except Exception as e:
        print(f"[EROARE commit]: {e}")

# ═══════════════════════════════════════════════════════════════════════
# 2. CALCUL INDICATORI TEHNICI
# ═══════════════════════════════════════════════════════════════════════
def calculate_indicators(df):
    try:
        df = df.copy()
        df['ma20']  = df['Close'].ewm(span=20, adjust=False).mean()
        df['ma50']  = df['Close'].ewm(span=50, adjust=False).mean()
        df['ma200'] = df['Close'].ewm(span=200, adjust=False).mean()

        delta    = df['Close'].diff()
        gain     = delta.where(delta > 0, 0.0)
        loss     = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs       = avg_gain / avg_loss.replace(0, 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))

        true_range = pd.concat([
            df['High'] - df['Low'],
            (df['High'] - df['Close'].shift()).abs(),
            (df['Low']  - df['Close'].shift()).abs()
        ], axis=1).max(axis=1)
        df['atr'] = true_range.ewm(com=13, adjust=False).mean()
        df['vol_ma50'] = df['Volume'].rolling(window=50).mean()
        return df
    except Exception as e:
        print(f"[EROARE indicatori]: {e}")
        return df

# ═══════════════════════════════════════════════════════════════════════
# 3. CALCUL FIBONACCI
# ═══════════════════════════════════════════════════════════════════════
def calculeaza_fibonacci(df, idx_bara1):
    try:
        fereastra  = df.iloc[idx_bara1 - 50 : idx_bara1]
        swing_high = fereastra['High'].max()
        swing_low  = df.iloc[idx_bara1]['Low']

        if swing_high <= swing_low: return None, None
        amplitudine = swing_high - swing_low

        niveluri = {
            '0.236': round(swing_high - amplitudine * 0.236, 2),
            '0.382': round(swing_high - amplitudine * 0.382, 2),
            '0.500': round(swing_high - amplitudine * 0.500, 2),
            '0.618': round(swing_high - amplitudine * 0.618, 2),
            '0.786': round(swing_high - amplitudine * 0.786, 2),
        }

        toleranta = swing_high * 0.005
        nivel_atins = None
        for nume, valoare in niveluri.items():
            if abs(swing_low - valoare) <= toleranta:
                nivel_atins = nume
                break
        if not nivel_atins:
            cel_mai_apropiat = min(niveluri.items(), key=lambda x: abs(swing_low - x[1]))
            nivel_atins = f"~{cel_mai_apropiat[0]}"

        retragere_pct = round((amplitudine / swing_high) * 100, 1)
        return nivel_atins, retragere_pct
    except:
        return None, None

# ═══════════════════════════════════════════════════════════════════════
# 4. DETECTARE SEMNAL FINAL (CORECȚII CLAUDE INTEGRATE)
# ═══════════════════════════════════════════════════════════════════════
def detecteaza_semnal(df, simbol, idx):
    try:
        if len(df) < 410: return None

        # Fix Problema 2: Calculam idx_pozitiv imediat
        idx_pozitiv = idx if idx >= 0 else len(df) + idx

        c  = df.iloc[idx]      # bara 3 - finala
        p1 = df.iloc[idx - 1]  # bara 2
        p2 = df.iloc[idx - 2]  # bara 1

        # Fix Problema 1: Verificam trendul pe 200 de bare cu index pozitiv
        if not (c['ma20'] > c['ma50'] > c['ma200']): return None
        if c['ma200'] <= df.iloc[idx_pozitiv - 200]['ma200']: return None

        if not (c['Close'] > c['Open'] and p1['Close'] > p1['Open'] and p2['Close'] > p2['Open']):
            return None

        margin = 0.3 * p2['atr']
        atinge_ema20 = (p2['Low'] <= p2['ma20'] + margin) and (p2['Low'] >= p2['ma20'] - margin)
        atinge_ema50 = (p2['Low'] <= p2['ma50'] + margin) and (p2['Low'] >= p2['ma50'] - margin)
        if not (atinge_ema20 or atinge_ema50): return None

        if not (c['Close'] > p2['High']): return None
        if (c['Close'] * c['Volume']) < 1_000_000: return None
        if not (40 <= p2['rsi'] <= 55): return None
        if not (1 <= p2['atr'] <= 2.8): return None
        if c['Volume'] < c['vol_ma50']: return None

        # Fix Problema 3: Apel Fibonacci explicit
        idx_bara1 = idx_pozitiv - 2
        nivel_fib, retragere_pct = calculeaza_fibonacci(df, idx_bara1)

        zona_ma   = "EMA20" if atinge_ema20 else "EMA50"
        swing_low = min(c['Low'], p1['Low'], p2['Low'])
        sl        = round(swing_low - (c['atr'] * 0.1), 2)
        risc      = c['Close'] - sl
        if risc <= 0: return None

        return {
            'simbol': simbol,
            'zona': zona_ma,
            'close_azi': round(c['Close'], 2),
            'sl_anticipat': sl,
            'tp1': round(c['Close'] + (risc * 1.5), 2),
            'tp2': round(c['Close'] + (risc * 3.0), 2),
            'sl_pct': round((risc / c['Close']) * 100, 2),
            'rsi': round(p2['rsi'], 1),
            'atr': round(p2['atr'], 4),
            'fib_nivel': nivel_fib if nivel_fib else 'N/A',
            'fib_retragere_pct': retragere_pct if retragere_pct else 'N/A',
            'data_setup': df.index[idx].strftime('%d-%m-%Y %H:%M')
        }
    except Exception as e:
        print(f"[EROARE detecteaza_semnal] {simbol}: {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════
# 5. MAIN SCANNER
# ═══════════════════════════════════════════════════════════════════════
def main():
    import sys
    prima_rulare = '--prima-rulare' in sys.argv

    if not os.path.exists('baza_de_date.json'):
        print("Eroare: Lipseste baza_de_date.json")
        return

    with open('baza_de_date.json', 'r') as f:
        db = json.load(f)

    watchlist = db.get('watchlist_trend_ascendent', [])
    setupuri_active = db.get('setupuri_active', [])
    existente = set(s['simbol'] for s in setupuri_active)

    lookback_idxs = list(range(-200, -1)) if prima_rulare else [-1]
    semnale_noi = []

    for simbol in watchlist:
        if simbol in existente: continue
        try:
            df = yf.Ticker(simbol).history(period="2y", interval="4h")
            if len(df) < 410: continue
            df = calculate_indicators(df)

            for idx in lookback_idxs:
                res = detecteaza_semnal(df, simbol, idx)
                if res:
                    setupuri_active.append(res)
                    semnale_noi.append(res)
                    existente.add(simbol)
                    break
        except:
            continue

    for s in semnale_noi:
        msg = (f"🎯 *SEMNAL CONFIRMAT (3 Verzi + EMA)*\n"
               f"━━━━━━━━━━━━━━━━━━━━━\n"
               f"📊 *Ticker:* `{s['simbol']}`\n"
               f"📅 *DATA CONFIRMARII:* `{s['data_setup']}`\n"
               f"📍 *Bounce la:* {s['zona']}\n"
               f"📐 *Fibonacci:* nivel {s['fib_nivel']} | retragere {s['fib_retragere_pct']}%\n"
               f"━━━━━━━━━━━━━━━━━━━━━\n"
               f"💰 *Pret intrare:* ${s['close_azi']}\n"
               f"🛑 *SL:* ${s['sl_anticipat']} ({s['sl_pct']}%)\n"
               f"🎯 *TP1:* ${s['tp1']} | *TP2:* ${s['tp2']}\n"
               f"━━━━━━━━━━━━━━━━━━━━━\n"
               f"📈 *RSI:* {s['rsi']} | *ATR:* {s['atr']}\n"
               f"✅ *EMA20 > EMA50 > EMA200 ↗*\n"
               f"🕐 *Timeframe:* 4H")
        bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

    if semnale_noi:
        db['setupuri_active'] = setupuri_active
        salveaza_si_commit(db, f"Scan - {datetime.now(TIMEZONE_RO).strftime('%H:%M')}")
    else:
        print(f"[INFO] Niciun semnal nou — {datetime.now(TIMEZONE_RO).strftime('%H:%M')}")

if __name__ == "__main__":
    main()
