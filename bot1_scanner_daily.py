import os
import json
import yfinance as yf
import pandas as pd
import numpy as np
import telebot
import subprocess
from datetime import datetime

# Configurare Bot
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

if not TOKEN or not CHAT_ID:
    print("❌ EROARE CRITICA: Lipsesc variabilele de mediu.")
    exit(1)

bot = telebot.TeleBot(TOKEN)

# ==========================================
# SALVARE SI COMMIT GITHUB
# ==========================================
def salveaza_si_commit(db, mesaj_commit):
    try:
        with open('baza_de_date.json', 'w') as f:
            json.dump(db, f, indent=4)
        
        # Procesul de salvare automata in GitHub pentru persistenta
        subprocess.run(['git', 'config', '--global', 'user.email', 'bot@github.com'])
        subprocess.run(['git', 'config', '--global', 'user.name', 'Trading Bot'])
        subprocess.run(['git', 'add', 'baza_de_date.json'])
        subprocess.run(['git', 'commit', '-m', mesaj_commit])
        subprocess.run(['git', 'push'])
        print(f"[INFO] Commit reusit: {mesaj_commit}")
    except Exception as e:
        print(f"[EROARE commit]: {e}")

# ==========================================
# INDICATORI TEHNICI
# ==========================================
def calculate_indicators(df):
    try:
        df = df.copy()
        # Moving Averages
        df['ma20'] = df['Close'].rolling(window=20).mean()
        df['ma50'] = df['Close'].rolling(window=50).mean()
        df['ma200'] = df['Close'].rolling(window=200).mean()
        
        # RSI
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # ATR pentru Stop Loss volatil
        high_low = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close = (df['Low'] - df['Close'].shift()).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = true_range.ewm(com=13, adjust=False).mean()
        
        # Volum
        df['vol_ma'] = df['Volume'].rolling(window=20).mean()
        
        return df
    except Exception as e:
        print(f"Eroare calcul: {e}")
        return df

# ==========================================
# LOGICA DE DETECTIE PULLBACK
# ==========================================
def detecteaza_pullback(df, simbol):
    try:
        if len(df) < 210: return None

        i = -1 # Folosim ultima lumanare inchisa (Daily)
        c = df.iloc[i]
        prev = df.iloc[i-1]
        
        close, open_, high, low = c['Close'], c['Open'], c['High'], c['Low']
        ma20, ma50, ma200 = c['ma20'], c['ma50'], c['ma200']
        rsi, volume, vol_ma = c['rsi'], c['Volume'], c['vol_ma']

        # 1. TREND: Bullish curat
        trend_ok = close > ma200 and ma50 > ma200 and ma20 > ma50
        if not trend_ok: return None

        # 2. PULLBACK: Pretul a coborat spre MA20 sau MA50
        pullback_ma20 = low <= ma20 * 1.015 and close > ma50
        pullback_ma50 = low <= ma50 * 1.015 and close > ma200
        if not (pullback_ma20 or pullback_ma50): return None

        # 3. CONFLUENTE: RSI intre 40-55 si Volum scazut pe pullback
        if not (40 <= rsi <= 55): return None
        if volume > vol_ma * 1.1: return None # Vrem volum mic, nu panic sale

        # 4. CONFIRMARE: Lumanare bullish (Engulfing sau Rejection)
        is_bullish = close > open_
        rejection = (close - low) > (high - low) * 0.5 # Wick lung jos
        if not (is_bullish or rejection): return None

        # Calcule SL si TP
        zona = "MA20" if pullback_ma20 else "MA50"
        sl = round(min(low, ma50) - (c['atr'] * 0.5), 2)
        distanta_sl = close - sl
        tp1 = round(close + (distanta_sl * 1.5), 2)
        tp2 = round(close + (distanta_sl * 3.0), 2)

        return {
            'simbol': simbol,
            'zona': zona,
            'entry': round(close, 2),
            'sl': sl,
            'tp1': tp1,
            'tp2': tp2,
            'sl_pct': round((sl-close)/close*100, 2),
            'tp1_pct': round((tp1-close)/close*100, 2),
            'tp2_pct': round((tp2-close)/close*100, 2),
            'data_setup': datetime.now().strftime('%Y-%m-%d'),
            'status': 'asteapta_confirmare',
            'tp1_atins': False
        }
    except: return None

# ==========================================
# EXECUTIE
# ==========================================
def main():
    if not os.path.exists('baza_de_date.json'):
        print("Eroare: baza_de_date.json nu exista!")
        return

    with open('baza_de_date.json', 'r') as f:
        db = json.load(f)

    watchlist = db.get('watchlist_trend_ascendent', [])
    setupuri_active = db.get('setupuri_active', [])
    existente = [s['simbol'] for s in setupuri_active]

    print(f"--- Scanare Daily: {len(watchlist)} simboluri ---")
    semnale_noi = []

    for simbol in watchlist:
        if simbol in existente: continue
        
        try:
            df = yf.Ticker(simbol).history(period="1y")
            df = calculate_indicators(df)
            res = detecteaza_pullback(df, simbol)
            
            if res:
                setupuri_active.append(res)
                semnale_noi.append(res)
                print(f"✅ Setup gasit: {simbol}")
        except: continue

    if semnale_noi:
        for s in semnale_noi:
            msg = (
                f"🔍 *SETUP IDENTIFICAT — Daily*\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 *Ticker:* `{s['simbol']}`\n"
                f"🎯 *Pullback la:* {s['zona']}\n"
                f"⏳ *Status:* Așteaptă confirmare 1H\n\n"
                f"💰 *Entry anticipat:* ${s['entry']}\n"
                f"🛑 *SL:* ${s['sl']} ({s['sl_pct']}%)\n"
                f"🎯 *TP1:* ${s['tp1']} (+{s['tp1_pct']}%)\n"
                f"🎯 *TP2:* ${s['tp2']} (+{s['tp2_pct']}%)\n"
                f"━━━━━━━━━━━━━━━━━━━━━"
            )
            bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
        
        db['setupuri_active'] = setupuri_active
        salveaza_si_commit(db, f"Update setups {datetime.now().strftime('%Y-%m-%d')}")
    else:
        print("Niciun setup nou astazi.")

if __name__ == "__main__":
    main()
