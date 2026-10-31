"""Indicator definitions and rule-based macro reads. Free of I/O so the rules can be unit tested.

The rules are deliberately simple heuristics. Every read returns the evidence and thresholds it used.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Indicator:
    key: str
    series_id: str
    group: str
    label: str
    units: str  # what `value` means, for the reader
    transform: str = "lin"  # FRED units parameter
    start: str = "2015-01-01"


INDICATORS = [
    Indicator("fed_funds", "FEDFUNDS", "rates", "Fed funds rate", "%"),
    Indicator("treasury_2y", "DGS2", "rates", "2-year Treasury yield", "%"),
    Indicator("treasury_10y", "DGS10", "rates", "10-year Treasury yield", "%"),
    Indicator("curve_10y_2y", "T10Y2Y", "rates", "10y minus 2y Treasury spread", "pct points"),
    Indicator("curve_10y_3m", "T10Y3M", "rates", "10y minus 3m Treasury spread", "pct points"),
    Indicator("cpi_yoy", "CPIAUCSL", "inflation", "CPI inflation", "% YoY", "pc1"),
    Indicator("core_cpi_yoy", "CPILFESL", "inflation", "Core CPI inflation", "% YoY", "pc1"),
    Indicator("core_pce_yoy", "PCEPILFE", "inflation", "Core PCE inflation (Fed target 2%)", "% YoY", "pc1"),
    Indicator("breakeven_10y", "T10YIE", "inflation", "10-year breakeven inflation", "%"),
    Indicator("unemployment", "UNRATE", "labor", "Unemployment rate", "%"),
    Indicator("payrolls_change", "PAYEMS", "labor", "Nonfarm payrolls, monthly change", "thousands", "chg"),
    Indicator("initial_claims", "ICSA", "labor", "Initial jobless claims (weekly)", "claims"),
    Indicator("real_gdp_growth", "A191RL1Q225SBEA", "growth", "Real GDP growth (annualized, quarterly)", "%"),
    Indicator("industrial_production_yoy", "INDPRO", "growth", "Industrial production", "% YoY", "pc1"),
    Indicator("housing_starts", "HOUST", "housing", "Housing starts (annualized)", "thousands"),
    Indicator("sahm_rule", "SAHMREALTIME", "recession", "Sahm rule recession indicator", "pct points"),
    Indicator(
        "financial_conditions", "NFCI", "financial_conditions", "Chicago Fed financial conditions", "index"
    ),
    Indicator("high_yield_spread", "BAMLH0A0HYM2", "financial_conditions", "High-yield bond spread", "%"),
    Indicator(
        "consumer_sentiment", "UMCSENT", "consumer", "UMich consumer sentiment", "index", start="1978-01-01"
    ),
    Indicator("retail_sales_yoy", "RSAFS", "consumer", "Retail sales", "% YoY", "pc1"),
    Indicator("real_consumption_yoy", "PCEC96", "consumer", "Real personal consumption", "% YoY", "pc1"),
    Indicator("savings_rate", "PSAVERT", "consumer", "Personal savings rate", "%"),
    Indicator("card_delinquency", "DRCCLACBS", "consumer", "Credit-card delinquency rate", "%"),
]
BY_KEY = {i.key: i for i in INDICATORS}

SECTOR_FOCUS = {
    "Technology": ("rates", "growth"),
    "Communication Services": ("consumer", "growth", "rates"),
    "Consumer Cyclical": ("consumer", "labor", "rates"),
    "Consumer Defensive": ("inflation", "consumer"),
    "Financial Services": ("rates", "financial_conditions", "growth"),
    "Real Estate": ("rates", "housing"),
    "Utilities": ("rates", "inflation"),
    "Energy": ("growth", "inflation"),
    "Industrials": ("growth", "rates"),
    "Basic Materials": ("growth", "inflation"),
    "Healthcare": ("rates",),
}
CONSUMER_SENSITIVITY = {
    "Consumer Cyclical": "high",
    "Communication Services": "medium",
    "Consumer Defensive": "medium",
}


def _r(x, digits: int = 2):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), digits)


def latest(s: pd.Series | None) -> dict:
    """Latest and prior observation with dates."""
    if s is None or s.empty:
        return {"value": None, "date": None, "prior": None, "change": None}
    value, prior = s.iloc[-1], s.iloc[-2] if len(s) > 1 else None
    return {
        "value": _r(value),
        "date": str(s.index[-1].date()),
        "prior": _r(prior),
        "change": _r(value - prior) if prior is not None else None,
    }


def value_at_offset(s: pd.Series | None, months: int) -> float | None:
    """Value as of `months` before the latest observation."""
    if s is None or s.empty:
        return None
    # A few days' slack so month-end dates line up (Sep 30 minus 6 months is Mar 30, not Mar 31).
    cutoff = s.index[-1] - pd.DateOffset(months=months) + pd.Timedelta(days=3)
    earlier = s[s.index <= cutoff]
    return None if earlier.empty else float(earlier.iloc[-1])


def pct_change_over(s: pd.Series | None, months: int) -> float | None:
    then = value_at_offset(s, months)
    if s is None or s.empty or not then:
        return None
    return round((float(s.iloc[-1]) / then - 1) * 100, 2)


def percentile(s: pd.Series | None) -> float | None:
    """Percent of history at or below the latest value."""
    if s is None or len(s) < 2:
        return None
    return round(float((s <= s.iloc[-1]).mean()) * 100, 1)


# --- macro reads -----------------------------------------------------------------------------------------


def growth_read(gdp: pd.Series, payrolls: pd.Series, indpro: pd.Series) -> dict:
    g = latest(gdp)["value"]
    p3 = _r(payrolls.iloc[-3:].mean(), 0) if len(payrolls) >= 3 else None
    ip = latest(indpro)["value"]
    if (g is not None and g < 0) or (p3 is not None and p3 < 0):
        label = "contracting"
    elif (g is not None and g < 1.5) or (p3 is not None and p3 < 100) or (ip is not None and ip < 0):
        label = "slowing"
    else:
        label = "expanding"
    return {
        "label": label,
        "evidence": {"real_gdp_growth_pct": g, "payrolls_3m_avg_k": p3, "industrial_production_yoy_pct": ip},
        "rule": "contracting if GDP < 0 or 3m payroll avg < 0; slowing if GDP < 1.5%, payrolls < 100k or "
        "industrial production falling; otherwise expanding",
    }


def inflation_read(core_cpi: pd.Series, core_pce: pd.Series) -> dict:
    now, before = latest(core_cpi)["value"], value_at_offset(core_cpi, 6)
    pce = latest(core_pce)["value"]
    trend = None
    if now is not None and before is not None:
        trend = "rising" if now - before > 0.2 else "falling" if now - before < -0.2 else "stable"
    level = None
    if pce is not None:
        level = "above target" if pce > 2.5 else "near target" if pce >= 1.5 else "below target"
    return {
        "label": f"{level}, {trend}" if level and trend else level or trend,
        "trend": trend,
        "vs_target": level,
        "evidence": {"core_cpi_yoy_pct": now, "core_cpi_yoy_6m_ago_pct": _r(before), "core_pce_yoy_pct": pce},
        "rule": "trend: core CPI YoY vs 6 months ago (±0.2 pts); target: core PCE vs 2% (above 2.5%, below 1.5%)",
    }


def policy_read(
    fed_funds: pd.Series, core_pce: pd.Series, curve_10y_2y: pd.Series, curve_10y_3m: pd.Series
) -> dict:
    ff, pce = latest(fed_funds)["value"], latest(core_pce)["value"]
    real = _r(ff - pce) if ff is not None and pce is not None else None
    stance = None
    if real is not None:
        stance = "restrictive" if real > 1 else "accommodative" if real < 0 else "neutral"
    c2, c3 = latest(curve_10y_2y)["value"], latest(curve_10y_3m)["value"]
    curve = None
    if c2 is not None or c3 is not None:
        curve = "inverted" if min(x for x in (c2, c3) if x is not None) < 0 else "positive"
    return {
        "stance": stance,
        "curve": curve,
        "evidence": {"fed_funds_pct": ff, "real_fed_funds_pct": real, "curve_10y_2y": c2, "curve_10y_3m": c3},
        "rule": "real rate = Fed funds - core PCE: restrictive > 1, accommodative < 0; curve inverted if either "
        "spread < 0",
    }


def stress_read(vix: float | None, hy_spread: pd.Series, nfci: pd.Series) -> dict:
    hy, fc = latest(hy_spread)["value"], latest(nfci)["value"]
    levels = []
    if vix is not None:
        levels.append("high" if vix > 30 else "elevated" if vix > 20 else "calm")
    if hy is not None:
        levels.append("high" if hy > 7 else "elevated" if hy > 5 else "calm")
    if fc is not None:
        levels.append("elevated" if fc > 0 else "calm")
    label = "high" if "high" in levels else "elevated" if "elevated" in levels else "calm" if levels else None
    return {
        "label": label,
        "evidence": {"vix": _r(vix), "high_yield_spread_pct": hy, "financial_conditions_index": fc},
        "rule": "VIX > 20 elevated, > 30 high; HY spread > 5% elevated, > 7% high; NFCI > 0 tighter than average",
    }


def recession_read(sahm: pd.Series, curve_10y_3m: pd.Series) -> dict:
    s = latest(sahm)["value"]
    monthly = curve_10y_3m.resample("ME").last().dropna() if not curve_10y_3m.empty else curve_10y_3m
    inverted_months = int((monthly.iloc[-12:] < 0).sum()) if len(monthly) else None
    if s is not None and s >= 0.5:
        risk = "high"
    elif (s is not None and s >= 0.3) or (inverted_months or 0) >= 3:
        risk = "moderate"
    else:
        risk = "low"
    return {
        "risk": risk,
        "evidence": {"sahm_rule": s, "months_10y_3m_inverted_last_12": inverted_months},
        "rule": "high if Sahm rule >= 0.5 (triggered); moderate if Sahm >= 0.3 or the 10y-3m curve was inverted "
        "3+ of the last 12 months",
    }


def regime(growth: str | None, inflation_trend: str | None, inflation_level: str | None) -> str:
    hot = inflation_level == "above target" and inflation_trend != "falling"
    if growth == "contracting":
        return "contraction"
    if growth == "slowing":
        return "stagflation risk" if hot else "slowdown with easing inflation"
    if growth == "expanding":
        return "overheating risk" if hot else "steady expansion"
    return "unclear"


def market_signals(closes: pd.DataFrame) -> dict:
    def col(name):
        return closes[name].dropna() if name in closes.columns else None

    copper, gold = col("copper"), col("gold")
    ratio = (copper / gold).dropna() if copper is not None and gold is not None else None
    return {
        "sp500_3m_pct": pct_change_over(col("sp500"), 3),
        "oil_3m_pct": pct_change_over(col("oil_wti"), 3),
        "dollar_3m_pct": pct_change_over(col("dollar_index"), 3),
        "copper_to_gold_3m_pct": pct_change_over(ratio, 3),
        "note": "Rising copper/gold usually signals stronger growth expectations; a rising dollar tightens "
        "global financial conditions.",
    }


# --- consumer --------------------------------------------------------------------------------------------


def consumer_read(
    sentiment: pd.Series,
    real_consumption: pd.Series,
    delinquency: pd.Series,
    unemployment: pd.Series,
    xly_xlp_3m: float | None,
) -> dict:
    pctl = percentile(sentiment)
    pce = latest(real_consumption)["value"]
    dq_now, dq_year_ago = latest(delinquency)["value"], value_at_offset(delinquency, 12)
    un_now = latest(unemployment)["value"]
    un_low = float(unemployment.iloc[-12:].min()) if len(unemployment) else None
    points = {
        "sentiment": 1 if pctl is not None and pctl > 50 else -1 if pctl is not None and pctl < 25 else 0,
        "spending": 1 if pce is not None and pce > 2 else -1 if pce is not None and pce < 0 else 0,
        "market": 0 if xly_xlp_3m is None else 1 if xly_xlp_3m > 0 else -1,
        "credit": -1 if dq_now is not None and dq_year_ago is not None and dq_now > dq_year_ago else 0,
        "jobs": -1 if un_now is not None and un_low is not None and un_now - un_low >= 0.5 else 0,
    }
    score = sum(points.values())
    return {
        "label": "strong" if score >= 2 else "weak" if score <= -1 else "mixed",
        "score": score,
        "points": points,
        "rule": "+1/-1 each: sentiment percentile > 50 / < 25; real consumption YoY > 2% / < 0; discretionary "
        "beating staples over 3 months; -1 if card delinquencies rose over a year; -1 if unemployment is 0.5 "
        "pts above its 12-month low. strong >= 2, weak <= -1",
    }


# --- stock relationships ---------------------------------------------------------------------------------


def monthly_returns(prices: pd.Series) -> pd.Series:
    return prices.resample("ME").last().pct_change().dropna()


def correlation(a: pd.Series, b: pd.Series, min_months: int = 24) -> float | None:
    pair = pd.concat({"a": a, "b": b}, axis=1, sort=True).dropna()
    if len(pair) < min_months or pair["a"].std() == 0 or pair["b"].std() == 0:
        return None
    return round(float(pair["a"].corr(pair["b"])), 3)


def beta(stock: pd.Series, market: pd.Series, min_months: int = 24) -> float | None:
    pair = pd.concat({"s": stock, "m": market}, axis=1, sort=True).dropna()
    if len(pair) < min_months or pair["m"].var() == 0:
        return None
    return round(float(pair["s"].cov(pair["m"]) / pair["m"].var()), 3)


def monthly_change(s: pd.Series) -> pd.Series:
    """Month-over-month change in level (for yields and indexes measured in points)."""
    return s.resample("ME").last().diff().dropna()
