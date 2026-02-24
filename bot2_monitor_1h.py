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
        subprocess.run(['git', 'config', '--global', 'user.email', 'bot@github.com'])
        subprocess.run(['git', 'config', '--global', 'user.name', 'Trading Bot'])
        subprocess.run(['git', 'add', 'baza_de_date.json'])
        subprocess.run(['git', 'commit', '-m', mesaj_commit])
        subprocess.run(['git', 'push'])
        print(f"[INFO] Update baza de date: {mesaj_commit}")
    except Exception as e:
        print(f"[EROARE commit]: {e}")

# ==========================================
# MONITORIZARE NIVELE (1H)
# ==========================================
def ruleaza_monitor_1h():
    if not os.path.exists('baza_de_date.json'): return
    
    with open('baza_de_date.json', 'r') as f:
        db = json.load(f)

    setupuri_active = db.get('setupuri_active', [])
    istoric = db.get('istoric_trades', [])
    
    if not setupuri_active:
        print("Nicio pozitie activa de monitorizat.")
        return

    print(f"--- Monitorizare 1H: {len(setupuri_active)} pozitii ---")
    pos_ramase = []
    ceva_schimbat = False

    for s in setupuri_active:
        simbol = s['simbol']
        try:
            # Luam date pe 1 ora
            ticker = yf.Ticker(simbol)
            df = ticker.history(period="3d", interval="1h")
            if df.empty: 
                pos_ramase.append(s)
                continue
            
            pret_acum = df['Close'].iloc[-1]
            high_acum = df['High'].iloc[-1]
            low_acum = df['Low'].iloc[-1]
            ma50_1h = df['Close'].rolling(window=50).mean().iloc[-1]

            # 1. VERIFICA CONFIRMARE (Daca era in asteptare)
            if s['status'] == 'asteapta_confirmare':
                # Confirmam daca pretul depaseste High-ul lumanarii de semnal Daily
                if pret_acum > s['entry']:
                    s['status'] = 'confirmat'
                    ceva_schimbat = True
                    msg = (f"✅ *CONFIRMARE INTRARE — {simbol}*\n"
                           f"💰 Entry executat la: ${round(pret_acum, 2)}\n"
                           f"🛑 SL: ${s['sl']}\n🎯 TP1: ${s['tp1']}")
                    bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

            # 2. VERIFICA STOP LOSS
            if low_acum <= s['sl']:
                msg = (f"❌ *SL ATINS — {simbol}*\n"
                       f"💸 Inchis la: ${s['sl']}\n"
                       f"📉 Rezultat: {s['sl_pct']}%")
                bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
                s['status'] = 'inchis_sl'
                istoric.append(s)
                ceva_schimbat = True
                continue # Nu il mai adaugam in pos_ramase

            # 3. VERIFICA TP1
            if not s['tp1_atins'] and high_acum >= s['tp1']:
                s['tp1_atins'] = True
                s['sl'] = s['entry'] # MUTAM SL LA BREAK EVEN
                ceva_schimbat = True
                msg = (f"🎯 *TP1 ATINS — {simbol}*\n"
                       f"💰 Profit 50% marcat!\n"
                       f"🛡️ SL mutat la Entry: ${s['entry']} (Fara Risc)")
                bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

            # 4. VERIFICA TP2
            if s['tp1_atins'] and high_acum >= s['tp2']:
                msg = (f"🚀 *TP2 ATINS — {simbol}*\n"
                       f"✅ Trade finalizat cu succes!\n"
                       f"📈 Profit: +{s['tp2_pct']}%")
                bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
                s['status'] = 'inchis_tp2'
                istoric.append(s)
                ceva_schimbat = True
                continue

            # 5. EXIT MA50 (Trend change pe 1H)
            if s['status'] == 'confirmat' and pret_acum < ma50_1h:
                msg = (f"⚠️ *EXIT PREVENTIV — {simbol}*\n"
                       f"📉 Close sub MA50 pe 1H. Trend slabit.\n"
                       f"💰 Inchis tot la: ${round(pret_acum, 2)}")
                bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
                s['status'] = 'inchis_ma50'
                istoric.append(s)
                ceva_schimbat = True
                continue

            pos_ramase.append(s)

        except Exception as e:
            print(f"Eroare monitorizare {simbol}: {e}")
            pos_ramase.append(s)

    if ceva_schimbat:
        db['setupuri_active'] = pos_ramase
        db['istoric_trades'] = istoric
        salveaza_si_commit(db, f"Monitor Update {datetime.now().strftime('%H:%M')}")

if __name__ == "__main__":
    ruleaza_monitor_1h()
