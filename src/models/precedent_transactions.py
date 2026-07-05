"""
Precedent Transactions Analysis.

IMPORTANT: unlike the other three models, this is deliberately NOT a
crawler target. There is no free, structured M&A deal database covering
European transactions -- the real ones (Refinitiv, Mergermarket,
PitchBook) are paid. Trying to scrape deal terms from press releases at
scale is low-coverage and high-maintenance for what you'd get out of it.

Treat this module as a manual-curation workflow: you (or a future paid
data source) add deals to data/processed/precedent_deals.csv, and this
module turns that into implied multiples -- same math as comps.py, just
on a deal dataset instead of a public-peer dataset.
"""
from __future__ import annotations

from dataclasses import dataclass
import csv
from pathlib import Path


@dataclass
class PrecedentDeal:
    target_name: str
    acquirer_name: str
    announcement_date: str
    deal_value_ev: float
    target_ebitda_ltm: float
    target_revenue_ltm: float
    sector: str
    deal_premium_pct: float | None = None  # premium to undisturbed share price, if public target


def load_precedent_deals(csv_path: Path) -> list[PrecedentDeal]:
    """
    Expects a CSV with columns matching PrecedentDeal fields. Start this
    file by hand with deals you know about (e.g. from sector news you
    already follow) -- there's no shortcut to a free, complete dataset here.
    """
    deals = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            deals.append(
                PrecedentDeal(
                    target_name=row["target_name"],
                    acquirer_name=row["acquirer_name"],
                    announcement_date=row["announcement_date"],
                    deal_value_ev=float(row["deal_value_ev"]),
                    target_ebitda_ltm=float(row["target_ebitda_ltm"]),
                    target_revenue_ltm=float(row["target_revenue_ltm"]),
                    sector=row["sector"],
                    deal_premium_pct=float(row["deal_premium_pct"]) if row.get("deal_premium_pct") else None,
                )
            )
    return deals


def deal_multiples(deal: PrecedentDeal) -> dict:
    return {
        "ev_ebitda": deal.deal_value_ev / deal.target_ebitda_ltm if deal.target_ebitda_ltm else None,
        "ev_sales": deal.deal_value_ev / deal.target_revenue_ltm if deal.target_revenue_ltm else None,
    }
