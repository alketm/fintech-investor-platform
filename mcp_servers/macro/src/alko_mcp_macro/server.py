"""Macro MCP server: economic indicators (FRED), market signals (yfinance), and how a stock relates to them."""

import pandas as pd
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from alko_mcp_macro import analytics as a
from alko_mcp_macro import fred, market

mcp = MCPServer(
    "alko-macro",
    instructions="US macro environment from FRED (Federal Reserve Bank of St. Louis) and market prices. `symbol` "
    "is optional: without it tools describe the market-wide picture; with it they add how that stock or ETF "
    "relates to the macro backdrop.",
)


# --- data access (replaced in tests) ---------------------------------------------------------------------


def _fred(keys: list[str]) -> dict[str, pd.Series]:
    specs = {k: (a.BY_KEY[k].series_id, a.BY_KEY[k].transform, a.BY_KEY[k].start) for k in keys}
    try:
        return fred.many(specs)
    except fred.FredError as e:
        raise ToolError(str(e)) from e


def _closes(names: list[str], symbol: str | None = None) -> pd.DataFrame:
    """Daily closes for the named market series (plus `symbol` if given), columns renamed to the names."""
    tickers = [market.MARKET_SYMBOLS[n] for n in names] + ([symbol] if symbol else [])
    df = market.closes(tickers)
    return df.rename(columns={v: k for k, v in market.MARKET_SYMBOLS.items()})


def _info(symbol: str) -> dict:
    return market.info(symbol)


# --- helpers ---------------------------------------------------------------------------------------------


def _symbol(symbol: str | None) -> str | None:
    return symbol.strip().upper() if symbol and symbol.strip() else None


