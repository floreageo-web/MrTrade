import os
import telebot

# Setări Telegram
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
bot = telebot.TeleBot(TOKEN)

def standby():
    # Acest script este în standby pentru a proteja lista manuală de 317 acțiuni
    print("Scanner în standby. Folosim lista fixă din baza_de_date.json")
    bot.send_message(CHAT_ID, "🚀 Pornim analiza tehnică pe lista celor 317 acțiuni în trend...")

if __name__ == "__main__":
    standby()
