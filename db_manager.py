import os
import pandas as pd
from yahooquery import Ticker
import time
import random
from datetime import datetime

# --- CONFIGURARE ---
DATA_DIR = 'data'

SYMBOLS_CONTEXT = ['SPY', 'XLK', 'XLF', 'XLV', 'XLY', 'XLP', 'XLE', 'XLI', 'XLB', 'XLU', 'XLRE', 'XLC']

SYMBOLS_STOCKS = [
    "TNK", "FHI", "POR", "APG", "BDC", "BE", "INCY", "DBD", "OR", "YETI", "TERN", "PARR", 
    "AMTM", "DTM", "SPHR", "PHM", "DXPE", "GRAL", "AAOI", "CWEN", "LNT", "BBU", "XMTR", 
    "NTB", "CATY", "CECO", "FLS", "ORA", "GVA", "GXO", "NBIX", "XYL", "ATKR", "IFS", 
    "SEDG", "DINO", "FORM", "FTS", "ALGT", "MCHP", "VSCO", "ABVX", "SQM", "LASR", "DLTR", 
    "FITB", "ARWR", "BPOP", "RHP", "SIMO", "FTI", "AS", "ATI", "WF", "MIRM", "EIX", 
    "UTG", "VIK", "FLR", "APAM", "DAL", "CUBI", "LEA", "MGA", "EMA", "KEN", "BEPC", 
    "BALL", "UCB", "SATS", "MHO", "PATK", "TPH", "SII", "DOO", "BSAC", "ASTS", "WYNN", 
    "GIL", "ON", "CENX", "VIST", "UCTT", "RNA", "RRR", "SWX", "NGVT", "MSGE", "WS", 
    "TX", "ALGM", "WPC", "LSCC", "TPC", "INDB", "MRX", "CNX", "SF", "DKL", "PCVX", 
    "MC", "CMC", "ACMR", "YUMC", "EXEL", "PBF", "NVT", "ACA", "GL", "CRUS", "AUB", 
    "NMIH", "CFG", "KYMR", "BTU", "KB", "WBS", "HLIO", "BKE", "VOYA", "FMX", "BIPC", 
    "SRRK", "TR", "TPB", "ENLT", "PFG", "FIBK", "GPC", "DIOD", "HXL", "ESNT", "HP", 
    "VAL", "HIG", "REZI", "GFI", "UBSI", "OMAB", "TEX", "USFD", "GPCR", "BTSG", "BOKF", 
    "BIP", "NFG", "TS", "JXN", "CNM", "CAKE", "RBA", "CRC", "KMT", "BCH", "FSS", 
    "SBCF", "SGI", "THO", "PAHC", "L", "BMA", "COGT", "BHE", "TIGO", "TCBI", "BWA", 
    "TRMK", "GOLF", "LUV", "BKU", "RPRX", "HOLX", "CELC", "DVN", "CHEF", "SIG", "MT", 
    "GEF", "HTH", "FLEX", "CCS", "FELE", "SMTC", "DK", "UAL", "IPGP", "IMAX", "RMBS", 
    "STT", "IBOC", "AZZ", "COCO", "FBNC", "EMBJ", "WSFS", "ECG", "HWC", "AMKR", "CTVA", 
    "TECH", "TXT", "BC", "BVN", "CGNX", "CNO", "DD", "SSB", "NWE", "GRBK", "OTTR", 
    "TECK", "RNST", "AL", "KNSA", "NYAX", "TBBB", "BFH", "BRC", "ZM", "WFRD", "PKX", 
    "BBUC", "LIVN", "IONS", "ATMU", "SDRL", "ALV", "DNTH", "PFGC", "TSEM", "NXT", 
    "QGEN", "MAZE", "SEI", "VSAT", "BCO", "NATL", "KALU", "TNL", "TRNO", "SWK", 
    "PACS", "TKR", "CCJ", "ANDE", "GDS", "LQDA", "CCK", "ROAD", "INSW", "BG", "PLUS", 
    "FBK", "TTMI", "ABCB", "WAL", "PAAS", "ENTG", "LTM", "RVMD", "DG", "CBU", "KLIC", 
    "NUVL", "JOE", "HNI", "HUT", "AA", "ZION", "KRMN", "DOCN", "APTV", "ZWS", "FR", 
    "CELH", "PII", "PHIN", "EDU", "SUPN", "AIR", "CIB", "STNG", "TFII", "LAZ", "CAMT", 
    "UMBF", "EPR", "EXAS", "AHR", "HASI", "SNEX", "SYNA", "HCC", "SHG", "GBCI", 
    "ATRO", "CTRE", "TMHC", "WES", "ADM", "MCY", "OVV", "EFSC", "ACT", "DCI", "AGI", 
    "NE", "CGON", "HRMY", "SFBS", "ST", "TTEK", "LAUR", "PLAB", "ROL", "JHG", "AGCO", 
    "HTHT", "HAS", "AX"
]

ALL_SYMBOLS = SYMBOLS_CONTEXT + SYMBOLS_STOCKS

def setup_db():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def get_data(symbol):
    file_path = os.path.join(DATA_DIR, f"{symbol}.csv")
    start_date = "2025-01-01"
    
    try:
        t = Ticker(symbol)
        df_new = t.history(start=start_date, interval='1d')
        
        if df_new is None or (isinstance(df_new, dict) and 'error' in df_new) or df_new.empty:
            print(f"[!] {symbol} - Date indisponibile.")
            return False

        df_new = df_new.reset_index()
        expected_cols = ['date', 'open', 'high', 'low', 'close', 'adjclose', 'volume']
        for col in expected_cols:
            if col not in df_new.columns: df_new[col] = 0.0

        df_new = df_new[expected_cols]
        df_new.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
        df_new = df_new.fillna(0.0)

        if os.path.exists(file_path):
            df_old = pd.read_csv(file_path)
            df_final = pd.concat([df_old, df_new]).drop_duplicates(subset=['Date'], keep='last')
        else:
            df_final = df_new

        df_final['Date'] = pd.to_datetime(df_final['Date'])
        df_final = df_final.sort_values('Date')
        df_final.to_csv(file_path, index=False)
        return True
    except Exception as e:
        print(f"[X] {symbol} - Eroare: {e}")
        return False

if __name__ == "__main__":
    setup_db()
    total = len(ALL_SYMBOLS)
    print(f"[INIT] Sesiune de 2 ore pentru {total} simboluri. Ora: {datetime.now()}")
    
    for i, s in enumerate(ALL_SYMBOLS, 1):
        success = get_data(s)
        if success:
            print(f"[{i}/{total}] {s} sincronizat cu succes.")
        
        # LOGICA DE TIMP PENTRU 2 ORE (120 min / 332 actiuni = ~21 secunde medie)
        if i < total: # Nu mai asteptam dupa ultima actiune
            # Pauza variabila intre 15 si 28 secunde pentru a simula un om
            wait_time = random.uniform(15, 28)
            
            # La fiecare 15 actiuni, facem o pauza mult mai mare (o "pauza de cafea")
            if i % 15 == 0:
                coffee_break = random.uniform(120, 240) # Pauza de 2-4 minute
                print(f"--- Pauza lunga (Coffee Break): {coffee_break/60:.1f} minute ---")
                time.sleep(coffee_break)
            else:
                time.sleep(wait_time)

    print(f"[FINAL] Colectare terminata la ora: {datetime.now()}")
