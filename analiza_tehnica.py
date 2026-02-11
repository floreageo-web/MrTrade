import os
import json
import yfinance as yf
import pandas as pd
import numpy as np
import telebot

# Configurare Bot
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
bot = telebot.TeleBot(TOKEN)

def calculeaza_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculeaza_atr(df, window=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(window=window).mean()

def ruleaza_analiza_istoric():
    try:
        with open('baza_de_date.json', 'r') as f:
            db = json.load(f)
        
        simboluri = db.get('watchlist_trend_ascendent', [])
        bot.send_message(CHAT_ID, f"📜 Caut breakout-uri în ultimele 20 de zile pentru cele {len(simboluri)} acțiuni...")
        
        istoric_breakout = []

        for simbol in simboluri:
            try:
                df = yf.Ticker(simbol).history(period="1y")
                if len(df) < 220: continue

                # Calculăm indicatorii pentru tot tabelul o singură dată
                ema20 = df['Close'].ewm(span=20, adjust=False).mean()
                ema50 = df['Close'].ewm(span=50, adjust=False).mean()
                ema200 = df['Close'].ewm(span=200, adjust=False).mean()
                rsi = calculeaza_rsi(df['Close'])
                atr = calculeaza_atr(df)
                vol_mediu_20 = df['Volume'].rolling(window=20).mean()

                # Verificăm ultimele 20 de zile (de la -20 până la ultima zi disponibilă)
                for i in range(-20, 0):
                    data_analizei = df.index[i].strftime('%Y-%m-%d')
                    
                    pret = df['Close'].iloc[i]
                    v_ema20 = ema20.iloc[i]
                    v_ema50 = ema50.iloc[i]
                    v_ema200 = ema200.iloc[i]
                    v_vol_azi = df['Volume'].iloc[i]
                    v_vol_m = vol_mediu_20.iloc[i-1] # Volumul mediu de dinaintea acelei zile
                    v_rsi = rsi.iloc[i]
                    v_atr_p = (atr.iloc[i] / pret) * 100

                    # CRITERIILE TALE (Valori: Volum > 500k, ATR > 1.5%, RSI 45-65, Energie > 150%)
                    c1 = pret > v_ema200 and v_ema50 > v_ema200
                    c2 = v_ema20 > v_ema50
                    c3 = ema50.iloc[i] > ema50.iloc[i-1] # Slope pozitiv
                    c4 = v_vol_m > 500_000
                    c5 = v_vol_azi > (v_vol_m * 1.5)
                    c6 = v_atr_p > 1.5
                    c7 = 45 <= v_rsi <= 65

                    if all([c1, c2, c3, c4, c5, c6, c7]):
                        msg = (f"📅 **DATA: {data_analizei}**\n"
                               f"🚀 Breakout detectat: **{simbol}**\n"
                               f"💰 Preț atunci: {pret:.2f}$\n"
                               f"⚡ Energie Volum: {((v_vol_azi/v_vol_m)*100):.0f}%\n"
                               f"🌊 ATR: {v_atr_p:.2f}%")
                        bot.send_message(CHAT_ID, msg)
                        istoric_breakout.append({"simbol": simbol, "data": data_analizei})
                        # Ieșim din buclă pentru acest simbol dacă a avut deja breakout recent? 
                        # Sau le lăsăm pe toate? (Momentan le las pe toate)

            except:
                continue

        bot.send_message(CHAT_ID, "✅ Istoricul pe ultimele 20 de zile a fost generat.")

    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ Eroare: {str(e)}")

if __name__ == "__main__":
    ruleaza_analiza_istoric()
