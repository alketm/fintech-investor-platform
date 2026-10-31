"""get_analyst_ratings with yfinance replaced by fakes: no network access."""

from types import SimpleNamespace

import pandas as pd
import pytest
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError

from alko_mcp_news import server

TREND = pd.DataFrame(
    {
        "period": ["0m", "-1m"],
        "strongBuy": [6, 6],
        "buy": [18, 19],
        "hold": [13, 13],
        "sell": [3, 3],
        "strongSell": [3, 3],
    }
)


def _changes():
    # 12 recent actions (one per day) plus one older than 90 days.
    dates = [pd.Timestamp("2026-10-20") - pd.Timedelta(days=i) for i in range(12)] + [
        pd.Timestamp("2026-05-01")
    ]
    return pd.DataFrame(
        {
            "Firm": [f"Firm {i}" for i in range(13)],
            "ToGrade": ["Buy"] * 13,
            "FromGrade": ["Hold"] + [""] * 12,
            "Action": ["up"] + ["main"] * 12,
            "priceTargetAction": ["Raises"] * 13,
            "currentPriceTarget": [400.0] + [350.0] * 12,
            "priorPriceTarget": [0.0] + [340.0] * 12,
        },
        index=pd.DatetimeIndex(dates, name="GradeDate"),
    )


COVERED = SimpleNamespace(
    info={"recommendationKey": "buy", "recommendationMean": 2.23256, "numberOfAnalystOpinions": 38},
    recommendations=TREND,
    analyst_price_targets={"current": 300.0, "low": 245.0, "high": 405.0, "mean": 330.0, "median": 337.5},
    upgrades_downgrades=_changes(),
)

UNCOVERED = SimpleNamespace(
    info={"quoteType": "ETF"},
    recommendations=pd.DataFrame(),
    analyst_price_targets={},
    upgrades_downgrades=None,
)


@pytest.fixture(autouse=True)
def fake_yfinance(monkeypatch):
    monkeypatch.setattr(server, "_ticker", lambda s: COVERED if s == "AAPL" else UNCOVERED)
    monkeypatch.setattr(server, "_now", lambda: pd.Timestamp("2026-10-31"))


def test_full_output():
    out = server.get_analyst_ratings(" aapl ")
    assert out["symbol"] == "AAPL"
    assert out["consensus"] == {"rating": "buy", "mean_score": 2.23, "analyst_count": 38}
    assert out["price_targets"]["upside_to_mean_pct"] == 10.0
    assert out["price_targets"]["median"] == 337.5
    assert out["rating_trend"][0] == {
        "period": "0m",
        "strongBuy": 6,
        "buy": 18,
        "hold": 13,
        "sell": 3,
        "strongSell": 3,
        "total": 43,
    }


def test_recent_changes_are_limited_and_cleaned():
    changes = server.get_analyst_ratings("AAPL")["recent_changes"]
    assert len(changes) == server.RATING_CHANGE_LIMIT
    assert all(c["date"] >= "2026-08-02" for c in changes)
    first = changes[0]
    assert first == {
        "date": "2026-10-20",
        "firm": "Firm 0",
        "action": "upgrade",
        "from_grade": "Hold",
        "to_grade": "Buy",
        "price_target_action": "Raises",
        "price_target": 400.0,
        "prior_price_target": None,
    }
    assert changes[1]["action"] == "maintained" and changes[1]["from_grade"] is None


def test_no_coverage_is_an_error():
    with pytest.raises(ToolError, match="No analyst coverage for VTI"):
        server.get_analyst_ratings("VTI")


async def test_no_coverage_message_reaches_mcp_client():
    # Only ToolError messages survive to the client in mcp 2.x; anything else is masked.
    async with Client(server.mcp) as client:
        result = await client.call_tool("get_analyst_ratings", {"symbol": "VTI"})
    assert result.is_error
    assert "No analyst coverage for VTI" in result.content[0].text
