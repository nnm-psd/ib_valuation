"""
Map IFRS taxonomy XBRL concepts (as used in ESEF filings) to the canonical
schema fields defined in schema.py.

This dict is intentionally the single source of truth for "messy reality ->
clean model". Expect to extend it as you encounter company-specific
extension taxonomies or alternate IFRS tags for the same concept (e.g. some
issuers tag operating profit as ProfitLossFromOperatingActivities, others
roll their own extension concept). When that happens, add the extra key
here rather than special-casing it downstream.
"""

IFRS_TAG_TO_CANONICAL: dict[str, str] = {
    # Income statement
    "ifrs-full:Revenue": "revenue",
    "ifrs-full:RevenueFromContractsWithCustomers": "revenue",
    "ifrs-full:CostOfSales": "cogs",
    "ifrs-full:GrossProfit": "gross_profit",
    "ifrs-full:SellingGeneralAndAdministrativeExpense": "sga",
    "ifrs-full:ProfitLossFromOperatingActivities": "ebit",
    "ifrs-full:DepreciationDepletionAndAmortisationExpense": "d_and_a",
    "ifrs-full:InterestExpense": "interest_expense",
    "ifrs-full:ProfitLossBeforeTax": "pretax_income",
    "ifrs-full:IncomeTaxExpenseContinuingOperations": "tax_expense",
    "ifrs-full:ProfitLoss": "net_income",

    # Balance sheet
    "ifrs-full:CashAndCashEquivalents": "cash",
    "ifrs-full:CurrentAssets": "total_current_assets",
    "ifrs-full:Assets": "total_assets",
    "ifrs-full:CurrentBorrowings": "short_term_debt",
    "ifrs-full:NoncurrentBorrowings": "long_term_debt",
    "ifrs-full:Liabilities": "total_liabilities",
    "ifrs-full:Equity": "total_equity",
    "ifrs-full:NumberOfSharesOutstanding": "shares_outstanding",

    # Cash flow statement
    "ifrs-full:CashFlowsFromUsedInOperatingActivities": "cfo",
    "ifrs-full:PurchaseOfPropertyPlantAndEquipment": "capex",
    "ifrs-full:DividendsPaid": "dividends_paid",
}


def map_concept(concept: str) -> str | None:
    """Return the canonical field name for a raw IFRS XBRL concept, or None if unmapped."""
    return IFRS_TAG_TO_CANONICAL.get(concept)
