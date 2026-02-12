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

def ruleaza_analiza_scurta():
    try:
        with open('baza_de_date.json', 'r') as f:
            db = json.load(f)
        
        simboluri = db.get('watchlist_trend_ascendent', [])
        # Mesaj de control in log-uri
        print(f"Incep analiza scurta pentru {len(simboluri)} actiuni...")
        
        rezultate_finale = []
        tickere_gasite = set()

        for simbol in simboluri:
            try:
                df = yf.Ticker(simbol).history(period="1y")
                if len(df) < 200: continue

                ema20 = df['Close'].ewm(span=20, adjust=False).mean()
                ema50 = df['Close'].ewm(span=50, adjust=False).mean()
                ema200 = df['Close'].ewm(span=200, adjust=False).mean()
                rsi = calculeaza_rsi(df['Close'])
                atr = calculeaza_atr(df)
                vol_mediu_20 = df['Volume'].rolling(window=20).mean()

                # Verificam ultimele 4 zile (3 zile trecute + astazi)
                # i merge de la -4, -3, -2, -1
                for i in range(-4, 0):
                    if simbol in tickere_gasite: break # Daca l-am gasit deja, sari peste restul zilelor

                    pret = df['Close'].iloc[i]
                    v_vol_azi = df['Volume'].iloc[i]
                    v_vol_m = vol_mediu_20.iloc[i-1]
                    v_rsi = rsi.iloc[i]
                    v_atr_p = (atr.iloc[i] / pret) * 100
                    
                    # Criterii: EMA, Volum > 500k, Energie > 150%, ATR > 1.5%, RSI 45-65
                    c1 = pret > ema200.iloc[i] and ema50.iloc[i] > ema200.iloc[i]
                    c2 = ema20.iloc[i] > ema50.iloc[i]
                    c3 = ema50.iloc[i] > ema50.iloc[i-1]
                    c4 = v_vol_m > 500_000
                    c5 = v_vol_azi > (v_vol_m * 1.5)
                    c6 = v_atr_p > 1.5
                    c7 = 45 <= v_rsi <= 65

                    if all([c1, c2, c3, c4, c5, c6, c7]):
                        data_str = df.index[i].strftime('%d-%m')
                        rezultate_finale.append(f"🔹 {simbol} | {data_str} | {pret:.2f}$")
                        tickere_gasite.add(simbol)

            except:
                continue

        # Constructie mesaj unic
        if rezultate_finale:
            antet = f"✅ Au fost gasite {len(rezultate_finale)} actiuni care au spart:\n\n"
            mesaj_complet = antet + "\n".join(rezultate_finale)
            
            # Daca mesajul e prea lung pentru Telegram (peste 4096 caractere), il taiem
            if len(mesaj_complet) > 4000:
                mesaj_complet = mesaj_complet[:3900] + "\n...si altele."
            
            bot.send_message(CHAT_ID, mesaj_complet)
        else:
            bot.send_message(CHAT_ID, "🔍 Nicio actiune nu a indeplinit criteriile in ultimele 4 zile.")

    except Exception as e:
        print(f"Eroare: {e}")

if __name__ == "__main__":
    ruleaza_analiza_scurta()
