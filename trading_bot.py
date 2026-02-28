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
        subprocess.run(['git', 'commit', '-m', mesaj_commit])
        subprocess.run(['git', 'push'])
        print(f"[INFO] Commit reusit: {mesaj_commit}")
    except Exception as e:
        print(f"[EROARE commit]: {e}")

# ═══════════════════════════════════════════════════════════════════════
# 2. CALCUL INDICATORI TEHNICI
# ═══════════════════════════════════════════════════════════════════════
def calculate_indicators(df):
    try:
        df = df.copy()
        df['ma20']  = df['Close'].rolling(window=20).mean()
        df['ma50']  = df['Close'].rolling(window=50).mean()
        df['ma200'] = df['Close'].rolling(window=200).mean()
        
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))

        true_range = pd.concat([df['High']-df['Low'], (df['High']-df['Close'].shift()).abs(), (df['Low']-df['Close'].shift()).abs()], axis=1).max(axis=1)
        df['atr'] = true_range.ewm(com=13, adjust=False).mean()
        df['vol_ma'] = df['Volume'].rolling(window=120).mean()
        return df
    except Exception as e:
        return df

# ═══════════════════════════════════════════════════════════════════════
# 3. DETECTARE PULLBACK (Strategia 3 Verzi + Breakout Wick)
# ═══════════════════════════════════════════════════════════════════════
def detecteaza_pullback(df, simbol, idx):
    try:
        if len(df) < 210 or idx < -4: return None

        # Identificăm lumânările:
        # c (actuala), p1 (anterioara), p2 (prima verde din grup)
        c  = df.iloc[idx]
        p1 = df.iloc[idx - 1]
        p2 = df.iloc[idx - 2]
        
        # 1. LICHIDITATE (> 1M$)
        if (c['Close'] * c['Volume']) < 1_000_000: return None

        # 2. RSI (40 - 55)
        if not (40 <= c['rsi'] <= 55): return None

        # 3. CELE 3 BARE VERZI CONSECUTIVE
        trei_verzi = (c['Close'] > c['Open']) and (p1['Close'] > p1['Open']) and (p2['Close'] > p2['Open'])
        if not trei_verzi: return None

        # 4. CONDITIA TA: Close(3) > High(1)
        if not (c['Close'] > p2['High']): return None

        # 5. VERIFICARE TEST MEDIE (MA20 sau MA50) - oricare din cele 3 bare
        atins_ma = False
        zona_ma = ""
        for bar in [p2, p1, c]:
            margin = 0.2 * bar['atr']
            if (bar['Low'] <= bar['ma20'] + margin) or (bar['Low'] <= bar['ma50'] + margin):
                atins_ma = True
                zona_ma = "MA20/50"
                break
        if not atins_ma: return None

        # 6. MANAGEMENT RISC
        swing_low = min(c['Low'], p1['Low'], p2['Low'])
        sl = round(swing_low - (c['atr'] * 0.1), 2)
        risc = c['Close'] - sl
        if risc <= 0: return None

        return {
            'simbol': simbol,
            'zona': zona_ma,
            'close_azi': round(c['Close'], 2),
            'sl_anticipat': sl,
            'tp1': round(c['Close'] + (risc * 1.5), 2),
            'tp2': round(c['Close'] + (risc * 3.0), 2),
            'sl_pct': round((risc / c['Close']) * 100, 2),
            'rsi': round(c['rsi'], 1),
            'data_setup': df.index[idx].strftime('%Y-%m-%d %H:%M')
        }
    except:
        return None

# ═══════════════════════════════════════════════════════════════════════
# 4. MAIN SCANNER
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
    
    lookback_idxs = list(range(-30, 0)) if prima_rulare else [-1]
    semnale_noi = []

    for simbol in watchlist:
        if simbol in existente: continue
        try:
            df = yf.Ticker(simbol).history(period="2y", interval="4h")
            if len(df) < 210: continue
            df = calculate_indicators(df)

            for idx in lookback_idxs:
                res = detecteaza_pullback(df, simbol, idx)
                if res:
                    setupuri_active.append(res)
                    semnale_noi.append(res)
                    existente.add(simbol)
                    break
        except: continue

    if semnale_noi:
        for s in semnale_noi:
            msg = (f"🎯 *CONFIRMARE STRATEGIE (3 Verzi)*\n"
                   f"📊 *Ticker:* `{s['simbol']}`\n"
                   f"💰 *Pret:* ${s['close_azi']} (Breakout High ✅)\n"
                   f"🛑 *SL:* ${s['sl_anticipat']} ({s['sl_pct']}%)\n"
                   f"🎯 *TP1:* ${s['tp1']} | *TP2:* ${s['tp2']}\n"
                   f"📈 *RSI:* {s['rsi']} | 4H Timeframe")
            bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
        
        db['setupuri_active'] = setupuri_active
        salveaza_si_commit(db, f"Scan 317 - {datetime.now(TIMEZONE_RO).strftime('%H:%M')}")

if __name__ == "__main__":
    main()
