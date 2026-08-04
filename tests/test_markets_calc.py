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

    def test_power_zero_neg_rejected(self):
        from v2.toolkit.calc_kit_light import math_power

        ok, body = math_power(0, -1)
        self.assertFalse(ok)

    def test_bmi_and_compound(self):
        from v2.toolkit.calc_kit_light import bmi, compound_deposit

        ok, body = bmi(70, 175)
        self.assertTrue(ok)
        self.assertIn("BMI", body)
        ok, body = compound_deposit(1_000_000, 20, 12)
        self.assertTrue(ok)
        self.assertIn("مرکب", body)

    def test_multistep_eval_fields(self):
        from v2.handlers.calc_kit_commands import _eval_from_fields

        ok, body = _eval_from_fields("linear", {"a": "2", "b": "-4"})
        self.assertTrue(ok)
        self.assertIn("2", body.replace("٬", ""))

    def test_add_days(self):
        from v2.toolkit.calendar_light import add_days

        ok, body = add_days("2020/01/01", 10, lang="en")
        self.assertTrue(ok)
        self.assertIn("2020-01-11", body)


class FxCalculatorTests(unittest.TestCase):
    def test_parse_toman_and_usd(self):
        from v2.toolkit.fx_calculator import parse_amount_unit

        ok, amount, code = parse_amount_unit("100000 تومان")
        self.assertTrue(ok)
        self.assertEqual(code, "IRT")
        self.assertEqual(amount, 100000.0)
        ok, amount, code = parse_amount_unit("50 USD")
        self.assertTrue(ok)
        self.assertEqual(code, "USD")

    def test_reply_html_uses_enum(self):
        import inspect

        from pyrogram.enums import ParseMode
        from v2.core import msg_format as mf

        src = inspect.getsource(mf.reply_html)
        self.assertIn("ParseMode.HTML", src)
        self.assertNotEqual(ParseMode.HTML, "html")


class MarketBoardTests(unittest.TestCase):
    def test_report_hub_and_gold_no_third_party_brand(self):
        from v2.toolkit import fx_light
        from v2.toolkit.market_board import Quote, PROVIDER_LABEL_FA

        fake = fx_light.RateBundle(
            rates={"USD": 1_900_000.0, "EUR": 2_100_000.0, "JPY": 12_000.0, "USDT": 1_900_000.0},
            source=PROVIDER_LABEL_FA,
            market="free_market",
            fetched_at=1.0,
        )
        quotes = {
            "USD": Quote("USD", 1_900_000.0, "IRR", d=1000.0, dp=0.05, dt="12:00"),
            "EUR": Quote("EUR", 2_100_000.0, "IRR", d=-500.0, dp=-0.02),
            "GOLD18": Quote("GOLD18", 5_000_000.0, "IRR", d=100.0, dp=0.01),
            "SEKEE": Quote("SEKEE", 80_000_000.0, "IRR"),
        }
        with mock.patch.object(fx_light, "get_irr_rate_bundle", return_value=(True, fake)):
            with mock.patch.object(fx_light, "_quote_cache", quotes):
                ok_hub, hub = fx_light.market_quotes_report(lang="fa", section="hub")
                ok_gold, gold = fx_light.market_quotes_report(lang="fa", section="gold")
                ok_usd, usd = fx_light.market_quotes_report(lang="fa", section="usd")
        self.assertTrue(ok_hub)
        self.assertTrue(ok_gold)
        self.assertTrue(ok_usd)
        self.assertNotIn("TGJU", hub.upper())
        self.assertNotIn("tgju", hub.lower())
        self.assertNotIn("TGJU", gold.upper())
        self.assertIn("بازار آزاد", hub)
        self.assertIn("طلا", gold)

    def test_connect_cta_keyboard(self):
        from v2.core.connect_cta import connect_keyboard

        kb = connect_keyboard(drive=True, cloudflare=True, lang="fa")
        self.assertIsNotNone(kb)
        data = [b.callback_data for row in kb.inline_keyboard for b in row]
        self.assertIn("cta:drive_connect", data)
        self.assertIn("cta:cf_connect", data)


if __name__ == "__main__":
    unittest.main()
