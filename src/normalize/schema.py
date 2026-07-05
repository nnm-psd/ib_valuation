"""
Canonical financial statement schema. Every company, regardless of its
specific IFRS tagging quirks, gets normalized into these dataclasses.
This is what the valuation models (dcf.py, comps.py, lbo.py) consume --
they never touch raw XBRL tags directly.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class IncomeStatement:
    fiscal_year: int
    revenue: float | None = None
    cogs: float | None = None
    gross_profit: float | None = None
    sga: float | None = None
    ebitda: float | None = None
    d_and_a: float | None = None
    ebit: float | None = None
    interest_expense: float | None = None
    pretax_income: float | None = None
    tax_expense: float | None = None
    net_income: float | None = None


@dataclass
class BalanceSheet:
    fiscal_year: int
    cash: float | None = None
    total_current_assets: float | None = None
    total_assets: float | None = None
    short_term_debt: float | None = None
    long_term_debt: float | None = None
    total_liabilities: float | None = None
    total_equity: float | None = None
    shares_outstanding: float | None = None


@dataclass
class CashFlowStatement:
    fiscal_year: int
    cfo: float | None = None              # cash flow from operations
    capex: float | None = None
    free_cash_flow: float | None = None   # cfo - capex, computed if not directly tagged
    dividends_paid: float | None = None


@dataclass
class CompanyFinancials:
    company_name: str
    ticker: str | None
    country: str
    income_statements: list[IncomeStatement]
    balance_sheets: list[BalanceSheet]
    cash_flow_statements: list[CashFlowStatement]
