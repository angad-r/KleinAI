"""
Klein AI - Configuration and Environment Management
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from workspace directory
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

APP_NAME = "Klein AI"
APP_TAGLINE = "One Topic. Complete Research. Powered by AI."
APP_VERSION = "1.0.0"

# Default Model Selection
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
AVAILABLE_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-2.5-flash",
    "gemini-2.5-pro"
]

# Database Path
DB_PATH = Path(__file__).resolve().parent.parent / "klein_research.db"

# Web Scraping Configuration
DEFAULT_TIMEOUT = 12
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
MAX_SEARCH_RESULTS_PER_QUERY = 4
MAX_TOTAL_SOURCES = 8
MAX_EXTRACT_CHARS = 4500

KNOWN_PLACEHOLDERS = {
    "aizasy...", "your_gemini_api_key_here", "your_key_here",
    "tvly-...", "your_tavily_api_key_here"
}

def clean_api_key(raw_key: str = None) -> str:
    """Sanitize API keys by stripping whitespace, wrapping quotes, and placeholder values."""
    if not raw_key:
        return ""
    cleaned = str(raw_key).strip()
    # Strip quotes if wrapped
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
        cleaned = cleaned[1:-1].strip()
    if cleaned.lower() in KNOWN_PLACEHOLDERS:
        return ""
    return cleaned

def mask_api_key(key: str = None) -> str:
    """Safely mask API key for telemetry and diagnostic displays without exposing secrets."""
    cleaned = clean_api_key(key)
    if not cleaned:
        return "Not Configured"
    if len(cleaned) <= 8:
        return "Configured (Invalid Format / Too Short)"
    return f"{cleaned[:6]}...{cleaned[-4:]} ({len(cleaned)} chars)"

def get_gemini_api_key(runtime_key: str = None) -> str:
    """Retrieve Gemini API key with priority: explicit runtime parameter > .env (GEMINI_API_KEY or GOOGLE_API_KEY) > empty string"""
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
    """Retrieve Tavily API key with priority: explicit runtime parameter > .env > empty string"""
    if runtime_key is not None:
        return clean_api_key(runtime_key)
    return clean_api_key(os.getenv("TAVILY_API_KEY"))
