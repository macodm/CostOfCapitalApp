"""International cost of capital comparison — launch with `streamlit run app.py`."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from data_sources import (
    CURRENCIES, BETA_URL, OECD_URL, RATING_URL, TE_URL,
    fetch_betas, fetch_bbb_spread, fetch_tax_rates, fetch_bond_yield,
)
from finance import compute_cost_of_capital

st.set_page_config(
    page_title="International Cost of Capital", page_icon="🌍", layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 1350px;}
[data-testid="stMetric"] {border: 1px solid #e2e8f0; border-radius: 10px;
  padding: 14px 16px; background-color: rgba(148,163,184,0.045);}
.small-note {color:#64748b; font-size:0.92rem;}
</style>""", unsafe_allow_html=True)


@st.cache_data(ttl=3600, show_spinner=False)
def get_betas():
    return fetch_betas()


@st.cache_data(ttl=3600, show_spinner=False)
def get_bbb():
    return fetch_bbb_spread()


@st.cache_data(ttl=3600, show_spinner=False)
def get_taxes():
    return fetch_tax_rates()


@st.cache_data(ttl=3600, show_spinner=False)
def get_yield(country):
    return fetch_bond_yield(country)


def source_line(label, result):
    status = result["status"]
    symbol = "✅" if status == "Live" else ("⚠️" if result["data"] is not None else "❌")
    st.markdown(f"**{symbol} {label}** — {status}")
    st.caption(f"Source period / observation: {result['period']} | Fetch: {result['fetched_at']}")
    st.markdown(f"[Open original source]({result['url']})")
    if result.get("error"):
        st.caption(f"Live fetch detail: {result['error']}")


def numeric_override(label, fetched, key, minimum, maximum, increment, precision=3):
    """A separate switch prevents a stale input from silently replacing fresh data."""
    auto_is_missing = fetched is None
    default_on = auto_is_missing
    enabled = st.checkbox(f"Override {label}", value=default_on, key=f"override_{key}")
    if enabled:
        val = st.number_input(
            f"{label} (manual)", min_value=float(minimum), max_value=float(maximum),
            value=float(fetched) if fetched is not None else float(max(0, minimum)),
            step=float(increment), format=f"%.{precision}f", key=f"manual_{key}",
        )
        return float(val), True
    if auto_is_missing:
        st.error(f"No automatic {label} quote. Turn on its manual override.")
        return None, False
    st.caption(f"{label}: **{fetched:.{precision}f}** (fetched or dated source)")
    return float(fetched), False


st.title("🌍 International Cost of Capital")
st.markdown("Compare a project's **cost of equity, borrowing cost, and WACC** in USD and another country's currency, using a common project capital structure, tax rate and equity premium.")

head_left, head_right = st.columns([5, 2])
with head_right:
    if st.button("🔄 Refresh all source data", use_container_width=True,
                 help="Clear source caches and request live figures again. Manual overrides remain as set."):
        get_betas.clear(); get_bbb.clear(); get_taxes.clear(); get_yield.clear()
        st.rerun()

with st.spinner("Loading Damodaran and OECD inputs…"):
    with ThreadPoolExecutor(max_workers=3) as pool:
        fb = pool.submit(get_betas)
        fs = pool.submit(get_bbb)
        ft = pool.submit(get_taxes)
        beta_res, bbb_res, tax_res = fb.result(), fs.result(), ft.result()

betas = beta_res["data"]
industry_names = sorted(betas)
def_industry = "Software (System & Application)"

with st.sidebar:
    st.header("Project setup")
    industry = st.selectbox("Industry (U.S. Damodaran beta)", industry_names,
                            index=industry_names.index(def_industry)
                            if def_industry in industry_names else 0)
    choice = st.selectbox("Target country", sorted(CURRENCIES) + ["Other (manual / custom)"],
                          index=sorted(CURRENCIES).index("United States"))
    country = choice
    if choice == "Other (manual / custom)":
        country = st.text_input("Custom country name", value="Custom country").strip() or "Custom country"
        currency = st.text_input("ISO currency code", value="LOC", max_chars=3).strip().upper() or "LOC"
    else:
        currency = CURRENCIES[choice]
    st.divider()
    erp = st.number_input("Equity risk premium (%)", min_value=0.0, max_value=30.0,
                          value=6.5, step=0.25, format="%.2f")
    debt_share = st.slider("Debt / total financing (%)", min_value=0, max_value=95,
                           value=30, step=1,
                           help="Debt / (Debt + Equity). 100% debt is excluded because D/E would be undefined.")
    st.caption(f"Equity financing: {100-debt_share}%")

