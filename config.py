# ============================================================
# config.py — Setări principale Swing Trader
# ============================================================

# --- TELEGRAM ---
TELEGRAM_TOKEN = "PUNE_TOKEN_TAU_AICI"
TELEGRAM_CHAT_ID = "PUNE_CHAT_ID_TAU_AICI"

# --- PARAMETRI STRATEGIE ---
EMA_FAST = 21
EMA_MID = 50
EMA_SLOW = 200
RSI_PERIOD = 14
RSI_MIN = 40
RSI_MAX = 55
PRICE_MIN = 35
PRICE_MAX = 150
RISK_PER_TRADE = 0.01       # 1% risc per tranzacție
CAPITAL = 10000             # Capital total în $
RR_TP1 = 1.5                # Risk/Reward TP1
RR_TP2 = 2.5                # Risk/Reward TP2
BACKTEST_MONTHS = 12        # Luni de backtesting

# --- LISTA TICKERE (317 acțiuni NASDAQ/NYSE în trend ascendent) ---
# Înlocuiește cu lista ta completă de 317 tickere
TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD", "INTC", "QCOM",
    "AVGO", "TXN", "MU", "AMAT", "LRCX", "KLAC", "MRVL", "SNPS", "CDNS", "FTNT",
    "PANW", "CRWD", "ZS", "OKTA", "NET", "DDOG", "MDB", "SNOW", "PLTR", "GTLB",
    "NOW", "CRM", "ADBE", "INTU", "WDAY", "VEEV", "HUBS", "BILL", "PAYC", "PCTY",
    "V", "MA", "PYPL", "SQ", "FIS", "FISV", "GPN", "AXP", "DFS", "COF",
    "JPM", "BAC", "WFC", "GS", "MS", "BLK", "SCHW", "ICE", "CME", "CBOE",
    "UNH", "ISRG", "ELV", "CI", "HUM", "CVS", "MCK", "ABC", "CAH", "MOH",
    "LLY", "JNJ", "PFE", "ABBV", "MRK", "BMY", "AMGN", "GILD", "REGN", "VRTX",
    "HD", "LOW", "TGT", "WMT", "COST", "AMZN", "TJX", "ROST", "DLTR", "DG",
    "MCD", "SBUX", "YUM", "CMG", "DPZ", "QSR", "DNUT", "TXRH", "BJRI", "CAKE",
    "NEE", "DUK", "SO", "AEP", "EXC", "SRE", "PEG", "ED", "XEL", "WEC",
    "XOM", "CVX", "COP", "EOG", "PXD", "MPC", "VLO", "PSX", "HES", "DVN",
    "CAT", "DE", "HON", "MMM", "GE", "EMR", "ROK", "PH", "ETN", "AME",
    "BA", "LMT", "RTX", "NOC", "GD", "LHX", "HII", "TDG", "HWM", "CW",
    "AMGN", "BIIB", "ILMN", "IQV", "TMO", "DHR", "A", "BIO", "RVTY", "MTD",
    "PLD", "AMT", "CCI", "EQIX", "PSA", "EXR", "AVB", "EQR", "MAA", "UDR",
    "UBER", "LYFT", "ABNB", "BKNG", "EXPE", "TRIP", "DASH", "GRUB", "OPEN", "Z",
    "NFLX", "DIS", "CMCSA", "T", "VZ", "CHTR", "TMUS", "LUMN", "DISH", "SIRI",
    "ENPH", "SEDG", "RUN", "FSLR", "CSIQ", "SPWR", "NOVA", "ARRY", "SHLS", "STEM",
    # Adaugă restul până la 317
]
