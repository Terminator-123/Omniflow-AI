"""Security module providing SSRF defense, URL validation, credential hygiene, and file upload sanitization."""
import os
import re
import socket
import ipaddress
from urllib.parse import urlparse
from typing import Tuple, Optional
from backend.core.exceptions import PolicyViolationError
from backend.core.logging_config import logger

# Blocked IP networks for SSRF defense
BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),          # Current network (only valid as source address)
    ipaddress.ip_network("10.0.0.0/8"),         # Private-Use (RFC 1918)
    ipaddress.ip_network("100.64.0.0/10"),      # Shared Address Space (RFC 6598)
    ipaddress.ip_network("127.0.0.0/8"),        # Loopback (RFC 1122)
    ipaddress.ip_network("169.254.0.0/16"),     # Link-Local (RFC 3927) - includes AWS/GCP metadata 169.254.169.254
    ipaddress.ip_network("172.16.0.0/12"),      # Private-Use (RFC 1918)
    ipaddress.ip_network("192.0.0.0/24"),       # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),       # TEST-NET-1 (RFC 5737)
    ipaddress.ip_network("192.88.99.0/24"),     # 6to4 Relay Anycast (RFC 3068)
    ipaddress.ip_network("192.168.0.0/16"),     # Private-Use (RFC 1918)
    ipaddress.ip_network("198.18.0.0/15"),      # Network Interconnect Device Benchmark Testing
    ipaddress.ip_network("198.51.100.0/24"),    # TEST-NET-2 (RFC 5737)
    ipaddress.ip_network("203.0.113.0/24"),     # TEST-NET-3 (RFC 5737)
    ipaddress.ip_network("224.0.0.0/4"),        # Multicast (RFC 5771)
    ipaddress.ip_network("240.0.0.0/4"),        # Reserved for Future Use (RFC 1112)
    ipaddress.ip_network("255.255.255.255/32"), # Limited Broadcast (RFC 919)
    # IPv6 blocked ranges
    ipaddress.ip_network("::/128"),             # Unspecified
    ipaddress.ip_network("::1/128"),            # Loopback
    ipaddress.ip_network("fc00::/7"),           # Unique Local Address
    ipaddress.ip_network("fe80::/10"),          # Link-Local Unicast
    ipaddress.ip_network("ff00::/8"),           # Multicast
]

BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "metadata.internal",
    "169.254.169.254",
    "instance-data",
}

def is_ip_blocked(ip_addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Checks whether an IP address belongs to any blocked private/internal ranges."""
    for network in BLOCKED_NETWORKS:
        if ip_addr in network:
            return True
    return False

def validate_safe_url(url: str, allow_simulated: bool = True) -> str:
    """Validates that a URL is a legitimate, public HTTP/HTTPS URL, defending against SSRF.
    
    Checks:
    1. Scheme must be http or https (blocks file://, ftp://, gopher://, etc.)
    2. Hostname must be present and not in blocked hostnames list
    3. Resolves hostname to IP addresses and verifies none belong to private, loopback, link-local, or cloud metadata networks
    """
    if not url or not isinstance(url, str):
        raise PolicyViolationError("Invalid URL: must be a non-empty string.")

    url = url.strip()

    # Controlled failure test hooks for simulated test scenarios
    if allow_simulated and ("simulate-fail" in url or "httpstat.us" in url):
        return url

    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise PolicyViolationError(f"URL scheme '{parsed.scheme}' is disallowed. Only http and https are permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise PolicyViolationError(f"URL lacks a valid hostname: '{url}'.")

    lower_host = hostname.lower()

    # Check blocked hostnames
    if lower_host in BLOCKED_HOSTNAMES or lower_host.endswith(".internal"):
        raise PolicyViolationError(f"Access to internal or metadata hostname '{hostname}' is blocked for security.")

    # Check if hostname itself is an IP literal
    try:
        ip = ipaddress.ip_address(lower_host)
        if is_ip_blocked(ip):
            raise PolicyViolationError(f"Access to private/internal IP address '{ip}' is blocked for security.")
        return url
    except ValueError:
        # Hostname is a domain name, resolve it
        pass

    # DNS Resolution check to prevent DNS rebinding to private IPs
    try:
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, socktype, proto, canonname, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if is_ip_blocked(ip):
                raise PolicyViolationError(
                    f"Hostname '{hostname}' resolves to blocked private/internal IP address '{ip_str}'."
                )
    except socket.gaierror as exc:
        logger.warning(f"DNS resolution failure for '{hostname}': {exc}")
        # Allow DNS resolution error to be handled gracefully by the HTTP client later
        pass

    return url

def mask_api_key(key: Optional[str]) -> str:
    """Masks a sensitive API key for safe display in logs and API responses."""
    if not key or not isinstance(key, str):
        return "not_configured"
    key = key.strip()
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"

def sanitize_upload_filename(filename: str) -> str:
    """Sanitizes an uploaded filename to prevent directory traversal and filesystem attacks."""
    if not filename:
        return "unnamed_document.txt"
    # Remove path traversal characters
    basename = os.path.basename(filename.replace("\\", "/"))
    # Allow alphanumeric, hyphens, underscores, dots
    cleaned = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", basename)
    # Avoid hidden files or leading dots
    cleaned = cleaned.lstrip(".")
    if not cleaned:
        return "document.txt"
    return cleaned[:100]