with st.spinner("Loading 10-year sovereign yields…"):
    with ThreadPoolExecutor(max_workers=2) as pool:
        fu = pool.submit(get_yield, "United States")
        fc = pool.submit(get_yield, country) if choice != "Other (manual / custom)" else None
        us_yield_res = fu.result()
        foreign_yield_res = fc.result() if fc else {
            "data": None, "status": "Unavailable — manual entry required", "period": "Custom country",
            "url": TE_URL, "fetched_at": "Not fetched", "error": "Enter a manual government yield"}

if st.session_state.get("tax_source") not in ("United States", "Target country"):
    st.session_state["tax_source"] = "United States"

st.subheader("1. Tax rate applied to the project")
st.caption("Choose **one** statutory project tax rate. It is used for re-levering beta and for the after-tax cost of debt in BOTH currencies.")
tax_btn_us, tax_btn_local, tax_label = st.columns([1, 1, 2])
with tax_btn_us:
    if st.button("Use U.S. tax rate", use_container_width=True,
                 type="primary" if st.session_state["tax_source"] == "United States" else "secondary"):
        st.session_state["tax_source"] = "United States"
with tax_btn_local:
    if st.button("Use target-country tax rate", use_container_width=True,
                 type="primary" if st.session_state["tax_source"] == "Target country" else "secondary"):
        st.session_state["tax_source"] = "Target country"
with tax_label:
    st.info("Selected: **" + ("United States" if st.session_state["tax_source"] == "United States" else country) + "**")

with st.expander("2. Review fetched values and edit inputs", expanded=True):
    left, right = st.columns(2)
    with left:
        st.markdown("**Industry and USD inputs**")
        raw_beta = betas.get(industry)
        beta, beta_over = numeric_override("Unlevered beta", raw_beta,
                                           f"beta_{industry}", 0.0, 8.0, .05)
        us_tax, us_tax_over = numeric_override("U.S. corporate tax rate (%)",
                tax_res["data"].get("United States"), "us_tax", 0.0, 100.0, .25, 2)
        usd_bbb, bbb_over = numeric_override("USD BBB spread (%)", bbb_res["data"],
                                             "usd_bbb", 0.0, 50.0, .05, 3)
        usd_yield, us_yield_over = numeric_override("U.S. 10Y yield (%)", us_yield_res["data"],
                                                     "us_10y", -10.0, 100.0, .05, 4)
    with right:
        st.markdown(f"**{country} / {currency} inputs**")
        target_tax, local_tax_over = numeric_override(f"{country} tax rate (%)",
                tax_res["data"].get(country), f"tax_{country}", 0.0, 100.0, .25, 2)
        local_yield, local_yield_over = numeric_override(f"{country} 10Y yield (%)",
                foreign_yield_res["data"], f"yield_{country}", -10.0, 100.0, .05, 4)
        st.markdown("**Foreign-currency BBB spread**")
        foreign_bbb_manual = st.checkbox("Override automatically calculated local BBB spread",
                                         value=False, key=f"foreign_bbb_override_{country}")
        # Calculated on the actual USD spread and both currently active yields.
        if (usd_bbb is not None and usd_yield is not None and local_yield is not None
                and usd_yield > -100):
            auto_foreign_bbb = usd_bbb * (100 + local_yield) / (100 + usd_yield)
        else:
            auto_foreign_bbb = None
        if foreign_bbb_manual:
            local_spread_input = st.number_input(
                f"Manual {currency} BBB spread (%)", min_value=0.0, max_value=50.0,
                value=float(auto_foreign_bbb) if auto_foreign_bbb is not None else 1.11,
                step=.05, format="%.4f", key=f"foreign_bbb_{country}")
        else:
            local_spread_input = None
            st.caption((f"Auto: **{auto_foreign_bbb:.4f}%** = USD BBB spread × "
                        f"(1 + {country} 10Y) / (1 + U.S. 10Y)")
                       if auto_foreign_bbb is not None else "Auto spread unavailable until both bond yields are entered")

selected_tax = us_tax if st.session_state["tax_source"] == "United States" else target_tax
needed = {"Unlevered beta": beta, "Project corporate tax": selected_tax,
          "USD BBB spread": usd_bbb, "U.S. 10-year yield": usd_yield,
          "Target-country 10-year yield": local_yield}
missing = [k for k, v in needed.items() if v is None]
if missing:
    st.error("Missing inputs: " + ", ".join(missing) + ". Enable manual entry above to continue.")
    st.stop()

try:
    result = compute_cost_of_capital(
        unlevered_beta=beta, tax_rate_pct=selected_tax,
        debt_share_pct=debt_share, erp_pct=erp,
        usd_yield_pct=usd_yield, foreign_yield_pct=local_yield,
        usd_bbb_spread_pct=usd_bbb,
        foreign_bbb_override_pct=local_spread_input,
    )
except ValueError as exc:
    st.error(str(exc)); st.stop()