def _profile(symbol: str) -> dict:
    info = _info(symbol)
    if not info.get("quoteType"):
        raise ToolError(f"Unknown symbol {symbol}")
    return {
        "symbol": symbol,
        "name": info.get("longName") or info.get("shortName"),
        "quote_type": info.get("quoteType"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "category": info.get("category"),
    }


def _stock_returns(closes: pd.DataFrame, symbol: str) -> pd.Series:
    if symbol not in closes.columns or closes[symbol].dropna().empty:
        raise ToolError(f"No price history for {symbol}")
    return a.monthly_returns(closes[symbol].dropna())


def _series(closes: pd.DataFrame, name: str) -> pd.Series:
    return closes[name].dropna() if name in closes.columns else pd.Series(dtype=float)


# --- tools -----------------------------------------------------------------------------------------------


@mcp.tool()
def get_economic_indicators(symbol: str | None = None) -> dict:
    """Latest US economic indicators from FRED, grouped as rates, inflation, labor, growth, housing, recession,
    financial conditions and consumer. Each has value, units, observation date, prior value and change.
    With `symbol`: the stock's sector and which indicator groups matter most for it."""
    symbol = _symbol(symbol)
    data = _fred([i.key for i in a.INDICATORS])
    groups: dict[str, dict] = {}
    for ind in a.INDICATORS:
        groups.setdefault(ind.group, {})[ind.key] = {
            "label": ind.label,
            "units": ind.units,
            "fred_series": ind.series_id,
            **a.latest(data.get(ind.key)),
        }
    result = {"source": "FRED, Federal Reserve Bank of St. Louis", "indicators": groups}
    if symbol:
        profile = _profile(symbol)
        focus = a.SECTOR_FOCUS.get(profile["sector"], ())
        result["stock"] = {
            **profile,
            "most_relevant_groups": list(focus),
            "note": None if focus else "No sector mapping (ETF or unclassified); see category instead.",
        }
    return result


@mcp.tool()
def analyze_macro_environment(symbol: str | None = None) -> dict:
    """Rule-based read of the US macro environment: growth (expanding / slowing / contracting), inflation (trend
    and vs the Fed's 2% target), monetary policy (real Fed funds rate, yield-curve shape), market stress (VIX,
    high-yield spread, financial conditions), recession signals (Sahm rule, curve inversion), market signals
    (S&P 500, oil, dollar, copper/gold over 3 months) and an overall regime label. Each read lists its evidence
    and rule. With `symbol`: its sector, beta to the S&P 500, and 5-year correlations of its monthly returns
    with changes in the 10-year yield, oil and the dollar."""
    symbol = _symbol(symbol)
    keys = [
        "real_gdp_growth",
        "payrolls_change",
        "industrial_production_yoy",
        "core_cpi_yoy",
        "core_pce_yoy",
        "fed_funds",
        "curve_10y_2y",
        "curve_10y_3m",
        "high_yield_spread",
        "financial_conditions",
        "sahm_rule",
    ]
    d = _fred(keys)
    closes = _closes(["vix", "sp500", "us10y_yield", "dollar_index", "oil_wti", "copper", "gold"], symbol)

    vix = _series(closes, "vix")
    growth = a.growth_read(d["real_gdp_growth"], d["payrolls_change"], d["industrial_production_yoy"])
    inflation = a.inflation_read(d["core_cpi_yoy"], d["core_pce_yoy"])
    result = {
        "regime": a.regime(growth["label"], inflation["trend"], inflation["vs_target"]),
        "growth": growth,
        "inflation": inflation,
        "policy": a.policy_read(d["fed_funds"], d["core_pce_yoy"], d["curve_10y_2y"], d["curve_10y_3m"]),
        "stress": a.stress_read(
            float(vix.iloc[-1]) if len(vix) else None, d["high_yield_spread"], d["financial_conditions"]
        ),
        "recession": a.recession_read(d["sahm_rule"], d["curve_10y_3m"]),
        "market_signals": a.market_signals(closes),
        "as_of": {k: a.latest(v)["date"] for k, v in d.items()},
        "note": "Heuristic labels from published thresholds; use the evidence, not just the label.",
    }
    if symbol:
        returns = _stock_returns(closes, symbol)
        result["stock"] = {
            **_profile(symbol),
            "beta_to_sp500": a.beta(returns, a.monthly_returns(_series(closes, "sp500"))),
            "correlation_with": {
                "us10y_yield_change": a.correlation(
                    returns, a.monthly_change(_series(closes, "us10y_yield"))
                ),
                "oil_return": a.correlation(returns, a.monthly_returns(_series(closes, "oil_wti"))),
                "dollar_return": a.correlation(returns, a.monthly_returns(_series(closes, "dollar_index"))),
            },
            "months": len(returns),
            "note": "Correlations of monthly returns over up to 5 years; |r| < 0.2 is weak.",
        }
    return result


@mcp.tool()
def analyze_consumer_sentiment(symbol: str | None = None) -> dict:
    """US consumer health: UMich sentiment (level, 1- and 12-month change, percentile since 1978), spending
    (retail sales and real consumption YoY), savings rate, credit-card delinquencies, unemployment, and the
    market's view (consumer discretionary vs staples over 3 and 12 months), with an overall strong / mixed / weak
    read and its scoring. With `symbol`: how consumer-sensitive its sector is, and correlations of its monthly
    returns with sentiment changes and discretionary-vs-staples performance."""
    symbol = _symbol(symbol)
    keys = [
        "consumer_sentiment",
        "retail_sales_yoy",
        "real_consumption_yoy",
        "savings_rate",
        "card_delinquency",
        "unemployment",
    ]
    d = _fred(keys)
    closes = _closes(["consumer_discretionary", "consumer_staples"], symbol)
    xly, xlp = _series(closes, "consumer_discretionary"), _series(closes, "consumer_staples")
    ratio = (xly / xlp).dropna()
    xly_xlp_3m, xly_xlp_12m = a.pct_change_over(ratio, 3), a.pct_change_over(ratio, 12)

    sentiment = d["consumer_sentiment"]
    then_1m, then_12m = a.value_at_offset(sentiment, 1), a.value_at_offset(sentiment, 12)
    now = a.latest(sentiment)
    result = {
        "read": a.consumer_read(
            sentiment, d["real_consumption_yoy"], d["card_delinquency"], d["unemployment"], xly_xlp_3m
        ),
        "sentiment": {
            **now,
            "change_1m": round(now["value"] - then_1m, 1) if now["value"] is not None and then_1m else None,
            "change_12m": round(now["value"] - then_12m, 1)
            if now["value"] is not None and then_12m
            else None,
            "percentile_since_1978": a.percentile(sentiment),
        },
        "spending": {
            "retail_sales_yoy_pct": a.latest(d["retail_sales_yoy"]),
            "real_consumption_yoy_pct": a.latest(d["real_consumption_yoy"]),
            "savings_rate_pct": a.latest(d["savings_rate"]),
        },
        "credit_and_jobs": {
            "card_delinquency_pct": a.latest(d["card_delinquency"]),
            "unemployment_pct": a.latest(d["unemployment"]),
        },
        "market_view": {
            "discretionary_vs_staples_3m_pct": xly_xlp_3m,
            "discretionary_vs_staples_12m_pct": xly_xlp_12m,
            "note": "XLY/XLP relative performance: positive means investors favor discretionary spending stocks.",
        },
    }
    if symbol:
        profile = _profile(symbol)
        returns = _stock_returns(closes, symbol)
        result["stock"] = {
            **profile,
            "consumer_sensitivity": a.CONSUMER_SENSITIVITY.get(profile["sector"], "low"),
            "correlation_with": {
                "sentiment_change": a.correlation(returns, a.monthly_change(sentiment)),
                "discretionary_vs_staples": a.correlation(returns, a.monthly_returns(ratio)),
            },
            "months": len(returns),
            "note": "Sector sensitivity is a rule of thumb; correlations use monthly data over up to 5 years.",
        }
    return result


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
