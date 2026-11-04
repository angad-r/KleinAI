"""
ResearchMate AI - Gemini API Key Validation and Diagnostics Test Suite
Tests credential inspection, placeholder cleaning, mask security, fast auth failure,
and connection diagnostic probes.
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Ensure root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config import clean_api_key, mask_api_key, get_gemini_api_key
from core.gemini_client import (
    GeminiClient,
    GeminiAuthError,
    GeminiRateLimitError,
    GeminiNetworkError,
    GeminiModelError,
    classify_error
)
from google.genai import errors


# 1. API KEY SANITIZATION & MASKING SECURITY
def test_clean_api_key_placeholders():
    """Verify placeholder values from docs and UI are sanitized to empty."""
    assert clean_api_key("your_gemini_api_key_here") == ""
    assert clean_api_key("your_key_here") == ""
    assert clean_api_key("") == ""
    assert clean_api_key(None) == ""


def test_clean_api_key_quotes_and_whitespace():
    """Verify surrounding quotes and whitespace are trimmed."""
    assert clean_api_key(' "MOCK_VALID_KEY_123" ') == "MOCK_VALID_KEY_123"
    assert clean_api_key(" 'MOCK_VALID_KEY_456' ") == "MOCK_VALID_KEY_456"


def test_mask_api_key_security():
    """Verify raw API keys are never exposed in diagnostics or logs (Zero-Leakage Policy)."""
    raw = "TEST_DUMMY_SECRET_KEY_1234567890_ABCD"
    masked = mask_api_key(raw)
    assert raw not in masked
    assert masked == "Configured"
    assert mask_api_key("") == "Not Configured"
    assert mask_api_key(None) == "Not Configured"


# 2. ERROR CLASSIFICATION
def test_classify_auth_error():
    """Verify 400 INVALID_ARGUMENT and API_KEY_INVALID are categorized as AUTH_ERROR."""
    mock_err = errors.ClientError(
        code=400,
        response_json={"error": {"message": "API key not valid. Please pass a valid API key."}}
    )
    cat, msg = classify_error(mock_err)
    assert cat == "AUTH_ERROR"
    assert "Google Gemini API Key is invalid" in msg


def test_classify_rate_limit_error():
    """Verify 429 RESOURCE_EXHAUSTED is categorized as RATE_LIMIT."""
    mock_err = errors.ClientError(
        code=429,
        response_json={"error": {"message": "Resource has been exhausted (e.g. check quota)."}}
    )
    cat, msg = classify_error(mock_err)
    assert cat == "RATE_LIMIT"
    assert "rate limit or quota" in msg.lower()


def test_classify_network_error():
    """Verify network connection and socket exceptions are categorized as NETWORK_ERROR."""
    net_err = ConnectionError("Failed to establish a new connection: [Errno 11001] getaddrinfo failed")
    cat, msg = classify_error(net_err)
    assert cat == "NETWORK_ERROR"
    assert "network connection" in msg.lower()


# 3. CONNECTION TEST PROBE
def test_test_connection_missing_key():
    """Verify test_connection returns MISSING_KEY status when key is empty."""
    res = GeminiClient.test_connection(api_key="")
    assert res["success"] is False
    assert res["category"] == "MISSING_KEY"
    assert "missing" in res["message"].lower()


def test_test_connection_invalid_key():
    """Verify test_connection identifies invalid credentials via Google API ClientError."""
    res = GeminiClient.test_connection(api_key="mock_invalid_dummy_key_0000000000")
    assert res["success"] is False
    assert res["category"] == "AUTH_ERROR"
    assert "invalid" in res["message"].lower()


# 4. FAST AUTH FAILURE WITHOUT SLOW RETRIES
def test_fast_auth_failure_no_retries():
    """Verify that GeminiClient raises GeminiAuthError on attempt 1 without slow retries."""
    client = GeminiClient(api_key="mock_invalid_dummy_key_0000000000")
    with pytest.raises(GeminiAuthError) as exc_info:
        client._call_model("Hello, test!")
    assert "invalid or unauthorized" in str(exc_info.value).lower()
