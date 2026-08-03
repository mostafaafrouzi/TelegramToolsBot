"""Markets board + calc kit smoke tests."""

from __future__ import annotations

import unittest
from unittest import mock


class CalcKitTests(unittest.TestCase):
    def test_percent_and_loan(self):
        from v2.toolkit.calc_kit_light import loan_emi, percent_of

        ok, body = percent_of(25, 200)
        self.assertTrue(ok)
        self.assertIn("12.5", body.replace("٬", "").replace(",", ""))
        ok, body = loan_emi(1_000_000, 12, 12)
        self.assertTrue(ok)
        self.assertIn("قسط", body)

    def test_eval_plate(self):
        from v2.handlers.calc_kit_commands import _eval_calc

        ok, body = _eval_calc("plate", "22")
        self.assertTrue(ok)
        self.assertIn("تهران", body)

    def test_date_diff(self):
        from v2.toolkit.calendar_light import date_diff

        ok, body = date_diff("2001/01/01", "2002/01/01", lang="en")
        self.assertTrue(ok)
        self.assertIn("365", body)


class MarketBoardTests(unittest.TestCase):
    def test_report_uses_bundle_and_gold(self):
        from v2.toolkit import fx_light

        fake = fx_light.RateBundle(
            rates={"USD": 1_900_000.0, "EUR": 2_100_000.0, "JPY": 12_000.0, "USDT": 1_900_000.0},
            source="TEST",
            market="free_market",
            fetched_at=1.0,
        )
        with mock.patch.object(fx_light, "get_irr_rate_bundle", return_value=(True, fake)):
            with mock.patch.object(fx_light, "_gold_cache", {"XAU_OZ": 4000.0, "SEKEE": 1_800_000_000.0}, create=True):
                fx_light._gold_cache = {"XAU_OZ": 4000.0, "SEKEE": 1_800_000_000.0}
                ok, body = fx_light.market_quotes_report(lang="fa")
        self.assertTrue(ok)
        self.assertIn("دلار", body)
        self.assertIn("ین", body)
        self.assertIn("سکه", body)


if __name__ == "__main__":
    unittest.main()
