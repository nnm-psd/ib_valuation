"""
IB Valuation Lab — Streamlit Cloud-ready version.
No SQLite dependency: fetches yfinance data live, cached per session.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

from src.models.dcf import WaccInputs, compute_wacc, project_fcff, run_dcf
from src.models.comps import compute_multiples, peer_set_summary_stats, implied_valuation_from_multiple
from src.models.lbo import build_sources_and_uses, build_debt_schedule, compute_returns
from config.settings import DEFAULT_MARKET_RISK_PREMIUM, DEFAULT_TERMINAL_GROWTH_RATE, DEFAULT_TAX_RATE_FR

st.set_page_config(page_title="IB Valuation Lab", layout="wide", page_icon="💼")

# ── data layer (cached so yfinance isn't re-hit on every widget interaction) ──
@st.cache_data(ttl=3600, show_spinner="Fetching financial data...")
def load_company(ticker: str) -> dict:
    import time
    
    for attempt in range(3):
        try:
            t = yf.Ticker(ticker)
            info = t.info
            
            # yfinance returns a minimal dict with no financials when rate-limited
            if not info.get("regularMarketPrice") and not info.get("currentPrice") and not info.get("marketCap"):
                raise ValueError("Empty response — likely rate limited")
            
            return {
                "info":          info,
                "income_stmt":   t.income_stmt,
                "balance_sheet": t.balance_sheet,
                "cash_flow":     t.cash_flow,
            }
        except Exception as e:
            if attempt < 2:
                time.sleep(2 + attempt * 3)  # wait 2s, then 5s
                continue
            raise e

def field_from_df(df: pd.DataFrame, candidates: list[str], col_idx: int = 0) -> float | None:
    for name in candidates:
        if name in df.index:
            try:
                v = df.loc[name].iloc[col_idx]
                return float(v) if pd.notna(v) else None
            except Exception:
                continue
    return None

def fmt(v, scale=1e9, suffix="B"):
    if v is None: return "N/A"
    return f"${v/scale:.2f}{suffix}"

# ── sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.title("💼 IB Valuation Lab")
st.sidebar.caption("Enter any Yahoo Finance ticker.")

PRESETS = {
    "STMicroelectronics": "STM",
    "Airbus": "AIR.PA",
    "LVMH": "MC.PA",
    "ASML": "ASML",
    "TotalEnergies": "TTE.PA",
    "BNP Paribas": "BNP.PA",
}
preset = st.sidebar.selectbox("Quick pick", ["(type your own)"] + list(PRESETS.keys()))
if preset == "(type your own)":
    ticker_input = st.sidebar.text_input("Ticker", placeholder="e.g. STM, AIR.PA, MC.PA").upper().strip()
else:
    ticker_input = PRESETS[preset]
    st.sidebar.text_input("Ticker", value=ticker_input, disabled=True)

if not ticker_input:
    st.title("💼 IB Valuation Lab")
    st.info("Enter a Yahoo Finance ticker in the sidebar to get started.\n\n"
            "**European tickers:** Euronext Paris → `.PA` (e.g. `AIR.PA`), NYSE → no suffix (e.g. `STM`)")
    st.stop()

# ── load data ─────────────────────────────────────────────────────────────────

try:
    data = load_company(ticker_input)
except Exception as e:
    st.error(f"Could not fetch data for `{ticker_input}`: {e}")
    st.stop()

info   = data["info"]
inc    = data["income_stmt"]
bal    = data["balance_sheet"]
cf     = data["cash_flow"]

if inc.empty:
    st.error(f"No financial data found for `{ticker_input}`. Check the ticker symbol.")
    st.stop()

name        = info.get("longName") or info.get("shortName") or ticker_input
sector      = info.get("sector", "N/A")
country     = info.get("country", "N/A")
price       = info.get("currentPrice") or info.get("regularMarketPrice")
shares      = info.get("sharesOutstanding")
market_cap  = info.get("marketCap")
beta_raw    = info.get("beta") or 1.0
total_debt  = info.get("totalDebt") or 0
cash_info   = info.get("totalCash") or 0

# Latest year column (index 0 = most recent)
revenue      = field_from_df(inc, ["Total Revenue", "Operating Revenue"])
gross_profit = field_from_df(inc, ["Gross Profit"])
ebitda       = field_from_df(inc, ["EBITDA", "Normalized EBITDA"])
ebit         = field_from_df(inc, ["EBIT", "Operating Income"])
net_income   = field_from_df(inc, ["Net Income", "Net Income Common Stockholders"])
d_and_a      = field_from_df(inc, ["Reconciled Depreciation"])
interest_exp = field_from_df(inc, ["Interest Expense", "Interest Expense Non Operating"])
cfo          = field_from_df(cf,  ["Operating Cash Flow"])
capex        = field_from_df(cf,  ["Capital Expenditure"])
fcf          = field_from_df(cf,  ["Free Cash Flow"])
cash_bs      = field_from_df(bal, ["Cash And Cash Equivalents",
                                    "Cash Cash Equivalents And Short Term Investments"])
target_ev    = (market_cap or 0) + total_debt - (cash_bs or cash_info or 0)

st.title(f"💼 {name}")
st.caption(f"`{ticker_input}` · {sector} · {country}")

# ── tabs ──────────────────────────────────────────────────────────────────────

tab_overview, tab_dcf, tab_comps, tab_lbo = st.tabs(
    ["📊 Overview", "📈 DCF", "🔍 Comps", "🏦 LBO"]
)

# ─── OVERVIEW ─────────────────────────────────────────────────────────────────
with tab_overview:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Price",      f"${price:,.2f}"       if price      else "N/A")
    c2.metric("Market Cap", fmt(market_cap))
    c3.metric("EV",         fmt(target_ev))
    c4.metric("Beta",       f"{beta_raw:.2f}"       if beta_raw   else "N/A")
    c5.metric("Net Debt",   fmt(total_debt - (cash_bs or 0)))

    st.divider()

    # Income statement trend table
    key_rows = {
        "Revenue":      ["Total Revenue", "Operating Revenue"],
        "Gross Profit": ["Gross Profit"],
        "EBITDA":       ["EBITDA", "Normalized EBITDA"],
        "EBIT":         ["EBIT", "Operating Income"],
        "Net Income":   ["Net Income", "Net Income Common Stockholders"],
        "Free Cash Flow": ["Free Cash Flow"],
    }
    trend = {}
    for label, cands in key_rows.items():
        for c in cands:
            if c in inc.index:
                trend[label] = inc.loc[c] / 1e9
                break
            if c in cf.index:
                trend[label] = cf.loc[c] / 1e9
                break
    if trend:
        trend_df = pd.DataFrame(trend).T
        trend_df.columns = [str(c.year) for c in trend_df.columns]
        st.subheader("Income statement trend ($B)")
        st.dataframe(
            trend_df.style.format("{:.2f}").highlight_max(axis=1, color="#d4edda").highlight_min(axis=1, color="#f8d7da"),
            use_container_width=True,
        )

    # Chart
    if "Revenue" in trend and "EBITDA" in trend:
        years = [str(c.year) for c in inc.columns]
        fig = go.Figure()
        fig.add_bar(name="Revenue",x=years, y=trend["Revenue"].values, marker_color="#4C72B0")
        fig.add_bar(name="EBITDA",  x=years, y=trend["EBITDA"].values,  marker_color="#55A868")
        fig.update_layout(barmode="group", title="Revenue & EBITDA ($B)",
                          yaxis_title="$B", xaxis_title="Fiscal Year",
                          plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

# ─── DCF ──────────────────────────────────────────────────────────────────────
with tab_dcf:
    st.subheader("DCF — Discounted Cash Flow")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**WACC**")
        rfr  = st.number_input("Risk-free rate",        value=0.033, step=0.001, format="%.3f")
        beta = st.number_input("Beta",                  value=round(float(beta_raw), 2), step=0.05)
        mrp  = st.number_input("Market risk premium",   value=DEFAULT_MARKET_RISK_PREMIUM, step=0.005, format="%.3f")
        cod  = st.number_input("Cost of debt (pre-tax)",value=0.04,  step=0.005, format="%.3f")
        tax  = st.number_input("Tax rate",              value=DEFAULT_TAX_RATE_FR, step=0.01)
    with col2:
        st.markdown("**Growth**")
        g1 = st.number_input("Revenue growth yr 1–3 (%)", value=5.0, step=0.5) / 100
        g2 = st.number_input("Revenue growth yr 4–5 (%)", value=3.0, step=0.5) / 100
        tg = st.number_input("Terminal growth (%)",        value=DEFAULT_TERMINAL_GROWTH_RATE * 100, step=0.1) / 100
    with col3:
        st.markdown("**Balance sheet**")
        debt_input = st.number_input("Total debt ($B)",  value=round(total_debt / 1e9, 2), step=0.1)
        cash_input = st.number_input("Cash ($B)",        value=round((cash_bs or cash_info or 0) / 1e9, 2), step=0.1)

    wacc_inputs = WaccInputs(
        risk_free_rate=rfr, beta=beta, market_risk_premium=mrp,
        cost_of_debt=cod, tax_rate=tax,
        market_value_equity=market_cap or 1,
        market_value_debt=debt_input * 1e9,
    )
    wacc = compute_wacc(wacc_inputs)
    growth_rates = [g1, g1, g1, g2, g2]

    try:
        fcff_proj = project_fcff(
            base_ebit=ebit or 0, tax_rate=tax, base_d_and_a=d_and_a or 0,
            base_capex=abs(capex or 0), base_delta_nwc=0,
            revenue_growth_rates=growth_rates,
        )
        result = run_dcf(
            fcff_proj, wacc=wacc, terminal_growth=tg,
            total_debt=debt_input * 1e9, cash=cash_input * 1e9,
            shares_outstanding=shares or 1,
        )
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("WACC",             f"{wacc*100:.2f}%")
        c2.metric("Enterprise Value", fmt(result["enterprise_value"]))
        c3.metric("Equity Value",     fmt(result["equity_value"]))
        c4.metric("Implied Price/Share", f"${result['value_per_share']:.2f}" if result["value_per_share"] else "N/A")

        if price and result["value_per_share"]:
            updown = (result["value_per_share"] / price - 1) * 100
            color = "normal" if updown >= 0 else "inverse"
            st.metric("Upside / Downside vs current price", f"{updown:+.1f}%", delta_color=color)

        # Sensitivity table
        st.subheader("Sensitivity — Implied Price/Share")
        wacc_range = [wacc + d for d in [-0.02, -0.01, 0, 0.01, 0.02]]
        tg_range   = [tg   + d for d in [-0.01, -0.005, 0, 0.005, 0.01]]
        sens = {}
        for w in wacc_range:
            row = {}
            for t in tg_range:
                try:
                    r = run_dcf(fcff_proj, wacc=w, terminal_growth=t,
                                total_debt=debt_input*1e9, cash=cash_input*1e9,
                                shares_outstanding=shares or 1)
                    row[f"TG {t*100:.1f}%"] = f"${r['value_per_share']:.1f}" if r["value_per_share"] else "err"
                except Exception:
                    row[f"TG {t*100:.1f}%"] = "err"
            sens[f"WACC {w*100:.1f}%"] = row
        st.dataframe(pd.DataFrame(sens).T, use_container_width=True)
        st.caption("Rows = WACC · Columns = terminal growth rate")

    except Exception as e:
        st.error(f"DCF error: {e}")

# ─── COMPS ────────────────────────────────────────────────────────────────────
with tab_comps:
    st.subheader("Comparable Companies Analysis")
    peer_input = st.text_input("Peer tickers (comma-separated)",
                               placeholder="NVDA, INTC, TXN, ASML, AMAT")

    target_m = compute_multiples(
        enterprise_value=target_ev, market_cap=market_cap or 0,
        ebitda=ebitda or 1, revenue=revenue or 1, net_income=net_income or 1,
    )
    target_m.company_name = name

    if peer_input.strip():
        peers = [t.strip().upper() for t in peer_input.split(",") if t.strip()]
        peer_multiples = []

        with st.spinner("Fetching peers..."):
            for pt in peers:
                try:
                    pd_data = load_company(pt)
                    pi = pd_data["info"]
                    pi_inc = pd_data["income_stmt"]
                    p_mc   = pi.get("marketCap") or 0
                    p_debt = pi.get("totalDebt") or 0
                    p_cash = pi.get("totalCash") or 0
                    p_ev   = p_mc + p_debt - p_cash
                    p_ebitda  = field_from_df(pi_inc, ["EBITDA","Normalized EBITDA"]) or 1
                    p_revenue = field_from_df(pi_inc, ["Total Revenue","Operating Revenue"]) or 1
                    p_ni      = field_from_df(pi_inc, ["Net Income","Net Income Common Stockholders"]) or 1
                    m = compute_multiples(p_ev, p_mc, p_ebitda, p_revenue, p_ni)
                    m.company_name = pt
                    peer_multiples.append(m)
                except Exception as e:
                    st.warning(f"{pt}: {e}")

        if peer_multiples:
            stats = peer_set_summary_stats(peer_multiples)
            rows = []
            for m in [target_m] + peer_multiples:
                is_target = m.company_name == name
                rows.append({
                    "Company":  ("⭐ " if is_target else "") + m.company_name,
                    "EV/EBITDA": f"{m.ev_ebitda:.1f}x" if m.ev_ebitda else "N/A",
                    "EV/Sales":  f"{m.ev_sales:.2f}x"  if m.ev_sales  else "N/A",
                    "P/E":       f"{m.pe:.1f}x"         if m.pe        else "N/A",
                })
            # Add peer median row
            rows.append({
                "Company":   "── Peer Median ──",
                "EV/EBITDA": f"{stats['ev_ebitda']['median']:.1f}x" if stats['ev_ebitda']['median'] else "N/A",
                "EV/Sales":  f"{stats['ev_sales']['median']:.2f}x"  if stats['ev_sales']['median']  else "N/A",
                "P/E":       f"{stats['pe']['median']:.1f}x"         if stats['pe']['median']         else "N/A",
            })
            st.dataframe(pd.DataFrame(rows).set_index("Company"), use_container_width=True)

            med_ev_ebitda = stats["ev_ebitda"]["median"]
            med_ev_sales  = stats["ev_sales"]["median"]
            st.divider()
            st.markdown("**Implied equity value — peer median multiples**")
            ca, cb = st.columns(2)
            if med_ev_ebitda and ebitda:
                ca.metric("via EV/EBITDA", fmt(implied_valuation_from_multiple(ebitda, med_ev_ebitda, total_debt, cash_bs or 0)))
            if med_ev_sales and revenue:
                cb.metric("via EV/Sales",  fmt(implied_valuation_from_multiple(revenue, med_ev_sales, total_debt, cash_bs or 0)))
    else:
        st.caption("Enter peer tickers above to populate the comps table.")

# ─── LBO ──────────────────────────────────────────────────────────────────────
with tab_lbo:
    st.subheader("LBO — Leveraged Buyout")

    base_ebitda_b = (ebitda or 0) / 1e9
    base_fcf_b    = (fcf or 0) / 1e9

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Entry assumptions**")
        entry_mult  = st.number_input("Entry EV/EBITDA",          value=8.0,  step=0.5)
        lev_mult    = st.number_input("Leverage (Debt/EBITDA)",   value=4.0,  step=0.25)
        interest_r  = st.number_input("Interest rate on debt",    value=0.06, step=0.005, format="%.3f")
        mgmt_rollover = st.number_input("Mgmt rollover ($B)",     value=0.0,  step=0.1)
    with col2:
        st.markdown("**Exit assumptions**")
        exit_mult   = st.number_input("Exit EV/EBITDA",           value=8.0,  step=0.5)
        holding_yrs = st.number_input("Holding period (years)",   value=5,    step=1, min_value=1, max_value=10)
        ebitda_cagr = st.number_input("EBITDA CAGR (%)",          value=5.0,  step=0.5) / 100

    su = build_sources_and_uses(base_ebitda_b, entry_mult, lev_mult)
    exit_ebitda_b = base_ebitda_b * (1 + ebitda_cagr) ** holding_yrs
    fcf_sweep = [base_fcf_b * (1 + ebitda_cagr) ** y for y in range(1, int(holding_yrs) + 1)]
    schedule = build_debt_schedule(su.new_debt, interest_r, fcf_sweep)
    exit_net_debt = schedule[-1].ending_debt if schedule else su.new_debt
    returns = compute_returns(su.sponsor_equity - mgmt_rollover, exit_ebitda_b, exit_mult, exit_net_debt, int(holding_yrs))

    st.divider()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Entry EV",       f"${su.entry_ev:.1f}B")
    c2.metric("New Debt",       f"${su.new_debt:.1f}B")
    c3.metric("Sponsor Equity", f"${su.sponsor_equity:.1f}B")
    c4.metric("IRR",  f"{returns['irr']*100:.1f}%"  if returns["irr"]  else "N/A")
    c5.metric("MOIC", f"{returns['moic']:.2f}x"     if returns["moic"] else "N/A")

    if schedule:
        sched_df = pd.DataFrame([{
            "Year": s.year,
            "Beginning Debt ($B)": round(s.beginning_debt, 2),
            "Interest ($B)":       round(s.interest_expense, 2),
            "Cash Sweep ($B)":     round(s.cash_sweep, 2),
            "Ending Debt ($B)":    round(s.ending_debt, 2),
        } for s in schedule]).set_index("Year")
        st.subheader("Debt schedule")
        st.dataframe(sched_df, use_container_width=True)

        fig2 = go.Figure()
        fig2.add_bar(name="Ending Debt", x=sched_df.index, y=sched_df["Ending Debt ($B)"], marker_color="#d9534f")
        fig2.update_layout(title="Debt Paydown ($B)", yaxis_title="$B", xaxis_title="Year",
                           plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)
