"""Run from project root: python -m unittest discover -s tests -v"""
import unittest
from finance import compute_cost_of_capital as calc

BASE = dict(unlevered_beta=1.23, tax_rate_pct=25.53, debt_share_pct=30,
            erp_pct=6.5, usd_yield_pct=5.145, foreign_yield_pct=9.308,
            usd_bbb_spread_pct=1.11)


class CostOfCapitalTest(unittest.TestCase):
    def test_independently_calculated_usd_example(self):
        r = calc(**BASE)
        t = .2553
        d = .30
        direct_beta = 1.23 * (1 + (1-t)*d/(1-d))
        manual_ke = 5.145 + direct_beta * 6.5
        manual_kd = 5.145 + 1.11
        manual_wacc = .70 * manual_ke + .30 * manual_kd * (1-t)
        self.assertAlmostEqual(r.levered_beta, direct_beta, places=12)
        self.assertAlmostEqual(r.usd_cost_equity_pct, manual_ke, places=12)
        self.assertAlmostEqual(r.usd_cost_debt_pct, manual_kd, places=12)
        self.assertAlmostEqual(r.usd_wacc_pct, manual_wacc, places=12)

    def test_equal_yields_identical_results_when_spread_auto(self):
        r = calc(**{**BASE, "foreign_yield_pct": BASE["usd_yield_pct"]})
        self.assertAlmostEqual(r.usd_cost_equity_pct, r.foreign_cost_equity_pct)
        self.assertAlmostEqual(r.usd_cost_debt_pct, r.foreign_cost_debt_pct)
        self.assertAlmostEqual(r.usd_wacc_pct, r.foreign_wacc_pct)
        self.assertAlmostEqual(r.usd_bbb_spread_pct, r.foreign_bbb_spread_pct)

    def test_zero_debt_wacc_equals_equity(self):
        r = calc(**{**BASE, "debt_share_pct": 0})
        self.assertAlmostEqual(r.usd_wacc_pct, r.usd_cost_equity_pct)
        self.assertAlmostEqual(r.foreign_wacc_pct, r.foreign_cost_equity_pct)
        self.assertAlmostEqual(r.levered_beta, BASE["unlevered_beta"])

    def test_local_spread_override_does_not_change_usd(self):
        old = calc(**BASE)
        new = calc(**BASE, foreign_bbb_override_pct=4.5)
        self.assertEqual(old.usd_wacc_pct, new.usd_wacc_pct)
        self.assertEqual(old.usd_cost_debt_pct, new.usd_cost_debt_pct)
        self.assertEqual(old.usd_cost_equity_pct, new.usd_cost_equity_pct)
        self.assertNotEqual(old.foreign_wacc_pct, new.foreign_wacc_pct)
        self.assertEqual(new.foreign_bbb_spread_pct, 4.5)

    def test_local_auto_spread_scales_by_yield_ratio(self):
        r = calc(**BASE)
        manual = 1.11 * 1.09308 / 1.05145
        self.assertAlmostEqual(r.foreign_bbb_spread_pct, manual)

    def test_invalid_all_debt(self):
        with self.assertRaises(ValueError):
            calc(**{**BASE, "debt_share_pct": 100})


if __name__ == "__main__":
    unittest.main()
