"""Manual / smoke tests for link_direct (no pytest required).

Run: python -m v2.transfer.test_link_direct
"""

from __future__ import annotations

from v2.transfer.link_direct import detect_link_type, probe_metadata


def test_detect() -> None:
    assert detect_link_type("https://example.com/a.zip") == "direct"
    assert detect_link_type("https://www.youtube.com/watch?v=x") == "youtube"
    assert detect_link_type("magnet:?xt=urn:btih:abc") == "magnet"


def test_probe_direct_smoke() -> None:
    meta = probe_metadata("https://www.google.com/robots.txt")
    assert meta.link_type == "direct"


if __name__ == "__main__":
    test_detect()
    test_probe_direct_smoke()
    print("ok")
