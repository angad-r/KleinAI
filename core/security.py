"""
Klein AI - Cryptographic Security & Server-Side Session Manager (Version 2.0)
Provides authenticated symmetric encryption for user API credentials using Fernet (AES-128-CBC + HMAC-SHA256).
Enforces zero client-side secret exposure:
- Keys are never stored in browser localStorage.
- Keys are never reflected in API response payloads or logs.
- Keys are transmitted to server, encrypted into an HttpOnly cookie, and decrypted only on the server.
"""
import os
import json
import base64
import hashlib
import time
from typing import Dict, Any, Optional, Tuple
from http import cookies

from cryptography.fernet import Fernet, InvalidToken

# Master secret key derived from environment
_RAW_SECRET = os.getenv("SECRET_KEY", "klein-ai-default-master-secret-key-v2-prod-2026").strip()
# Derive deterministic 32-byte key for Fernet
_KEY_HASH = hashlib.sha256(_RAW_SECRET.encode("utf-8")).digest()
_FERNET_KEY = base64.urlsafe_b64encode(_KEY_HASH)
_CIPHER = Fernet(_FERNET_KEY)

COOKIE_NAME = "klein_session"
DEFAULT_SESSION_TTL_SECONDS = 7 * 24 * 3600  # 7 days


def is_custom_secret_configured() -> bool:
    """Returns True if operator configured a custom non-default SECRET_KEY."""
    val = os.getenv("SECRET_KEY", "").strip()
    return bool(val and val != "klein-ai-default-master-secret-key-v2-prod-2026")


def encrypt_user_credentials(
    gemini_key: str = "",
    tavily_key: str = "",
    user_id: str = "anonymous",
    ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS
) -> str:
    """
    Encrypts user API credentials into a tamper-evident, authenticated ciphertext token.
    """
    payload = {
        "gk": gemini_key.strip() if gemini_key else "",
        "tk": tavily_key.strip() if tavily_key else "",
        "uid": user_id,
        "exp": int(time.time()) + ttl_seconds,
        "iat": int(time.time())
    }
    raw_json = json.dumps(payload, separators=(',', ':')).encode("utf-8")
    return _CIPHER.encrypt(raw_json).decode("utf-8")


def decrypt_user_credentials(token: str) -> Dict[str, Any]:
    """
    Decrypts session token and verifies authenticity and expiration.
    Returns dictionary with gemini_key, tavily_key, user_id, and valid flag.
    Never throws unhandled exceptions.
    """
    if not token or not isinstance(token, str):
        return {"gemini_key": "", "tavily_key": "", "user_id": "anonymous", "valid": False}
    try:
        raw_bytes = _CIPHER.decrypt(token.strip().encode("utf-8"), ttl=None)
        payload = json.loads(raw_bytes.decode("utf-8"))
        # Check expiration
        now = int(time.time())
        if payload.get("exp", 0) < now:
            return {"gemini_key": "", "tavily_key": "", "user_id": "anonymous", "valid": False, "expired": True}
        return {
            "gemini_key": payload.get("gk", ""),
            "tavily_key": payload.get("tk", ""),
            "user_id": payload.get("uid", "anonymous"),
            "valid": True,
            "expired": False
        }
    except (InvalidToken, Exception):
        return {"gemini_key": "", "tavily_key": "", "user_id": "anonymous", "valid": False}


def extract_credentials_from_environ(environ: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts session credentials from WSGI environ HTTP_COOKIE or HTTP_X_SESSION_TOKEN header.
    """
    token = ""
    # 1. Check HTTP Cookie
    cookie_header = environ.get("HTTP_COOKIE", "")
    if cookie_header:
        try:
            c = cookies.SimpleCookie()
            c.load(cookie_header)
            if COOKIE_NAME in c:
                token = c[COOKIE_NAME].value
        except Exception:
            pass

    # 2. Check Authorization or X-Session-Token header
    if not token:
        token = environ.get("HTTP_X_SESSION_TOKEN", "")

    return decrypt_user_credentials(token)


def build_session_cookie(
    token: str,
    max_age: int = DEFAULT_SESSION_TTL_SECONDS,
    secure: bool = True,
    clear: bool = False
) -> str:
    """
    Builds a secure Set-Cookie header string for WSGI response headers.
    Enforces HttpOnly and SameSite=Lax.
    """
    if clear:
        return f"{COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax" + ("; Secure" if secure else "")
    cookie_str = f"{COOKIE_NAME}={token}; Path=/; Max-Age={max_age}; HttpOnly; SameSite=Lax"
    if secure:
        cookie_str += "; Secure"
    return cookie_str
