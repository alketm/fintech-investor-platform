"""Financial statements MCP server: statements plus growth, health, efficiency and ratio analysis."""

from typing import Literal

import yfinance as yf
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from alko_mcp_financials import analytics
from alko_mcp_financials.analytics import Statements, Window
from alko_mcp_financials.statements import (
    BALANCE_LINES,
    CASH_FLOW_LINES,
    INCOME_LINES,
    payload,
    sort_newest_first,
)

mcp = MCPServer(
    "mcp_financials",
    instructions="Company financial statements (from yfinance: about 4 fiscal years and 5-7 quarters) and "
    "analysis built on them. Values are in the company's reporting currency.",
)

Period = Literal["annual", "quarterly"]
FINANCIAL_SECTORS = {"Financial Services"}

_FRAMES = {
    ("income", "annual"): "income_stmt",
    ("income", "quarterly"): "quarterly_income_stmt",
    ("balance", "annual"): "balance_sheet",
    ("balance", "quarterly"): "quarterly_balance_sheet",
    ("cash_flow", "annual"): "cashflow",
    ("cash_flow", "quarterly"): "quarterly_cashflow",
}


# yfinance access, replaced in tests.
def _ticker(symbol: str) -> yf.Ticker:
    return yf.Ticker(symbol)


def _company(symbol: str) -> tuple[str, yf.Ticker, dict]:
    symbol = symbol.strip().upper()
    ticker = _ticker(symbol)
    info = ticker.info or {}
    if info.get("quoteType") == "ETF":
        raise ToolError(f"{symbol} is an ETF; financial statements apply to companies")
    return symbol, ticker, info


def _frame(ticker: yf.Ticker, kind: str, period: str):
    return sort_newest_first(getattr(ticker, _FRAMES[(kind, period)]))


def _statements(symbol: str, ticker: yf.Ticker) -> Statements:
    s = Statements(
        income=_frame(ticker, "income", "annual"),
        balance=_frame(ticker, "balance", "annual"),
        cash_flow=_frame(ticker, "cash_flow", "annual"),
        quarterly_income=_frame(ticker, "income", "quarterly"),
    )
    if s.income.empty:
        raise ToolError(f"No financial statements for {symbol}")
    return s


def _statement_tool(symbol: str, kind: str, period: Period, lines: dict) -> dict:
    symbol, ticker, info = _company(symbol)
    periods = payload(_frame(ticker, kind, period), lines)
    if not periods:
        raise ToolError(f"No {kind.replace('_', ' ')} data for {symbol}")
    return {"symbol": symbol, "period": period, "currency": info.get("financialCurrency"), "periods": periods}


@mcp.tool()
def get_income_statement(symbol: str, period: Period = "annual") -> dict:
    """Income statement per period, newest first: revenue, cost of revenue, gross profit, R&D, SG&A, operating
    expense and income, EBIT, EBITDA, interest expense, pretax income, tax, net income, diluted EPS and shares."""
    return _statement_tool(symbol, "income", period, INCOME_LINES)


@mcp.tool()
def get_balance_sheet(symbol: str, period: Period = "annual") -> dict:
    """Balance sheet per period, newest first: total/current assets, cash, short-term investments, receivables,
    inventory, net PP&E, goodwill and intangibles, total/current liabilities, payables, total/long-term/net debt,
    shareholders' equity, retained earnings, working capital and shares outstanding."""
    return _statement_tool(symbol, "balance", period, BALANCE_LINES)


@mcp.tool()
def get_cash_flow(symbol: str, period: Period = "annual") -> dict:
    """Cash flow statement per period, newest first: operating cash flow, capex, free cash flow, D&A,
    stock-based compensation, change in working capital, investing and financing cash flow, dividends, buybacks,
    and debt issued/repaid. Outflows are negative."""
    return _statement_tool(symbol, "cash_flow", period, CASH_FLOW_LINES)


