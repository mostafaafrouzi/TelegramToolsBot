"""Smoke tests for the expanded toolkit (no pytest required).

Run: python -m v2.toolkit.test_extended_tools
"""

from __future__ import annotations

from v2.toolkit.extended_tools import (
    base_convert,
    clean_whitespace,
    color_convert,
    count_text,
    date_to_ts,
    generate_password,
    generate_token_hex,
    generate_uuid,
    json_format,
    jwt_decode,
    lorem_ipsum,
    now_panel,
    random_number,
    reverse_text,
    safe_calc,
    sha1_hex,
    sha512_hex,
    size_convert,
    slugify,
    to_lower,
    to_title,
    to_upper,
    ts_to_date,
    url_decode,
    url_encode,
)


def test_hashes() -> None:
    assert sha1_hex("hello") == "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"
    assert sha512_hex("hello").startswith("9b71d224bd62f3785d96d46ad3ea3d73")


def test_url() -> None:
    assert url_encode("a b") == "a%20b"
    assert url_decode("%D8%B3")[0] is True


def test_text() -> None:
    assert to_upper("abc") == "ABC"
    assert to_lower("ABC") == "abc"
    assert to_title("hello world") == "Hello World"
    assert reverse_text("abc") == "cba"
    assert slugify("Hello WORLD!") == "hello-world"
    assert "chars:" in count_text("foo")
    assert clean_whitespace("a   b\n\n\n\nc") == "a b\n\nc"


def test_generators() -> None:
    assert len(generate_uuid()) == 36
    assert len(generate_password(16)) == 16
    assert len(generate_token_hex(8)) == 16
    assert int(random_number(5, 5)) == 5
    assert "Lorem" in lorem_ipsum(1)


def test_converters() -> None:
    ok, body = ts_to_date("1700000000")
    assert ok and "UTC" in body
    ok, body = date_to_ts("2024-01-01")
    assert ok and int(body) > 1_700_000_000
    ok, body = base_convert("0xff")
    assert ok and "dec: 255" in body
    ok, body = color_convert("#ff8800")
    assert ok and "rgb(255, 136, 0)" in body
    ok, body = size_convert("1.5 GiB")
    assert ok and "GiB   : 1.500" in body
    ok, body = json_format('{"b":1,"a":2}')
    assert ok and '"a": 2' in body
    assert "UTC" in now_panel()


def test_calc() -> None:
    ok, body = safe_calc("(2+3)*5")
    assert ok and body == "25"
    ok, body = safe_calc("__import__('os')")
    assert not ok


def test_jwt() -> None:
    sample = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0."
        "signature"
    )
    ok, body = jwt_decode(sample)
    assert ok and "John Doe" in body


if __name__ == "__main__":
    test_hashes()
    test_url()
    test_text()
    test_generators()
    test_converters()
    test_calc()
    test_jwt()
    print("ok")
