"""
Comparable Companies Analysis: pull a peer set, compute trading multiples,
apply peer-derived multiples to the target's financials to get an implied
valuation range.
"""
from __future__ import annotations

from dataclasses import dataclass
import statistics


@dataclass
class PeerMultiples:
    company_name: str
    ev_ebitda: float | None
    ev_sales: float | None
    pe: float | None


def compute_multiples(
    enterprise_value: float, market_cap: float, ebitda: float, revenue: float, net_income: float
) -> PeerMultiples:
    return PeerMultiples(
        company_name="",
        ev_ebitda=enterprise_value / ebitda if ebitda else None,
        ev_sales=enterprise_value / revenue if revenue else None,
        pe=market_cap / net_income if net_income else None,
    )


def peer_set_summary_stats(peers: list[PeerMultiples]) -> dict:
    """
    Median is generally preferred over mean for comps to reduce the
    influence of outliers (a single peer trading at a weird multiple
    shouldn't swing your valuation).
    """
    def _stat(values: list[float]) -> dict:
        clean = [v for v in values if v is not None]
        if not clean:
            return {"median": None, "mean": None, "min": None, "max": None}
        return {
            "median": statistics.median(clean),
            "mean": statistics.mean(clean),
            "min": min(clean),
            "max": max(clean),
        }

    return {
        "ev_ebitda": _stat([p.ev_ebitda for p in peers]),
        "ev_sales": _stat([p.ev_sales for p in peers]),
        "pe": _stat([p.pe for p in peers]),
    }


def implied_valuation_from_multiple(
    target_metric: float, peer_multiple: float, total_debt: float = 0.0, cash: float = 0.0,
    is_equity_multiple: bool = False,
) -> float:
    """
    Apply a peer multiple to the target's own metric.
    For EV multiples (EV/EBITDA, EV/Sales): result is enterprise value, so
    subtract debt and add cash to get to equity value if you need it.
    For equity multiples (P/E): result is already equity value.
    """
    raw_value = target_metric * peer_multiple
    if is_equity_multiple:
        return raw_value
    return raw_value - total_debt + cash
