import os
import json
import yfinance as yf
import pandas as pd
import numpy as np
import telebot
from datetime import datetime

# Configurare Bot
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

if not TOKEN or not CHAT_ID:
    print("❌ EROARE CRITICA: Lipsesc variabilele de mediu.")
    exit(1)

bot = telebot.TeleBot(TOKEN)

def calculate_indicators_smc(df):
    try:
        df = df.copy()

        df['ema20']  = df['Close'].ewm(span=20,  adjust=False).mean()
        df['ema50']  = df['Close'].ewm(span=50,  adjust=False).mean()
        df['ema200'] = df['Close'].ewm(span=200, adjust=False).mean()

        delta    = df['Close'].diff()
        gain     = delta.where(delta > 0, 0.0)
        loss     = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs       = avg_gain / avg_loss.replace(0, 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))

        high_low   = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close  = (df['Low']  - df['Close'].shift()).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr']  = true_range.ewm(com=13, adjust=False).mean()

        df['vol_ma'] = df['Volume'].rolling(window=20).mean()

        df['pivot_high'] = df['High'].rolling(window=11, center=True).apply(
            lambda x: x[5] if x[5] == max(x) else np.nan, raw=True
        )
        df['pivot_low'] = df['Low'].rolling(window=11, center=True).apply(
            lambda x: x[5] if x[5] == min(x) else np.nan, raw=True
        )
        df['last_pivot_high'] = df['pivot_high'].ffill()
        df['last_pivot_low']  = df['pivot_low'].ffill()

        return df
    except Exception as e:
        print(f"[EROARE indicatori]: {e}")
        return df


def detecteaza_semnal_smc(df, simbol):
    try:
        if len(df) < 210:
            return None

        i     = -2
        c     = df.iloc[i]
        prev  = df.iloc[i-1]
        prev3 = df.iloc[i-2]

        # FILTRU 1 — TREND PUTERNIC
        dist_ema20_50  = (c['ema20'] - c['ema50'])  / c['ema50']  * 100
        dist_ema50_200 = (c['ema50'] - c['ema200']) / c['ema200'] * 100
        trend_ok = (
            c['Close'] > c['ema200'] and
            c['ema50'] > c['ema200'] and
            c['ema20'] > c['ema50']  and
            dist_ema20_50  > 0.5     and
            dist_ema50_200 > 0.5
        )
        if not trend_ok:
            return None

        # FILTRU 2 — PUTERE LUMANARE
        body       = abs(c['Close'] - c['Open'])
        range_tot  = c['High'] - c['Low']
        body_ratio = body / range_tot if range_tot > 0 else 0
        if body_ratio < 0.60:
            return None

        # CONDITII SMC
        bull_ob    = (prev['Close'] < prev['Open']) and (c['Close'] > prev['Close'] * 1.005) and (c['Volume'] > c['vol_ma'] * 1.3)
        bull_fvg   = (c['Low'] > prev3['High']) and (prev['Close'] > prev['Open'])
        swing_low  = df['Low'].iloc[i-6:i-1].min()
        bull_sweep = (c['Low'] < swing_low and c['Close'] > swing_low and c['Close'] > c['Open'])
        bos_bull   = (not pd.isna(c['last_pivot_high']) and c['Close'] > c['last_pivot_high'] and
                      prev['Close'] <= c['last_pivot_high'] and c['rsi'] > 50 and c['Volume'] > c['vol_ma'] * 1.1)

        # ENTRY SIGNALS
        e1 = bull_ob    and 45 <= c['rsi'] <= 58 and c['Volume'] > c['vol_ma'] * 1.5
        e2 = bull_sweep and 42 <= c['rsi'] <= 58 and c['Volume'] > c['vol_ma'] * 1.5
        e3 = bos_bull   and 50 <= c['rsi'] <= 62 and c['Volume'] > c['vol_ma'] * 1.5
        e4 = bull_fvg   and c['Close'] > c['Open'] and 42 <= c['rsi'] <= 58 and c['Volume'] > c['vol_ma'] * 1.5
        e5 = bull_sweep and bull_ob and 45 <= c['rsi'] <= 62 and c['Volume'] > c['vol_ma'] * 1.5

        if not any([e1, e2, e3, e4, e5]):
            return None

        # SCORING
        scor      = 0
        vol_ratio = c['Volume'] / c['vol_ma']

        if e5:                     scor += 3
        if e2 or e3:               scor += 2
        if e1 or e4:               scor += 1
        if vol_ratio >= 2.0:       scor += 2
        elif vol_ratio >= 1.5:     scor += 1
        if 50 <= c['rsi'] <= 55:   scor += 2
        elif 45 <= c['rsi'] <= 58: scor += 1
        if body_ratio >= 0.75:     scor += 1

        if scor < 4:
            return None

        tip = "COMBO 🔥" if e5 else "Sweep 💧" if e2 else "BOS 📊" if e3 else "OB 📦" if e1 else "FVG 🕳️"

        sl     = round(c['Close'] - (c['atr'] * 1.5), 2)
        tp     = round(c['Close'] + (c['atr'] * 3.0), 2)
        sl_pct = round((sl - c['Close']) / c['Close'] * 100, 2)
        tp_pct = round((tp - c['Close']) / c['Close'] * 100, 2)

        return {
            'simbol': simbol,
            'tip':    tip,
            'entry':  round(c['Close'], 2),
            'sl':     sl,
            'tp':     tp,
            'sl_pct': sl_pct,
            'tp_pct': tp_pct,
            'scor':   scor,
            'rsi':    round(c['rsi'], 1),
            'vol':    round(vol_ratio, 2)
        }

    except Exception as e:
        print(f"[EROARE semnal {simbol}]: {e}")
        return None


