import os
import telebot

# Citim cheile direct din "Seif"
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

bot = telebot.TeleBot(TOKEN)

def test_final():
    try:
        # Trimitem un mesaj simplu, fără bursa, fără AI
        bot.send_message(CHAT_ID, "🎯 MrTrade este ONLINE! Dacă primești asta, legătura e 100% corectă.")
        print("Mesaj trimis cu succes!")
    except Exception as e:
        print(f"Eroare detectată: {e}")

if __name__ == "__main__":
    test_final()
