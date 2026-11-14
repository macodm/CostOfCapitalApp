"""Pure financial calculations for the International Cost of Capital app.

Inputs are percentages, e.g. 6.5 means 6.5%, except unlevered_beta.
All numbers are nominal annual rates; no market data is fetched here.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import math


@dataclass(frozen=True)
class CostOfCapital:
    unlevered_beta: float
    levered_beta: float
    debt_share_pct: float
    tax_rate_pct: float
    equity_risk_premium_pct: float
    usd_yield_pct: float
    foreign_yield_pct: float
    usd_bbb_spread_pct: float
    foreign_bbb_spread_pct: float
    foreign_spread_overridden: bool
    usd_cost_equity_pct: float
    foreign_cost_equity_pct: float
    usd_cost_debt_pct: float
    foreign_cost_debt_pct: float
    usd_after_tax_debt_pct: float
    foreign_after_tax_debt_pct: float
    usd_wacc_pct: float
    foreign_wacc_pct: float

    def as_dict(self):
        return asdict(self)


def compute_cost_of_capital(
    *, unlevered_beta: float, tax_rate_pct: float, debt_share_pct: float,
    erp_pct: float, usd_yield_pct: float, foreign_yield_pct: float,
    usd_bbb_spread_pct: float, foreign_bbb_override_pct: float | None = None,
) -> CostOfCapital:
    """Calculate capital costs in two currencies.

    Assumptions to verify against the formulas handed out in class:
      beta_L = beta_U * [1 + (1 - tax) * D/E]
      Ke(c) = 10Y government yield(c) + beta_L * (one shared ERP)
      Kd(USD) = USD 10Y + USD BBB default spread
      foreign BBB spread (auto) = USD BBB spread * (1+r_foreign)/(1+r_USD)
      Kd(local) = foreign 10Y + foreign BBB spread
      WACC(c) = (1-D/V)*Ke(c) + (D/V)*Kd(c)*(1-tax)

    Fisher scaling of the *spread* is a modeling convention, not a quoted
    local BBB spread or a formal cross-currency no-arbitrage derivation.
    Government yields of countries with sovereign risk are not necessarily
    risk-free; these inputs are deliberately the assignment's bond yields.
    """
    inputs = [unlevered_beta, tax_rate_pct, debt_share_pct, erp_pct,
              usd_yield_pct, foreign_yield_pct, usd_bbb_spread_pct]
    if foreign_bbb_override_pct is not None:
        inputs.append(foreign_bbb_override_pct)
    if not all(math.isfinite(float(x)) for x in inputs):
        raise ValueError("All inputs must be finite numbers.")
    if not 0 <= debt_share_pct < 100:
        raise ValueError("Debt financing must be between 0% and less than 100%.")
    if not 0 <= tax_rate_pct <= 100:
        raise ValueError("Tax rate must be between 0% and 100%.")
    if unlevered_beta < 0 or erp_pct < 0 or usd_bbb_spread_pct < 0:
        raise ValueError("Beta, equity premium and BBB spread cannot be negative.")
    if foreign_bbb_override_pct is not None and foreign_bbb_override_pct < 0:
        raise ValueError("The local BBB spread cannot be negative.")
    if usd_yield_pct <= -100 or foreign_yield_pct <= -100:
        raise ValueError("Government yields must be above -100%.")

    tax = tax_rate_pct / 100
    d = debt_share_pct / 100
    e = 1 - d
    debt_to_equity = d / e
    levered_beta = unlevered_beta * (1 + (1 - tax) * debt_to_equity)
    equity_premium = levered_beta * erp_pct
    us_ke = usd_yield_pct + equity_premium
    local_ke = foreign_yield_pct + equity_premium
    us_kd = usd_yield_pct + usd_bbb_spread_pct

    # Percent spreads and decimal rates cancel correctly in this ratio.
    auto_local_spread = usd_bbb_spread_pct * (100 + foreign_yield_pct) / (100 + usd_yield_pct)
    local_spread = (auto_local_spread if foreign_bbb_override_pct is None
                    else foreign_bbb_override_pct)
    local_kd = foreign_yield_pct + local_spread
    us_kd_after_tax = us_kd * (1 - tax)
    local_kd_after_tax = local_kd * (1 - tax)
    us_wacc = e * us_ke + d * us_kd_after_tax
    local_wacc = e * local_ke + d * local_kd_after_tax

    return CostOfCapital(
        unlevered_beta=unlevered_beta, levered_beta=levered_beta,
        debt_share_pct=debt_share_pct, tax_rate_pct=tax_rate_pct,
        equity_risk_premium_pct=erp_pct, usd_yield_pct=usd_yield_pct,
        foreign_yield_pct=foreign_yield_pct, usd_bbb_spread_pct=usd_bbb_spread_pct,
        foreign_bbb_spread_pct=local_spread,
        foreign_spread_overridden=foreign_bbb_override_pct is not None,
        usd_cost_equity_pct=us_ke, foreign_cost_equity_pct=local_ke,
        usd_cost_debt_pct=us_kd, foreign_cost_debt_pct=local_kd,
        usd_after_tax_debt_pct=us_kd_after_tax,
        foreign_after_tax_debt_pct=local_kd_after_tax,
        usd_wacc_pct=us_wacc, foreign_wacc_pct=local_wacc,
    )