st.divider()
st.subheader("3. Cost of capital comparison")
a, b = st.columns(2, gap="large")
for col, heading, rf, ke, kd, after_tax, wacc, spread in [
    (a, "United States · USD", result.usd_yield_pct, result.usd_cost_equity_pct,
     result.usd_cost_debt_pct, result.usd_after_tax_debt_pct,
     result.usd_wacc_pct, result.usd_bbb_spread_pct),
    (b, f"{country} · {currency}", result.foreign_yield_pct, result.foreign_cost_equity_pct,
     result.foreign_cost_debt_pct, result.foreign_after_tax_debt_pct,
     result.foreign_wacc_pct, result.foreign_bbb_spread_pct),
]:
    with col:
        st.markdown(f"### {heading}")
        st.metric("WACC", f"{wacc:.2f}%")
        x, y = st.columns(2)
        x.metric("Cost of equity", f"{ke:.2f}%")
        y.metric("Pre-tax cost of debt", f"{kd:.2f}%")
        st.caption(f"10Y government yield: **{rf:.4f}%** · BBB spread: **{spread:.4f}%** · after-tax debt cost: **{after_tax:.2f}%**")

st.caption(f"Shared inputs: unlevered beta {beta:.3f}; re-levered beta {result.levered_beta:.4f}; ERP {erp:.2f}%; debt {debt_share}%; applied tax {selected_tax:.2f}%. Foreign spread: {'manual' if foreign_bbb_manual else 'auto calculated'}.")

with st.expander("Show formulas and key modeling assumptions"):
    st.latex(r"\frac{D}{E}=\frac{w_D}{1-w_D},\quad \beta_L=\beta_U\left[1+(1-T)\frac{D}{E}\right]")
    st.latex(r"K_{e,c}=Y_{10,c}+\beta_L\cdot ERP")
    st.latex(r"s_{BBB,local}=s_{BBB,USD}\frac{1+Y_{10,local}}{1+Y_{10,USD}}\quad (\mathrm{unless\ manually\ overridden})")
    st.latex(r"K_{d,USD}=Y_{10,USD}+s_{BBB,USD},\quad K_{d,local}=Y_{10,local}+s_{BBB,local}")
    st.latex(r"WACC_c=(1-w_D)K_{e,c}+w_D K_{d,c}(1-T)")
    st.markdown("**Important:** Rates in equations are decimals (e.g., 5% = 0.05). The foreign spread adjustment is a Fisher-style *spread-scaling convention*, not a market-observed foreign BBB spread. The same numeric ERP, project tax rate, and financing mix are used in both currencies. Sovereign yields may contain default and liquidity premiums; this simplified exercise treats them as the government-yield bases. **Verify these choices against the class formulas before submission.**")

st.divider()
st.subheader("4. Compare every available industry")
compare_rows = []
local_label = f"{country} ({currency}) WACC (%)"
for sector, sector_beta in betas.items():
    # If beta is manually overridden, only replace the selected industry's row.
    active_beta = beta if sector == industry else float(sector_beta)
    x = compute_cost_of_capital(
        unlevered_beta=active_beta, tax_rate_pct=selected_tax,
        debt_share_pct=debt_share, erp_pct=erp,
        usd_yield_pct=usd_yield, foreign_yield_pct=local_yield,
        usd_bbb_spread_pct=usd_bbb, foreign_bbb_override_pct=local_spread_input)
    compare_rows.append({
        "Industry": sector, "Unlevered beta": active_beta, "Levered beta": x.levered_beta,
        "U.S. Ke (%)": x.usd_cost_equity_pct, "U.S. Kd (%)": x.usd_cost_debt_pct,
        "U.S. WACC (%)": x.usd_wacc_pct, f"{country} ({currency}) Ke (%)": x.foreign_cost_equity_pct,
        f"{country} ({currency}) Kd (%)": x.foreign_cost_debt_pct,
        local_label: x.foreign_wacc_pct,
    })
comparison = pd.DataFrame(compare_rows).sort_values("U.S. WACC (%)").reset_index(drop=True)
if beta_res["status"] != "Live":
    st.warning(f"Industry comparison uses a dated January 2026 offline snapshot ({len(betas)} Damodaran sectors). Refresh to check for newer industry data.")
if beta_over:
    st.caption("Manual beta override affects the selected industry only; other industry betas stay at source values.")
st.dataframe(comparison, hide_index=True, use_container_width=True,
             column_config={c: st.column_config.NumberColumn(c, format="%.3f")
                            for c in comparison.columns if c != "Industry"})
st.markdown("**Industry WACC visualization**")
st.bar_chart(comparison.set_index("Industry")[["U.S. WACC (%)", local_label]],
             height=360, use_container_width=True)

