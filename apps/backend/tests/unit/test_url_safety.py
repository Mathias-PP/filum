"""Tests for the SSRF guard in app.core.url_safety.

Regression coverage for the audit finding (HIGH): the `/sources/extract`
endpoint is no-auth and rate-limited to 10/min, so a malicious actor
could probe internal services via the backend if we don't reject
loopback / private / link-local / metadata IPs up-front.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.url_safety import UnsafeUrlError, assert_url_is_safe


class TestSchemeFilter:
    def test_https_allowed(self):
        # google.com is a stable public host for the test resolution path.
        assert_url_is_safe("https://www.google.com/")

    def test_http_allowed(self):
        assert_url_is_safe("http://www.google.com/")

    def test_javascript_scheme_rejected(self):
        with pytest.raises(UnsafeUrlError, match="Only http"):
            assert_url_is_safe("javascript:alert(1)")

    def test_file_scheme_rejected(self):
        with pytest.raises(UnsafeUrlError, match="Only http"):
            assert_url_is_safe("file:///etc/passwd")

    def test_ftp_scheme_rejected(self):
        with pytest.raises(UnsafeUrlError, match="Only http"):
            assert_url_is_safe("ftp://example.com/")

    def test_missing_host_rejected(self):
        with pytest.raises(UnsafeUrlError, match="no host"):
            assert_url_is_safe("http:///path")


class TestLiteralIpRejection:
    """Literal IPs in the URL bypass DNS — must be caught without I/O."""

    def test_loopback_ipv4_rejected(self):
        with pytest.raises(UnsafeUrlError, match="non-public"):
            assert_url_is_safe("http://127.0.0.1/")

    def test_loopback_ipv6_rejected(self):
        with pytest.raises(UnsafeUrlError, match="non-public"):
            assert_url_is_safe("http://[::1]/")

    def test_private_rfc1918_rejected(self):
        for ip in ("10.0.0.1", "172.16.0.1", "192.168.1.1"):
            with pytest.raises(UnsafeUrlError, match="non-public"):
                assert_url_is_safe(f"http://{ip}/")

    def test_link_local_rejected(self):
        # 169.254.169.254 is the AWS / GCP metadata endpoint — the worst
        # offender. Also general link-local 169.254.*.
        with pytest.raises(UnsafeUrlError, match="non-public"):
            assert_url_is_safe("http://169.254.169.254/latest/meta-data/")

    def test_multicast_rejected(self):
        with pytest.raises(UnsafeUrlError, match="non-public"):
            assert_url_is_safe("http://224.0.0.1/")

    def test_unspecified_rejected(self):
        with pytest.raises(UnsafeUrlError, match="non-public"):
            assert_url_is_safe("http://0.0.0.0/")

    def test_public_ipv4_allowed(self):
        # 8.8.8.8 is Google DNS — always public.
        assert_url_is_safe("http://8.8.8.8/")


class TestDnsResolution:
    """Hostnames that resolve to private IPs must be rejected."""

    def test_hostname_resolving_to_loopback_rejected(self):
        # `localhost` typically resolves to 127.0.0.1.
        with pytest.raises(UnsafeUrlError, match="non-public"):
            assert_url_is_safe("http://localhost/admin")

    def test_dns_failure_rejected(self):
        # Non-existent TLD → gaierror → wrapped as UnsafeUrlError.
        with pytest.raises(UnsafeUrlError, match="DNS"):
            assert_url_is_safe("http://this-domain-does-not-exist.invalid/")

    def test_mocked_private_resolution_rejected(self):
        # A hostname that on this network would resolve to a private IP
        # (think of an internal service exposed via DNS like
        # `database.internal.company.com` → 10.0.0.5). Mock getaddrinfo
        # to simulate that without depending on a real such name.
        fake_infos = [(0, 0, 0, "", ("10.0.0.5", 0))]
        with patch("app.core.url_safety.socket.getaddrinfo", return_value=fake_infos):
            with pytest.raises(UnsafeUrlError, match="non-public"):
                assert_url_is_safe("http://internal.example.com/")
