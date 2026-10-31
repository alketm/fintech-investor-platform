"""News MCP server: recent headlines for a ticker."""

from datetime import UTC, datetime

import yfinance as yf
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("alko-news", instructions="Recent news headlines for stocks and ETFs.")


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
    items = yf.Ticker(symbol.upper()).news or yf.Search(symbol.upper(), news_count=limit).news or []
    articles = [_normalize(i) for i in items[:limit]]
    return {"symbol": symbol.upper(), "articles": [a for a in articles if a["title"]]}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
