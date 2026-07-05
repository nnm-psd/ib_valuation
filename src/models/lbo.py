"""
Leveraged Buyout model: sources & uses at entry, a simple cash-sweep debt
schedule, exit at an assumed multiple, and resulting IRR/MOIC to the
equity sponsor.

Note: leverage multiples and debt pricing assumptions here are NOT
crawlable from ESEF filings -- they're market assumptions you set
yourself (informed by current leveraged loan market commentary), same
as a real banker would in absence of a live debt commitment letter.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SourcesAndUses:
    entry_ev: float
    entry_net_debt: float           # debt at target that's refinanced/assumed
    new_debt: float                 # new acquisition debt raised
    sponsor_equity: float            # plug: entry_ev - new_debt (+ fees if modeled)
    transaction_fees: float = 0.0


def build_sources_and_uses(entry_ebitda: float, entry_multiple: float, leverage_multiple: float) -> SourcesAndUses:
    entry_ev = entry_ebitda * entry_multiple
    new_debt = entry_ebitda * leverage_multiple
    sponsor_equity = entry_ev - new_debt
    return SourcesAndUses(entry_ev=entry_ev, entry_net_debt=0.0, new_debt=new_debt, sponsor_equity=sponsor_equity)


@dataclass
class DebtScheduleYear:
    year: int
    beginning_debt: float
    interest_expense: float
    mandatory_amortization: float
    cash_sweep: float
    ending_debt: float


def build_debt_schedule(
    starting_debt: float,
    interest_rate: float,
    free_cash_flow_for_debt_paydown: list[float],
    mandatory_amortization_pct: float = 0.0,
    cash_sweep_pct: float = 1.0,
) -> list[DebtScheduleYear]:
    schedule = []
    debt = starting_debt

    for year, fcf in enumerate(free_cash_flow_for_debt_paydown, start=1):
        interest = debt * interest_rate
        mandatory = min(debt, starting_debt * mandatory_amortization_pct)
        cash_available_for_sweep = max(fcf - interest - mandatory, 0)
        sweep = min(debt - mandatory, cash_available_for_sweep * cash_sweep_pct)
        ending = max(debt - mandatory - sweep, 0)

        schedule.append(DebtScheduleYear(year, debt, interest, mandatory, sweep, ending))
        debt = ending

    return schedule


def compute_returns(
    sponsor_equity_in: float, exit_ebitda: float, exit_multiple: float, exit_net_debt: float, holding_period_years: int
) -> dict:
    exit_ev = exit_ebitda * exit_multiple
    exit_equity_value = exit_ev - exit_net_debt

    moic = exit_equity_value / sponsor_equity_in if sponsor_equity_in else None
    irr = (moic ** (1 / holding_period_years) - 1) if moic else None

    return {
        "exit_enterprise_value": exit_ev,
        "exit_equity_value": exit_equity_value,
        "moic": moic,
        "irr": irr,
    }
