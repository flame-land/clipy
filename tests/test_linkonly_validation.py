"""Tests for standalone URL validation in link-only channels."""
from cogs.linkonly import is_single_http_url


def test_accepts_standalone_http_urls():
    assert is_single_http_url("https://example.com")
    assert is_single_http_url("http://example.com/path?q=1")
    assert is_single_http_url("  https://example.com/path  ")


def test_rejects_text_mixed_with_url():
    assert not is_single_http_url("Check this https://example.com")
    assert not is_single_http_url("https://example.com check this")
    assert not is_single_http_url("")


def test_rejects_non_http_and_multiple_urls():
    assert not is_single_http_url("ftp://example.com/file")
    assert not is_single_http_url("https://example.com https://example.org")


def test_rejects_invalid_urls():
    assert not is_single_http_url("https://")
    assert not is_single_http_url("https://example.com:badport")
