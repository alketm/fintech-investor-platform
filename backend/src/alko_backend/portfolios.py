"""Portfolio holdings, valuation and analysis."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path

from alko_backend.config import PORTFOLIOS_FILE

QuoteFn = Callable[[str], Awaitable[float]]


def load_portfolios(path: Path = PORTFOLIOS_FILE) -> dict[str, dict]:
    data = json.loads(path.read_text())
    return {p["id"]: p for p in data["portfolios"]}


async def value_portfolio(portfolio: dict, quote: QuoteFn) -> dict:
    prices = await asyncio.gather(*(quote(h["symbol"]) for h in portfolio["holdings"]))
    holdings = []
    for h, price in zip(portfolio["holdings"], prices, strict=True):
        market_value = h["shares"] * price
        cost = h["shares"] * h["cost_basis"]
        holdings.append(
            {
                **h,
                "price": price,
                "market_value": round(market_value, 2),
                "cost": round(cost, 2),
                "gain": round(market_value - cost, 2),
                "gain_pct": round((market_value / cost - 1) * 100, 2) if cost else None,
            }
        )
    total_value = sum(h["market_value"] for h in holdings)
    total_cost = sum(h["cost"] for h in holdings)
    return {
        "id": portfolio["id"],
        "name": portfolio["name"],
        "account_type": portfolio["account_type"],
        "holdings": holdings,
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_gain": round(total_value - total_cost, 2),
        "total_gain_pct": round((total_value / total_cost - 1) * 100, 2) if total_cost else None,
    }


def analyze(valued: dict) -> dict:
    """Allocation by holding and by asset type, plus concentration, from a valued portfolio."""
    total = valued["total_value"]
    by_holding = sorted(
        (
            {
                "symbol": h["symbol"],
                "type": h["type"],
                "weight_pct": round(h["market_value"] / total * 100, 2),
                "gain": h["gain"],
                "gain_pct": h["gain_pct"],
            }
            for h in valued["holdings"]
        ),
        key=lambda x: x["weight_pct"],
        reverse=True,
    )
    by_type: dict[str, float] = {}
    for h in valued["holdings"]:
        by_type[h["type"]] = by_type.get(h["type"], 0.0) + h["market_value"]
    return {
        "id": valued["id"],
        "name": valued["name"],
        "total_value": total,
        "by_holding": by_holding,
        "by_type": [{"type": t, "weight_pct": round(v / total * 100, 2)} for t, v in sorted(by_type.items())],
        "largest_position": by_holding[0] if by_holding else None,
        "top3_weight_pct": round(sum(h["weight_pct"] for h in by_holding[:3]), 2),
    }


def describe_for_agent(portfolio: dict) -> str:
    """Compact holdings description to give agents as context."""
    lines = [f"{portfolio['name']} ({portfolio['account_type']}):"]
    lines += [
        f"- {h['symbol']} ({h['type']}): {h['shares']} shares, cost basis ${h['cost_basis']:.2f}/share"
        for h in portfolio["holdings"]
    ]
    return "\n".join(lines)
