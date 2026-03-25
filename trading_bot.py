import os
import json
import yfinance as yf
import pandas as pd
import numpy as np
import telebot
import subprocess
import pytz
from datetime import datetime, timedelta
import logging

# Configurare logging pentru monitorizare în GitHub Actions
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ===============================
# CONFIGURARE
# ===============================
TOKEN   = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

if not TOKEN or not CHAT_ID:
    logging.error("Lipsesc variabilele de mediu TELEGRAM_TOKEN sau TELEGRAM_CHAT_ID")
    exit(1)

bot = telebot.TeleBot(TOKEN)
TIMEZONE_RO = pytz.timezone('Europe/Bucharest')

# ═══════════════════════════════════════════════════════════════════════
# 1. CURĂȚARE SEMNALE VECHI (WATCHLIST-UL RĂMÂNE INTACT)
# ═══════════════════════════════════════════════════════════════════════
def curata_semnale_vechi(db, zile_limita=10):
    acum = datetime.now(TIMEZONE_RO)
    for categorie in ['setupuri_active', 'ciocan_active']:
        if categorie in db:
            noi_semnale = []
            for s in db[categorie]:
                try:
                    data_s = datetime.strptime(s['data_setup'], '%d-%m-%Y %H:%M')
                    data_s = TIMEZONE_RO.localize(data_s)
                    if (acum - data_s).days < zile_limita:
                        noi_semnale.append(s)
                except Exception as e:
                    logging.warning(f"Eroare curatare {s.get('simbol')}: {e}")
                    continue
            db[categorie] = noi_semnale
    return db

# ═══════════════════════════════════════════════════════════════════════
# 2. GITHUB AUTO-SAVE
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
            subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'])
            subprocess.run(['git', 'push'])
            logging.info("Baza de date actualizata pe GitHub.")
    except Exception as e:
        logging.error(f"Eroare GitHub Commit: {e}")

