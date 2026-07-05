# ib_valuation_lab

A no-LLM pipeline to crawl structured European (ESEF/IFRS XBRL) company filings
and build the standard investment-banking valuation suite: DCF, Comparable
Companies, LBO, and Precedent Transactions — surfaced through a Streamlit app.

## Why this is feasible without an LLM

Since FY2021 (mandatory from 2022), all EU-regulated-market issuers file annual
reports in ESEF format: XHTML with Inline XBRL (iXBRL) tags on their IFRS
consolidated statements. That means income statement, balance sheet, and cash
flow data is already machine-readable and taggable — no need to parse PDFs
with an LLM. `filings.xbrl.org` mirrors these filings with a JSON index.

## Pipeline

```
filings.xbrl.org (discover + download) 
        -> Arelle (parse iXBRL -> raw XBRL facts)
        -> taxonomy_mapping (IFRS tags -> canonical schema)
        -> SQLite/Postgres (normalized time series)
        -> models/ (dcf, comps, lbo, precedent_transactions)
        -> Streamlit app
```

## Known data gaps (be aware before you build on top of this)

- ESEF covers consolidated IFRS annual statements only — no guaranteed
  segment-level detail, no standardized adjusted/non-GAAP figures.
- Smaller caps sometimes file ESEF imperfectly (AMF reported ~15% of issuers
  needed a corrective filing in year one). Expect to handle missing tags.
- There is no free, structured M&A precedent-transaction database for Europe.
  `precedent_transactions.py` is deliberately a manual-input module, not a
  crawler — be honest with yourself about this one.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/crawl_company.py --name "STMicroelectronics" --years 2021 2022 2023
streamlit run src/app/streamlit_app.py
```

## Repo layout

```
config/             settings (DB path, default WACC inputs, etc.)
src/crawler/         discover + download + parse ESEF/iXBRL filings
src/normalize/       map IFRS XBRL tags -> canonical financial statement schema
src/market_data/      price, shares outstanding, risk-free rate, peer betas
src/db/              SQLAlchemy schema for normalized financials
src/models/          dcf.py, comps.py, lbo.py, precedent_transactions.py
src/app/             Streamlit UI
scripts/             CLI entry points (crawl, build model, export)
```

## Status

Scaffold stage. The crawler module structure mirrors the filings.xbrl.org API
as documented; verify the exact endpoint shape against their live API docs
before relying on it for production crawling, since the sandbox this was
built in could not make live requests to filings.xbrl.org to confirm.