def ruleaza_scanare_smc():
    try:
        with open('baza_de_date.json', 'r') as f:
            db = json.load(f)

        simboluri = db.get('watchlist_trend_ascendent', [])
        ora       = datetime.now().strftime('%H:%M')

        print(f"[INFO] Scanare {len(simboluri)} simboluri | {ora}")

        gasite = []

        for simbol in simboluri:
            try:
                df = yf.Ticker(simbol).history(period="2y", interval="1d")
                if len(df) < 210:
                    continue
                df  = calculate_indicators_smc(df)
                res = detecteaza_semnal_smc(df, simbol)
                if res:
                    gasite.append(res)
                    print(f"[SEMNAL] {simbol} | {res['tip']} | Scor: {res['scor']}")
            except Exception as e:
                print(f"[EROARE] {simbol}: {e}")
                continue

        gasite.sort(key=lambda x: x['scor'], reverse=True)
        top3 = gasite[:3]

        if top3:
            print(f"[INFO] {len(top3)} semnale trimise pe Telegram")
            for s in top3:
                stele = '🔥' * min(s['scor'] // 2, 5)
                msg = (
                    f"🔥 *SEMNAL SMC PRIORITAR*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📊 *Ticker:* `{s['simbol']}`\n"
                    f"🎯 *Tip:* {s['tip']}\n"
                    f"⭐ *Scor:* {s['scor']}/10 {stele}\n\n"
                    f"💰 *Entry:* ${s['entry']}\n"
                    f"🛑 *SL:* ${s['sl']} ({s['sl_pct']}%)\n"
                    f"🎯 *TP:* ${s['tp']} (+{s['tp_pct']}%)\n"
                    f"📐 *R/R:* 1:2\n\n"
                    f"📈 *Confluente:*\n"
                    f"• RSI: {s['rsi']} ✅\n"
                    f"• Volum: {s['vol']}x medie ✅\n"
                    f"• Trend: BULLISH PUTERNIC ✅\n\n"
                    f"⚠️ _DYOR - Analiza Automata_\n"
                    f"━━━━━━━━━━━━━━━━━━━━━"
                )
                bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
        else:
            bot.send_message(
                CHAT_ID,
                "🔍 *Scanare SMC Finalizată*\nNiciun semnal premium azi. ✅",
                parse_mode='Markdown'
            )

    except Exception as e:
        print(f"[EROARE SCANARE]: {e}")


if __name__ == "__main__":
    ruleaza_scanare_smc()
