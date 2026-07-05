"""
Pull market data needed by the valuation models that ESEF filings don't
give you: current share price, shares outstanding (current, not last
fiscal year-end), beta, and a risk-free rate proxy.
"""
from __future__ import annotations

from dataclasses import dataclass

import yfinance as yf


@dataclass
class MarketSnapshot:
    ticker: str
    price: float | None
    shares_outstanding: float | None
    beta: float | None
    market_cap: float | None


def get_market_snapshot(ticker: str) -> MarketSnapshot:
    """
    ticker should be the Yahoo Finance ticker, e.g. "STM.PA" for
    STMicroelectronics on Euronext Paris, "AIR.PA" for Airbus, etc.
    """
    t = yf.Ticker(ticker)
    info = t.info  # note: can be slow / occasionally rate-limited, consider caching

    return MarketSnapshot(
        ticker=ticker,
        price=info.get("currentPrice"),
        shares_outstanding=info.get("sharesOutstanding"),
        beta=info.get("beta"),
        market_cap=info.get("marketCap"),
    )


def get_risk_free_rate_proxy() -> float:
    """
    Placeholder: use the 10Y French OAT or German Bund yield as the
    risk-free rate for Euro-denominated DCFs. Wire this up to a real
    yield-curve source (Banque de France, ECB SDW) rather than hardcoding.
    """
    raise NotImplementedError(
        "Wire this up to a live Euro-area sovereign yield source "
        "(e.g. ECB Statistical Data Warehouse) before using in a real model."
    )
