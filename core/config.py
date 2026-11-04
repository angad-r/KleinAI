"""
Klein AI - Configuration and Environment Management (Version 2.0)
Centralized source of truth for models, credentials, network constraints, and database settings.
"""
import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Load .env from workspace directory
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

APP_NAME = "Klein AI"
APP_TAGLINE = "Autonomous Academic Research & Literature Synthesis Platform"
APP_VERSION = "2.0.0"

# ==============================================================================
# MODEL CONFIGURATION (SINGLE SOURCE OF TRUTH)
# ==============================================================================
# Officially supported Google Gemini model identifiers
SUPPORTED_MODELS: List[str] = [
    "gemini-1.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-pro",
    "gemini-2.5-flash"
]

DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
if DEFAULT_GEMINI_MODEL not in SUPPORTED_MODELS:
    DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"

AVAILABLE_MODELS = list(SUPPORTED_MODELS)

# ==============================================================================
# DATABASE CONFIGURATION
# ==============================================================================
# Supports PostgreSQL (via DATABASE_URL in production) or SQLite (for local testing)
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_PATH = Path(__file__).resolve().parent.parent / "klein_research.db"

# ==============================================================================
# REDIS & BACKGROUND JOB WORKER CONFIGURATION
# ==============================================================================
REDIS_URL = os.getenv("REDIS_URL", "").strip()
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "4"))
JOB_TIMEOUT_SECONDS = int(os.getenv("JOB_TIMEOUT_SECONDS", "300"))

# ==============================================================================
# WEB SCRAPING & NETWORK SECURITY CONSTRAINTS
# ==============================================================================
DEFAULT_TIMEOUT = int(os.getenv("SCRAPE_TIMEOUT", "12"))
USER_AGENT = "KleinAI-AcademicResearcher/2.0 (+https://github.com/angad-r/KleinAI)"
MAX_SEARCH_RESULTS_PER_QUERY = 5
MAX_TOTAL_SOURCES = 10
MAX_EXTRACT_CHARS = 8000
MAX_SCRAPE_BYTES = 2 * 1024 * 1024  # 2 MB stream limit
MAX_REDIRECTS = 5
ALLOWED_CONTENT_TYPES = {"text/html", "application/xhtml+xml", "application/xml", "text/plain"}

# Request body size limit for WSGI endpoints
MAX_REQUEST_BODY_BYTES = 64 * 1024  # 64 KB
MAX_REQUEST_BODY_SIZE = MAX_REQUEST_BODY_BYTES

# CORS Allowed Origins
DEFAULT_ALLOWED_ORIGINS = "https://kleinai.vercel.app,http://localhost:8501,http://localhost:3000,http://127.0.0.1:8501"
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS).split(",")
    if o.strip()
]

# ==============================================================================
# API CREDENTIAL MANAGEMENT & SANITIZATION
# ==============================================================================
KNOWN_PLACEHOLDERS = {
    "your_gemini_api_key_here", "your_key_here",
    "your_tavily_api_key_here", "your_api_key_here",
    "placeholder_key", "sample_key", "<your_api_key>"
}

def clean_api_key(raw_key: str = None) -> str:
    """Sanitize API keys by stripping whitespace, wrapping quotes, and placeholder values."""
    if not raw_key:
        return ""
    cleaned = str(raw_key).strip()
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
        cleaned = cleaned[1:-1].strip()
    if cleaned.lower() in KNOWN_PLACEHOLDERS:
        return ""
    return cleaned

def mask_api_key(key: str = None) -> str:
    """
    Safely reports API key status without leaking prefixes, suffixes, lengths, or secrets.
    Conforms strictly to minimal disclosure security requirements.
    """
    cleaned = clean_api_key(key)
    return "Configured" if bool(cleaned) else "Not Configured"

def get_gemini_api_key(runtime_key: str = None) -> str:
    """Retrieve Gemini API key with priority: runtime parameter > .env (GEMINI_API_KEY) > .env (GOOGLE_API_KEY)"""
    if runtime_key is not None:
        return clean_api_key(runtime_key)
    
    env_gemini = clean_api_key(os.getenv("GEMINI_API_KEY"))
    if env_gemini:
        return env_gemini
        
    env_google = clean_api_key(os.getenv("GOOGLE_API_KEY"))
    if env_google:
        return env_google
        
    return ""

def get_tavily_api_key(runtime_key: str = None) -> str:
    """Retrieve Tavily API key with priority: runtime parameter > .env (TAVILY_API_KEY)"""
    if runtime_key is not None:
        return clean_api_key(runtime_key)
    return clean_api_key(os.getenv("TAVILY_API_KEY"))
