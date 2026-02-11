import yfinance as yf
import pandas as pd
import requests
import os
import json

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
    rs = gain / loss.replace(0, 1e-10)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    tr = pd.concat([df['High']-df['Low'], 
                    abs(df['High']-df['Close'].shift()), 
                    abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)
    df['ATR_PCT'] = (tr.rolling(14).mean() / df['Close']) * 100
    
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    return df.dropna()

def ruleaza_analiza_cu_raport():
    try:
        with open("baza_de_date.json", "r") as f:
            db = json.load(f)
    except:
        trimite_mesaj("❌ Eroare: Nu gasesc `baza_de_date.json`!")
        return

    tickers = db.get("watchlist_trend_ascendent", [])
    if not tickers:
        trimite_mesaj("⚠️ Lista `watchlist_trend_ascendent` este goala!")
        return

    trimite_mesaj(f"🚀 Incep scanarea pentru {len(tickers)} actiuni (60 zile)...")

    # Contori pentru statistica
    stats = {
        "pret": 0,
        "vol_avg": 0,
        "vol_rel": 0,
        "atr": 0,
        "rsi": 0,
        "trend": 0,
        "succes": 0
    }

    for symbol in tickers:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="150d")
            if len(df) < 70: continue
            
            df = calculeaza_indicatori(df)
            limit = max(len(df) - 60, 0)
            
            gasit_ticker = False
            # Verificam daca a trecut macar o data in 60 de zile
            for i in range(len(df) - 1, limit - 1, -1):
                row = df.iloc[i]
                price = row['Close']
                vol_slice = df['Volume'].iloc[max(0, i-20):i]
                vol_avg = vol_slice.mean()
                vol_ratio = row['Volume'] / vol_avg if vol_avg > 0 else 0

                c_pret = 35 <= price <= 150
                c_vol_avg = vol_avg >= 500000
                c_vol_rel = vol_ratio >= 1.3
                c_atr = row['ATR_PCT'] >= 1.2
                c_rsi = 40 <= row['RSI'] <= 70
                c_trend = price > row['EMA20'] > row['EMA50']

                if c_pret and c_vol_avg and c_vol_rel and c_atr and c_rsi and c_trend:
                    data_s = df.index[i].strftime('%d-%m-%Y')
                    trimite_mesaj(f"✅ `{symbol}` - {data_s} - `{round(price, 2)}` $")
                    stats["succes"] += 1
                    gasit_ticker = True
                    break
            
            # Daca nu a trecut, vedem ce l-a blocat in ultima zi procesata
            if not gasit_ticker:
                ultimul = df.iloc[-1] # Verificam starea actuala pentru statistica
                v_avg = df['Volume'].iloc[-21:-1].mean()
                v_rel = ultimul['Volume'] / v_avg if v_avg > 0 else 0
                
                if not (35 <= ultimul['Close'] <= 150): stats["pret"] += 1
                elif v_avg < 500000: stats["vol_avg"] += 1
                elif v_rel < 1.3: stats["vol_rel"] += 1
                elif ultimul['ATR_PCT'] < 1.2: stats["atr"] += 1
                elif not (40 <= ultimul['RSI'] <= 70): stats["rsi"] += 1
                elif not (ultimul['Close'] > ultimul['EMA20'] > ultimul['EMA50']): stats["trend"] += 1

        except:
            continue

    # Construim raportul final
    raport = (
        f"🏁 *Scanare Finalizata!*\n\n"
        f"✅ Semnale gasite: {stats['succes']}\n\n"
        f"❌ *De ce au picat restul (starea curenta):*\n"
        f"• Pret ($35-150): {stats['pret']}\n"
        f"• Volum Mediu (<500k): {stats['vol_avg']}\n"
        f"• Energie Volum (<1.3x): {stats['vol_rel']}\n"
        f"• Volatilitate ATR (<1.2%): {stats['atr']}\n"
        f"• RSI (40-70): {stats['rsi']}\n"
        f"• Trend (EMA): {stats['trend']}"
    )
    trimite_mesaj(raport)

if __name__ == "__main__":
    ruleaza_analiza_cu_raport()
