# 📈 Swing Trader Bot — NASDAQ/NYSE

Bot complet pentru swing trading pe acțiuni în trend ascendent.
**Strategie:** EMA21 + RSI(40-55) + Lumânare de confirmare

---

## 🗂️ Structura Fișierelor

```
swing_trader/
├── config.py          # ⚙️  Setări: token Telegram, capital, parametri
├── indicators.py      # 📐 Calcul EMA21/50/200, RSI, ATR, detectare lumânări
├── screener.py        # 🔍 Scanare 317 acțiuni + detectare semnale
├── backtester.py      # 📊 Backtesting pe 12 luni
├── risk_manager.py    # ⚖️  Calculator poziție + Jurnal tranzacții
├── telegram_bot.py    # 📱 Trimitere semnale pe Telegram
├── dashboard.py       # 🌐 Dashboard web (Flask)
├── main.py            # 🚀 Orchestrator principal
└── requirements.txt   # 📦 Dependențe
```

---

## ⚙️ Configurare (OBLIGATORIU)

### 1. Editează `config.py`:
```python
TELEGRAM_TOKEN  = "tokenul_tau_de_la_BotFather"
TELEGRAM_CHAT_ID = "chat_id_ul_tau"
CAPITAL          = 10000    # Capitalul tău în $
RISK_PER_TRADE   = 0.01     # 1% risc per tranzacție
```

### 2. Înlocuiește lista TICKERS cu cele 317 acțiuni ale tale

### 3. Instalează dependențele:
```bash
pip install -r requirements.txt
```

---

## 🚀 Rulare

```bash
# Mod complet (dashboard + scheduler zilnic) — RECOMANDAT
python main.py

# Doar o scanare manuală acum
python main.py --mode scan

# Backtesting complet pe toate acțiunile
python main.py --mode backtest

# Doar dashboard-ul web
python main.py --mode dashboard

# Test conexiune Telegram
python main.py --mode test
```

### Dashboard web:
Deschide browserul la: **http://localhost:5000**

---

## 📊 Strategia Implementată

### Condiții de intrare (TOATE trebuie îndeplinite):
1. ✅ **EMA50 > EMA200** — trend ascendent confirmat
2. ✅ **Preț > EMA50** — acțiunea e deasupra trendului
3. ✅ **RSI între 40-55** — retragere în trend, nu supravândut
4. ✅ **Preț la ±2% de EMA21** — zona de suport
5. ✅ **Lumânare bullish** — Engulfing / Pin Bar / Bullish candle

### Ieșiri:
- 🛑 **Stop Loss:** preț_intrare - 1.5×ATR
- 🎯 **TP1:** +1.5R (50% din poziție)
- 🚀 **TP2:** +2.5R (restul pozitiei)

### Filtre de univers:
- Preț între $35 - $150
- Doar acțiuni NASDAQ/NYSE în trend ascendent

---

## 📱 Mesaje Telegram

Botul trimite automat la 17:30 (Luni-Vineri):
- Lista semnalelor de intrare (cu SL, TP1, TP2, shares)
- Statisticile jurnalului personal

Duminică la 10:00:
- Raport complet backtesting

---

## ⚠️ Disclaimer

Acest instrument este doar educațional. Nu constituie sfat financiar.
Tranzacționarea implică riscuri. Testează întotdeauna pe cont demo înainte.
