import os
import telebot
import yfinance as yf

# Luăm cheile din seif
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

bot = telebot.TeleBot(TOKEN)

def verifica_bursa():
    # Verificăm NVIDIA ca test
    simbol = "NVDA"
    data = yf.Ticker(simbol)
    pret_actual = data.history(period="1d")['Close'].iloc[-1]
    
    mesaj = f"🚀 MrTrade a pornit!\n📈 Prețul {simbol} este: {pret_actual:.2f} USD\n✅ Sistemul de monitorizare este activ."
    bot.send_message(CHAT_ID, mesaj)

if __name__ == "__main__":
    try:
        verifica_bursa()
    except Exception as e:
        print(f"Eroare: {e}")