st.divider()
st.subheader("5. Download calculations")
inputs = {
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "industry": industry, "target_country": country, "currency": currency,
    "project_tax_jurisdiction": st.session_state["tax_source"],
    "assumptions": {
        "unlevered_beta": beta, "project_tax_pct": selected_tax,
        "usd_tax_pct": us_tax, "target_tax_pct": target_tax,
        "erp_pct": erp, "debt_share_pct": debt_share,
        "usd_10y_pct": usd_yield, "target_10y_pct": local_yield,
        "usd_bbb_spread_pct": usd_bbb, "target_bbb_spread_override_pct": local_spread_input,
    },
    "results_pct": result.as_dict(),
    "sources": {"Damodaran betas": beta_res, "Damodaran BBB": bbb_res,
                "OECD corporate tax": tax_res, "US bonds": us_yield_res,
                "Target bonds": foreign_yield_res},
    "model_formula_version": "Shared ERP additive CAPM + Fisher-scaled local BBB spread (provisional)",
}
# Compact metadata in downloads; no user-specific secrets or account data.
d1, d2 = st.columns(2)
with d1:
    st.download_button("⬇ Download all-industry comparison (CSV)",
                       data=comparison.to_csv(index=False).encode("utf-8-sig"),
                       file_name="international_wacc_all_industries.csv",
                       mime="text/csv", use_container_width=True)
with d2:
    st.download_button("⬇ Download inputs, results and provenance (JSON)",
                       data=json.dumps(inputs, indent=2, default=str),
                       file_name="international_wacc_selected_project.json",
                       mime="application/json", use_container_width=True)

with st.expander("6. Data sources, observation dates and retrieval diagnostics", expanded=False):
    st.caption("'Live' means fetched during this session (or from the one-hour app cache). It does NOT mean the underlying observation was published today. 'Dated snapshot' explicitly means the live source could not be retrieved.")
    source_line("U.S. industry unlevered betas", beta_res)
    source_line("Large non-financial BBB borrowing spread", bbb_res)
    source_line("Corporate combined statutory tax rates", tax_res)
    source_line("U.S. 10-year bond yield", us_yield_res)
    source_line(f"{country} 10-year bond yield", foreign_yield_res)
    st.markdown(f"Main landing pages: [Damodaran betas]({BETA_URL}) · [Damodaran ratings]({RATING_URL}) · [OECD corporate taxes]({OECD_URL}) · [Trading Economics bonds]({TE_URL})")
    st.caption("The OECD 2024 publication linked in the course handout is older than the 2026 OECD database. Only automatically fetched or source-dated snapshots are reported; manual inputs are kept separate.")

with st.expander("7. Built-in calculation verification", expanded=False):
    if st.button("Run three invariant checks and a calculator example"):
        checks = []
        base = dict(unlevered_beta=1.23, tax_rate_pct=25.53, debt_share_pct=30,
                    erp_pct=6.5, usd_yield_pct=5.145, foreign_yield_pct=5.145,
                    usd_bbb_spread_pct=1.11)
        x = compute_cost_of_capital(**base)
        checks.append(("Equal yields → equal USD/local Ke, Kd and WACC",
                       all(abs(a-b) < 1e-11 for a,b in [
                           (x.usd_cost_equity_pct, x.foreign_cost_equity_pct),
                           (x.usd_cost_debt_pct, x.foreign_cost_debt_pct),
                           (x.usd_wacc_pct, x.foreign_wacc_pct)])))
        x0 = compute_cost_of_capital(**{**base, "debt_share_pct": 0})
        checks.append(("0% debt → WACC equals Ke in each currency",
                       abs(x0.usd_wacc_pct-x0.usd_cost_equity_pct)<1e-11 and
                       abs(x0.foreign_wacc_pct-x0.foreign_cost_equity_pct)<1e-11))
        mx = {**base, "foreign_yield_pct": 9.308}
        before = compute_cost_of_capital(**mx)
        after = compute_cost_of_capital(**mx, foreign_bbb_override_pct=3.4)
        checks.append(("Changing local BBB spread leaves USD Ke, Kd and WACC unchanged",
                       before.usd_wacc_pct == after.usd_wacc_pct and
                       before.usd_cost_equity_pct == after.usd_cost_equity_pct and
                       before.usd_cost_debt_pct == after.usd_cost_debt_pct))
        checks.append(("Independent arithmetic on 2026 U.S. software example",
                       abs(x.usd_wacc_pct - (
                           .7*(5.145 + 1.23*(1+.7447*(.3/.7))*6.5)
                           + .3*(5.145+1.11)*.7447)) < 1e-10))
        for msg, passed in checks:
            (st.success if passed else st.error)(("PASS — " if passed else "FAIL — ")+msg)
        st.caption("These are arithmetic/invariance checks, not proof that the modeling conventions match the handout. Full tests: python -m unittest discover -s tests -v")

st.caption("Educational model · Currency-specific *percent* discount rates, not foreign-exchange conversions of project cash flows. Validate assumptions and source dates before using in a valuation.")
