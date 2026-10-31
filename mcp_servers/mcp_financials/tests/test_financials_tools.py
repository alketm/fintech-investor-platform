"""Tool tests with yfinance replaced by fakes: no network access."""

from types import SimpleNamespace

import pandas as pd
import pytest
from financials_fixtures import BALANCE, CASH_FLOW, INCOME, INFO, QUARTERLY_INCOME
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError

from alko_mcp_financials import server


def _company(info=INFO):
    return SimpleNamespace(
        info=info,
        income_stmt=INCOME,
        quarterly_income_stmt=QUARTERLY_INCOME,
        balance_sheet=BALANCE,
        quarterly_balance_sheet=BALANCE,
        cashflow=CASH_FLOW,
        quarterly_cashflow=CASH_FLOW,
    )


TICKERS = {
    "EXM": _company(),
    "BANK": _company({**INFO, "sector": "Financial Services"}),
    "VTI": SimpleNamespace(info={"quoteType": "ETF"}),
    "EMPTY": SimpleNamespace(
        info={"quoteType": "EQUITY"},
        income_stmt=pd.DataFrame(),
        quarterly_income_stmt=pd.DataFrame(),
        balance_sheet=pd.DataFrame(),
        quarterly_balance_sheet=pd.DataFrame(),
        cashflow=pd.DataFrame(),
        quarterly_cashflow=pd.DataFrame(),
    ),
}


@pytest.fixture(autouse=True)
def fake_yfinance(monkeypatch):
    monkeypatch.setattr(server, "_ticker", lambda s: TICKERS[s])


def test_statements():
    income = server.get_income_statement(" exm ")
    assert income["symbol"] == "EXM" and income["currency"] == "USD"
    assert [p["period_end"] for p in income["periods"]] == ["2025-12-31", "2024-12-31", "2023-12-31"]
    assert income["periods"][0]["net_income"] == 180

    quarterly = server.get_income_statement("EXM", "quarterly")
    assert quarterly["period"] == "quarterly" and len(quarterly["periods"]) == 5

    assert server.get_balance_sheet("EXM")["periods"][0]["total_debt"] == 500
    assert server.get_cash_flow("EXM")["periods"][0]["free_cash_flow"] == 200


def test_overview():
    o = server.get_financial_overview("EXM", "max")
    assert o["profile"]["name"] == "Example Corp"
    assert o["years_covered"] == 2 and len(o["annual_trend"]) == 3
    assert o["cagr_pct"]["revenue"] == 25.0


def test_growth_window_is_capped_and_reported():
    g = server.get_growth_analysis("EXM", "1y")
    assert g["years_covered"] == 1 and g["metrics"]["revenue"]["cagr_pct"] == 25.0
    assert g["latest_quarter_yoy"]["revenue_yoy_pct"] == 25.0


def test_health_efficiency_ratios():
    assert server.get_health_analysis("EXM")["altman_z"]["zone"] == "safe"
    assert server.get_efficiency_analysis("EXM")["inventory_turnover"] == pytest.approx(6.667, abs=0.001)
    ratios = server.get_financial_ratios("EXM")
    assert ratios["fiscal_year_end"] == "2025-12-31"
    assert ratios["profitability"]["roa_pct"] == 10.0
    assert ratios["valuation"]["dividend_yield_pct"] == 2.0


def test_financial_sector_gets_notes():
    assert server.get_health_analysis("BANK")["altman_z"]["score"] is None
    assert "note" in server.get_efficiency_analysis("BANK")
    ratios = server.get_financial_ratios("BANK")
    assert ratios["profitability"]["fcf_margin_pct"] is None and ratios["valuation"]["fcf_yield_pct"] is None
    assert ratios["profitability"]["roe_pct"] is not None and "note" in ratios


def test_etf_and_missing_statements_are_tool_errors():
    with pytest.raises(ToolError, match="is an ETF"):
        server.get_financial_ratios("VTI")
    with pytest.raises(ToolError, match="No financial statements"):
        server.get_health_analysis("EMPTY")
    with pytest.raises(ToolError, match="No balance data"):
        server.get_balance_sheet("EMPTY")


async def test_all_eight_tools_registered_and_errors_reach_client():
    async with Client(server.mcp) as client:
        names = {t.name for t in (await client.list_tools()).tools}
        result = await client.call_tool("get_financial_overview", {"symbol": "VTI"})
    assert names == {
        "get_financial_overview",
        "get_income_statement",
        "get_balance_sheet",
        "get_cash_flow",
        "get_growth_analysis",
        "get_health_analysis",
        "get_efficiency_analysis",
        "get_financial_ratios",
    }
    assert result.is_error and "is an ETF" in result.content[0].text
