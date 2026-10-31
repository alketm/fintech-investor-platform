"""Institutional tools with yfinance replaced by fakes: no network access."""

from types import SimpleNamespace

import pandas as pd
import pytest
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError

from alko_mcp_institutional import analytics, server

COLUMNS = ["Date Reported", "Holder", "pctHeld", "Shares", "Value", "pctChange"]


def _table(rows):
    return pd.DataFrame(rows, columns=COLUMNS)


INSTITUTIONS = _table(
    [
        ("2026-06-30", "Seller Co", 0.09, 900, 90_000, -0.10),  # 1000 -> 900
        ("2026-06-30", "Buyer Co", 0.12, 1200, 120_000, 0.20),  # 1000 -> 1200
        ("2026-03-31", "Steady Co", 0.05, 500, 50_000, 0.0005),  # under 0.1%: unchanged
        ("2026-06-30", "New Co", 0.03, 300, 30_000, float("nan")),  # no change reported
    ]
)
FUNDS = _table([("2026-06-30", "Index Fund", 0.04, 400, 40_000, -0.20)])  # 500 -> 400
MAJOR = pd.DataFrame(
    {"Value": [0.02, 0.60, 0.62, 1234.0]},
    index=pd.Index(
        [
            "insidersPercentHeld",
            "institutionsPercentHeld",
            "institutionsFloatPercentHeld",
            "institutionsCount",
        ],
        name="Breakdown",
    ),
)

EMPTY = pd.DataFrame()
TICKERS = {
    "EXM": SimpleNamespace(
        info={"quoteType": "EQUITY", "sharesOutstanding": 10_000, "floatShares": 9_800},
        institutional_holders=INSTITUTIONS,
        mutualfund_holders=FUNDS,
        major_holders=MAJOR,
    ),
    "VTI": SimpleNamespace(info={"quoteType": "ETF"}),
    "NODATA": SimpleNamespace(
        info={"quoteType": "EQUITY"},
        institutional_holders=EMPTY,
        mutualfund_holders=EMPTY,
        major_holders=EMPTY,
    ),
}


@pytest.fixture(autouse=True)
def fake_yfinance(monkeypatch):
    monkeypatch.setattr(server, "_ticker", lambda s: TICKERS[s])


def test_change_estimates_prior_shares():
    up = analytics.change({"shares": 1200, "pct_change": 20.0})
    assert up["prior_shares"] == 1000 and up["share_change"] == 200 and up["direction"] == "increased"
    flat = analytics.change({"shares": 500, "pct_change": 0.05})
    assert flat["direction"] == "unchanged" and flat["share_change"] == 0
    unknown = analytics.change({"shares": 300, "pct_change": None})
    assert unknown["direction"] is None and unknown["prior_shares"] is None


def test_ownership_summary():
    o = server.get_institutional_ownership(" exm ")
    assert o["symbol"] == "EXM" and o["as_of"] == "2026-06-30"
    assert (o["institutions_pct"], o["institutions_pct_of_float"], o["insiders_pct"], o["other_pct"]) == (
        60.0,
        62.0,
        2.0,
        38.0,
    )
    assert o["institution_count"] == 1234
    assert o["institutional_shares_implied"] == 6000
    assert o["top10_institutions_pct"] == 29.0
    assert "45 days" in o["note"]


def test_top_holders_sorted_by_shares():
    t = server.get_top_institutional_holders("EXM")
    assert [h["holder"] for h in t["institutions"]] == ["Buyer Co", "Seller Co", "Steady Co", "New Co"]
    buyer = t["institutions"][0]
    assert buyer == {
        "holder": "Buyer Co",
        "date_reported": "2026-06-30",
        "pct_held": 12.0,
        "shares": 1200,
        "value": 120_000.0,
        "pct_change": 20.0,
    }
    assert t["institutions"][3]["pct_change"] is None
    assert t["mutual_funds"][0]["holder"] == "Index Fund"


def test_ownership_changes():
    c = server.get_institutional_ownership_changes("EXM")
    inst = c["institutions"]
    assert inst["summary"] == {
        "holders": 4,
        "increased": 1,
        "decreased": 1,
        "unchanged": 1,
        "unknown": 1,
        "net_share_change": 100,
        "net_change_pct_of_shares_outstanding": 1.0,
    }
    assert [m["holder"] for m in inst["largest_moves"]["increases"]] == ["Buyer Co"]
    assert [m["holder"] for m in inst["largest_moves"]["decreases"]] == ["Seller Co"]
    funds = c["mutual_funds"]["summary"]
    assert funds["decreased"] == 1 and funds["net_share_change"] == -100
    assert "overlap" in c["note"]


def test_etf_and_no_data_are_tool_errors():
    with pytest.raises(ToolError, match="is an ETF"):
        server.get_institutional_ownership("VTI")
    with pytest.raises(ToolError, match="No institutional ownership data for NODATA"):
        server.get_top_institutional_holders("NODATA")


async def test_tools_registered_and_errors_reach_client():
    async with Client(server.mcp) as client:
        names = {t.name for t in (await client.list_tools()).tools}
        result = await client.call_tool("get_institutional_ownership_changes", {"symbol": "VTI"})
    assert names == {
        "get_institutional_ownership",
        "get_top_institutional_holders",
        "get_institutional_ownership_changes",
    }
    assert result.is_error and "is an ETF" in result.content[0].text
