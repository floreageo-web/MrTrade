import os
import json
import yfinance as yf
import pandas as pd
import numpy as np
import telebot
import subprocess
from datetime import datetime

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

def calculate_indicators_1h(df):
    try:
        df = df.copy()
        df['ma20'] = df['Close'].rolling(window=20).mean()
        df['ma50'] = df['Close'].rolling(window=50).mean()

        delta    = df['Close'].diff()
        gain     = delta.where(delta > 0, 0.0)
        loss     = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs       = avg_gain / avg_loss.replace(0, 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))

        df['vol_ma'] = df['Volume'].rolling(window=20).mean()

        return df
    except Exception as e:
        print(f"[EROARE indicatori 1H]: {e}")
        return df


def ruleaza_monitor_1h():
    if not os.path.exists('baza_de_date.json'):
        print("[INFO] Baza de date inexistenta.")
        return

    with open('baza_de_date.json', 'r') as f:
        db = json.load(f)

    setupuri_active = db.get('setupuri_active', [])
    istoric         = db.get('istoric_trades', [])

    if not setupuri_active:
        print("[INFO] Nicio pozitie activa de monitorizat.")
        return

    ora = datetime.now().strftime('%H:%M')
    print(f"[INFO] Monitor 1H | {len(setupuri_active)} pozitii | {ora} UTC")

    pos_ramase    = []
    ceva_schimbat = False

    for s in setupuri_active:
        simbol = s['simbol']
        try:
            # 15 zile pentru suficiente bare pentru MA50 pe 1H
            df = yf.Ticker(simbol).history(period="15d", interval="1h")

            if df.empty or len(df) < 50:
                pos_ramase.append(s)
                continue

            df = calculate_indicators_1h(df)

            c    = df.iloc[-1]
            prev = df.iloc[-2]

            pret_acum = round(c['Close'], 2)
            high_acum = c['High']
            low_acum  = c['Low']
            open_acum = c['Open']
            ma50_1h   = c['ma50']
            rsi_1h    = c['rsi']
            vol_acum  = c['Volume']
            vol_ma_1h = c['vol_ma']

            # ==========================================
            # DACA SETUP-UL ASTEAPTA CONFIRMARE
            # ==========================================
            if s['status'] == 'asteapta_confirmare':

                # Confirmare stricta pe 1H:
                # 1. Lumanare verde
                # 2. Sparge high-ul barei precedente pe 1H
                # 3. Pret peste close-ul Daily de ieri
                # 4. RSI peste 45
                # 5. Volum decent
                confirmare_1h = (
                    c['Close']  > c['Open']      and
                    c['Close']  > prev['High']   and
                    c['Close']  > s['close_azi'] and
                    rsi_1h      > 45             and
                    vol_acum    > vol_ma_1h * 0.9
                )

                if confirmare_1h:
                    entry_real = pret_acum
                    sl_real    = s['sl_anticipat']
                    risc       = entry_real - sl_real

                    # Fallback daca risc e negativ sau zero
                    if risc <= 0:
                        risc = entry_real * 0.02

                    tp1     = round(entry_real + (risc * 2), 2)  # R:R 2:1
                    tp2     = round(entry_real + (risc * 3), 2)  # R:R 3:1

                    sl_pct  = round((sl_real    - entry_real) / entry_real * 100, 2)
                    tp1_pct = round((tp1        - entry_real) / entry_real * 100, 2)
                    tp2_pct = round((tp2        - entry_real) / entry_real * 100, 2)

                    s.update({
                        'status':    'confirmat',
                        'entry':     entry_real,
                        'sl':        sl_real,
                        'tp1':       tp1,
                        'tp2':       tp2,
                        'sl_pct':    sl_pct,
                        'tp1_pct':   tp1_pct,
                        'tp2_pct':   tp2_pct,
                        'tp1_atins': False
                    })

                    ceva_schimbat = True
                    print(f"[CONFIRMAT] {simbol} | Entry: ${entry_real}")

                    msg = (
                        f"✅ *CONFIRMARE INTRARE — 1H*\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📊 *Ticker:* `{simbol}`\n"
                        f"⏰ *Ora:* {ora} UTC\n"
                        f"📊 *1H confirmă Daily* ✅\n\n"
                        f"💰 *Entry:* ${entry_real}\n"
                        f"🛑 *SL:* ${sl_real} ({sl_pct}%)\n"
                        f"🎯 *TP1 (50%):* ${tp1} (+{tp1_pct}%) → R:R 2:1\n"
                        f"🎯 *TP2 (50%):* ${tp2} (+{tp2_pct}%) → R:R 3:1\n\n"
                        f"⚙️ *Management:*\n"
                        f"• La TP1 → mută SL la Entry\n"
                        f"• La TP2 → ieși tot\n"
                        f"• Close sub MA50 → ieși tot\n\n"
                        f"⚠️ _DYOR - Analiza Automata_\n"
                        f"━━━━━━━━━━━━━━━━━━━━━"
                    )
                    bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

                pos_ramase.append(s)
                continue

            # ==========================================
            # DACA SETUP-UL E CONFIRMAT — MONITORIZARE
            # ==========================================
            if s['status'] == 'confirmat':

                # VERIFICA TP1 PRIMUL — prioritate fata de SL
                # In aceeasi lumanare high poate atinge TP si low SL
                # Alegem intotdeauna TP daca ambele sunt atinse
                if not s['tp1_atins'] and high_acum >= s['tp1']:
                    s['tp1_atins'] = True
                    s['sl']        = s['entry']  # SL mutat la breakeven
                    ceva_schimbat  = True
                    print(f"[TP1] {simbol} | ${s['tp1']}")

                    msg = (
                        f"🎯 *TP1 ATINS — {simbol}*\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"⏰ *Ora:* {ora} UTC\n\n"
                        f"💰 *Ieși 50%* la ${s['tp1']}\n"
                        f"🛡️ *SL mutat la Entry:* ${s['entry']}\n"
                        f"📊 *Fără risc de acum* ✅\n\n"
                        f"🎯 *TP2 target:* ${s['tp2']} (+{s['tp2_pct']}%)\n"
                        f"━━━━━━━━━━━━━━━━━━━━━"
                    )
                    bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
                    pos_ramase.append(s)
                    continue

                # VERIFICA TP2
                if s['tp1_atins'] and high_acum >= s['tp2']:
                    ceva_schimbat = True
                    print(f"[TP2] {simbol} | ${s['tp2']}")

                    rezultat_total = round(
                        ((s['tp1'] - s['entry']) / s['entry'] * 100 * 0.5) +
                        ((s['tp2'] - s['entry']) / s['entry'] * 100 * 0.5), 2
                    )

                    msg = (
                        f"🚀 *TP2 ATINS — TRADE COMPLET!*\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📊 *Ticker:* `{simbol}`\n"
                        f"⏰ *Ora:* {ora} UTC\n\n"
                        f"💰 *Ieși restul* la ${s['tp2']}\n"
                        f"✅ *Trade finalizat cu succes!*\n\n"
                        f"📈 *Rezultat total:* +{rezultat_total}%\n"
                        f"• TP1: +{s['tp1_pct']}% pe 50%\n"
                        f"• TP2: +{s['tp2_pct']}% pe 50%\n\n"
                        f"💪 *Excelent! Așteptăm următorul setup.*\n"
                        f"━━━━━━━━━━━━━━━━━━━━━"
                    )
                    bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

                    s['status']    = 'inchis_tp2'
                    s['data_exit'] = datetime.now().strftime('%Y-%m-%d')
                    istoric.append(s)
                    continue

                # VERIFICA SL
                if low_acum <= s['sl']:
                    ceva_schimbat = True
                    print(f"[SL] {simbol} | ${s['sl']}")

                    if s['tp1_atins']:
                        rezultat_msg = f"• TP1 atins anterior +{s['tp1_pct']}%\n• Restul închis la breakeven"
                        titlu        = "⚠️ *IESIRE BREAKEVEN*"
                    else:
                        rezultat     = round((s['sl'] - s['entry']) / s['entry'] * 100, 2)
                        rezultat_msg = f"• Pierdere: {rezultat}%"
                        titlu        = "❌ *SL ATINS*"

                    msg = (
                        f"{titlu} — {simbol}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"⏰ *Ora:* {ora} UTC\n\n"
                        f"💸 *Închis la:* ${s['sl']}\n"
                        f"{rezultat_msg}\n\n"
                        f"💪 *Pierdere controlată. Next!*\n"
                        f"━━━━━━━━━━━━━━━━━━━━━"
                    )
                    bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

                    s['status']    = 'inchis_sl'
                    s['data_exit'] = datetime.now().strftime('%Y-%m-%d')
                    istoric.append(s)
                    continue

                # VERIFICA CLOSE SUB MA50 PE 1H
                # Trebuie si lumanare rosie ca sa nu iasa pe spike
                if pret_acum < ma50_1h and c['Close'] < c['Open']:
                    ceva_schimbat = True
                    print(f"[MA50 EXIT] {simbol}")

                    msg = (
                        f"⚠️ *IEȘIRE TOTALĂ — {simbol}*\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"⏰ *Ora:* {ora} UTC\n\n"
                        f"📉 *Close sub MA50 pe 1H*\n"
                        f"💰 *Ieși TOT la piață imediat!*\n"
                        f"📊 *Pret curent:* ${pret_acum}\n"
                        f"📊 *MA50 1H:* ${round(ma50_1h, 2)}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━"
                    )
                    bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

                    s['status']    = 'inchis_ma50'
                    s['data_exit'] = datetime.now().strftime('%Y-%m-%d')
                    istoric.append(s)
                    continue

                # Niciun nivel atins — pozitia ramane deschisa
                pos_ramase.append(s)
                print(f"[ACTIV] {simbol} | Pret: ${pret_acum} | TP1: ${s['tp1']} | SL: ${s['sl']}")

        except Exception as e:
            print(f"[EROARE] {simbol}: {e}")
            pos_ramase.append(s)
            continue

    if ceva_schimbat:
        db['setupuri_active'] = pos_ramase
        db['istoric_trades']  = istoric
        salveaza_si_commit(
            db,
            f"Monitor 1H {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
    else:
        print("[INFO] Nicio modificare — nu e nevoie de commit")


if __name__ == "__main__":
    ruleaza_monitor_1h()
