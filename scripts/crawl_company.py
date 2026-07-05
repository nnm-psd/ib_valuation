"""
Crawl a company's financials from yfinance and store in SQLite.

Usage:
    python scripts/crawl_company.py --ticker STM --name "STMicroelectronics"
    python scripts/crawl_company.py --ticker AIR.PA --name "Airbus"
    python scripts/crawl_company.py --ticker MC.PA --name "LVMH"
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.crawler.yfinance_fetcher import fetch_snapshot, fetch_financials, extract_field, FIELD_MAP
from src.db.models import init_db, SessionLocal, Company, FinancialLine, MarketDataPoint

STATEMENT_MAP = {
    "income_stmt":   ["revenue","cogs","gross_profit","sga","rd","ebit","ebitda",
                      "d_and_a","interest_expense","pretax_income","tax_expense","net_income"],
    "balance_sheet": ["cash","total_assets","short_term_debt","long_term_debt",
                      "total_debt","total_equity","total_liabilities"],
    "cash_flow":     ["cfo","capex","free_cash_flow","dividends_paid"],
}

def crawl(ticker: str, name: str | None) -> None:
    init_db()
    session = SessionLocal()

    # ── snapshot (price, beta, shares, etc.) ─────────────────────────
    print(f"Fetching snapshot for {ticker} ...")
    snap = fetch_snapshot(ticker)
    display_name = name or snap.name

    company = session.query(Company).filter_by(ticker=ticker).first()
    if company is None:
        company = Company(
            name=display_name,
            ticker=ticker,
            country=snap.country or "?",
            sector=snap.sector,
        )
        session.add(company)
        session.commit()
        print(f"  Created company: {display_name} ({snap.sector}, {snap.country})")
    else:
        print(f"  Company already exists: {display_name}")

    # ── financials ────────────────────────────────────────────────────
    print("Fetching financial statements ...")
    dfs = fetch_financials(ticker)

    stored = 0
    for stmt_key, fields in STATEMENT_MAP.items():
        df = dfs.get(stmt_key)
        if df is None or df.empty:
            print(f"  WARNING: {stmt_key} is empty for {ticker}")
            continue

        for field in fields:
            candidates = FIELD_MAP.get(field, [])
            year_values = extract_field(df, candidates)
            for year, value in year_values.items():
                if value is None:
                    continue
                # upsert: delete existing row for same (company, year, field)
                session.query(FinancialLine).filter_by(
                    company_id=company.id,
                    fiscal_year=year,
                    field_name=field,
                ).delete()
                session.add(FinancialLine(
                    company_id=company.id,
                    fiscal_year=year,
                    statement=stmt_key,
                    field_name=field,
                    value=value,
                ))
                stored += 1

    # ── market data point ─────────────────────────────────────────────
    if snap.price:
        from datetime import date
        session.query(MarketDataPoint).filter_by(
            company_id=company.id, date=str(date.today())
        ).delete()
        session.add(MarketDataPoint(
            company_id=company.id,
            date=str(date.today()),
            close_price=snap.price,
            shares_outstanding=snap.shares_outstanding,
        ))

    session.commit()
    session.close()
    print(f"  Stored {stored} financial line items")
    print(f"  Price: {snap.price} | Beta: {snap.beta} | Market cap: {snap.market_cap:,.0f}" if snap.market_cap else "  No price data")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True, help="Yahoo Finance ticker, e.g. STM or AIR.PA")
    parser.add_argument("--name", default=None, help="Display name (optional, falls back to yfinance longName)")
    args = parser.parse_args()
    crawl(args.ticker, args.name)
