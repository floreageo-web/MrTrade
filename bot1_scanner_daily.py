from datetime import datetime

def detecteaza_pullback(df, simbol):
    try:
        # ===============================
        # PROTECȚIE DATE MINIME
        # ===============================
        if len(df) < 210:
            return None

        idx   = -1
        c     = df.iloc[idx]
        prev  = df.iloc[idx - 1]
        prev2 = df.iloc[idx - 2]

        close  = c['Close']
        open_  = c['Open']
        high   = c['High']
        low    = c['Low']
        ma20   = c['ma20']
        ma50   = c['ma50']
        ma200  = c['ma200']
        rsi    = c['rsi']
        volume = c['Volume']
        vol_ma = c['vol_ma']
        atr    = c['atr']

        # ===============================
        # 1. FILTRU LICHIDITATE
        # ===============================
        dollar_volume = close * volume
        if dollar_volume < 1_500_000:
            return None

        # ===============================
        # 2. TREND PUTERNIC
        # ===============================
        trend_ok = (
            close > ma200 and
            ma50  > ma200 and
            ma20  > ma50  and
            c.get('ma200_rising', False) is True
        )
        if not trend_ok:
            return None

        # ===============================
        # 3. PULLBACK CONTROLAT
        # ===============================
        pullback_ma20 = low <= ma20 * 1.015 and close >= ma20 * 0.98
        pullback_ma50 = low <= ma50 * 1.015 and close >= ma50 * 0.98

        if not (pullback_ma20 or pullback_ma50):
            return None

        zona = "MA20 🎯" if pullback_ma20 else "MA50 🎯"

        # ===============================
        # 4. RSI GOLDILOCKS
        # ===============================
        if not (45 <= rsi <= 55):
            return None

        # ===============================
        # 5. VOLUM REDUS (PULLBACK SĂNĂTOS)
        # ===============================
        vol_ratio = volume / vol_ma
        if vol_ratio > 0.75:
            return None

        # ===============================
        # 6. CONFIRMARE PRICE ACTION
        # ===============================

        # Engulfing bullish (realist, dar încă strict)
        engulfing = (
            close > open_ and
            close > prev['Close'] and
            open_  < prev['Open']
        )

        # Rejection / Pin bar
        corp     = abs(close - open_)
        wick_jos = min(open_, close) - low
        respingere = (
            close > open_ and
            wick_jos >= corp * 2
        )

        # Inside Bar real + breakout
        inside_bar = (
            prev['High'] < prev2['High'] and
            prev['Low']  > prev2['Low']
        )
        inside_break = inside_bar and close > prev['High']

        if not (engulfing or respingere or inside_break):
            return None

        if engulfing:
            tip_lumanare = "ENGULFING 💪"
        elif inside_break:
            tip_lumanare = "INSIDE BREAK 📊"
        else:
            tip_lumanare = "REJECTION PIN 🔄"

        # ===============================
        # 7. SL INTELIGENT (STRUCTURAL)
        # ===============================
        lookback   = min(6, len(df) - 2)
        swing_low  = df['Low'].iloc[idx - lookback:idx].min()

        sl_anticipat = round(
            min(swing_low, ma50) - atr * 0.2,
            2
        )

        sl_pct = round(
            (close - sl_anticipat) / close * 100,
            2
        )

        # ===============================
        # OUTPUT FINAL
        # ===============================
        return {
            'simbol':        simbol,
            'zona':          zona,
            'tip_lumanare':  tip_lumanare,
            'close_azi':     round(close, 2),
            'sl_anticipat':  sl_anticipat,
            'sl_pct':        sl_pct,
            'rsi':           round(rsi, 1),
            'vol_ratio':     round(vol_ratio, 2),
            'ma20':          round(ma20, 2),
            'ma50':          round(ma50, 2),
            'atr':           round(atr, 2),
            'swing_low':     round(swing_low, 2),
            'data_setup':    datetime.now().strftime('%Y-%m-%d'),
            'status':        'asteapta_confirmare',
            'tp1_atins':     False
        }

    except Exception as e:
        print(f"[EROARE semnal {simbol}]: {e}")
        return None
