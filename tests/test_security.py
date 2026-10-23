"""Unit tests for security hardening: SSRF defense, private network blocking, and credential masking."""
import pytest
from backend.core.security import validate_safe_url, mask_api_key, sanitize_upload_filename
from backend.core.exceptions import PolicyViolationError
from backend.services.gemini_service import gemini_service

def test_validate_safe_url_public_domains():
    """Verifies that public HTTPS domains pass SSRF validation."""
    assert validate_safe_url("https://www.ibm.com/think/topics/ai-agents") == "https://www.ibm.com/think/topics/ai-agents"
    assert validate_safe_url("https://cloud.google.com/discover/what-are-ai-agents") == "https://cloud.google.com/discover/what-are-ai-agents"
    assert validate_safe_url("https://www.nist.gov/itl/ai-risk-management-framework") == "https://www.nist.gov/itl/ai-risk-management-framework"

def test_validate_safe_url_blocks_schemes():
    """Verifies that non-HTTP/HTTPS schemes are strictly rejected."""
    with pytest.raises(PolicyViolationError, match="disallowed"):
        validate_safe_url("file:///etc/passwd")

    with pytest.raises(PolicyViolationError, match="disallowed"):
        validate_safe_url("ftp://internal.server/data")

    with pytest.raises(PolicyViolationError, match="disallowed"):
        validate_safe_url("gopher://evil.com/")

def test_validate_safe_url_blocks_loopback_and_metadata():
    """Verifies that localhost, 127.0.0.1, and cloud metadata (169.254.169.254) are rejected."""
    with pytest.raises(PolicyViolationError, match="blocked for security"):
        validate_safe_url("http://127.0.0.1:8000/internal")

    with pytest.raises(PolicyViolationError, match="blocked for security"):
        validate_safe_url("http://localhost:8501")

    with pytest.raises(PolicyViolationError, match="blocked for security"):
        validate_safe_url("http://169.254.169.254/latest/meta-data/")

    with pytest.raises(PolicyViolationError, match="blocked for security"):
        validate_safe_url("http://metadata.google.internal/computeMetadata/v1/")

def test_validate_safe_url_blocks_private_networks():
    """Verifies that RFC 1918 private IPv4 addresses are rejected."""
    with pytest.raises(PolicyViolationError, match="blocked for security"):
        validate_safe_url("http://10.0.0.1/admin")

    with pytest.raises(PolicyViolationError, match="blocked for security"):
        validate_safe_url("http://192.168.1.1/router")

    with pytest.raises(PolicyViolationError, match="blocked for security"):
        validate_safe_url("http://172.16.0.5:8080/")

def test_mask_api_key():
    """Verifies that API keys are masked safely."""
    assert mask_api_key(None) == "not_configured"
    assert mask_api_key("") == "not_configured"
    assert mask_api_key("short") == "****"
    assert mask_api_key("AIzaSyD-1234567890abcdef") == "AIza...cdef"

def test_sanitize_upload_filename():
    """Verifies path traversal characters are stripped."""
    assert sanitize_upload_filename("../../etc/passwd") == "passwd"
    assert sanitize_upload_filename("..\\..\\windows\\system32\\cmd.exe") == "cmd.exe"
    assert sanitize_upload_filename("valid_research_doc.pdf") == "valid_research_doc.pdf"

def test_set_api_key_sanitization():
    """Verifies that set_api_key rejects newline injection or invalid control characters."""
    assert gemini_service.set_api_key("AIza\nINJECTION") is False
    assert gemini_service.set_api_key("A" * 300) is False
