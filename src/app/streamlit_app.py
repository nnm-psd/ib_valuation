import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from src.db.models import SessionLocal, Company, FinancialLine, MarketDataPoint, init_db
from src.models.dcf import WaccInputs, compute_wacc, project_fcff, run_dcf
from src.models.comps import compute_multiples, peer_set_summary_stats, implied_valuation_from_multiple
from src.models.lbo import build_sources_and_uses, build_debt_schedule, compute_returns
from config.settings import DEFAULT_MARKET_RISK_PREMIUM, DEFAULT_TERMINAL_GROWTH_RATE, DEFAULT_TAX_RATE_FR

st.set_page_config(page_title="IB Valuation Lab", layout="wide", page_icon="💼")
st.title("💼 IB Valuation Lab")

init_db()
session = SessionLocal()

# ── helpers ──────────────────────────────────────────────────────────────────

def get_financials(company_id: int) -> pd.DataFrame:
    rows = session.query(FinancialLine).filter_by(company_id=company_id).all()
    if not rows:
        return pd.DataFrame()
    data = [{"year": r.fiscal_year, "field": r.field_name, "value": r.value} for r in rows]
    df = pd.DataFrame(data).pivot_table(index="field", columns="year", values="value")
    return df.sort_index(axis=1)

def field(df: pd.DataFrame, name: str, year: int) -> float | None:
    try:
        v = df.loc[name, year]
        return float(v) if pd.notna(v) else None
    except KeyError:
        return None

def latest_year(df: pd.DataFrame) -> int:
    return max(df.columns) if not df.empty else 0

def fmt(v, scale=1e9, suffix="B"):
    if v is None: return "N/A"
    return f"${v/scale:.2f}{suffix}"

# ── sidebar: company picker ───────────────────────────────────────────────────

companies = session.query(Company).all()
st.sidebar.header("Company")

if not companies:
    st.sidebar.warning("No companies in DB yet.")
    st.info("Run the crawler first:\n```\npython scripts/crawl_company.py --ticker STM --name STMicroelectronics\n```")
    st.stop()

selected_name = st.sidebar.selectbox("Select company", [c.name for c in companies])
company = next(c for c in companies if c.name == selected_name)
fin = get_financials(company.id)
ly = latest_year(fin)

mkt = session.query(MarketDataPoint).filter_by(company_id=company.id).order_by(MarketDataPoint.date.desc()).first()
price = mkt.close_price if mkt else None
shares = mkt.shares_outstanding if mkt else None
market_cap = price * shares if (price and shares) else None

# ── tabs ──────────────────────────────────────────────────────────────────────

tab_overview, tab_dcf, tab_comps, tab_lbo = st.tabs(["📊 Overview", "📈 DCF", "🔍 Comps", "🏦 LBO"])

# ─── OVERVIEW ────────────────────────────────────────────────────────────────
with tab_overview:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Sector", company.sector or "N/A")
    col2.metric("Price", f"${price:,.2f}" if price else "N/A")
    col3.metric("Market Cap", fmt(market_cap))
    col4.metric("Country", company.country or "N/A")

    if fin.empty:
        st.warning("No financial data stored. Run the crawler.")
    else:
        st.subheader("Financial Summary")
        key_fields = ["revenue","gross_profit","ebitda","ebit","net_income","free_cash_flow"]
        display = fin.loc[[f for f in key_fields if f in fin.index]]
        display = display / 1e9
        display.index = [f.replace("_"," ").title() for f in display.index]
        st.dataframe(
            display.style.format("{:.2f}B").highlight_max(axis=1, color="#d4edda").highlight_min(axis=1, color="#f8d7da"),
            use_container_width=True,
        )

        # Revenue + EBITDA bar chart
        if "revenue" in fin.index and "ebitda" in fin.index:
            fig = go.Figure()
            years = list(fin.columns)
            fig.add_bar(name="Revenue", x=years, y=fin.loc["revenue"]/1e9, marker_color="#4C72B0")
            fig.add_bar(name="EBITDA", x=years, y=fin.loc["ebitda"]/1e9, marker_color="#55A868")
            fig.update_layout(barmode="group", title="Revenue & EBITDA ($B)", yaxis_title="$B", xaxis_title="Fiscal Year")
            st.plotly_chart(fig, use_container_width=True)

