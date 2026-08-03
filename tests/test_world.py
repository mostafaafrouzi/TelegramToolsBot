"""World / Feed Reader unit tests (stdlib unittest)."""

from __future__ import annotations

import json
import unittest
from unittest import mock


class WmoAndTimezoneTests(unittest.TestCase):
    def test_wmo_label_fa_en(self):
        from v2.toolkit.weather_light import wmo_label

        self.assertIn("صاف", wmo_label(0, lang="fa"))
        self.assertEqual(wmo_label(0, lang="en"), "Clear")

    def test_timezone_direct_iana(self):
        from v2.toolkit.timezone_light import timezone_report

        ok, body = timezone_report("Asia/Tehran", lang="en")
        self.assertTrue(ok)
        self.assertIn("Asia/Tehran", body)
        self.assertIn("Local:", body)


class CalendarAgeTests(unittest.TestCase):
    def test_age_gregorian(self):
        from v2.toolkit.calendar_light import age_report

        ok, body = age_report("2000/01/01", lang="en")
        self.assertTrue(ok)
        self.assertIn("years", body.lower())

    def test_age_bad_format(self):
        from v2.toolkit.calendar_light import age_report

        ok, body = age_report("not-a-date", lang="fa")
        self.assertFalse(ok)


class RssResolveTests(unittest.TestCase):
    def test_youtube_channel(self):
        from v2.toolkit.rss_resolve import resolve_feed_url

        url, kind, _hint = resolve_feed_url(
            "https://www.youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw"
        )
        self.assertEqual(kind, "youtube")
        self.assertIn("feeds/videos.xml?channel_id=", url)

    def test_twitter_user(self):
        from v2.toolkit.rss_resolve import resolve_feed_url

        url, kind, _hint = resolve_feed_url("https://x.com/Telegram")
        self.assertEqual(kind, "twitter")
        self.assertIn("/twitter/user/Telegram", url)

    def test_youtube_handle_resolves(self):
        from v2.toolkit.rss_resolve import resolve_feed_url

        html = '<html><meta itemprop="channelId" content="UC_x5XG1OV2P6uZZ5FSM9Ttw"></html>'
        with mock.patch("v2.toolkit.rss_resolve.urlopen") as uo:
            resp = mock.MagicMock()
            resp.read.return_value = html.encode("utf-8")
            resp.__enter__.return_value = resp
            resp.__exit__.return_value = False
            uo.return_value = resp
            url, kind, hint = resolve_feed_url("https://www.youtube.com/@GoogleDevelopers")
        self.assertEqual(kind, "youtube")
        self.assertIn("channel_id=UC_x5XG1OV2P6uZZ5FSM9Ttw", url)
        self.assertEqual(hint, "")


class RssItemsTests(unittest.TestCase):
    def test_new_items_since_json_seen(self):
        from v2.toolkit.rss_light import encode_seen_ids, new_items_since

        old = [
            {"id": "a", "title": "A", "link": "http://a"},
            {"id": "b", "title": "B", "link": "http://b"},
        ]
        new = [
            {"id": "c", "title": "C", "link": "http://c"},
            {"id": "a", "title": "A", "link": "http://a"},
        ]
        fresh = new_items_since(encode_seen_ids(old), new, limit=5)
        self.assertEqual(len(fresh), 1)
        self.assertEqual(fresh[0]["id"], "c")

    def test_atom_parse(self):
        from v2.toolkit.rss_light import _parse_items_xml

        atom = """<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Hello</title>
            <id>urn:1</id>
            <link href="https://example.com/1" rel="alternate"/>
          </entry>
        </feed>"""
        items = _parse_items_xml(atom, limit=5)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Hello")
        self.assertEqual(items[0]["link"], "https://example.com/1")


class FxIrrTests(unittest.TestCase):
    def test_same_currency(self):
        from v2.toolkit.fx_light import currency_convert

        ok, body = currency_convert(10, "USD", "USD", lang="en")
        self.assertTrue(ok)
        self.assertIn("USD", body)

    def test_irr_bridge_mocked(self):
        from v2.toolkit.fx_light import currency_convert

        with mock.patch("v2.toolkit.fx_light._irr_usd_rate", return_value=(True, 420000.0)):
            ok, body = currency_convert(1, "USD", "IRR", lang="fa")
        self.assertTrue(ok)
        self.assertIn("IRR", body)


class FeedDuplicateGuardTests(unittest.TestCase):
    def test_add_feed_returns_existing(self):
        import tempfile
        from pathlib import Path

        from queue_db import QueueDB

        td = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        try:
            db = QueueDB(Path(td.name) / "q.sqlite3")
            a = db.add_feed(99, "https://example.com/feed.xml", label="one")
            b = db.add_feed(99, "https://example.com/feed.xml", label="two")
            self.assertEqual(a, b)
            self.assertEqual(db.count_feeds(99), 1)
        finally:
            td.cleanup()


class MenuWorldTests(unittest.TestCase):
    def test_world_menu_has_time_and_no_main_feed(self):
        from v2.core import menu_engine

        def tr(_uid, key, **_kw):
            return key

        kb = menu_engine.build_world_menu(1, tr)
        labels = [btn.text for row in kb.keyboard for btn in row]
        self.assertIn("btn_world_time", labels)
        self.assertIn("btn_world_age", labels)

        main = menu_engine.build_main_menu(1, tr, is_admin=False)
        main_labels = [btn.text for row in main.keyboard for btn in row]
        self.assertNotIn("btn_main_feed", main_labels)
        self.assertIn("btn_main_world", main_labels)


if __name__ == "__main__":
    unittest.main()
