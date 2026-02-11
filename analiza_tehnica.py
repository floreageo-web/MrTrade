import yfinance as yf
import pandas as pd
import requests
import os
import json
import time

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

def ruleaza_analiza_totala():
    try:
        with open("baza_de_date.json", "r") as f:
            db = json.load(f)
    except Exception as e:
        trimite_mesaj(f"❌ Eroare critica la citirea JSON: {e}")
        return

    tickers = db.get("watchlist_trend_ascendent", [])
    
    # VERIFICARE 1: Cate actiuni vede botul?
    total_lista = len(tickers)
    trimite_mesaj(f"📊 *Verificare Lista:* Am gasit `{total_lista}` actiuni in Trend Ascendent. Pornesc analiza...")

    stats = {"succes": 0, "pret": 0, "vol_avg": 0, "vol_rel": 0, "atr": 0, "rsi": 0, "trend": 0, "erori": 0}
    procesate_cu_succes = 0

    for symbol in tickers:
        try:
            ticker = yf.Ticker(symbol)
            # Folosim period="1y" ca sa fim siguri ca avem date pentru EMA
            df = ticker.history(period="100d")
            
            if df.empty or len(df) < 50:
                stats["erori"] += 1
                continue
            
            procesate_cu_succes += 1
            df = calculeaza_indicatori(df)
            limit = max(len(df) - 60, 0)
            
            gasit_ticker = False
            for i in range(len(df) - 1, limit - 1, -1):
                row = df.iloc[i]
                p = row['Close']
                v_avg = df['Volume'].iloc[max(0, i-20):i].mean()
                v_ratio = row['Volume'] / v_avg if v_avg > 0 else 0

                # Conditii stricte
                c_p = 35 <= p <= 150
                c_va = v_avg >= 500000
                c_vr = v_ratio >= 1.3
                c_at = row['ATR_PCT'] >= 1.2
                c_rs = 40 <= row['RSI'] <= 70
                c_tr = p > row['EMA20'] > row['EMA50']

                if c_p and c_va and c_vr and c_at and c_rs and c_tr:
                    data_s = df.index[i].strftime('%d-%m-%Y')
                    trimite_mesaj(f"✅ `{symbol}` - {data_s} - `{round(p, 2)}` $")
                    stats["succes"] += 1
                    gasit_ticker = True
                    break
            
            if not gasit_ticker:
                ultimul = df.iloc[-1]
                v_a = df['Volume'].iloc[-21:-1].mean()
                v_r = ultimul['Volume'] / v_a if v_a > 0 else 0
                
                if not (35 <= ultimul['Close'] <= 150): stats["pret"] += 1
                if v_a < 500000: stats["vol_avg"] += 1
                if v_r < 1.3: stats["vol_rel"] += 1
                if ultimul['ATR_PCT'] < 1.2: stats["atr"] += 1
                if not (40 <= ultimul['RSI'] <= 70): stats["rsi"] += 1
                if not (ultimul['Close'] > ultimul['EMA20'] > ultimul['EMA50']): stats["trend"] += 1
        except:
            stats["erori"] += 1
            continue

    # Raportul final trebuie sa insumeze totalul actiunilor
    raport = (
        f"🏁 *Analiza Finalizata*\n\n"
        f"📋 Din `{total_lista}` actiuni:\n"
        f"✅ Semnale: {stats['succes']}\n"
        f"⚠️ Erori date Yahoo: {stats['erori']}\n\n"
        f"❌ *Motive esec (ultima stare):*\n"
        f"• Pret: {stats['pret']}\n"
        f"• Vol. Mediu: {stats['vol_avg']}\n"
        f"• Energie: {stats['vol_rel']}\n"
        f"• ATR: {stats['atr']}\n"
        f"• RSI: {stats['rsi']}\n"
        f"• Trend: {stats['trend']}"
    )
    trimite_mesaj(raport)

if __name__ == "__main__":
    ruleaza_analiza_totala()
