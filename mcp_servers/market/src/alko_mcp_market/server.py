"""Market MCP server: market summary, sectors, movers, stock technical analysis and price history."""

import pandas as pd
import yfinance as yf
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from alko_mcp_market import analytics as a
from alko_mcp_market.analytics import Window

mcp = MCPServer(
    "alko-market",
    instructions="US market data from yfinance (delayed about 15 minutes): index and sector performance, daily "
    "movers, technical analysis of a stock, and price history. Indicators are descriptive, not trading signals.",
)

INDICES = {
    "^GSPC": "S&P 500",
    "^DJI": "Dow Jones Industrial Average",
    "^IXIC": "Nasdaq Composite",
    "^RUT": "Russell 2000",
}
CROSS_ASSET = {"DX-Y.NYB": "US dollar index", "CL=F": "WTI crude oil", "GC=F": "Gold"}
SECTORS = {
    "XLK": "Technology",
    "XLF": "Financial Services",
    "XLV": "Healthcare",
    "XLY": "Consumer Cyclical",
    "XLP": "Consumer Defensive",
    "XLE": "Energy",
    "XLI": "Industrials",
    "XLB": "Basic Materials",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLC": "Communication Services",
}
SECTOR_ETF = {name: etf for etf, name in SECTORS.items()}
MOVER_LISTS = {"gainers": "day_gainers", "losers": "day_losers", "most_active": "most_actives"}


# --- yfinance access (replaced in tests) -----------------------------------------------------------------


def _download(symbols: list[str], start: pd.Timestamp | None) -> pd.DataFrame:
    """Daily OHLCV with (field, symbol) columns, dividend-adjusted."""
    kwargs = {"start": start.strftime("%Y-%m-%d")} if start is not None else {"period": "max"}
    df = yf.download(symbols, auto_adjust=True, progress=False, threads=True, **kwargs)
    if df.empty:
        return df
    df.index = pd.DatetimeIndex(df.index).tz_localize(None)
    return df


def _screen(name: str, count: int) -> list[dict]:
    return yf.screen(name, count=count).get("quotes", [])


def _info(symbol: str) -> dict:
    return yf.Ticker(symbol).info or {}


def _today() -> pd.Timestamp:
    return pd.Timestamp.today()


# --- helpers ---------------------------------------------------------------------------------------------


def _closes(df: pd.DataFrame, symbol: str) -> pd.Series:
    if df.empty or ("Close", symbol) not in df.columns:
        return pd.Series(dtype=float)
    return df[("Close", symbol)].dropna()


def _symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not symbol:
        raise ToolError("symbol is empty")
    return symbol


def _perf(closes: pd.Series, window: Window) -> dict:
    return {
        "last": round(float(closes.iloc[-1]), 4) if len(closes) else None,
        "change_1d_pct": a.window_return(closes, "1d"),
        "change_window_pct": a.window_return(closes, window),
    }


# --- tools -----------------------------------------------------------------------------------------------


@mcp.tool()
def get_market_summary(window: Window = "1mo") -> dict:
    """US market snapshot: S&P 500, Dow, Nasdaq and Russell 2000 (last close, 1-day and window change %), VIX and
    10-year Treasury yield (level and change in points), dollar, oil and gold (change %), the S&P 500 versus its
    50- and 200-day averages, and breadth across the 11 sector ETFs (how many rose, leader and laggard)."""
    symbols = [*INDICES, "^VIX", "^TNX", *CROSS_ASSET, *SECTORS]
    df = _download(symbols, a.fetch_start(window, _today(), min_days=300))
    if df.empty:
        raise ToolError("No market data returned")

    indices = {name: _perf(_closes(df, sym), window) for sym, name in INDICES.items()}
    levels = {}
    for sym, name in (("^VIX", "vix"), ("^TNX", "us10y_yield_pct")):
        closes = _closes(df, sym)
        span = a.window_slice(closes, window)
        levels[name] = {
            "last": round(float(closes.iloc[-1]), 3) if len(closes) else None,
            "change_window_points": a.last_change(span),
        }
    cross = {name: _perf(_closes(df, sym), window) for sym, name in CROSS_ASSET.items()}
    sector_moves = {SECTORS[s]: a.window_return(_closes(df, s), window) for s in SECTORS}
    known = {k: v for k, v in sector_moves.items() if v is not None}
    sp = _closes(df, "^GSPC")
    ma = a.moving_averages(sp) if len(sp) else {}
    return {
        "window": window,
        "as_of": str(sp.index[-1].date()) if len(sp) else None,
        "indices": indices,
        "volatility_and_rates": levels,
        "cross_asset": cross,
        "sp500_trend": {
            "price_vs_ma50_pct": ma.get("price_vs_ma50_pct"),
            "price_vs_ma200_pct": ma.get("price_vs_ma200_pct"),
            "cross": ma.get("cross"),
        },
        "breadth": {
            "sectors_up": int(sum(v > 0 for v in known.values())),
            "sectors_total": len(known),
            "leader": max(known, key=known.get) if known else None,
            "laggard": min(known, key=known.get) if known else None,
        },
    }


