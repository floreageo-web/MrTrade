# ============================================================
# indicators.py — Calcul indicatori tehnici
# ============================================================

import pandas as pd
import numpy as np


def calc_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculează EMA pentru o serie de prețuri."""
    return series.ewm(span=period, adjust=False).mean()


def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculează RSI(14)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculează ATR (Average True Range) — util pentru stop loss dinamic."""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Adaugă toți indicatorii pe DataFrame-ul de prețuri."""
    df = df.copy()
    close = df["Close"]

    df["EMA21"]  = calc_ema(close, 21)
    df["EMA50"]  = calc_ema(close, 50)
    df["EMA200"] = calc_ema(close, 200)
    df["RSI"]    = calc_rsi(close, 14)
    df["ATR"]    = calc_atr(df, 14)

    return df


def is_bullish_candle(row: pd.Series) -> bool:
    """Detectează lumânare bullish (close > open cu minim 0.3% body)."""
    body = abs(row["Close"] - row["Open"])
    range_ = row["High"] - row["Low"]
    if range_ == 0:
        return False
    body_pct = body / range_
    return row["Close"] > row["Open"] and body_pct >= 0.3


def is_engulfing(prev: pd.Series, curr: pd.Series) -> bool:
    """Detectează Bullish Engulfing."""
    prev_bearish = prev["Close"] < prev["Open"]
    curr_bullish = curr["Close"] > curr["Open"]
    engulfs = curr["Close"] > prev["Open"] and curr["Open"] < prev["Close"]
    return prev_bearish and curr_bullish and engulfs


def is_pin_bar(row: pd.Series) -> bool:
    """Detectează Pin Bar bullish (lower wick mare, body mic sus)."""
    body = abs(row["Close"] - row["Open"])
    lower_wick = min(row["Open"], row["Close"]) - row["Low"]
    upper_wick = row["High"] - max(row["Open"], row["Close"])
    if body == 0:
        return False
    return lower_wick >= 2 * body and upper_wick <= body
