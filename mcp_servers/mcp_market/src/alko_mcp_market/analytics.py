"""Window returns, technical indicators and resampling. Free of I/O so they can be unit tested.

Price inputs are date-indexed daily closes (or OHLCV frames), oldest first.
"""

from typing import Literal

import numpy as np
import pandas as pd

Window = Literal["1d", "5d", "1mo", "3mo", "6mo", "ytd", "1y", "3y", "5y", "10y", "max"]
TRADING_DAYS = 252
_TRADING_DAY_WINDOWS = {"1d": 1, "5d": 5}
_OFFSETS = {
    "1mo": pd.DateOffset(months=1),
    "3mo": pd.DateOffset(months=3),
    "6mo": pd.DateOffset(months=6),
    "1y": pd.DateOffset(years=1),
    "3y": pd.DateOffset(years=3),
    "5y": pd.DateOffset(years=5),
    "10y": pd.DateOffset(years=10),
}


def fetch_start(window: Window, today: pd.Timestamp, min_days: int = 0) -> pd.Timestamp | None:
    """First date to download: the window start with a cushion, and at least `min_days` back."""
    today = today.normalize()
    if window == "max":
        return None
    if window in _TRADING_DAY_WINDOWS:
        start = today - pd.Timedelta(days=14)
    elif window == "ytd":
        start = pd.Timestamp(year=today.year, month=1, day=1) - pd.Timedelta(days=7)
    else:
        start = today - _OFFSETS[window] - pd.Timedelta(days=7)
    return min(start, today - pd.Timedelta(days=min_days)) if min_days else start


def base_index(closes: pd.Series, window: Window) -> int | None:
    """Position of the base close for a window return: the last close on or before the window start."""
    closes = closes.dropna()
    if len(closes) < 2:
        return None
    if window in _TRADING_DAY_WINDOWS:
        n = _TRADING_DAY_WINDOWS[window]
        return len(closes) - 1 - n if len(closes) > n else None
    if window == "max":
        return 0
    last = closes.index[-1]
    start = pd.Timestamp(year=last.year, month=1, day=1) if window == "ytd" else last - _OFFSETS[window]
    before = np.flatnonzero(closes.index <= start)
    return int(before[-1]) if len(before) else 0


def window_slice(closes: pd.Series, window: Window) -> pd.Series:
    closes = closes.dropna()
    i = base_index(closes, window)
    return closes.iloc[i:] if i is not None else closes.iloc[0:0]


def window_return(closes: pd.Series, window: Window) -> float | None:
    """Percent change from the window's base close to the last close."""
    s = window_slice(closes, window)
    return None if len(s) < 2 else round(float(s.iloc[-1] / s.iloc[0] - 1) * 100, 3)


def last_change(closes: pd.Series) -> float | None:
    """Change in level (points) over the window slice: for yields and the VIX."""
    return None if len(closes) < 2 else round(float(closes.iloc[-1] - closes.iloc[0]), 3)


def rsi(closes: pd.Series, period: int = 14) -> float | None:
    """Wilder's relative strength index of the latest close."""
    delta = closes.dropna().diff().dropna()
    if len(delta) < period:
        return None
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    if loss.iloc[-1] == 0:
        return 100.0
    return round(float(100 - 100 / (1 + gain.iloc[-1] / loss.iloc[-1])), 2)


def macd(closes: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict | None:
    closes = closes.dropna()
    if len(closes) < slow + signal:
        return None
    line = closes.ewm(span=fast, adjust=False).mean() - closes.ewm(span=slow, adjust=False).mean()
    sig = line.ewm(span=signal, adjust=False).mean()
    hist = line - sig
    return {
        "macd": round(float(line.iloc[-1]), 4),
        "signal": round(float(sig.iloc[-1]), 4),
        "histogram": round(float(hist.iloc[-1]), 4),
        "state": "bullish" if hist.iloc[-1] > 0 else "bearish",
    }


def moving_averages(closes: pd.Series) -> dict:
    closes = closes.dropna()
    price = float(closes.iloc[-1])
    out: dict = {}
    for n in (50, 200):
        ma = float(closes.iloc[-n:].mean()) if len(closes) >= n else None
        out[f"ma{n}"] = round(ma, 4) if ma else None
        out[f"price_vs_ma{n}_pct"] = round((price / ma - 1) * 100, 2) if ma else None
    cross = None
    if len(closes) >= 201:
        ma50, ma200 = closes.rolling(50).mean(), closes.rolling(200).mean()
        diff = (ma50 - ma200).dropna()
        cross = (
            "golden cross (50-day above 200-day)"
            if diff.iloc[-1] > 0
            else "death cross (50-day below 200-day)"
        )
        flips = np.flatnonzero(np.sign(diff.values[1:]) != np.sign(diff.values[:-1]))
        out["last_cross_date"] = str(diff.index[flips[-1] + 1].date()) if len(flips) else None
    out["cross"] = cross
    return out


def trend_label(
    price_vs_ma50: float | None, price_vs_ma200: float | None, ma50: float | None, ma200: float | None
) -> str | None:
    if None in (price_vs_ma50, price_vs_ma200, ma50, ma200):
        return None
    if price_vs_ma50 > 0 and price_vs_ma200 > 0 and ma50 > ma200:
        return "uptrend"
    if price_vs_ma50 < 0 and price_vs_ma200 < 0 and ma50 < ma200:
        return "downtrend"
    return "mixed"


TREND_RULE = (
    "uptrend: price above the 50- and 200-day averages and 50 above 200; downtrend: the reverse; "
    "otherwise mixed. RSI above 70 is often read as overbought, below 30 as oversold."
)


def volatility(closes: pd.Series) -> float | None:
    r = closes.dropna().pct_change().dropna()
    return None if len(r) < 10 else round(float(r.std() * np.sqrt(TRADING_DAYS)) * 100, 2)


def max_drawdown(closes: pd.Series) -> float | None:
    closes = closes.dropna()
    if len(closes) < 2:
        return None
    return round(float((closes / closes.cummax() - 1).min()) * 100, 2)


def beta(stock: pd.Series, market: pd.Series) -> float | None:
    pair = pd.concat({"s": stock, "m": market}, axis=1, sort=True).dropna().pct_change().dropna()
    if len(pair) < 20 or pair["m"].var() == 0:
        return None
    return round(float(pair["s"].cov(pair["m"]) / pair["m"].var()), 3)


def resample_rule(window: Window) -> tuple[str, str | None]:
    if window in ("1d", "5d", "1mo", "3mo", "6mo", "ytd"):
        return "daily", None
    if window in ("1y", "3y", "5y"):
        return "weekly", "W-FRI"
    return "monthly", "ME"


def resample_ohlcv(df: pd.DataFrame, rule: str | None) -> pd.DataFrame:
    """Aggregate daily OHLCV; each bar is labeled with the last trading day in it."""
    df = df.dropna(subset=["Close"])
    if rule is None or df.empty:
        return df
    grouper = pd.Grouper(freq=rule)
    out = df.groupby(grouper).agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    )
    out["date"] = df.index.to_series().groupby(grouper).last()
    return out.dropna(subset=["Close", "date"]).set_index("date")
