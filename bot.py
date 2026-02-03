import os
import telebot
import yfinance as yf
import google.generativeai as genai

# Configurare chei din "Seiful" GitHub
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')

# Configurare Inteligență Artificială (Gemini)
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')
bot = telebot.TeleBot(TOKEN)

def cere_sfat_ai(date_bursa, simbol):
    prompt = f"""
    Ești un expert în Trading Instituțional și Strategia 'Anti-Stop Hunting'. 
    Analizează aceste date recente pentru {simbol}:
    {date_bursa}
    
    REGULI DE ANALIZĂ:
    1. LICHIDITATE: Verifică dacă prețul a coborât recent sub un nivel de suport (minim) pentru a activa stop-loss-urile retail, apoi a dat semne de revenire.
    2. REJECȚIE: Caută o respingere rapidă de la minime.
    3. TARGET: Urmărim un profit de +12% pe termen mediu.

    Răspunde în ROMÂNĂ, scurt și clar:
    - [🚀 SEMNAL]: BUY (dacă strategia e respectată) sau WAIT (dacă nu e clar).
    - [📝 MOTIV]: Explică în 2 propoziții dacă s-a curățat lichiditatea.
    - [🎯 TARGET]: Confirmă pragul de 12%.
    """
    response = model.generate_content(prompt)
    return response.text

def verifica_si_analizeaza():
    # Lista de acțiuni/crypto de monitorizat
    portofoliu = ["NVDA", "BTC-USD"] 
    
    for simbol in portofoliu:
        ticker = yf.Ticker(simbol)
        # Luăm ultimele 5 zile cu interval de 1 oră pentru a vedea "mișcările de păcălire"
        hist = ticker.history(period="5d", interval="1h")
        
        if hist.empty:
            continue
            
        pret_actual = hist['Close'].iloc[-1]
        
        # Trimitem ultimele 20 de ore de tranzacționare către AI
        date_text = hist.tail(20).to_string()
        sfat_ai = cere_sfat_ai(date_text, simbol)
        
        mesaj = (f"🤖 **Analiză MrTrade AI: {simbol}**\n"
                 f"💰 Preț actual: {pret_actual:.2f}\n\n"
                 f"{sfat_ai}")
        
        bot.send_message(CHAT_ID, mesaj, parse_mode="Markdown")

if __name__ == "__main__":
    try:
        verifica_si_analizeaza()
    except Exception as e:
        print(f"Eroare: {e}")
