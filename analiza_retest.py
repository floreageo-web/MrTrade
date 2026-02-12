import os
import pandas as pd
import yfinance as yf
import telebot

# Configurare Bot
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
bot = telebot.TeleBot(TOKEN)

def ruleaza_retest_tabel():
    file_path = 'watchlist_manual.csv'
    
    # Verificăm dacă fișierul există
    if not os.path.exists(file_path):
        print(f"⚠️ Fișierul {file_path} nu a fost găsit. Creează-l pe GitHub.")
        return

    try:
        # Citim tabelul CSV
        df = pd.read_csv(file_path)
        
        # Curățăm eventualele spații goale din numele coloanelor
        df.columns = df.columns.str.strip()

        if df.empty:
            print("Tabelul este gol.")
            return

        print(f"🔎 Verific retest pentru {len(df)} acțiuni din tabel...")

        for index, row in df.iterrows():
            try:
                ticker_symbol = str(row['ticker']).strip().upper()
                r_min = float(row['rezistenta_min'])
                r_max = float(row['rezistenta_max'])

                # Luăm prețul actual (ultima cotație)
                ticker = yf.Ticker(ticker_symbol)
                data_pret = ticker.history(period="1d")
                
                if data_pret.empty:
                    continue
                    
                pret_actual = data_pret['Close'].iloc[-1]

                # --- LOGICA DE RETEST ---
                # Dacă prețul este între minim și maxim
                if r_min <= pret_actual <= r_max:
                    msg = (f"🎯 **RETEST ZONE: {ticker_symbol}**\n"
                           f"💰 Preț Actual: {pret_actual:.2f}$\n"
                           f"📥 Zonă Intrare: {r_min} - {r_max}\n"
                           f"📉 Status: Prețul a revenit la suport!")
                    bot.send_message(CHAT_ID, msg)
                    
                # Dacă prețul a sărit peste zonă, dar e aproape (opțional, pentru monitorizare)
                elif r_max < pret_actual <= (r_max * 1.02):
                    print(f"{ticker_symbol} este foarte aproape de zona de retest.")

            except Exception as e:
                print(f"Eroare la procesarea tickerului {row.get('ticker')}: {e}")
                continue

    except Exception as e:
        print(f"Eroare la citirea fișierului CSV: {e}")

if __name__ == "__main__":
    ruleaza_retest_tabel()
