"""Growth, health, efficiency and ratio calculations on annual statements. Free of I/O for unit testing.

All functions take `Statements` whose frames have the newest period in column 0. Ratios return None whenever
an input is missing or a denominator is zero, rather than guessing.
"""

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from alko_mcp_financials.statements import value

Window = Literal["1y", "2y", "3y", "max"]
DAYS = 365


@dataclass
class Statements:
    income: pd.DataFrame
    balance: pd.DataFrame
    cash_flow: pd.DataFrame
    quarterly_income: pd.DataFrame = field(default_factory=pd.DataFrame)

    def v(self, key: str, col: int = 0) -> float | None:
        for df in (self.income, self.balance, self.cash_flow):
            found = value(df, key, col)
            if found is not None:
                return found
        return None

    def avg(self, key: str) -> float | None:
        """Average of the latest and prior year-end balance; the latest alone if there is no prior year."""
        latest, prior = self.v(key, 0), self.v(key, 1)
        if latest is None:
            return None
        return latest if prior is None else (latest + prior) / 2

    def years(self) -> int:
        return len(self.income.columns)

    def year_label(self, col: int) -> str:
        return str(pd.Timestamp(self.income.columns[col]).date())


def div(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None or b == 0 else a / b


def pct(x: float | None, digits: int = 2) -> float | None:
    return None if x is None else round(x * 100, digits)


def rnd(x: float | None, digits: int = 3) -> float | None:
    return None if x is None else round(x, digits)


def window_years(window: Window, available: int) -> int:
    """Number of year-over-year steps to cover, capped by the periods available."""
    wanted = {"1y": 1, "2y": 2, "3y": 3, "max": available - 1}[window]
    return max(0, min(wanted, available - 1))


def cagr(start: float | None, end: float | None, years: int) -> float | None:
    if start is None or end is None or years <= 0 or start <= 0 or end <= 0:
        return None  # CAGR is undefined across sign changes
    return (end / start) ** (1 / years) - 1


def free_cash_flow(s: Statements, col: int = 0) -> float | None:
    fcf = s.v("free_cash_flow", col)
    if fcf is None:
        ocf, capex = s.v("operating_cash_flow", col), s.v("capital_expenditure", col)
        fcf = None if ocf is None or capex is None else ocf + capex  # capex is reported negative
    return fcf


# --- trend and growth ------------------------------------------------------------------------------------


def annual_trend(s: Statements, steps: int) -> list[dict]:
    """Key figures for the latest `steps + 1` fiscal years, oldest first."""
    rows = []
    for col in range(min(steps, s.years() - 1), -1, -1):
        revenue = s.v("revenue", col)
        rows.append(
            {
                "fiscal_year_end": s.year_label(col),
                "revenue": s.v("revenue", col),
                "net_income": s.v("net_income", col),
                "free_cash_flow": free_cash_flow(s, col),
                "gross_margin_pct": pct(div(s.v("gross_profit", col), revenue)),
                "operating_margin_pct": pct(div(s.v("operating_income", col), revenue)),
                "net_margin_pct": pct(div(s.v("net_income", col), revenue)),
            }
        )
    return rows


GROWTH_METRICS = (
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "diluted_eps",
    "operating_cash_flow",
    "free_cash_flow",
    "stockholders_equity",
)


def _metric(s: Statements, key: str, col: int) -> float | None:
    return free_cash_flow(s, col) if key == "free_cash_flow" else s.v(key, col)


def growth(s: Statements, steps: int) -> dict:
    metrics = {}
    for key in GROWTH_METRICS:
        series = []
        for col in range(steps, -1, -1):
            current, prior = _metric(s, key, col), _metric(s, key, col + 1)
            # YoY against a negative base has no meaningful sign, so it is left out.
            yoy = div(current - prior, prior) if current is not None and prior and prior > 0 else None
            series.append({"fiscal_year_end": s.year_label(col), "value": current, "yoy_pct": pct(yoy)})
        start, end = _metric(s, key, steps), _metric(s, key, 0)
        metrics[key] = {"yearly": series, "cagr_pct": pct(cagr(start, end, steps))}
    return metrics


def latest_quarter_yoy(quarterly_income: pd.DataFrame) -> dict | None:
    """Latest quarter vs the same quarter a year earlier (4 columns back)."""
    if quarterly_income is None or len(quarterly_income.columns) < 5:
        return None
    out = {
        "quarter_end": str(pd.Timestamp(quarterly_income.columns[0]).date()),
        "year_ago_quarter_end": str(pd.Timestamp(quarterly_income.columns[4]).date()),
    }
    for key in ("revenue", "net_income", "diluted_eps"):
        now, then = value(quarterly_income, key, 0), value(quarterly_income, key, 4)
        out[f"{key}_yoy_pct"] = pct(div(now - then, then)) if now is not None and then and then > 0 else None
    return out


# --- health ----------------------------------------------------------------------------------------------


def altman_z(s: Statements, market_cap: float | None) -> dict:
    ta, tl = s.v("total_assets"), s.v("total_liabilities")
    parts = [
        (1.2, div(s.v("working_capital") or _working_capital(s), ta)),
        (1.4, div(s.v("retained_earnings"), ta)),
        (3.3, div(s.v("ebit") or s.v("operating_income"), ta)),
        (0.6, div(market_cap, tl)),
        (1.0, div(s.v("revenue"), ta)),
    ]
    if any(x is None for _, x in parts):
        return {"score": None, "zone": None, "note": "Missing inputs for Altman Z"}
    z = sum(w * x for w, x in parts)
    zone = "safe" if z > 2.99 else "grey" if z >= 1.81 else "distress"
    return {"score": round(z, 2), "zone": zone}


def _working_capital(s: Statements, col: int = 0) -> float | None:
    ca, cl = s.v("current_assets", col), s.v("current_liabilities", col)
    return None if ca is None or cl is None else ca - cl


def _signal(condition: bool | None) -> int | None:
    return None if condition is None else int(condition)


def _gt(a: float | None, b: float | None) -> bool | None:
    return None if a is None or b is None else a > b


def piotroski(s: Statements) -> dict:
    """Piotroski F-score on the latest two fiscal years. ROA uses year-end total assets."""
    roa = [div(s.v("net_income", c), s.v("total_assets", c)) for c in (0, 1)]
    leverage = [div(s.v("long_term_debt", c), s.v("total_assets", c)) for c in (0, 1)]
    current_ratio = [div(s.v("current_assets", c), s.v("current_liabilities", c)) for c in (0, 1)]
    gross_margin = [div(s.v("gross_profit", c), s.v("revenue", c)) for c in (0, 1)]
    turnover = [div(s.v("revenue", c), s.v("total_assets", c)) for c in (0, 1)]
    ocf, ni = s.v("operating_cash_flow"), s.v("net_income")
    shares = [s.v("shares_outstanding", c) or s.v("diluted_shares", c) for c in (0, 1)]

    signals = {
        "positive_roa": _signal(None if roa[0] is None else roa[0] > 0),
        "positive_operating_cash_flow": _signal(None if ocf is None else ocf > 0),
        "improving_roa": _signal(_gt(roa[0], roa[1])),
        "cash_flow_exceeds_net_income": _signal(_gt(ocf, ni)),
        "lower_leverage": _signal(_gt(leverage[1], leverage[0])),
        "higher_current_ratio": _signal(_gt(current_ratio[0], current_ratio[1])),
        "no_share_dilution": _signal(None if None in shares else shares[0] <= shares[1]),
        "higher_gross_margin": _signal(_gt(gross_margin[0], gross_margin[1])),
        "higher_asset_turnover": _signal(_gt(turnover[0], turnover[1])),
    }
    known = [v for v in signals.values() if v is not None]
    return {"score": sum(known), "signals_available": len(known), "signals": signals}


def health(s: Statements, market_cap: float | None, is_financial: bool) -> dict:
    cl = s.v("current_liabilities")
    cash_sti = s.v("cash_and_short_term_investments") or s.v("cash")
    ca, inventory = s.v("current_assets"), s.v("inventory") or 0.0
    debt, equity, ta = s.v("total_debt"), s.v("stockholders_equity"), s.v("total_assets")
    net_debt = s.v("net_debt")
    if net_debt is None and debt is not None and cash_sti is not None:
        net_debt = debt - cash_sti
    ebit = s.v("ebit") or s.v("operating_income")
    interest = s.v("interest_expense")

    result = {
        "fiscal_year_end": s.year_label(0),
        "liquidity": {
            "current_ratio": rnd(div(ca, cl)),
            "quick_ratio": rnd(div(None if ca is None else ca - inventory, cl)),
            "cash_ratio": rnd(div(cash_sti, cl)),
        },
        "leverage": {
            "debt_to_equity": rnd(div(debt, equity)),
            "debt_to_assets": rnd(div(debt, ta)),
            "liabilities_to_assets": rnd(div(s.v("total_liabilities"), ta)),
            "net_debt": net_debt,
            "net_debt_to_ebitda": rnd(div(net_debt, s.v("ebitda"))),
        },
        "interest_coverage": rnd(div(ebit, abs(interest) if interest else None)),
        "altman_z": altman_z(s, market_cap),
        "piotroski_f": piotroski(s),
        "notes": [],
    }
    if is_financial:
        result["altman_z"] = {"score": None, "zone": None, "note": "Not meaningful for financial companies"}
        result["notes"].append(
            "Financial-sector company: liquidity ratios, Altman Z, debt-based leverage and the cash-flow and "
            "margin signals in Piotroski are not comparable to industrial companies; judge capital strength from "
            "regulatory capital instead."
        )
    return result


# --- efficiency and ratios -------------------------------------------------------------------------------


def efficiency(s: Statements) -> dict:
    revenue, cogs = s.v("revenue"), s.v("cost_of_revenue")
    inventory_turnover = div(cogs, s.avg("inventory"))
    receivables_turnover = div(revenue, s.avg("accounts_receivable"))
    payables_turnover = div(cogs, s.avg("accounts_payable"))
    dio, dso, dpo = (div(DAYS, t) for t in (inventory_turnover, receivables_turnover, payables_turnover))
    avg_wc = None
    wc = [s.v("working_capital", c) or _working_capital(s, c) for c in (0, 1)]
    if wc[0] is not None:
        avg_wc = wc[0] if wc[1] is None else (wc[0] + wc[1]) / 2
    return {
        "fiscal_year_end": s.year_label(0),
        "asset_turnover": rnd(div(revenue, s.avg("total_assets"))),
        "fixed_asset_turnover": rnd(div(revenue, s.avg("net_ppe"))),
        "inventory_turnover": rnd(inventory_turnover),
        "receivables_turnover": rnd(receivables_turnover),
        "payables_turnover": rnd(payables_turnover),
        "working_capital_turnover": rnd(div(revenue, avg_wc)) if avg_wc and avg_wc > 0 else None,
        "days_inventory_outstanding": rnd(dio, 1),
        "days_sales_outstanding": rnd(dso, 1),
        "days_payables_outstanding": rnd(dpo, 1),
        # A missing DIO counts as zero (no inventory) so service companies still get a cycle.
        "cash_conversion_cycle_days": rnd((dso + (dio or 0) - dpo), 1)
        if dso is not None and dpo is not None
        else None,
        "rd_pct_of_revenue": pct(div(s.v("research_and_development"), revenue)),
        "sga_pct_of_revenue": pct(div(s.v("selling_general_admin"), revenue)),
    }


def profitability(s: Statements) -> dict:
    revenue, ni = s.v("revenue"), s.v("net_income")
    ebit = s.v("ebit") or s.v("operating_income")
    tax_rate = div(s.v("tax_provision"), s.v("pretax_income"))
    if tax_rate is not None and not 0 <= tax_rate <= 0.5:
        tax_rate = None  # one-off tax items make the effective rate meaningless
    cash = s.v("cash_and_short_term_investments") or s.v("cash") or 0.0
    debt, equity = s.v("total_debt"), s.v("stockholders_equity")
    invested = None if debt is None or equity is None else debt + equity - cash
    nopat = None if ebit is None or tax_rate is None else ebit * (1 - tax_rate)
    return {
        "gross_margin_pct": pct(div(s.v("gross_profit"), revenue)),
        "operating_margin_pct": pct(div(s.v("operating_income"), revenue)),
        "net_margin_pct": pct(div(ni, revenue)),
        "ebitda_margin_pct": pct(div(s.v("ebitda"), revenue)),
        "fcf_margin_pct": pct(div(free_cash_flow(s), revenue)),
        "roe_pct": pct(div(ni, s.avg("stockholders_equity"))),
        "roa_pct": pct(div(ni, s.avg("total_assets"))),
        "roic_pct": pct(div(nopat, invested)) if invested and invested > 0 else None,
    }


def valuation(info: dict, s: Statements) -> dict:
    price, market_cap = info.get("currentPrice"), info.get("marketCap")
    fcf = info.get("freeCashflow") or free_cash_flow(s)

    def f(key):
        return rnd(info.get(key), 2) if isinstance(info.get(key), int | float) else None

    return {
        "pe_trailing": f("trailingPE"),
        "pe_forward": f("forwardPE"),
        "peg": f("trailingPegRatio") or f("pegRatio"),
        "price_to_book": f("priceToBook"),
        "price_to_sales": f("priceToSalesTrailing12Months"),
        "ev_to_ebitda": f("enterpriseToEbitda"),
        "ev_to_revenue": f("enterpriseToRevenue"),
        "dividend_yield_pct": pct(div(info.get("dividendRate"), price)),
        "payout_ratio_pct": pct(info.get("payoutRatio")),
        "fcf_yield_pct": pct(div(fcf, market_cap)),
    }


def per_share(info: dict, s: Statements) -> dict:
    shares = s.v("shares_outstanding") or info.get("sharesOutstanding")
    return {
        "eps_diluted": s.v("diluted_eps"),
        "book_value_per_share": rnd(div(s.v("stockholders_equity"), shares), 2),
        "fcf_per_share": rnd(div(free_cash_flow(s), shares), 2),
    }
