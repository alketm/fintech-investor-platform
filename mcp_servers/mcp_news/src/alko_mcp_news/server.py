"""News MCP server: recent headlines and analyst ratings for a ticker."""

import math
from datetime import UTC, datetime

import pandas as pd
import yfinance as yf
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer(
    "mcp_news",
    instructions="Recent news headlines for stocks and ETFs, and sell-side analyst ratings for stocks.",
)

RATING_CHANGE_DAYS = 90
RATING_CHANGE_LIMIT = 10
ACTIONS = {
    "up": "upgrade",
    "down": "downgrade",
    "init": "initiated",
    "main": "maintained",
    "reit": "reiterated",
}


# yfinance access, replaced in tests.
def _ticker(symbol: str) -> yf.Ticker:
    return yf.Ticker(symbol)


def _now() -> pd.Timestamp:
    return pd.Timestamp.now()


def _num(value, digits: int = 2):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(value) else round(value, digits)


def _normalize(item: dict) -> dict:
    # yfinance has returned both a flat shape and one nested under "content".
    content = item.get("content") or item
    provider = content.get("provider") or {}
    link = (content.get("canonicalUrl") or {}).get("url") or content.get("link")
    published = content.get("pubDate") or content.get("providerPublishTime")
    if isinstance(published, int | float):
        published = datetime.fromtimestamp(published, UTC).isoformat()
    return {
        "title": content.get("title"),
        "publisher": provider.get("displayName") or content.get("publisher"),
        "published": published,
        "summary": content.get("summary"),
        "related_tickers": item.get("relatedTickers") or [],
        "link": link,
    }


@mcp.tool()
def get_news(symbol: str, limit: int = 10) -> dict:
    """Recent news headlines mentioning a ticker. limit is capped at 25.

    Articles often only mention the ticker in passing; use related_tickers and the title to judge relevance.
    """
    limit = max(1, min(limit, 25))
    # Ticker.news is often empty; the search endpoint is the reliable fallback.
    items = _ticker(symbol.upper()).news or yf.Search(symbol.upper(), news_count=limit).news or []
    articles = [_normalize(i) for i in items[:limit]]
    return {"symbol": symbol.upper(), "articles": [a for a in articles if a["title"]]}


@mcp.tool()
def get_analyst_ratings(symbol: str) -> dict:
    """Sell-side analyst view of a stock: consensus rating and score (1 = strong buy ... 5 = strong sell), number
    of analysts, price targets (low/high/mean/median and upside to the mean), monthly rating counts for recent
    months, and the most recent upgrades, downgrades and initiations (last 90 days, up to 10).
    ETFs and stocks without coverage return an error."""
    symbol = symbol.strip().upper()
    ticker = _ticker(symbol)
    info = ticker.info or {}
    trend = ticker.recommendations
    if not info.get("numberOfAnalystOpinions") and (trend is None or trend.empty):
        raise ToolError(f"No analyst coverage for {symbol}")

    targets = ticker.analyst_price_targets or {}
    current = _num(targets.get("current") or info.get("currentPrice"))
    mean = _num(targets.get("mean"))
    return {
        "symbol": symbol,
        "consensus": {
            "rating": info.get("recommendationKey"),
            "mean_score": _num(info.get("recommendationMean")),
            "analyst_count": info.get("numberOfAnalystOpinions"),
        },
        "price_targets": {
            "current_price": current,
            "low": _num(targets.get("low")),
            "high": _num(targets.get("high")),
            "mean": mean,
            "median": _num(targets.get("median")),
            "upside_to_mean_pct": round((mean / current - 1) * 100, 2) if mean and current else None,
        },
        "rating_trend": _rating_trend(trend),
        "recent_changes": _recent_changes(ticker.upgrades_downgrades),
    }


def _rating_trend(trend: pd.DataFrame | None) -> list[dict]:
    if trend is None or trend.empty:
        return []
    cols = ["strongBuy", "buy", "hold", "sell", "strongSell"]
    rows = []
    for _, r in trend.iterrows():
        counts = {c: int(r.get(c, 0) or 0) for c in cols}
        rows.append({"period": r.get("period"), **counts, "total": sum(counts.values())})
    return rows


def _recent_changes(changes: pd.DataFrame | None) -> list[dict]:
    if changes is None or changes.empty:
        return []
    changes = changes.sort_index(ascending=False)
    since = _now() - pd.Timedelta(days=RATING_CHANGE_DAYS)
    recent = changes[pd.DatetimeIndex(changes.index) >= since].head(RATING_CHANGE_LIMIT)
    return [
        {
            "date": str(pd.Timestamp(ts).date()),
            "firm": r.get("Firm"),
            "action": ACTIONS.get(r.get("Action"), r.get("Action")),
            "from_grade": r.get("FromGrade") or None,
            "to_grade": r.get("ToGrade") or None,
            "price_target_action": r.get("priceTargetAction") or None,
            "price_target": _num(r.get("currentPriceTarget")) or None,  # 0 means no target given
            "prior_price_target": _num(r.get("priorPriceTarget")) or None,
        }
        for ts, r in recent.iterrows()
    ]


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
