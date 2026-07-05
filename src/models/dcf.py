"""
Discounted Cash Flow model: build WACC via CAPM, project FCFF, discount,
add terminal value (Gordon growth or exit multiple), back into equity value.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WaccInputs:
    risk_free_rate: float
    beta: float
    market_risk_premium: float
    cost_of_debt: float
    tax_rate: float
    market_value_equity: float
    market_value_debt: float


def cost_of_equity_capm(risk_free_rate: float, beta: float, market_risk_premium: float) -> float:
    return risk_free_rate + beta * market_risk_premium


def compute_wacc(inputs: WaccInputs) -> float:
    ke = cost_of_equity_capm(inputs.risk_free_rate, inputs.beta, inputs.market_risk_premium)
    kd_after_tax = inputs.cost_of_debt * (1 - inputs.tax_rate)

    total = inputs.market_value_equity + inputs.market_value_debt
    weight_equity = inputs.market_value_equity / total
    weight_debt = inputs.market_value_debt / total

    return weight_equity * ke + weight_debt * kd_after_tax


@dataclass
class FcffProjection:
    fiscal_year: int
    fcff: float


def project_fcff(
    base_ebit: float,
    tax_rate: float,
    base_d_and_a: float,
    base_capex: float,
    base_delta_nwc: float,
    revenue_growth_rates: list[float],
    fcff_margin_decay: float = 0.0,
) -> list[float]:
    """
    Simple single-driver FCFF projection: grow EBIT/D&A/capex/NWC together
    with revenue growth assumptions. fcff_margin_decay lets you fade the
    margin toward a long-run level over the projection -- set to 0 to hold
    margins flat.

    FCFF = EBIT*(1-tax) + D&A - Capex - Delta NWC
    """
    projections = []
    ebit, d_and_a, capex, delta_nwc = base_ebit, base_d_and_a, base_capex, base_delta_nwc

    for i, g in enumerate(revenue_growth_rates):
        margin_factor = (1 - fcff_margin_decay) ** i
        ebit *= (1 + g) * margin_factor
        d_and_a *= (1 + g)
        capex *= (1 + g)
        delta_nwc *= (1 + g)

        nopat = ebit * (1 - tax_rate)
        fcff = nopat + d_and_a - capex - delta_nwc
        projections.append(fcff)

    return projections


def terminal_value_gordon(last_fcff: float, wacc: float, terminal_growth: float) -> float:
    if wacc <= terminal_growth:
        raise ValueError("WACC must exceed terminal growth rate for Gordon growth to be valid.")
    return last_fcff * (1 + terminal_growth) / (wacc - terminal_growth)


def terminal_value_exit_multiple(terminal_ebitda: float, exit_multiple: float) -> float:
    return terminal_ebitda * exit_multiple


def discount_cash_flows(cash_flows: list[float], wacc: float) -> list[float]:
    return [cf / (1 + wacc) ** (i + 1) for i, cf in enumerate(cash_flows)]


def enterprise_to_equity_value(
    enterprise_value: float, total_debt: float, cash: float, minority_interest: float = 0.0
) -> float:
    return enterprise_value - total_debt + cash - minority_interest


def run_dcf(
    fcff_projections: list[float],
    wacc: float,
    terminal_growth: float,
    total_debt: float,
    cash: float,
    shares_outstanding: float,
) -> dict:
    discounted = discount_cash_flows(fcff_projections, wacc)
    tv = terminal_value_gordon(fcff_projections[-1], wacc, terminal_growth)
    discounted_tv = tv / (1 + wacc) ** len(fcff_projections)

    enterprise_value = sum(discounted) + discounted_tv
    equity_value = enterprise_to_equity_value(enterprise_value, total_debt, cash)
    value_per_share = equity_value / shares_outstanding if shares_outstanding else None

    return {
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "value_per_share": value_per_share,
        "pv_explicit_fcff": sum(discounted),
        "pv_terminal_value": discounted_tv,
    }
