import os
import pandas as pd
import yfinance as yf
import telebot
from datetime import datetime

# 1. Validare si Oprire Fortata
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

if not TOKEN or not CHAT_ID:
    print("❌ EROARE CRITICA: Lipsesc variabilele de mediu.")
    exit(1)

bot = telebot.TeleBot(TOKEN)

def calculeaza_indicatori_pro(df, window=14):
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # Wilder Smoothing corect
    avg_gain = gain.ewm(com=window-1, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(com=window-1, min_periods=window, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # ATR corect
    high_low = df['High'] - df['Low']
    high_cp = abs(df['High'] - df['Close'].shift())
    low_cp = abs(df['Low'] - df['Close'].shift())
    df['TR'] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    df['ATR'] = df['TR'].rolling(window=window).mean()
    return df

def ruleaza_strategia_finala():
    file_path = 'watchlist_manual.csv'
    if not os.path.exists(file_path): return

    df_manual = pd.read_csv(file_path)
    acum = datetime.now()

    for index, row in df_manual.iterrows():
        ticker_symbol = str(row['ticker']).strip().upper() if 'ticker' in row.index else 'UNKNOWN'
        
        try:
            r_min_orig = float(row['rezistenta_min'])
            r_max_orig = float(row['rezistenta_max'])
            
            data_str = str(row['data_breakout'])
            if len(data_str.split('-')) == 2: data_str += f"-{acum.year}"
            data_brk = datetime.strptime(data_str, "%d-%m-%Y")
            
            zile_trecute = (acum - data_brk).days
            if not (3 <= zile_trecute <= 10): continue

            ticker = yf.Ticker(ticker_symbol)
            
            # Context Daily (Trend & Volatilitate)
            df_d = ticker.history(period="100d", interval="1d")
            if len(df_d) < 50: continue
            df_d = calculeaza_indicatori_pro(df_d)
            atr_daily = df_d['ATR'].iloc[-1]
            ma50_d = df_d['Close'].rolling(50).mean().iloc[-1]
            
            if pd.isna(ma50_d) or df_d['Close'].iloc[-1] < ma50_d: continue

            # Context 1H (Analiza Semnal)
            df_1h = ticker.history(period="30d", interval="1h")
            if len(df_1h) < 25: continue
            
            # Safe Timezone Convert
            if df_1h.index.tz is not None:
                df_1h.index = df_1h.index.tz_convert(None)
            
            df_1h = calculeaza_indicatori_pro(df_1h)
            df_after_brk = df_1h[df_1h.index > data_brk]
            
            # Verificare Invalidare post-breakout
            if not df_after_brk.empty:
                if df_after_brk['High'].max() > (r_max_orig * 1.04): continue
                if df_after_brk['Low'].min() < (r_min_orig * 0.99): continue

            ultima = df_1h.iloc[-1]
            
            # Validare TP 8% vs ATR Daily (1.2x ATR minimum)
            if (ultima['Close'] * 0.08) < (1.2 * atr_daily): continue

            # Zona adaptiva pe ATR 1H
            zona_low = r_min_orig - (0.5 * ultima['ATR'])
            zona_high = r_max_orig + (0.5 * ultima['ATR'])
            
            in_zona = ultima['Low'] <= zona_high and ultima['High'] >= zona_low
            rsi_ok = 45 <= ultima['RSI'] <= 60
            
            # Volum peste medie 5h
            vol_med_5h = df_1h['Volume'].iloc[-6:-1].mean()
            if pd.isna(vol_med_5h) or vol_med_5h == 0: continue
            vol_ok = ultima['Volume'] > vol_med_5h
            
            # --- CALCUL WICK CORECTAT (Sugestia 1) ---
            total_range = ultima['High'] - ultima['Low']
            if total_range == 0: continue
            
            # Wick-ul este distanta de la Low pana la baza corpului (care e minimul dintre Open si Close)
            lower_wick = min(ultima['Open'], ultima['Close']) - ultima['Low']
            
            confirmare_wick = (lower_wick / total_range) > 0.4
            inchidere_peste_mijloc = ultima['Close'] > (ultima['Low'] + total_range * 0.5)

            if in_zona and rsi_ok and vol_ok and confirmare_wick and inchidere_peste_mijloc:
                tp_8 = ultima['Close'] * 1.08
                ticker_safe = ticker_symbol.replace('_', '\\_')
                
                msg = (f"💎 **FINAL PREMIUM SETUP: {ticker_safe}**\n\n"
                       f"📊 **Context:**\n"
                       f"• Trend: ✅ OK (Peste MA50)\n"
                       f"• Time: {zile_trecute}d de la breakout\n"
                       f"• Volatilitate: ✅ Target 8% valid vs ATR\n\n"
                       f"⚡ **Indicatori 1H:**\n"
                       f"• Pret: {ultima['Close']:.2f}$ | RSI: {ultima['RSI']:.1f}\n"
                       f"• Volum: +{(ultima['Volume']/vol_med_5h - 1)*100:.0f}% vs medie\n\n"
                       f"🕯️ **Reversie:**\n"
                       f"• Wick Inferior: {lower_wick/total_range*100:.0f}%\n"
                       f"• Inchidere: ✅ Peste mijloc\n\n"
                       f"🎯 **Target (8%): {tp_8:.2f}$**")
                
                bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

        except Exception as e:
            print(f"Eroare {ticker_symbol}: {e}")

if __name__ == "__main__":
    ruleaza_strategia_finala()
