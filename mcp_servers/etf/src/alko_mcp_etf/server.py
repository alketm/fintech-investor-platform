"""ETF MCP server: fund facts, holdings, sectors, performance, price history and risk."""

import math
from collections.abc import Callable
from datetime import UTC, datetime

import pandas as pd
import yfinance as yf
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from alko_mcp_etf import analytics
from alko_mcp_etf.analytics import Window

mcp = MCPServer(
    "alko-etf",
    instructions="ETF data. Every tool takes a list of symbols so several funds can be compared in one call. "
    "Per-symbol failures are reported under `errors` without failing the rest.",
)

MAX_SYMBOLS = 20


# --- yfinance access (replaced in tests) -------------------------------------------------------------------


def _ticker(symbol: str) -> yf.Ticker:
    return yf.Ticker(symbol)


def _download(symbols: list[str], start: pd.Timestamp | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Daily (close, adj_close) frames with one column per symbol."""
    kwargs = {"start": start.strftime("%Y-%m-%d")} if start is not None else {"period": "max"}
    df = yf.download(symbols, auto_adjust=False, progress=False, threads=True, **kwargs)
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
    df.index = pd.DatetimeIndex(df.index).tz_localize(None)
    return df["Close"], df["Adj Close"]


def _today() -> pd.Timestamp:
    return pd.Timestamp.today()


# --- helpers ---------------------------------------------------------------------------------------------


def _symbols(symbol_list: list[str]) -> list[str]:
    symbols = list(dict.fromkeys(s.strip().upper() for s in symbol_list if s and s.strip()))
    if not symbols:
        raise ToolError("symbol_list is empty")
    if len(symbols) > MAX_SYMBOLS:
        raise ToolError(f"At most {MAX_SYMBOLS} symbols per call")
    return symbols


def _num(value, scale: float = 1.0, digits: int = 4):
    if value is None or isinstance(value, str):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(value) else round(value * scale, digits)


def _per_symbol(symbols: list[str], fn: Callable[[str], dict]) -> tuple[list[dict], dict[str, str]]:
    results, errors = [], {}
    for symbol in symbols:
        try:
            results.append({"symbol": symbol, **fn(symbol)})
        except Exception as e:  # one bad symbol must not fail the batch
            errors[symbol] = str(e) or type(e).__name__
    return results, errors


def _etf_ticker(symbol: str) -> yf.Ticker:
    ticker = _ticker(symbol)
    quote_type = (ticker.info or {}).get("quoteType")
    if quote_type is None:
        raise ToolError("Unknown symbol")
    if quote_type != "ETF":
        raise ToolError(f"Not an ETF (quote type {quote_type})")
    return ticker


def _prices(symbols: list[str], window: Window, extra: tuple[str, ...] = ()):
    close, adj = _download([*symbols, *extra], analytics.window_start(window, _today()))
    return close, adj


def _column(frame: pd.DataFrame, symbol: str) -> pd.Series:
    if symbol not in frame.columns or frame[symbol].dropna().empty:
        raise ToolError("No price history for this window")
    return frame[symbol]


# --- tools -----------------------------------------------------------------------------------------------


@mcp.tool()
def get_etf_basic_info(symbol_list: list[str]) -> dict:
    """Fund facts for each ETF: name, family, category, exchange, currency, inception date, expense ratio %,
    total assets, dividend yield %, NAV and annual turnover %."""

    def info(symbol: str) -> dict:
        ticker = _etf_ticker(symbol)
        i = ticker.info
        inception = i.get("fundInceptionDate")
        turnover = None
        try:
            turnover = _num(ticker.funds_data.fund_operations.loc["Annual Holdings Turnover"].iloc[0], 100, 2)
        except Exception:
            pass
        expense = i.get("netExpenseRatio")
        if expense is None and i.get("annualReportExpenseRatio") is not None:
            expense = i["annualReportExpenseRatio"] * 100
        return {
            "name": i.get("longName") or i.get("shortName"),
            "fund_family": i.get("fundFamily"),
            "category": i.get("category"),
            "legal_type": i.get("legalType"),
            "exchange": i.get("exchange"),
            "currency": i.get("currency"),
            "inception_date": datetime.fromtimestamp(inception, UTC).date().isoformat()
            if inception
            else None,
            "expense_ratio_pct": _num(expense),
            "total_assets": _num(i.get("totalAssets"), digits=0),
            "yield_pct": _num(i.get("yield"), 100, 3),
            "nav_price": _num(i.get("navPrice")),
            "annual_turnover_pct": turnover,
        }

    results, errors = _per_symbol(_symbols(symbol_list), info)
    return {"results": results, "errors": errors}


@mcp.tool()
def get_etf_performance(symbol_list: list[str], window: Window = "1y") -> dict:
    """Return over the window for each ETF: price return %, total return % with dividends reinvested, annualized
    return % (windows of a year or more only), start/end dates and prices."""
    symbols = _symbols(symbol_list)
    close, adj = _prices(symbols, window)
    results, errors = _per_symbol(
        symbols, lambda s: analytics.performance(_column(close, s), _column(adj, s))
    )
    return {"window": window, "results": results, "errors": errors}


@mcp.tool()
def get_etf_price_history(symbol_list: list[str], window: Window = "1y") -> dict:
    """Price history for each ETF as {date, close, adj_close} points (adj_close includes dividends). Points are
    daily up to 6mo/ytd, weekly (last trading day of each week) for 1y-5y, and monthly for 10y/max."""
    symbols = _symbols(symbol_list)
    close, adj = _prices(symbols, window)
    interval, rule = analytics.resample_rule(window)
    results, errors = _per_symbol(
        symbols, lambda s: {"points": analytics.price_points(_column(close, s), _column(adj, s), rule)}
    )
    return {"window": window, "interval": interval, "results": results, "errors": errors}


@mcp.tool()
def get_etf_top_holdings(symbol_list: list[str]) -> dict:
    """Top 10 holdings of each ETF with their weight %, and the combined weight of those holdings."""

    def holdings(symbol: str) -> dict:
        top = _etf_ticker(symbol).funds_data.top_holdings
        rows = [
            {"symbol": sym, "name": row.get("Name"), "weight_pct": _num(row.get("Holding Percent"), 100, 2)}
            for sym, row in top.head(10).iterrows()
        ]
        if not rows:
            return {
                "holdings": [],
                "top10_weight_pct": None,
                "note": "The data source has no holdings for this fund (common for bond funds).",
            }
        return {
            "holdings": rows,
            "top10_weight_pct": round(sum(r["weight_pct"] or 0 for r in rows), 2),
        }

    results, errors = _per_symbol(_symbols(symbol_list), holdings)
    return {"results": results, "errors": errors}


@mcp.tool()
def get_etf_sector_breakdown(symbol_list: list[str]) -> dict:
    """Sector weights % (equity sectors, largest first) and asset-class mix % (stock, bond, cash, other) for each
    ETF. Bond funds typically have few or no sector weights."""

    def breakdown(symbol: str) -> dict:
        funds = _etf_ticker(symbol).funds_data
        sectors = sorted(
            (
                {"sector": name, "weight_pct": _num(w, 100, 2)}
                for name, w in (funds.sector_weightings or {}).items()
                if _num(w)
            ),
            key=lambda x: x["weight_pct"],
            reverse=True,
        )
        assets = {k.removesuffix("Position"): _num(v, 100, 2) for k, v in (funds.asset_classes or {}).items()}
        return {"sectors": sectors, "asset_classes": assets}

    results, errors = _per_symbol(_symbols(symbol_list), breakdown)
    return {"results": results, "errors": errors}


@mcp.tool()
def get_etf_risk_metrics(symbol_list: list[str], window: Window = "1y", benchmark: str = "SPY") -> dict:
    """Risk over the window for each ETF from daily dividend-adjusted returns: annualized volatility, downside
    deviation, max drawdown (with peak/trough dates), beta and correlation vs `benchmark`, Sharpe and Sortino
    ratios, and 1-day historical VaR/CVaR at 95%. Uses the average 13-week T-bill yield as the risk-free rate."""
    symbols = _symbols(symbol_list)
    benchmark = benchmark.strip().upper()
    close, adj = _prices(symbols, window, extra=(benchmark, "^IRX"))

    rf, rf_source = 0.0, "unavailable, using 0"
    if "^IRX" in close.columns and not close["^IRX"].dropna().empty:
        rf, rf_source = float(close["^IRX"].dropna().mean()) / 100, "13-week T-bill (^IRX) average"
    bench = adj[benchmark] if benchmark in adj.columns else pd.Series(dtype=float)

    results, errors = _per_symbol(symbols, lambda s: analytics.risk_metrics(_column(adj, s), bench, rf))
    return {
        "window": window,
        "benchmark": benchmark,
        "risk_free_rate_pct": round(rf * 100, 3),
        "risk_free_rate_source": rf_source,
        "results": results,
        "errors": errors,
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