@mcp.tool()
def get_financial_overview(symbol: str, window: Window = "3y") -> dict:
    """One-call summary of a company: profile (sector, industry, size), trailing-12-month figures (revenue,
    EBITDA, net income, free cash flow, margins, EPS, P/E), a per-fiscal-year trend over `window` (revenue, net
    income, FCF, margins), and CAGR for revenue, net income and FCF. `window` is capped by available data."""
    symbol, ticker, info = _company(symbol)
    s = _statements(symbol, ticker)
    steps = analytics.window_years(window, s.years())
    trend = analytics.annual_trend(s, steps)
    first, last = trend[0], trend[-1]

    def growth(key):
        return analytics.pct(analytics.cagr(first[key], last[key], steps))

    return {
        "symbol": symbol,
        "currency": info.get("financialCurrency"),
        "profile": {
            "name": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country"),
            "employees": info.get("fullTimeEmployees"),
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
        },
        "trailing_12m": {
            "revenue": info.get("totalRevenue"),
            "ebitda": info.get("ebitda"),
            "net_income": info.get("netIncomeToCommon"),
            "free_cash_flow": info.get("freeCashflow"),
            "gross_margin_pct": analytics.pct(info.get("grossMargins")),
            "operating_margin_pct": analytics.pct(info.get("operatingMargins")),
            "net_margin_pct": analytics.pct(info.get("profitMargins")),
            "eps_diluted": info.get("trailingEps"),
            "pe_trailing": analytics.rnd(info.get("trailingPE"), 2),
        },
        "window": window,
        "years_covered": steps,
        "annual_trend": trend,
        "cagr_pct": {
            "revenue": growth("revenue"),
            "net_income": growth("net_income"),
            "free_cash_flow": growth("free_cash_flow"),
        },
    }


@mcp.tool()
def get_growth_analysis(symbol: str, window: Window = "3y") -> dict:
    """Growth over `window` fiscal years for revenue, gross profit, operating income, net income, diluted EPS,
    operating cash flow, free cash flow and equity: yearly values with year-over-year %, plus CAGR %. Also the
    latest quarter vs the same quarter a year earlier. YoY and CAGR are null across negative values."""
    symbol, ticker, info = _company(symbol)
    s = _statements(symbol, ticker)
    steps = analytics.window_years(window, s.years())
    if steps == 0:
        raise ToolError(f"Need at least two fiscal years of statements for {symbol}")
    return {
        "symbol": symbol,
        "currency": info.get("financialCurrency"),
        "window": window,
        "years_covered": steps,
        "metrics": analytics.growth(s, steps),
        "latest_quarter_yoy": analytics.latest_quarter_yoy(s.quarterly_income),
    }


@mcp.tool()
def get_health_analysis(symbol: str) -> dict:
    """Financial health from the latest fiscal year: liquidity (current, quick, cash ratios), leverage
    (debt/equity, debt/assets, liabilities/assets, net debt, net debt/EBITDA), interest coverage, Altman Z-score
    with zone (safe > 2.99, distress < 1.81), and Piotroski F-score (0-9) with each signal."""
    symbol, ticker, info = _company(symbol)
    s = _statements(symbol, ticker)
    is_financial = info.get("sector") in FINANCIAL_SECTORS
    return {
        "symbol": symbol,
        "currency": info.get("financialCurrency"),
        **analytics.health(s, info.get("marketCap"), is_financial),
    }


@mcp.tool()
def get_efficiency_analysis(symbol: str) -> dict:
    """Operating efficiency from the latest fiscal year (averaging balances with the prior year): asset,
    fixed-asset, inventory, receivables, payables and working-capital turnover; days inventory, sales and
    payables outstanding; cash conversion cycle; and R&D and SG&A as % of revenue."""
    symbol, ticker, info = _company(symbol)
    s = _statements(symbol, ticker)
    result = {"symbol": symbol, **analytics.efficiency(s)}
    if info.get("sector") in FINANCIAL_SECTORS:
        result["note"] = "Turnover and working-capital measures are not meaningful for financial companies."
    return result


@mcp.tool()
def get_financial_ratios(symbol: str) -> dict:
    """Key ratios: valuation (trailing/forward P/E, PEG, P/B, P/S, EV/EBITDA, EV/revenue, dividend yield, payout
    ratio, FCF yield) from current market data; profitability (gross, operating, net, EBITDA and FCF margins;
    ROE, ROA, ROIC) and per-share figures (EPS, book value, FCF) from the latest fiscal year."""
    symbol, ticker, info = _company(symbol)
    s = _statements(symbol, ticker)
    result = {
        "symbol": symbol,
        "currency": info.get("financialCurrency"),
        "fiscal_year_end": s.year_label(0),
        "valuation": analytics.valuation(info, s),
        "profitability": analytics.profitability(s),
        "per_share": analytics.per_share(info, s),
    }
    if info.get("sector") in FINANCIAL_SECTORS:
        # A financial company's operating cash flow swings with lending and deposits, so FCF says little.
        result["valuation"]["fcf_yield_pct"] = None
        result["profitability"]["fcf_margin_pct"] = None
        result["per_share"]["fcf_per_share"] = None
        result["note"] = (
            "Financial company: free-cash-flow measures are omitted; use ROE, ROA, P/B and P/E instead."
        )
    return result


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
