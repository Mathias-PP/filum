"""SSRF protection for user-supplied URLs.

The backend hits arbitrary URLs in two places:
  1. `/api/v1/sources/extract` — no-auth metadata extraction (OG tags,
     JSON-LD, Crossref). An attacker could supply `http://127.0.0.1:8000/health`
     or `http://169.254.169.254/latest/meta-data/` (AWS metadata) to probe
     the internal network or leak cloud secrets.
  2. `WaybackService.archive_url` — same surface for any URL persisted to
     a `Source.url` field via authenticated endpoints.

The check resolves the hostname and refuses any request whose final IP is
loopback, link-local, private, multicast, reserved, or unspecified. Both
IPv4 and IPv6 covered via `ipaddress.ip_address`.

Caveat: this is a single-resolution check. A "DNS rebinding" attacker who
controls the DNS could return a public IP to the validator and a private
IP to the subsequent `httpx.get`. Mitigations (e.g. resolving once and
passing the IP directly) are over-engineering for the current threat
model (single FastAPI worker, no privileged data on private RFC1918 IPs
on Railway). Document the limitation in PITFALLS if the threat model
ever changes.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeUrlError(ValueError):
    """The URL targets a host that must not be reachable from the backend."""


def _ip_is_safe(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True iff the IP is a public, routable address suitable for outbound
    requests. Rejects loopback, link-local, private, multicast, reserved,
    and unspecified (0.0.0.0 / ::) addresses."""
    return not (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_private
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def assert_url_is_safe(url: str) -> None:
    """Raise ``UnsafeUrlError`` if ``url`` targets a non-public host.

    Validates:
      - scheme is http or https
      - host is set
      - host resolves to at least one IP and ALL resolved IPs are public

    No network I/O beyond ``getaddrinfo`` on the hostname.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrlError(f"Only http(s) URLs are allowed (got {parsed.scheme!r})")
    host = parsed.hostname
    if not host:
        raise UnsafeUrlError("URL has no host")

    # Reject literal IPs that resolve as private without DNS lookup.
    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None
    if literal_ip is not None:
        if not _ip_is_safe(literal_ip):
            raise UnsafeUrlError(f"URL host is a non-public address ({host})")
        return

    # Resolve and check every returned address. `getaddrinfo` returns both
    # IPv4 and IPv6 results when available; we want all of them safe.
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise UnsafeUrlError(f"DNS resolution failed for {host}: {e}") from e
    if not infos:
        raise UnsafeUrlError(f"DNS returned no addresses for {host}")

    for info in infos:
        sockaddr = info[4]
        raw_ip = sockaddr[0]
        try:
            ip = ipaddress.ip_address(raw_ip)
        except ValueError:
            # getaddrinfo should never produce an invalid address, but be
            # defensive: treat anything we can't parse as unsafe.
            raise UnsafeUrlError(f"Unparseable IP from DNS for {host}: {raw_ip}") from None
        if not _ip_is_safe(ip):
            raise UnsafeUrlError(
                f"Host {host} resolves to a non-public address ({ip}). "
                "Loopback, private, link-local, and reserved ranges are blocked."
            )
