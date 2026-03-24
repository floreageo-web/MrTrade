import os
import json
import yfinance as yf
import pandas as pd
import numpy as np
import telebot
import subprocess
import pytz
import sys
from datetime import datetime

# ===============================
# CONFIGURARE
# ===============================
TOKEN  = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

if not TOKEN or not CHAT_ID:
    print("❌ EROARE: Lipsesc variabilele de mediu.")
    exit(1)

bot = telebot.TeleBot(TOKEN)
TIMEZONE_RO = pytz.timezone('Europe/Bucharest')

# 1. SALVARE + GIT COMMIT
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
    except Exception as e:
        print(f"[EROARE commit]: {e}")

# 2. CALCUL INDICATORI TEHNICI
def calculate_indicators(df):
    try:
        df = df.copy()
        df['ma20']  = df['Close'].ewm(span=20, adjust=False).mean()
        df['ma50']  = df['Close'].ewm(span=50, adjust=False).mean()
        df['ma200'] = df['Close'].ewm(span=200, adjust=False).mean()
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))
        true_range = pd.concat([
            df['High'] - df['Low'],
            (df['High'] - df['Close'].shift()).abs(),
            (df['Low']  - df['Close'].shift()).abs()
        ], axis=1).max(axis=1)
        df['atr'] = true_range.ewm(com=13, adjust=False).mean()
        df['vol_ma50'] = df['Volume'].rolling(window=50).mean()
        return df
    except: return df

# 3. CALCUL FIBONACCI
def calculeaza_fibonacci(df, idx_referinta):
    try:
        fereastra = df.iloc[idx_referinta - 50 : idx_referinta]
        swing_high = fereastra['High'].max()
        swing_low = df.iloc[idx_referinta]['Low']
        if swing_high <= swing_low: return None, None
        amplitudine = swing_high - swing_low
        niveluri = {'0.236': swing_high - amplitudine * 0.236, '0.382': swing_high - amplitudine * 0.382, '0.500': swing_high - amplitudine * 0.500, '0.618': swing_high - amplitudine * 0.618}
        cel_mai_apropiat = min(niveluri.items(), key=lambda x: abs(swing_low - x[1]))
        return f"~{cel_mai_apropiat[0]}", round((amplitudine / swing_high) * 100, 1)
    except: return None, None

# 4. STRATEGIE: 3 BARE VERZI
def detecteaza_semnal(df, simbol, idx):
    try:
        if len(df) < 410: return None
        c = df.iloc[idx]
        p1 = df.iloc[idx - 1]
        p2 = df.iloc[idx - 2]
        if not (c['ma20'] > c['ma50'] > c['ma200']): return None
        if not (c['Close'] > c['Open'] and p1['Close'] > p1['Open'] and p2['Close'] > p2['Open']): return None
        margin = 0.3 * p2['atr']
        if not ((abs(p2['Low'] - p2['ma20']) <= margin) or (abs(p2['Low'] - p2['ma50']) <= margin)): return None
        if not (c['Close'] > p2['High']): return None
        if (c['Close'] * c['Volume']) < 1_000_000: return None
        if not (40 <= p2['rsi'] <= 55) or not (1 <= p2['atr'] <= 2.8): return None
        if c['Volume'] < c['vol_ma50']: return None
        nivel_fib, retragere_pct = calculeaza_fibonacci(df, idx if idx >= 0 else len(df) + idx)
        sl = round(min(c['Low'], p1['Low'], p2['Low']) - (c['atr'] * 0.1), 2)
        risc = c['Close'] - sl
        return {'tip': '3_VERZI', 'simbol': simbol, 'close_azi': round(c['Close'], 2), 'sl': sl, 'tp1': round(c['Close'] + risc*1.5, 2), 'tp2': round(c['Close'] + risc*3, 2), 'data': df.index[idx].strftime('%d-%m %H:%M')}
    except: return None

# 6. MAIN SCANNER
def main():
    if not os.path.exists('baza_de_date.json'): return
    with open('baza_de_date.json', 'r') as f: db = json.load(f)
    
    watchlist = db.get('watchlist_trend_ascendent', [])
    setupuri_active = db.get('setupuri_active', [])
    existente = set(s['simbol'] for s in setupuri_active)

    semnale_noi = []
    for simbol in watchlist:
        try:
            df = yf.Ticker(simbol).history(period="2y", interval="4h")
            if len(df) < 10: continue
            df = calculate_indicators(df)
            if simbol not in existente:
                res = detecteaza_semnal(df, simbol, -1)
                if res:
                    setupuri_active.append(res)
                    semnale_noi.append(res)
        except: continue

    for s in semnale_noi:
        msg = f"🎯 *3 VERZI CONFIRMAT*\nTicker: `{s['simbol']}`\nPret: ${s['close_azi']}\nSL: ${s['sl']}\nTP1: ${s['tp1']}"
        bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

    if semnale_noi:
        db['setupuri_active'] = setupuri_active
        salveaza_si_commit(db, f"Scan 20:45 - {len(semnale_noi)} noi")

if __name__ == "__main__":
    main()
