import os
import json
import yfinance as yf
import pandas as pd
import numpy as np
import telebot
from datetime import datetime # Avem nevoie de asta pentru data

# Configurare Bot
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
bot = telebot.TeleBot(TOKEN)

def calculeaza_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calculeaza_atr(df, window=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(window=window).mean()

def ruleaza_analiza_noutati():
    try:
        if not os.path.exists('baza_de_date.json'):
            return
            
        with open('baza_de_date.json', 'r') as f:
            db = json.load(f)
        
        simboluri = db.get('watchlist_trend_ascendent', [])
        semnale_anterioare = set(db.get('signal_list_long', []))
        
        gasite_azi = []
        mesaje_noi = []
        # Generăm data de azi formatată pentru tabelul tău manual
        data_azi = datetime.now().strftime("%d-%m-%Y")

        for simbol in simboluri:
            try:
                ticker = yf.Ticker(simbol)
                df = ticker.history(period="1y")
                if len(df) < 200: continue

                close = df['Close']
                ema20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
                ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
                ema50_prev = close.ewm(span=50, adjust=False).mean().iloc[-2]
                ema200 = close.ewm(span=200, adjust=False).mean().iloc[-1]
                
                v_rsi = calculeaza_rsi(close).iloc[-1]
                v_atr = calculeaza_atr(df).iloc[-1]
                v_vol_azi = df['Volume'].iloc[-1]
                v_vol_m = df['Volume'].rolling(window=20).mean().iloc[-2]
                
                pret_actual = close.iloc[-1]
                v_atr_p = (v_atr / pret_actual) * 100

                # Filtre
                c1 = pret_actual > ema200 and ema50 > ema200
                c2 = ema20 > ema50
                c3 = ema50 > ema50_prev
                c4 = v_vol_m > 500_000
                c5 = v_vol_azi > (v_vol_m * 1.5)
                c6 = v_atr_p > 1.5
                c7 = 45 <= v_rsi <= 65

                if all([c1, c2, c3, c4, c5, c6, c7]):
                    gasite_azi.append(simbol)
                    if simbol not in semnale_anterioare:
                        # MODIFICAT: Trimitem Ticker și Data (cu backticks pentru copy-paste rapid)
                        mesaje_noi.append(f"🚀 **NOU:** `{simbol}` | {pret_actual:.2f}$ | Data: `{data_azi}`")
            except:
                continue

        # Trimitere mesaje
        if mesaje_noi:
            header = f"🔔 **{len(mesaje_noi)} Breakout-uri NOI:**\n\n"
            bot.send_message(CHAT_ID, header + "\n".join(mesaje_noi), parse_mode='Markdown')
        else:
            bot.send_message(CHAT_ID, "🔍 **Scanare Breakout:** Nu sunt breakout-uri noi în acest moment. ✅", parse_mode='Markdown')

        # Salvare
        db['signal_list_long'] = gasite_azi
        with open('baza_de_date.json', 'w') as f:
            json.dump(db, f, indent=4)

    except Exception as e:
        print(f"Eroare: {e}")

if __name__ == "__main__":
    ruleaza_analiza_noutati()