# ─── DCF ─────────────────────────────────────────────────────────────────────
with tab_dcf:
    st.subheader("DCF — Discounted Cash Flow")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**WACC inputs**")
        rfr   = st.number_input("Risk-free rate", value=0.033, step=0.001, format="%.3f", key="rfr")
        beta  = st.number_input("Beta", value=1.2, step=0.05, key="beta")
        mrp   = st.number_input("Market risk premium", value=DEFAULT_MARKET_RISK_PREMIUM, step=0.005, format="%.3f")
    with col2:
        st.markdown("**Debt & tax**")
        cod   = st.number_input("Cost of debt (pre-tax)", value=0.04, step=0.005, format="%.3f")
        tax   = st.number_input("Tax rate", value=DEFAULT_TAX_RATE_FR, step=0.01)
        total_debt = st.number_input("Total debt ($B)", value=(field(fin,"total_debt",ly) or 0)/1e9, step=0.1, format="%.2f")
    with col3:
        st.markdown("**Projection**")
        g1    = st.number_input("Growth yr 1-3 (%)", value=5.0, step=0.5) / 100
        g2    = st.number_input("Growth yr 4-5 (%)", value=3.0, step=0.5) / 100
        tg    = st.number_input("Terminal growth (%)", value=DEFAULT_TERMINAL_GROWTH_RATE*100, step=0.1) / 100

    cash_val   = field(fin, "cash", ly) or 0
    ebit_val   = field(fin, "ebit", ly) or 0
    da_val     = field(fin, "d_and_a", ly) or 0
    capex_val  = field(fin, "capex", ly) or 0

    wacc_inputs = WaccInputs(
        risk_free_rate=rfr, beta=beta, market_risk_premium=mrp,
        cost_of_debt=cod, tax_rate=tax,
        market_value_equity=market_cap or 1,
        market_value_debt=total_debt * 1e9,
    )
    wacc = compute_wacc(wacc_inputs)

    growth_rates = [g1, g1, g1, g2, g2]
    fcff_proj = project_fcff(
        base_ebit=ebit_val, tax_rate=tax, base_d_and_a=da_val,
        base_capex=abs(capex_val), base_delta_nwc=0,
        revenue_growth_rates=growth_rates,
    )

    result = run_dcf(
        fcff_proj, wacc=wacc, terminal_growth=tg,
        total_debt=total_debt * 1e9, cash=cash_val,
        shares_outstanding=shares or 1,
    )

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("WACC", f"{wacc*100:.2f}%")
    c2.metric("Enterprise Value", fmt(result["enterprise_value"]))
    c3.metric("Equity Value", fmt(result["equity_value"]))
    c4.metric("Implied Price/Share", f"${result['value_per_share']:.2f}" if result['value_per_share'] else "N/A")

    if price and result['value_per_share']:
        updown = (result['value_per_share'] / price - 1) * 100
        st.metric("Upside / Downside vs current price", f"{updown:+.1f}%")

    # Sensitivity: WACC vs terminal growth
    st.subheader("Sensitivity — Implied Price/Share")
    wacc_range = [wacc - 0.02, wacc - 0.01, wacc, wacc + 0.01, wacc + 0.02]
    tg_range   = [tg - 0.01, tg - 0.005, tg, tg + 0.005, tg + 0.01]
    sens_data = {}
    for w in wacc_range:
        row = {}
        for t in tg_range:
            try:
                r = run_dcf(fcff_proj, wacc=w, terminal_growth=t,
                            total_debt=total_debt*1e9, cash=cash_val, shares_outstanding=shares or 1)
                row[f"{t*100:.1f}%"] = f"${r['value_per_share']:.1f}" if r['value_per_share'] else "N/A"
            except Exception:
                row[f"{t*100:.1f}%"] = "err"
        sens_data[f"{w*100:.1f}%"] = row
    st.dataframe(pd.DataFrame(sens_data).T, use_container_width=True)
    st.caption("Rows = WACC, Columns = terminal growth rate")

