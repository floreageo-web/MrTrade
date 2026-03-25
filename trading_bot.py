import os
import json
import yfinance as yf
import pandas as pd
import numpy as np
import telebot
import subprocess
import pytz
import pandas_ta as ta
from datetime import datetime, timedelta
import sys

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
# 1. CURĂȚARE SEMNALE VECHI (FĂRĂ SĂ ATINGEM WATCHLIST-UL)
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
                except: continue
            db[categorie] = noi_semnale
    return db

# ═══════════════════════════════════════════════════════════════════════
# 2. SALVARE ȘI COMMIT GITHUB
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
    except: pass

# ═══════════════════════════════════════════════════════════════════════
# 3. CALCUL INDICATORI
# ═══════════════════════════════════════════════════════════════════════
def calculate_indicators(df):
    try:
        df = df.copy()
        df['ma20']  = ta.ema(df['Close'], length=20)
        df['ma50']  = ta.ema(df['Close'], length=50)
        df['ma200'] = ta.ema(df['Close'], length=200)
        df['rsi']   = ta.rsi(df['Close'], length=14)
        df['atr']   = ta.atr(df['High'], df['Low'], df['Close'], length=14)
        return df
    except: return df

def calculeaza_fibonacci(df, idx_ref):
    try:
        fereastra = df.iloc[idx_ref - 50 : idx_ref]
        s_high, s_low = fereastra['High'].max(), df.iloc[idx_ref]['Low']
        if s_high <= s_low: return "N/A"
        amp = s_high - s_low
        niveluri = {'0.236': s_high - amp*0.236, '0.382': s_high - amp*0.382, '0.500': s_high - amp*0.5, '0.618': s_high - amp*0.618}
        nivel = min(niveluri.items(), key=lambda x: abs(s_low - x[1]))[0]
        return nivel
    except: return "N/A"

# ═══════════════════════════════════════════════════════════════════════
# 4. STRATEGII (3 VERZI & CIOCAN VERDE + PREȚ > EMA20)
# ═══════════════════════════════════════════════════════════════════════
def detecteaza_semnal(df, simbol, idx):
    try:
        c, p1, p2 = df.iloc[idx], df.iloc[idx-1], df.iloc[idx-2]
        # TREND & PREȚ PESTE EMA 20
        if not (c['Close'] > c['ma20'] > c['ma50'] > c['ma200']): return None
        # 3 VERZI
        if not (c['Close'] > c['Open'] and p1['Close'] > p1['Open'] and p2['Close'] > p2['Open']): return None
        
        sl = round(min(c['Low'], p1['Low'], p2['Low']) - (c['atr'] * 0.1), 2)
        return {
            'tip': '3_VERZI', 'simbol': simbol, 'close_azi': round(c['Close'], 2), 
            'sl_anticipat': sl, 'ema20': round(c['ma20'], 2), 'ema50': round(c['ma50'], 2),
            'fib_nivel': calculeaza_fibonacci(df, idx-2), 'data_setup': df.index[idx].strftime('%d-%m-%Y %H:%M')
        }
    except: return None

def detecteaza_ciocan(df, simbol, idx):
    try:
        c = df.iloc[idx]
        # TREND & PREȚ PESTE EMA 20 & DOAR VERDE
        if not (c['Close'] > c['ma20'] > c['ma50'] > c['ma200']): return None
        if not (c['Close'] > c['Open']): return None
        
        corp = abs(c['Close'] - c['Open'])
        if corp <= 0 or (c['Open'] - c['Low']) < 2 * corp: return None
        
        return {
            'tip': 'CIOCAN', 'simbol': simbol, 'close_azi': round(c['Close'], 2), 
            'sl_anticipat': round(c['Low'] - (c['atr']*0.1), 2), 'ema20': round(c['ma20'], 2), 
            'ema50': round(c['ma50'], 2), 'fib_nivel': calculeaza_fibonacci(df, idx), 
            'data_setup': df.index[idx].strftime('%d-%m-%Y %H:%M')
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

    for simbol in watchlist:
        try:
            df = yf.Ticker(simbol).history(period="2y", interval="4h")
            if len(df) < 410: continue
            df = calculate_indicators(df)

            if simbol not in existente_3v:
                res = detecteaza_semnal(df, simbol, -1)
                if res: 
                    setupuri_active.append(res); semnale_noi.append(res); existente_3v.add(simbol)

            if simbol not in existente_ciocan:
                res = detecteaza_ciocan(df, simbol, -1)
                if res: 
                    ciocan_active.append(res); semnale_noi.append(res); existente_ciocan.add(simbol)
        except: continue

    for s in semnale_noi:
        msg = (f"🎯 *SEMNAL NOU ({s['tip']})*\n"
               f"📊 *Ticker:* `{s['simbol']}`\n"
               f"💰 *Pret:* ${s['close_azi']} | *SL:* ${s['sl_anticipat']}\n"
               f"📈 *EMA20:* ${s['ema20']} | *EMA50:* ${s['ema50']}\n"
               f"📐 *Fib:* {s['fib_nivel']}\n"
               f"📅 *Data:* {s['data_setup']}")
        bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

    if semnale_noi:
        db['setupuri_active'], db['ciocan_active'] = setupuri_active, ciocan_active
        salveaza_si_commit(db, f"Scan - {datetime.now(TIMEZONE_RO).strftime('%H:%M')}")

if __name__ == "__main__":
    main()
