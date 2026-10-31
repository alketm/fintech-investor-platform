"""Market-based macro signals from yfinance."""

import pandas as pd
import yfinance as yf

MARKET_SYMBOLS = {
    "vix": "^VIX",
    "sp500": "^GSPC",
    "us10y_yield": "^TNX",
    "dollar_index": "DX-Y.NYB",
    "oil_wti": "CL=F",
    "copper": "HG=F",
    "gold": "GC=F",
    "consumer_discretionary": "XLY",
    "consumer_staples": "XLP",
}


def closes(symbols: list[str], period: str = "5y") -> pd.DataFrame:
    """Daily closes (dividend-adjusted), one column per symbol."""
    df = yf.download(symbols, period=period, auto_adjust=True, progress=False, threads=True)
    if df.empty:
        return pd.DataFrame()
    out = df["Close"]
    out.index = pd.DatetimeIndex(out.index).tz_localize(None)
    return out


def info(symbol: str) -> dict:
    return yf.Ticker(symbol).info or {}
