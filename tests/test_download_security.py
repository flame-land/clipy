"""Regression tests for Clipy's download URL allowlist."""
import unittest

from cogs.download import validate_url


class DownloadURLValidationTests(unittest.TestCase):
    def test_accepts_supported_https_hosts(self):
        for url in (
            "https://youtube.com/watch?v=abc",
            "https://www.youtube.com/watch?v=abc",
            "https://youtu.be/abc",
            "https://www.instagram.com/reel/abc/",
            "https://fb.watch/abc/",
            "https://www.tiktok.com/@user/video/123",
        ):
            with self.subTest(url=url):
                self.assertEqual(validate_url(url), url)

    def test_rejects_unapproved_hosts_and_subdomain_tricks(self):
        for url in (
            "https://example.com/video",
            "https://youtube.com.example.org/watch?v=abc",
            "https://notyoutube.com/watch?v=abc",
            "http://youtube.com/watch?v=abc",
            "file:///etc/passwd",
            "javascript:alert(1)",
        ):
            with self.subTest(url=url):
                self.assertIsNone(validate_url(url))

    def test_rejects_credentials_and_nonstandard_ports(self):
        for url in (
            "https://user:pass@youtube.com/watch?v=abc",
            "https://youtube.com:8443/watch?v=abc",
            "https://youtube.com:444/watch?v=abc",
        ):
            with self.subTest(url=url):
                self.assertIsNone(validate_url(url))

    def test_rejects_malformed_urls(self):
        for url in ("https://[::1", "", "   "):
            with self.subTest(url=url):
                self.assertIsNone(validate_url(url))


if __name__ == "__main__":
    unittest.main()
