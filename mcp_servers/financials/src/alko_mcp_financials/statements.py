"""Line-item lookup on yfinance statement DataFrames (rows = line items, columns = period ends, newest first)."""

import math

import pandas as pd

# Output key -> yfinance row names to try, in order.
INCOME_LINES = {
    "revenue": ("Total Revenue", "Operating Revenue"),
    "cost_of_revenue": ("Cost Of Revenue", "Reconciled Cost Of Revenue"),
    "gross_profit": ("Gross Profit",),
    "research_and_development": ("Research And Development",),
    "selling_general_admin": ("Selling General And Administration",),
    "operating_expense": ("Operating Expense",),
    "operating_income": ("Operating Income", "Total Operating Income As Reported"),
    "ebit": ("EBIT",),
    "ebitda": ("EBITDA", "Normalized EBITDA"),
    "interest_expense": ("Interest Expense", "Interest Expense Non Operating"),
    "pretax_income": ("Pretax Income",),
    "tax_provision": ("Tax Provision",),
    "net_income": ("Net Income", "Net Income Common Stockholders"),
    "diluted_eps": ("Diluted EPS",),
    "diluted_shares": ("Diluted Average Shares",),
}

BALANCE_LINES = {
    "total_assets": ("Total Assets",),
    "current_assets": ("Current Assets",),
    "cash": ("Cash And Cash Equivalents",),
    "cash_and_short_term_investments": ("Cash Cash Equivalents And Short Term Investments",),
    "accounts_receivable": ("Accounts Receivable", "Receivables"),
    "inventory": ("Inventory",),
    "net_ppe": ("Net PPE",),
    "goodwill_and_intangibles": ("Goodwill And Other Intangible Assets",),
    "total_liabilities": ("Total Liabilities Net Minority Interest",),
    "current_liabilities": ("Current Liabilities",),
    "accounts_payable": ("Accounts Payable", "Payables"),
    "total_debt": ("Total Debt",),
    "long_term_debt": ("Long Term Debt", "Long Term Debt And Capital Lease Obligation"),
    "net_debt": ("Net Debt",),
    "stockholders_equity": ("Stockholders Equity", "Common Stock Equity"),
    "retained_earnings": ("Retained Earnings",),
    "working_capital": ("Working Capital",),
    "shares_outstanding": ("Ordinary Shares Number", "Share Issued"),
}

CASH_FLOW_LINES = {
    "operating_cash_flow": ("Operating Cash Flow", "Cash Flow From Continuing Operating Activities"),
    "capital_expenditure": ("Capital Expenditure",),
    "free_cash_flow": ("Free Cash Flow",),
    "depreciation_and_amortization": ("Depreciation And Amortization", "Depreciation Amortization Depletion"),
    "stock_based_compensation": ("Stock Based Compensation",),
    "change_in_working_capital": ("Change In Working Capital",),
    "investing_cash_flow": ("Investing Cash Flow",),
    "financing_cash_flow": ("Financing Cash Flow",),
    "dividends_paid": ("Cash Dividends Paid", "Common Stock Dividend Paid"),
    "share_repurchases": ("Repurchase Of Capital Stock",),
    "debt_issued": ("Issuance Of Debt",),
    "debt_repaid": ("Repayment Of Debt",),
}

LINES = {**INCOME_LINES, **BALANCE_LINES, **CASH_FLOW_LINES}


def clean(value) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(value) else value


def value(df: pd.DataFrame | None, key: str, col: int = 0) -> float | None:
    """Value of line `key` in the `col`-th most recent period, or None if absent."""
    if df is None or df.empty or col >= len(df.columns):
        return None
    for name in LINES[key]:
        if name in df.index:
            v = clean(df.iloc[:, col].get(name))
            if v is not None:
                return v
    return None


def sort_newest_first(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.loc[:, sorted(df.columns, reverse=True)]
    return df.dropna(axis=1, how="all")


def payload(df: pd.DataFrame, lines: dict[str, tuple[str, ...]]) -> list[dict]:
    """One dict per period with every line in `lines` (None where missing); periods with no data are dropped."""
    periods = []
    for col, end in enumerate(df.columns):
        row = {key: value(df, key, col) for key in lines}
        if any(v is not None for v in row.values()):
            periods.append({"period_end": str(pd.Timestamp(end).date()), **row})
    return periods
