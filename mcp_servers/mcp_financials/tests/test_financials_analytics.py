import pandas as pd
import pytest
from financials_fixtures import BALANCE, CASH_FLOW, INCOME, INFO, QUARTERLY_INCOME, frame

from alko_mcp_financials import analytics
from alko_mcp_financials.analytics import Statements
from alko_mcp_financials.statements import INCOME_LINES, payload, sort_newest_first, value


@pytest.fixture
def s():
    return Statements(INCOME, BALANCE, CASH_FLOW, sort_newest_first(QUARTERLY_INCOME))


def test_value_lookup_uses_aliases_and_handles_gaps():
    alt = frame({"Operating Revenue": [10.0]})
    assert value(alt, "revenue") == 10.0
    assert value(BALANCE, "inventory", 2) is None  # NaN
    assert value(BALANCE, "inventory", 9) is None  # no such column
    assert value(INCOME, "inventory") is None  # not on this statement


def test_payload_drops_empty_periods():
    periods = payload(sort_newest_first(QUARTERLY_INCOME), INCOME_LINES)
    assert len(periods) == 5
    assert periods[0]["period_end"] == "2025-12-31" and periods[0]["revenue"] == 300
    assert periods[0]["gross_profit"] is None


def test_window_years_and_cagr():
    assert analytics.window_years("3y", 3) == 2
    assert analytics.window_years("1y", 3) == 1
    assert analytics.window_years("max", 4) == 3
    assert analytics.cagr(640, 1000, 2) == pytest.approx(0.25)
    assert analytics.cagr(-10, 100, 2) is None


def test_annual_trend_oldest_first(s):
    trend = analytics.annual_trend(s, 2)
    assert [t["fiscal_year_end"] for t in trend] == ["2023-12-31", "2024-12-31", "2025-12-31"]
    assert trend[-1] == {
        "fiscal_year_end": "2025-12-31",
        "revenue": 1000,
        "net_income": 180,
        "free_cash_flow": 200,
        "gross_margin_pct": 40.0,
        "operating_margin_pct": 25.0,
        "net_margin_pct": 18.0,
    }


def test_growth(s):
    g = analytics.growth(s, 2)
    assert g["revenue"]["cagr_pct"] == 25.0
    assert [y["yoy_pct"] for y in g["revenue"]["yearly"]] == [None, 25.0, 25.0]
    assert g["net_income"]["yearly"][-1]["yoy_pct"] == 50.0
    assert g["net_income"]["cagr_pct"] == pytest.approx(43.02, abs=0.01)
    assert g["free_cash_flow"]["cagr_pct"] == pytest.approx(82.57, abs=0.01)


def test_free_cash_flow_falls_back_to_ocf_plus_capex():
    s = Statements(INCOME, BALANCE, CASH_FLOW.drop(index="Free Cash Flow"))
    assert analytics.free_cash_flow(s) == 200


def test_latest_quarter_yoy(s):
    q = analytics.latest_quarter_yoy(s.quarterly_income)
    assert q["revenue_yoy_pct"] == 25.0 and q["net_income_yoy_pct"] == 50.0
    assert q["diluted_eps_yoy_pct"] is None  # no EPS a year earlier
    assert analytics.latest_quarter_yoy(QUARTERLY_INCOME.iloc[:, :3]) is None


def test_health(s):
    h = analytics.health(s, market_cap=3000, is_financial=False)
    assert h["liquidity"] == {"current_ratio": 2.0, "quick_ratio": 1.75, "cash_ratio": 0.75}
    assert h["leverage"] == {
        "debt_to_equity": 0.5,
        "debt_to_assets": 0.25,
        "liabilities_to_assets": 0.5,
        "net_debt": 200,  # no Net Debt line: total debt - cash and short-term investments
        "net_debt_to_ebitda": 0.667,
    }
    assert h["interest_coverage"] == 10.0
    assert h["altman_z"] == {"score": 3.37, "zone": "safe"}
    assert h["notes"] == []


def test_piotroski(s):
    p = analytics.piotroski(s)
    assert p["signals_available"] == 9
    assert p["score"] == 8
    assert p["signals"]["higher_asset_turnover"] == 0  # 0.5 both years


def test_health_for_financial_companies_skips_altman(s):
    h = analytics.health(s, 3000, is_financial=True)
    assert h["altman_z"]["score"] is None and "Not meaningful" in h["altman_z"]["note"]
    assert h["notes"]


def test_health_with_missing_lines():
    bank = Statements(INCOME[["2025-12-31"]], frame({"Total Assets": [5000], "Total Debt": [800]}), CASH_FLOW)
    h = analytics.health(bank, 3000, is_financial=False)
    assert h["liquidity"]["current_ratio"] is None
    assert h["altman_z"]["score"] is None
    assert h["piotroski_f"]["signals_available"] < 9


def test_efficiency(s):
    e = analytics.efficiency(s)
    assert e["asset_turnover"] == pytest.approx(0.556, abs=0.001)
    assert e["fixed_asset_turnover"] == pytest.approx(2.222, abs=0.001)
    assert e["inventory_turnover"] == pytest.approx(6.667, abs=0.001)
    assert e["days_inventory_outstanding"] == pytest.approx(54.75, abs=0.06)
    assert e["days_sales_outstanding"] == pytest.approx(51.1, abs=0.06)
    assert e["days_payables_outstanding"] == pytest.approx(66.9, abs=0.06)
    assert e["cash_conversion_cycle_days"] == pytest.approx(38.9, abs=0.06)
    assert e["working_capital_turnover"] == pytest.approx(3.333, abs=0.001)
    assert e["rd_pct_of_revenue"] == 5.0 and e["sga_pct_of_revenue"] == 10.0


def test_profitability(s):
    p = analytics.profitability(s)
    assert p["gross_margin_pct"] == 40.0 and p["fcf_margin_pct"] == 20.0 and p["ebitda_margin_pct"] == 30.0
    assert p["roe_pct"] == pytest.approx(21.18, abs=0.01)
    assert p["roa_pct"] == 10.0
    assert p["roic_pct"] == pytest.approx(16.67, abs=0.01)  # NOPAT 200 / (500 + 1000 - 300)


def test_valuation_and_per_share(s):
    v = analytics.valuation(INFO, s)
    assert v["pe_trailing"] == 16.67 and v["pe_forward"] is None
    assert v["dividend_yield_pct"] == 2.0 and v["payout_ratio_pct"] == 30.0
    assert v["fcf_yield_pct"] == pytest.approx(6.67, abs=0.01)
    assert analytics.per_share(INFO, s) == {
        "eps_diluted": 1.8,
        "book_value_per_share": 10.0,
        "fcf_per_share": 2.0,
    }


def test_sort_newest_first_drops_empty_columns():
    df = frame(
        {"Total Revenue": [1.0, 2.0]}, columns=pd.to_datetime(["2023-12-31", "2025-12-31", "2024-12-31"])
    )
    out = sort_newest_first(df)
    assert [str(c.date()) for c in out.columns] == ["2025-12-31", "2023-12-31"]
