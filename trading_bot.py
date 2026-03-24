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
def calculeaza_fibonacci(df, idx_referinta):
    try:
        fereastra  = df.iloc[idx_referinta - 50 : idx_referinta]
        swing_high = fereastra['High'].max()
        swing_low  = df.iloc[idx_referinta]['Low']

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
# 4. STRATEGIE: 3 BARE VERZI
# ═══════════════════════════════════════════════════════════════════════
def detecteaza_semnal(df, simbol, idx):
    try:
        if len(df) < 410: return None
        idx_pozitiv = idx if idx >= 0 else len(df) + idx

        c  = df.iloc[idx]
        p1 = df.iloc[idx - 1]
        p2 = df.iloc[idx - 2] # Bara 1

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

        nivel_fib, retragere_pct = calculeaza_fibonacci(df, idx_pozitiv - 2)

        zona_ma   = "EMA20" if atinge_ema20 else "EMA50"
        swing_low = min(c['Low'], p1['Low'], p2['Low'])
        sl         = round(swing_low - (c['atr'] * 0.1), 2)
        risc      = c['Close'] - sl
        if risc <= 0: return None

        return {
            'tip': '3_VERZI',
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
    except:
        return None

# ═══════════════════════════════════════════════════════════════════════
# 5. STRATEGIE: CIOCAN (HAMMER)
# ═══════════════════════════════════════════════════════════════════════
def detecteaza_ciocan(df, simbol, idx):
    try:
        if len(df) < 410: return None
        idx_pozitiv = idx if idx >= 0 else len(df) + idx
        c = df.iloc[idx]

        if not (c['ma20'] > c['ma50'] > c['ma200']): return None
        if c['ma200'] <= df.iloc[idx_pozitiv - 200]['ma200']: return None

        corp      = abs(c['Close'] - c['Open'])
        fitil_jos = min(c['Open'], c['Close']) - c['Low']
        fitil_sus = c['High'] - max(c['Open'], c['Close'])

        if corp <= 0: return None
        if fitil_jos < 2 * corp: return None
        if fitil_sus > 0.1 * corp: return None

        margin = 0.3 * c['atr']
        atinge_ema20 = (c['Low'] <= c['ma20'] + margin) and (c['Low'] >= c['ma20'] - margin)
        atinge_ema50 = (c['Low'] <= c['ma50'] + margin) and (c['Low'] >= c['ma50'] - margin)
        if not (atinge_ema20 or atinge_ema50): return None

        if (c['Close'] * c['Volume']) < 1_000_000: return None
        if not (40 <= c['rsi'] <= 55): return None
        if not (1 <= c['atr'] <= 2.8): return None
        if c['Volume'] < c['vol_ma50']: return None

        nivel_fib, retragere_pct = calculeaza_fibonacci(df, idx_pozitiv)

        zona_ma = "EMA20" if atinge_ema20 else "EMA50"
        sl      = round(c['Low'] - (c['atr'] * 0.1), 2)
        risc    = c['Close'] - sl
        if risc <= 0: return None

        return {
            'tip': 'CIOCAN',
            'simbol': simbol,
            'zona': zona_ma,
            'close_azi': round(c['Close'], 2),
            'sl_anticipat': sl,
            'tp1': round(c['Close'] + (risc * 1.5), 2),
            'tp2': round(c['Close'] + (risc * 3.0), 2),
            'sl_pct': round((risc / c['Close']) * 100, 2),
            'rsi': round(c['rsi'], 1),
            'atr': round(c['atr'], 4),
            'fib_nivel': nivel_fib if nivel_fib else 'N/A',
            'fib_retragere_pct': retragere_pct if retragere_pct else 'N/A',
            'data_setup': df.index[idx].strftime('%d-%m-%Y %H:%M')
        }
    except:
        return None

# ═══════════════════════════════════════════════════════════════════════
# 6. MAIN SCANNER
# ═══════════════════════════════════════════════════════════════════════
def main():
    import sys
    prima_rulare = '--prima-rulare' in sys.argv

    if not os.path.exists('baza_de_date.json'):
        print("Eroare: Lipseste baza_de_date.json")
        return

    with open('baza_de_date.json', 'r') as f:
        db = json.load(f)

    watchlist        = db.get('watchlist_trend_ascendent', [])
    setupuri_active  = db.get('setupuri_active', [])
    ciocan_active    = db.get('ciocan_active', [])

    existente_3v     = set(s['simbol'] for s in setupuri_active)
    existente_ciocan = set(s['simbol'] for s in ciocan_active)

    lookback_3v      = list(range(-200, 0)) if prima_rulare else [-1]
    lookback_ciocan  = list(range(-30, 0)) # Ultimele 5 zile bursiere

    semnale_noi = []
    ciocan_noi  = []

    print(f"[INFO] Scanare pornita la {datetime.now(TIMEZONE_RO).strftime('%d-%m-%Y %H:%M')}")

    for simbol in watchlist:
        try:
            df = yf.Ticker(simbol).history(period="2y", interval="4h")
            if len(df) < 410: continue
            df = calculate_indicators(df)

            # --- SCAN 3 VERZI ---
            if simbol not in existente_3v:
                for idx in lookback_3v:
                    res = detecteaza_semnal(df, simbol, idx)
                    if res:
                        setupuri_active.append(res)
                        semnale_noi.append(res)
                        existente_3v.add(simbol)
                        break

            # --- SCAN CIOCAN ---
            if simbol not in existente_ciocan:
                for idx in lookback_ciocan:
                    res = detecteaza_ciocan(df, simbol, idx)
                    if res:
                        ciocan_active.append(res)
                        ciocan_noi.append(res)
                        existente_ciocan.add(simbol)
                        break

        except Exception as e:
            print(f"[EROARE] {simbol}: {e}")
            continue

    # --- TELEGRAM ---
    for s in semnale_noi:
        msg = (f"🎯 *SEMNAL CONFIRMAT (3 Verzi)*\n"
               f"━━━━━━━━━━━━━━━━━━━━━\n"
               f"📊 *Ticker:* `{s['simbol']}`\n"
               f"📅 *Data:* `{s['data_setup']}`\n"
               f"📍 *Bounce la:* {s['zona']}\n"
               f"📐 *Fibonacci:* nivel {s['fib_nivel']}\n"
               f"💰 *Pret:* ${s['close_azi']} | *SL:* ${s['sl_anticipat']}")
        bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

    for s in ciocan_noi:
        msg = (f"🔨 *SEMNAL CIOCAN (Hammer)*\n"
               f"━━━━━━━━━━━━━━━━━━━━━\n"
               f"📊 *Ticker:* `{s['simbol']}`\n"
               f"📅 *Data:* `{s['data_setup']}`\n"
               f"📍 *Bounce la:* {s['zona']}\n"
               f"📐 *Fibonacci:* nivel {s['fib_nivel']}\n"
               f"💰 *Pret:* ${s['close_azi']} | *SL:* ${s['sl_anticipat']}")
        bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

    if semnale_noi or ciocan_noi:
        db['setupuri_active'] = setupuri_active
        db['ciocan_active']   = ciocan_active
        salveaza_si_commit(db, f"Scan - {datetime.now(TIMEZONE_RO).strftime('%H:%M')}")

if __name__ == "__main__":
    main()