# ═══════════════════════════════════════════════════════════════════════
# 3. CALCUL INDICATORI (FĂRĂ LIBRĂRII EXTRA)
# ═══════════════════════════════════════════════════════════════════════
def calculate_indicators(df):
    try:
        df = df.copy()
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')

        # EMA 20, 50, 200
        df['ma20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['ma50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['ma200'] = df['Close'].ewm(span=200, adjust=False).mean()
        
        # RSI (Standard 14)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss.replace(0, 0.00001))
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # ATR (Standard 14)
        tr = pd.concat([
            df['High'] - df['Low'],
            (df['High'] - df['Close'].shift()).abs(),
            (df['Low'] - df['Close'].shift()).abs()
        ], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=14).mean()
        
        return df
    except Exception as e:
        logging.error(f"Eroare indicatori: {e}")
        return None

def calculeaza_fibonacci(df, idx):
    try:
        start_idx = max(0, idx - 50)
        fereastra = df.iloc[start_idx:idx]
        s_high = fereastra['High'].max()
        s_low = df.iloc[idx]['Low']
        if s_high <= s_low: return "N/A"
        amp = s_high - s_low
        niveluri = {'0.236': s_high - amp*0.236, '0.382': s_high - amp*0.382, '0.500': s_high - amp*0.5, '0.618': s_high - amp*0.618}
        return min(niveluri.items(), key=lambda x: abs(s_low - x[1]))[0]
    except: return "N/A"

# ═══════════════════════════════════════════════════════════════════════
# 4. STRATEGII CU FILTRELE DIN ULTIMELE 5 LUNI
# ═══════════════════════════════════════════════════════════════════════
def detecteaza_semnal(df, simbol, idx):
    try:
        if idx < 2: return None
        c, p1, p2 = df.iloc[idx], df.iloc[idx-1], df.iloc[idx-2]
        
        # 1. TREND & PREȚ PESTE EMA 20
        if not (c['Close'] > c['ma20'] > c['ma50'] > c['ma200']): return None
        
        # 2. CELE 3 LUMÂNĂRI VERZI
        if not (c['Close'] > c['Open'] and p1['Close'] > p1['Open'] and p2['Close'] > p2['Open']): return None
        
        # 3. FILTRELE DE AUR (RSI & ATR)
        if not (40 <= p2['rsi'] <= 55): return None
        if not (1 <= p2['atr'] <= 2.8): return None
        
        data_local = df.index[idx].tz_convert(TIMEZONE_RO).strftime('%d-%m-%Y %H:%M')
        sl = round(min(c['Low'], p1['Low'], p2['Low']) - (c['atr'] * 0.1), 2)
        
        return {
            'tip': '3_VERZI', 'simbol': simbol, 'close_azi': round(c['Close'], 2), 
            'sl_anticipat': sl, 'ema20': round(c['ma20'], 2), 'ema50': round(c['ma50'], 2),
            'fib_nivel': calculeaza_fibonacci(df, idx-2), 'data_setup': data_local
        }
    except: return None

def detecteaza_ciocan(df, simbol, idx):
    try:
        c = df.iloc[idx]
        
        # 1. TREND & PREȚ PESTE EMA 20 & DOAR VERDE
        if not (c['Close'] > c['ma20'] > c['ma50'] > c['ma200']): return None
        if not (c['Close'] > c['Open']): return None
        
        # 2. FILTRELE DE AUR (RSI & ATR)
        if not (40 <= c['rsi'] <= 55): return None
        if not (1 <= c['atr'] <= 2.8): return None
        
        # 3. FORMĂ CIOCAN
        corp = abs(c['Close'] - c['Open'])
        if corp <= 0 or (c['Open'] - c['Low']) < 2 * corp: return None
        
        data_local = df.index[idx].tz_convert(TIMEZONE_RO).strftime('%d-%m-%Y %H:%M')
        return {
            'tip': 'CIOCAN', 'simbol': simbol, 'close_azi': round(c['Close'], 2), 
            'sl_anticipat': round(c['Low'] - (c['atr'] * 0.1), 2), 'ema20': round(c['ma20'], 2), 
            'ema50': round(c['ma50'], 2), 'fib_nivel': calculeaza_fibonacci(df, idx), 
            'data_setup': data_local
        }
    except: return None

# ═══════════════════════════════════════════════════════════════════════
# 5. MAIN
# ═══════════════════════════════════════════════════════════════════════
def main():
    if not os.path.exists('baza_de_date.json'): return
    with open('baza_de_date.json', 'r') as f:
        db = json.load(f)

    db = curata_semnale_vechi(db)
    watchlist = db.get('watchlist_trend_ascendent', [])
    setupuri_active = db.get('setupuri_active', [])
    ciocan_active = db.get('ciocan_active', [])

    existente_3v = set(s['simbol'] for s in setupuri_active)
    existente_ciocan = set(s['simbol'] for s in ciocan_active)
    semnale_noi = []

    logging.info(f"Pornire scanare pentru {len(watchlist)} simboluri...")

    for simbol in watchlist:
        try:
            df = yf.Ticker(simbol).history(period="2y", interval="4h")
            if len(df) < 200: continue
            
            df = calculate_indicators(df)
            if df is None: continue

            # Verificare 3 Verzi
            if simbol not in existente_3v:
                res = detecteaza_semnal(df, simbol, -1)
                if res:
                    setupuri_active.append(res); semnale_noi.append(res); existente_3v.add(simbol)

            # Verificare Ciocan
            if simbol not in existente_ciocan:
                res = detecteaza_ciocan(df, simbol, -1)
                if res:
                    ciocan_active.append(res); semnale_noi.append(res); existente_ciocan.add(simbol)
        except Exception as e:
            logging.error(f"Eroare {simbol}: {e}")
            continue

    # Trimitere mesaje Telegram
    for s in semnale_noi:
        msg = (f"🎯 *SEMNAL NOU ({s['tip']})*\n"
               f"📊 *Ticker:* `{s['simbol']}`\n"
               f"💰 *Pret:* ${s['close_azi']} | *SL:* ${s['sl_anticipat']}\n"
               f"📈 *EMA20:* ${s['ema20']} | *EMA50:* ${s['ema50']}\n"
               f"📐 *Fib:* {s['fib_nivel']}\n"
               f"📅 *Data:* {s['data_setup']}")
        try:
            bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
        except: pass

    if semnale_noi:
        db['setupuri_active'], db['ciocan_active'] = setupuri_active, ciocan_active
        salveaza_si_commit(db, f"Scan {datetime.now(TIMEZONE_RO).strftime('%H:%M')}")
    else:
        logging.info("Scanare finalizata. Niciun semnal nou conform strategiei.")

if __name__ == "__main__":
    main()