@mcp.tool()
def get_sector_performance(window: Window = "1mo") -> dict:
    """Performance of the 11 SPDR sector ETFs over the window and the last day, each relative to the S&P 500,
    ranked best to worst, with the leader, laggard and the spread between them."""
    df = _download([*SECTORS, "^GSPC"], a.fetch_start(window, _today()))
    sp_window = a.window_return(_closes(df, "^GSPC"), window)
    rows = []
    for etf, name in SECTORS.items():
        closes = _closes(df, etf)
        r = a.window_return(closes, window)
        if r is None:
            continue
        rows.append(
            {
                "sector": name,
                "etf": etf,
                "change_window_pct": r,
                "change_1d_pct": a.window_return(closes, "1d"),
                "vs_sp500_pct_points": round(r - sp_window, 3) if sp_window is not None else None,
            }
        )
    if not rows:
        raise ToolError("No sector data returned")
    rows.sort(key=lambda x: x["change_window_pct"], reverse=True)
    return {
        "window": window,
        "sp500_change_window_pct": sp_window,
        "sectors": rows,
        "leader": rows[0]["sector"],
        "laggard": rows[-1]["sector"],
        "spread_pct_points": round(rows[0]["change_window_pct"] - rows[-1]["change_window_pct"], 3),
    }


@mcp.tool()
def get_market_movers() -> dict:
    """Today's top 10 US stock gainers, losers and most active by volume: symbol, name, price, change %, volume,
    volume relative to its 3-month average, and market cap. Lists come from Yahoo's predefined screeners."""
    result = {}
    for key, screener in MOVER_LISTS.items():
        try:
            quotes = _screen(screener, 10)
        except Exception as e:
            raise ToolError(f"Yahoo screener {screener} unavailable: {e}") from e
        result[key] = [
            {
                "symbol": q.get("symbol"),
                "name": q.get("shortName") or q.get("longName"),
                "price": q.get("regularMarketPrice"),
                "change_pct": round(q["regularMarketChangePercent"], 2)
                if q.get("regularMarketChangePercent") is not None
                else None,
                "volume": q.get("regularMarketVolume"),
                "volume_vs_3m_avg": round(q["regularMarketVolume"] / q["averageDailyVolume3Month"], 2)
                if q.get("regularMarketVolume") and q.get("averageDailyVolume3Month")
                else None,
                "market_cap": q.get("marketCap"),
            }
            for q in quotes
        ]
    result["note"] = "Gainers and losers often include small caps with outsized moves on news; check volume."
    return result


