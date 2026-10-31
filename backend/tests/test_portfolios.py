import pytest

from alko_backend.portfolios import analyze, load_portfolios, value_portfolio

from .conftest import PRICES


async def _quote(symbol):
    return PRICES[symbol]


def test_seed_has_brokerage_and_ira():
    portfolios = load_portfolios()
    assert set(portfolios) == {"brokerage", "ira"}
    for p in portfolios.values():
        assert {h["type"] for h in p["holdings"]} <= {"stock", "etf"}


async def test_value_portfolio_totals():
    portfolio = {
        "id": "x",
        "name": "X",
        "account_type": "taxable",
        "holdings": [
            {"symbol": "AAPL", "type": "stock", "shares": 10, "cost_basis": 100.0},
            {"symbol": "VTI", "type": "etf", "shares": 4, "cost_basis": 250.0},
        ],
    }
    valued = await value_portfolio(portfolio, _quote)
    assert valued["total_value"] == 3000.0
    assert valued["total_cost"] == 2000.0
    assert valued["holdings"][0]["gain_pct"] == 100.0
    assert valued["holdings"][1]["gain"] == 0.0


async def test_analysis_weights_sum_to_100():
    for portfolio in load_portfolios().values():
        result = analyze(await value_portfolio(portfolio, _quote))
        assert sum(h["weight_pct"] for h in result["by_holding"]) == pytest.approx(100, abs=0.05)
        assert sum(t["weight_pct"] for t in result["by_type"]) == pytest.approx(100, abs=0.05)
        weights = [h["weight_pct"] for h in result["by_holding"]]
        assert weights == sorted(weights, reverse=True)
        assert result["largest_position"]["weight_pct"] == weights[0]
