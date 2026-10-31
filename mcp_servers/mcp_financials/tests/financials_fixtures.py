"""A small made-up company with hand-checkable numbers. Columns are fiscal years, newest first."""

import pandas as pd

YEARS = pd.to_datetime(["2025-12-31", "2024-12-31", "2023-12-31"])
QUARTERS = pd.to_datetime(
    ["2025-12-31", "2025-09-30", "2025-06-30", "2025-03-31", "2024-12-31", "2024-09-30"]
)


def frame(rows: dict[str, list], columns=YEARS) -> pd.DataFrame:
    padded = {k: v + [float("nan")] * (len(columns) - len(v)) for k, v in rows.items()}
    return pd.DataFrame(padded, index=columns).T


INCOME = frame(
    {
        "Total Revenue": [1000, 800, 640],
        "Cost Of Revenue": [600, 500, 400],
        "Gross Profit": [400, 300, 240],
        "Research And Development": [50, 40, 30],
        "Selling General And Administration": [100, 90, 80],
        "Operating Income": [250, 170, 130],
        "EBIT": [250, 170, 130],
        "EBITDA": [300, 210, 160],
        "Interest Expense": [25, 20, 20],
        "Pretax Income": [225, 150, 110],
        "Tax Provision": [45, 30, 22],
        "Net Income": [180, 120, 88],
        "Diluted EPS": [1.8, 1.2, 0.88],
        "Diluted Average Shares": [100, 100, 100],
    }
)

BALANCE = frame(
    {
        "Total Assets": [2000, 1600, 1500],
        "Current Assets": [800, 600],
        "Current Liabilities": [400, 400],
        "Inventory": [100, 80],
        "Cash And Cash Equivalents": [200, 150],
        "Cash Cash Equivalents And Short Term Investments": [300, 200],
        "Accounts Receivable": [150, 130],
        "Accounts Payable": [120, 100],
        "Net PPE": [500, 400],
        "Total Liabilities Net Minority Interest": [1000, 900],
        "Total Debt": [500, 450],
        "Long Term Debt": [400, 420],
        "Stockholders Equity": [1000, 700, 600],
        "Retained Earnings": [600, 450],
        "Working Capital": [400, 200],
        "Ordinary Shares Number": [100, 100],
    }
)

CASH_FLOW = frame(
    {
        "Operating Cash Flow": [260, 150, 100],
        "Capital Expenditure": [-60, -50, -40],
        "Free Cash Flow": [200, 100, 60],
        "Cash Dividends Paid": [-60, -50, -40],
    }
)

# Quarterly income: latest quarter revenue 300 vs 240 a year earlier; the oldest column is empty.
QUARTERLY_INCOME = frame(
    {
        "Total Revenue": [300, 260, 230, 210, 240],
        "Net Income": [60, 50, 40, 30, 40],
        "Diluted EPS": [0.6, 0.5],
    },
    columns=QUARTERS,
)

INFO = {
    "quoteType": "EQUITY",
    "longName": "Example Corp",
    "sector": "Technology",
    "financialCurrency": "USD",
    "marketCap": 3000,
    "currentPrice": 30.0,
    "dividendRate": 0.6,
    "payoutRatio": 0.3,
    "trailingPE": 16.6667,
}
