"""Holder tables and ownership-change math, kept free of I/O so they can be unit tested."""

import math

import pandas as pd

UNCHANGED_THRESHOLD = 0.001  # |change| below 0.1% counts as unchanged
TOP_MOVES = 5


def clean(value) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(value) or math.isinf(value) else value


def pct(x: float | None, digits: int = 2) -> float | None:
    return None if x is None else round(x * 100, digits)


def holders(df: pd.DataFrame | None) -> list[dict]:
    """yfinance holder table -> list of holders, largest first."""
    if df is None or df.empty:
        return []
    rows = []
    for _, r in df.iterrows():
        reported = r.get("Date Reported")
        shares = clean(r.get("Shares"))
        rows.append(
            {
                "holder": r.get("Holder"),
                "date_reported": str(pd.Timestamp(reported).date()) if pd.notna(reported) else None,
                "pct_held": pct(clean(r.get("pctHeld")), 3),
                "shares": int(shares) if shares is not None else None,
                "value": clean(r.get("Value")),
                "pct_change": pct(clean(r.get("pctChange"))),
            }
        )
    return sorted(rows, key=lambda h: h["shares"] or 0, reverse=True)


def latest_date(*groups: list[dict]) -> str | None:
    dates = [h["date_reported"] for g in groups for h in g if h["date_reported"]]
    return max(dates) if dates else None


def change(holder: dict) -> dict:
    """Estimate the prior filing's shares from the current shares and the reported % change."""
    shares, pct_change = holder["shares"], holder["pct_change"]
    if shares is None or pct_change is None or pct_change <= -100:
        return {**holder, "prior_shares": None, "share_change": None, "direction": None}
    prior = round(shares / (1 + pct_change / 100))
    if abs(pct_change / 100) < UNCHANGED_THRESHOLD:
        direction = "unchanged"
    else:
        direction = "increased" if pct_change > 0 else "decreased"
    return {**holder, "prior_shares": prior, "share_change": shares - prior, "direction": direction}


def summarize_changes(rows: list[dict], shares_outstanding: float | None) -> dict:
    known = [r for r in rows if r["direction"] is not None]
    net = sum(r["share_change"] for r in known)
    return {
        "holders": len(rows),
        "increased": sum(r["direction"] == "increased" for r in known),
        "decreased": sum(r["direction"] == "decreased" for r in known),
        "unchanged": sum(r["direction"] == "unchanged" for r in known),
        "unknown": len(rows) - len(known),
        "net_share_change": net,
        "net_change_pct_of_shares_outstanding": (
            round(net / shares_outstanding * 100, 3) if shares_outstanding else None
        ),
    }


def largest_moves(rows: list[dict]) -> dict:
    moved = [r for r in rows if r["direction"] in ("increased", "decreased")]
    by_change = sorted(moved, key=lambda r: r["share_change"])
    pick = ("holder", "share_change", "pct_change", "shares")
    return {
        "increases": [{k: r[k] for k in pick} for r in reversed(by_change) if r["share_change"] > 0][
            :TOP_MOVES
        ],
        "decreases": [{k: r[k] for k in pick} for r in by_change if r["share_change"] < 0][:TOP_MOVES],
    }
