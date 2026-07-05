"""
Primary data fetcher: pulls income statement, balance sheet, cash flow,
and market snapshot from yfinance. Replaces the ESEF/XBRL crawler entirely.

Ticker convention for European companies on Yahoo Finance:
  Euronext Paris  -> suffix .PA  (e.g. AIR.PA, MC.PA, TTE.PA)
  NYSE/NASDAQ     -> no suffix   (e.g. STM, ASML)
  Euronext Milan  -> suffix .MI
  Xetra (DE)      -> suffix .DE
  LSE             -> suffix .L
"""
from __future__ import annotations

from dataclasses import dataclass
import pandas as pd
import yfinance as yf


@dataclass
class CompanySnapshot:
    name: str
    ticker: str
    sector: str | None
    country: str | None
    currency: str | None
    price: float | None
    shares_outstanding: float | None
    market_cap: float | None
    beta: float | None
    total_debt: float | None
    cash: float | None


def fetch_snapshot(ticker: str) -> CompanySnapshot:
    t = yf.Ticker(ticker)
    info = t.info
    return CompanySnapshot(
        name=info.get("longName") or info.get("shortName") or ticker,
        ticker=ticker,
        sector=info.get("sector"),
        country=info.get("country"),
        currency=info.get("currency"),
        price=info.get("currentPrice") or info.get("regularMarketPrice"),
        shares_outstanding=info.get("sharesOutstanding"),
        market_cap=info.get("marketCap"),
        beta=info.get("beta"),
        total_debt=info.get("totalDebt"),
        cash=info.get("totalCash"),
    )


def fetch_financials(ticker: str) -> dict[str, pd.DataFrame]:
    """
    Returns a dict with keys: income_stmt, balance_sheet, cash_flow.
    Each DataFrame has years as columns and line items as rows.
    Annual data only (not quarterly).
    """
    t = yf.Ticker(ticker)
    return {
        "income_stmt":   t.income_stmt,
        "balance_sheet": t.balance_sheet,
        "cash_flow":     t.cash_flow,
    }


def extract_field(df: pd.DataFrame, candidates: list[str]) -> dict[int, float | None]:
    """
    Try each candidate row name in order; return the first one found as
    a {fiscal_year: value} dict. Returns empty dict if none found.
    This handles yfinance's inconsistent row naming across tickers/years.
    """
    for name in candidates:
        if name in df.index:
            row = df.loc[name]
            return {
                col.year: (float(row[col]) if pd.notna(row[col]) else None)
                for col in df.columns
            }
    return {}


# Canonical field -> list of yfinance row names to try, in priority order
FIELD_MAP: dict[str, list[str]] = {
    # Income statement
    "revenue":          ["Total Revenue", "Operating Revenue"],
    "cogs":             ["Cost Of Revenue", "Reconciled Cost Of Revenue"],
    "gross_profit":     ["Gross Profit"],
    "sga":              ["Selling General And Administration"],
    "rd":               ["Research And Development"],
    "ebit":             ["EBIT", "Operating Income", "Total Operating Income As Reported"],
    "ebitda":           ["EBITDA", "Normalized EBITDA"],
    "d_and_a":          ["Reconciled Depreciation"],
    "interest_expense": ["Interest Expense", "Interest Expense Non Operating"],
    "pretax_income":    ["Pretax Income"],
    "tax_expense":      ["Tax Provision"],
    "net_income":       ["Net Income", "Net Income Common Stockholders"],
    # Balance sheet
    "cash":             ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"],
    "total_assets":     ["Total Assets"],
    "short_term_debt":  ["Current Debt", "Current Debt And Capital Lease Obligation"],
    "long_term_debt":   ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"],
    "total_debt":       ["Total Debt"],
    "total_equity":     ["Stockholders Equity", "Common Stock Equity"],
    "total_liabilities":["Total Liabilities Net Minority Interest"],
    # Cash flow
    "cfo":              ["Operating Cash Flow", "Cash Flows From Used In Operating Activities"],
    "capex":            ["Capital Expenditure"],
    "free_cash_flow":   ["Free Cash Flow"],
    "dividends_paid":   ["Common Stock Dividend Paid", "Payment Of Dividends"],
}
