import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
import json
from datetime import datetime, timedelta
import pytz

# --- CONFIGURARE TELEGRAM ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def trimite_mesaj(mesaj):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def calculeaza_indicatori(df):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    df['ATR'] = (pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift()), abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)).rolling(14).mean()
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    return df

def gaseste_rezistenta_valida(df_istoric):
    """ Cauta o zona de rezistenta de 4 puncte in istoricul oferit """
    last_price = df_istoric['Close'].iloc[-1]
    atr = (df_istoric['High'] - df_istoric['Low']).rolling(14).mean().iloc[-1]
    delta = max(0.008 * last_price, atr)
    
    # Detectie varfuri
    maxime = df_istoric[df_istoric['High'] == df_istoric['High'].rolling(window=21, center=True).max()]
    
    if len(maxime) >= 4:
        potențiala_zona = maxime['High'].iloc[-1]
        puncte = maxime[(maxime['High'] >= potențiala_zona - delta) & (maxime['High'] <= potențiala_zona + delta)]
        
        if len(puncte) >= 4:
            distante = puncte.index.to_series().diff().dt.days
            if (distante.dropna() >= 10).all():
                return puncte['High'].mean(), delta
    return None, None

def ruleaza_scanare():
    try:
        with open("baza_de_date.json", "r") as f:
            db = json.load(f)
    except: return

    tickers = db.get("watchlist_trend_ascendent", [])
    total_tickers = len(tickers)
    noi_breakouturi = []
    tz_ro = pytz.timezone('Europe/Bucharest')
    acum_ro = datetime.now(tz_ro)

    print(f"Scanare extinsa pe ultimele 20 de zile pentru {total_tickers} actiuni...")

    for index, symbol in enumerate(tickers, start=1):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="300d") 
            if len(df) < 150: continue
            df = calculeaza_indicatori(df)

            # Ne uitam in ultimele 20 de zile sa vedem daca a existat un moment de breakout
            for i in range(20, 0, -1):
                idx = -i
                data_punct = df.index[idx]
                cp = df['Close'].iloc[idx]
                
                # Definim istoricul de dinaintea acelei zile pentru a gasi rezistenta
                df_pana_la_zi = df.iloc[:idx]
                zona_z, delta = gaseste_rezistenta_valida(df_pana_la_zi)

                if zona_z and cp > (zona_z + delta):
                    # Verificam daca in ziua aia trendul era ok
                    cond_trend = (df['EMA20'].iloc[idx] > df['EMA50'].iloc[idx]) and (df['EMA50'].iloc[idx] > df['EMA50'].iloc[idx-10])
                    vol_mediu = df['Volume'].iloc[idx-20:idx].mean()
                    cond_vol = (vol_mediu >= 1000000) and (df['Volume'].iloc[idx] >= vol_mediu * 1.5)
                    
                    if cond_trend and cond_vol:
                        data_str = data_punct.strftime("%d-%m")
                        entry = f"{symbol}, {data_str}, {round(cp, 2)}"
                        
                        if entry not in noi_breakouturi:
                            noi_breakouturi.append(entry)
                            trimite_mesaj(f"✅ *BREAKOUT ISTORIC DETECTAT (Ult. 20 zile)*\n\n"
                                         f"📊 Ticker: `{symbol}` (#{index}/{total_tickers})\n"
                                         f"📅 Data Spargerii: `{data_str}`\n"
                                         f"💰 Preț la spargere: `{round(cp, 2)}` $\n"
                                         f"📏 Rezistență (Z): `{round(zona_z, 2)}`")
                        break # Gasit breakout pentru acest ticker, trecem la urmatorul

        except Exception as e:
            continue

    if noi_breakouturi:
        db["watchlist_long"] = list(set(db.get("watchlist_long", []) + noi_breakouturi))
        with open("baza_de_date.json", "w") as f:
            json.dump(db, f, indent=2)

if __name__ == "__main__":
    ruleaza_scanare()
