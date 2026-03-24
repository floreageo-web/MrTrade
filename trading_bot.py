import os
import json
import yfinance as yf
import pandas as pd
import numpy as np
import telebot
import subprocess
import pytz
from datetime import datetime, timedelta

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
# 1. CURĂȚARE SEMNALE VECHI (FĂRĂ A ATINGE WATCHLIST-UL)
# ═══════════════════════════════════════════════════════════════════════
def curata_semnale_vechi(db):
    acum = datetime.now(TIMEZONE_RO)
    limita_zile = 7
    
    # Curățăm DOAR listele de semnale, NU și watchlist-ul de 317
    for categorie in ['setupuri_active', 'ciocan_active']:
        if categorie in db:
            noi_semnale = []
            for s in db[categorie]:
                try:
                    # Format dată: 25-03-2026 01:02
                    data_s = datetime.strptime(s['data_setup'], '%d-%m-%Y %H:%M')
                    data_s = TIMEZONE_RO.localize(data_s)
                    
                    if (acum - data_s).days < limita_zile:
                        noi_semnale.append(s)
                except:
                    noi_semnale.append(s) # Păstrăm dacă formatul e vechi/greșit
            db[categorie] = noi_semnale
    return db

# ═══════════════════════════════════════════════════════════════════════
# 2. SALVARE SIGURĂ (ANTI-CONFLICT GITHUB)
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
            # Rebase trage datele noi (cele 317 acțiuni) înainte de a urca semnalele noi
            subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'])
            subprocess.run(['git', 'push'])
            print(f"[INFO] Salvare reușită: {mesaj_commit}")
        else:
            print("[INFO] Nimic nou de salvat.")
    except Exception as e:
        print(f"[EROARE SALVARE]: {e}")

# ═══════════════════════════════════════════════════════════════════════
# 3. CALCUL INDICATORI & FIBONACCI (LOGICA TA ORIGINALĂ)
# ═══════════════════════════════════════════════════════════════════════
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
        tr = pd.concat([df['High']-df['Low'], (df['High']-df['Close'].shift()).abs(), (df['Low']-df['Close'].shift()).abs()], axis=1).max(axis=1)
        df['atr'] = tr.ewm(com=13, adjust=False).mean()
        df['vol_ma50'] = df['Volume'].rolling(window=50).mean()
        return df
    except: return df

def calculeaza_fibonacci(df, idx_ref):
    try:
        fereastra = df.iloc[idx_ref - 50 : idx_ref]
        s_high, s_low = fereastra['High'].max(), df.iloc[idx_ref]['Low']
        if s_high <= s_low: return None, None
        amp = s_high - s_low
        niveluri = {'0.236': s_high - amp*0.236, '0.382': s_high - amp*0.382, '0.500': s_high - amp*0.5, '0.618': s_high - amp*0.618, '0.786': s_high - amp*0.786}
        nivel_atins = min(niveluri.items(), key=lambda x: abs(s_low - x[1]))[0]
        retr_pct = round((amp / s_high) * 100, 1)
        return nivel_atins, retr_pct
    except: return None, None

# ═══════════════════════════════════════════════════════════════════════
# 4. STRATEGII (3 VERZI & CIOCAN)
# ═══════════════════════════════════════════════════════════════════════
def detecteaza_semnal(df, simbol, idx):
    try:
        if len(df) < 410: return None
        idx_p = idx if idx >= 0 else len(df) + idx
        c, p1, p2 = df.iloc[idx], df.iloc[idx-1], df.iloc[idx-2]
        if not (c['ma20'] > c['ma50'] > c['ma200']): return None
        if not (c['Close'] > c['Open'] and p1['Close'] > p1['Open'] and p2['Close'] > p2['Open']): return None
        margin = 0.3 * p2['atr']
        if not ((p2['Low'] <= p2['ma20'] + margin and p2['Low'] >= p2['ma20'] - margin) or (p2['Low'] <= p2['ma50'] + margin and p2['Low'] >= p2['ma50'] - margin)): return None
        if not (40 <= p2['rsi'] <= 55 and 1 <= p2['atr'] <= 2.8): return None
        if (c['Close'] * c['Volume']) < 1000000: return None
        n_fib, r_pct = calculeaza_fibonacci(df, idx_p - 2)
        sl = round(min(c['Low'], p1['Low'], p2['Low']) - (c['atr'] * 0.1), 2)
        return {'tip': '3_VERZI', 'simbol': simbol, 'zona': "EMA", 'close_azi': round(c['Close'], 2), 'sl_anticipat': sl, 'fib_nivel': n_fib, 'data_setup': df.index[idx].strftime('%d-%m-%Y %H:%M')}
    except: return None

def detecteaza_ciocan(df, simbol, idx):
    try:
        c = df.iloc[idx]
        if not (c['ma20'] > c['ma50'] > c['ma200']): return None
        corp = abs(c['Close'] - c['Open'])
        if corp <= 0 or (min(c['Open'], c['Close']) - c['Low']) < 2 * corp: return None
        if not (40 <= c['rsi'] <= 55): return None
        n_fib, r_pct = calculeaza_fibonacci(df, idx if idx >= 0 else len(df)+idx)
        return {'tip': 'CIOCAN', 'simbol': simbol, 'zona': "EMA", 'close_azi': round(c['Close'], 2), 'sl_anticipat': round(c['Low'] - (c['atr']*0.1), 2), 'fib_nivel': n_fib, 'data_setup': df.index[idx].strftime('%d-%m-%Y %H:%M')}
    except: return None

# ═══════════════════════════════════════════════════════════════════════
# 5. MAIN
# ═══════════════════════════════════════════════════════════════════════
def main():
    if not os.path.exists('baza_de_date.json'): return
    with open('baza_de_date.json', 'r') as f:
        db = json.load(f)

    # 1. Curățăm semnalele mai vechi de 7 zile (nu afectează Watchlist-ul)
    db = curata_semnale_vechi(db)
    
    watchlist = db.get('watchlist_trend_ascendent', [])
    setupuri_active = db.get('setupuri_active', [])
    ciocan_active = db.get('ciocan_active', [])

    existente_3v = set(s['simbol'] for s in setupuri_active)
    existente_ciocan = set(s['simbol'] for s in ciocan_active)

    semnale_noi, ciocan_noi = [], []

    for simbol in watchlist:
        try:
            df = yf.Ticker(simbol).history(period="2y", interval="4h")
            if len(df) < 410: continue
            df = calculate_indicators(df)

            if simbol not in existente_3v:
                res = detecteaza_semnal(df, simbol, -1)
                if res:
                    setupuri_active.append(res)
                    semnale_noi.append(res)
                    existente_3v.add(simbol)

            if simbol not in existente_ciocan:
                res = detecteaza_ciocan(df, simbol, -1)
                if res:
                    ciocan_active.append(res)
                    ciocan_noi.append(res)
                    existente_ciocan.add(simbol)
        except: continue

    # Trimitere Telegram
    for s in semnale_noi + ciocan_noi:
        msg = f"🎯 *SEMNAL NOU ({s['tip']})*\n📊 *Ticker:* `{s['simbol']}`\n💰 *Pret:* ${s['close_azi']} | *SL:* ${s['sl_anticipat']}\n📐 *Fib:* {s['fib_nivel']}"
        bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

    if semnale_noi or ciocan_noi:
        db['setupuri_active'] = setupuri_active
        db['ciocan_active'] = ciocan_active
        salveaza_si_commit(db, f"Scan - {datetime.now(TIMEZONE_RO).strftime('%H:%M')}")

if __name__ == "__main__":
    main()