@mcp.tool()
def get_stock_analysis(symbol: str, window: Window = "1y") -> dict:
    """Technical and relative analysis of a stock or ETF: price and window return, return versus the S&P 500 and
    its sector ETF, 52-week high/low and distance from each, 50/200-day moving averages with golden/death cross,
    RSI(14), MACD(12,26,9), annualized volatility, max drawdown and beta over the window, volume versus its
    3-month average, and a rule-based trend label (rules included)."""
    symbol = _symbol(symbol)
    info = _info(symbol)
    if not info.get("quoteType"):
        raise ToolError(f"Unknown symbol {symbol}")
    sector_etf = SECTOR_ETF.get(info.get("sector"))
    tickers = [symbol, "^GSPC"] + ([sector_etf] if sector_etf and sector_etf != symbol else [])
    df = _download(tickers, a.fetch_start(window, _today(), min_days=400))
    closes = _closes(df, symbol)
    if len(closes) < 2:
        raise ToolError(f"No price history for {symbol}")

    span = a.window_slice(closes, window)
    ret = a.window_return(closes, window)
    sp = _closes(df, "^GSPC")
    sp_ret = a.window_return(sp, window)
    sector_ret = a.window_return(_closes(df, sector_etf), window) if sector_etf else None
    year = closes[closes.index > closes.index[-1] - pd.DateOffset(years=1)]
    price = float(closes.iloc[-1])
    hi, lo = float(year.max()), float(year.min())
    ma = a.moving_averages(closes)
    volume = df[("Volume", symbol)].dropna() if ("Volume", symbol) in df.columns else pd.Series(dtype=float)
    avg_vol = float(volume.iloc[-64:-1].mean()) if len(volume) > 1 else None

    return {
        "symbol": symbol,
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "window": window,
        "as_of": str(closes.index[-1].date()),
        "price": round(price, 4),
        "performance": {
            "change_window_pct": ret,
            "change_1d_pct": a.window_return(closes, "1d"),
            "vs_sp500_pct_points": round(ret - sp_ret, 3) if ret is not None and sp_ret is not None else None,
            "sector_etf": sector_etf,
            "vs_sector_pct_points": round(ret - sector_ret, 3)
            if ret is not None and sector_ret is not None
            else None,
        },
        "range_52w": {
            "high": round(hi, 4),
            "low": round(lo, 4),
            "below_high_pct": round((price / hi - 1) * 100, 2),
            "above_low_pct": round((price / lo - 1) * 100, 2),
        },
        "moving_averages": ma,
        "momentum": {"rsi14": a.rsi(closes), "macd": a.macd(closes)},
        "risk": {
            "annualized_volatility_pct": a.volatility(span),
            "max_drawdown_pct": a.max_drawdown(span),
            "beta_vs_sp500": a.beta(span, sp),
        },
        "volume": {
            "latest": int(volume.iloc[-1]) if len(volume) else None,
            "vs_3m_avg": round(float(volume.iloc[-1]) / avg_vol, 2) if avg_vol else None,
        },
        "trend": a.trend_label(
            ma.get("price_vs_ma50_pct"), ma.get("price_vs_ma200_pct"), ma.get("ma50"), ma.get("ma200")
        ),
        "rules": a.TREND_RULE,
    }


@mcp.tool()
def get_historical_data(symbol: str, window: Window = "1y") -> dict:
    """Price history for a stock, ETF or index as OHLCV bars (dividend-adjusted): daily up to 6mo/ytd, weekly for
    1y-5y, monthly for 10y/max, each labeled with its last trading day. Includes a summary: start and end dates,
    return, high, low and average daily volume."""
    symbol = _symbol(symbol)
    df = _download([symbol], a.fetch_start(window, _today()))
    closes = _closes(df, symbol)
    if len(closes) < 2:
        raise ToolError(f"No price history for {symbol}")
    i = a.base_index(closes, window) or 0
    start_date = closes.index[i]
    daily = pd.DataFrame({f: df[(f, symbol)] for f in ("Open", "High", "Low", "Close", "Volume")})
    daily = daily[daily.index >= start_date].dropna(subset=["Close"])
    interval, rule = a.resample_rule(window)
    bars = a.resample_ohlcv(daily, rule)
    return {
        "symbol": symbol,
        "window": window,
        "interval": interval,
        "summary": {
            "start": str(daily.index[0].date()),
            "end": str(daily.index[-1].date()),
            "return_pct": a.window_return(closes, window),
            "high": round(float(daily["High"].max()), 4),
            "low": round(float(daily["Low"].min()), 4),
            "avg_daily_volume": int(daily["Volume"].mean()) if daily["Volume"].notna().any() else None,
        },
        "bars": [
            {
                "date": str(ts.date()),
                "open": round(float(r.Open), 4),
                "high": round(float(r.High), 4),
                "low": round(float(r.Low), 4),
                "close": round(float(r.Close), 4),
                "volume": int(r.Volume) if pd.notna(r.Volume) else None,
            }
            for ts, r in bars.iterrows()
        ],
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
