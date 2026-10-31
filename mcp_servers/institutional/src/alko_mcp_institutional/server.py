"""Institutional MCP server: who owns a stock and whether the largest holders are buying or selling."""

import yfinance as yf
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from alko_mcp_institutional import analytics

mcp = MCPServer(
    "alko-institutional",
    instructions="Institutional ownership of stocks from 13F filings via yfinance: ownership summary, top 10 "
    "institutions and top 10 mutual funds, and their changes since the prior filing.",
)

COVERAGE_NOTE = (
    "13F filings lag the quarter end by up to 45 days, and holder data covers only the top 10 institutions and "
    "top 10 mutual funds."
)


# yfinance access, replaced in tests.
def _ticker(symbol: str) -> yf.Ticker:
    return yf.Ticker(symbol)


def _load(symbol: str) -> tuple[str, dict, list[dict], list[dict], dict]:
    """(symbol, info, institutions, funds, major_holders breakdown)."""
    symbol = symbol.strip().upper()
    ticker = _ticker(symbol)
    info = ticker.info or {}
    if info.get("quoteType") == "ETF":
        raise ToolError(f"{symbol} is an ETF; institutional ownership data covers individual stocks")
    institutions = analytics.holders(ticker.institutional_holders)
    funds = analytics.holders(ticker.mutualfund_holders)
    major = ticker.major_holders
    breakdown = {}
    if major is not None and not major.empty and "Value" in major.columns:
        breakdown = {k: analytics.clean(v) for k, v in major["Value"].items()}
    if not institutions and not funds and not breakdown:
        raise ToolError(f"No institutional ownership data for {symbol}")
    return symbol, info, institutions, funds, breakdown


@mcp.tool()
def get_institutional_ownership(symbol: str) -> dict:
    """Ownership summary for a stock: % held by institutions (of shares and of float), % held by insiders, the
    remaining "other" % (retail and unreported holders), number of institutions, shares outstanding and float,
    implied institutional shares, and the combined % held by the top 10 institutions."""
    symbol, info, institutions, funds, b = _load(symbol)
    inst = b.get("institutionsPercentHeld", info.get("heldPercentInstitutions"))
    insiders = b.get("insidersPercentHeld", info.get("heldPercentInsiders"))
    shares_out = info.get("sharesOutstanding")
    other = None
    if inst is not None and insiders is not None:
        other = max(0.0, 1 - inst - insiders)  # institutional % can exceed 100% via double-counted lending
    count = b.get("institutionsCount")
    return {
        "symbol": symbol,
        "as_of": analytics.latest_date(institutions, funds),
        "institutions_pct": analytics.pct(inst),
        "institutions_pct_of_float": analytics.pct(b.get("institutionsFloatPercentHeld")),
        "insiders_pct": analytics.pct(insiders),
        "other_pct": analytics.pct(other),
        "institution_count": int(count) if count is not None else None,
        "shares_outstanding": shares_out,
        "float_shares": info.get("floatShares"),
        "institutional_shares_implied": round(inst * shares_out) if inst is not None and shares_out else None,
        "top10_institutions_pct": round(sum(h["pct_held"] or 0 for h in institutions), 3)
        if institutions
        else None,
        "note": COVERAGE_NOTE,
    }


@mcp.tool()
def get_top_institutional_holders(symbol: str) -> dict:
    """Largest holders of a stock: the top 10 institutions and top 10 mutual funds, each with date reported,
    % of shares held, shares, market value, and % change in shares since the prior filing."""
    symbol, _, institutions, funds, _ = _load(symbol)
    return {
        "symbol": symbol,
        "as_of": analytics.latest_date(institutions, funds),
        "institutions": institutions,
        "mutual_funds": funds,
        "note": COVERAGE_NOTE,
    }


@mcp.tool()
def get_institutional_ownership_changes(symbol: str) -> dict:
    """Whether the largest holders are buying or selling: for each top institution and mutual fund, shares now,
    estimated shares at the prior filing, change in shares and direction; a summary per group (buyers vs sellers,
    net share change and as % of shares outstanding); and the largest increases and decreases."""
    symbol, info, institutions, funds, _ = _load(symbol)
    shares_out = info.get("sharesOutstanding")
    groups = {"institutions": institutions, "mutual_funds": funds}
    result = {"symbol": symbol, "as_of": analytics.latest_date(institutions, funds)}
    for name, rows in groups.items():
        changed = [analytics.change(h) for h in rows]
        result[name] = {
            "summary": analytics.summarize_changes(changed, shares_out),
            "largest_moves": analytics.largest_moves(changed),
            "holders": changed,
        }
    result["note"] = (
        f"{COVERAGE_NOTE} Prior shares are estimated from the reported % change; changes under 0.1% count as "
        "unchanged. Mutual funds are often part of the institutions listed, so the groups overlap."
    )
    return result


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