# ─── COMPS ───────────────────────────────────────────────────────────────────
with tab_comps:
    st.subheader("Comparable Companies Analysis")
    st.info("Add peers below using their Yahoo Finance tickers. Data is fetched live.")

    peer_tickers_input = st.text_input("Peer tickers (comma-separated)", placeholder="NVDA, INTC, TXN, ASML")

    target_ev = (market_cap or 0) + (total_debt * 1e9 if 'total_debt' in dir() else 0) - cash_val
    target_ebitda = field(fin, "ebitda", ly) or 1
    target_revenue = field(fin, "revenue", ly) or 1
    target_ni = field(fin, "net_income", ly) or 1

    target_multiples = compute_multiples(
        enterprise_value=target_ev, market_cap=market_cap or 0,
        ebitda=target_ebitda, revenue=target_revenue, net_income=target_ni,
    )
    target_multiples.company_name = selected_name

    if peer_tickers_input.strip():
        import yfinance as yf
        peer_tickers = [t.strip().upper() for t in peer_tickers_input.split(",") if t.strip()]
        peer_multiples_list = []

        with st.spinner("Fetching peer data..."):
            for pt in peer_tickers:
                try:
                    t = yf.Ticker(pt)
                    info = t.info
                    p_mc   = info.get("marketCap") or 0
                    p_debt = info.get("totalDebt") or 0
                    p_cash = info.get("totalCash") or 0
                    p_ev   = p_mc + p_debt - p_cash
                    inc = t.income_stmt
                    p_ebitda  = float(inc.loc["EBITDA"].iloc[0])  if "EBITDA" in inc.index else 1
                    p_revenue = float(inc.loc["Total Revenue"].iloc[0]) if "Total Revenue" in inc.index else 1
                    p_ni      = float(inc.loc["Net Income"].iloc[0])    if "Net Income" in inc.index else 1
                    m = compute_multiples(p_ev, p_mc, p_ebitda, p_revenue, p_ni)
                    m.company_name = pt
                    peer_multiples_list.append(m)
                except Exception as e:
                    st.warning(f"Could not fetch {pt}: {e}")

        if peer_multiples_list:
            stats = peer_set_summary_stats(peer_multiples_list)

            rows = []
            for m in [target_multiples] + peer_multiples_list:
                rows.append({
                    "Company": m.company_name + (" ← target" if m.company_name == selected_name else ""),
                    "EV/EBITDA": f"{m.ev_ebitda:.1f}x" if m.ev_ebitda else "N/A",
                    "EV/Sales":  f"{m.ev_sales:.2f}x"  if m.ev_sales  else "N/A",
                    "P/E":       f"{m.pe:.1f}x"         if m.pe        else "N/A",
                })
            st.dataframe(pd.DataFrame(rows).set_index("Company"), use_container_width=True)

            med_ev_ebitda = stats["ev_ebitda"]["median"]
            med_ev_sales  = stats["ev_sales"]["median"]
            if med_ev_ebitda and med_ev_sales:
                implied_ebitda = implied_valuation_from_multiple(target_ebitda, med_ev_ebitda, total_debt*1e9 if 'total_debt' in dir() else 0, cash_val)
                implied_sales  = implied_valuation_from_multiple(target_revenue, med_ev_sales,  total_debt*1e9 if 'total_debt' in dir() else 0, cash_val)
                st.divider()
                st.markdown("**Implied equity value (peer median multiples)**")
                ca, cb = st.columns(2)
                ca.metric("via EV/EBITDA", fmt(implied_ebitda))
                cb.metric("via EV/Sales",  fmt(implied_sales))
    else:
        st.caption("Enter peer tickers to see comps table and implied valuation.")

# ─── LBO ─────────────────────────────────────────────────────────────────────
with tab_lbo:
    st.subheader("LBO — Leveraged Buyout")

    base_ebitda = (field(fin, "ebitda", ly) or 0) / 1e9

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Entry**")
        entry_mult  = st.number_input("Entry EV/EBITDA", value=8.0, step=0.5)
        lev_mult    = st.number_input("Leverage (Debt/EBITDA)", value=4.0, step=0.25)
        interest_r  = st.number_input("Interest rate on debt", value=0.06, step=0.005, format="%.3f")
    with col2:
        st.markdown("**Exit**")
        exit_mult   = st.number_input("Exit EV/EBITDA", value=8.0, step=0.5)
        holding_yrs = st.number_input("Holding period (years)", value=5, step=1, min_value=1, max_value=10)
        ebitda_cagr = st.number_input("EBITDA CAGR (%)", value=5.0, step=0.5) / 100

    su = build_sources_and_uses(base_ebitda, entry_mult, lev_mult)
    exit_ebitda = base_ebitda * (1 + ebitda_cagr) ** holding_yrs

    # simple FCF for debt paydown: use trailing FCF as proxy, grow with EBITDA CAGR
    base_fcf = (field(fin, "free_cash_flow", ly) or 0) / 1e9
    fcf_for_sweep = [base_fcf * (1 + ebitda_cagr) ** y for y in range(1, holding_yrs + 1)]
    schedule = build_debt_schedule(su.new_debt, interest_r, fcf_for_sweep)
    exit_net_debt = schedule[-1].ending_debt if schedule else su.new_debt

    returns = compute_returns(su.sponsor_equity, exit_ebitda, exit_mult, exit_net_debt, holding_yrs)

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Entry EV", f"${su.entry_ev:.1f}B")
    c2.metric("Sponsor Equity", f"${su.sponsor_equity:.1f}B")
    c3.metric("IRR", f"{returns['irr']*100:.1f}%" if returns['irr'] else "N/A")
    c4.metric("MOIC", f"{returns['moic']:.2f}x" if returns['moic'] else "N/A")

    # Debt schedule table
    if schedule:
        sched_rows = [{
            "Year": s.year,
            "Beginning Debt ($B)": f"{s.beginning_debt:.2f}",
            "Interest ($B)": f"{s.interest_expense:.2f}",
            "Cash Sweep ($B)": f"{s.cash_sweep:.2f}",
            "Ending Debt ($B)": f"{s.ending_debt:.2f}",
        } for s in schedule]
        st.subheader("Debt Schedule")
        st.dataframe(pd.DataFrame(sched_rows).set_index("Year"), use_container_width=True)

session.close()
