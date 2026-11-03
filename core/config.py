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
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
AVAILABLE_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-pro"
]

# Database Path
DB_PATH = Path(__file__).resolve().parent.parent / "klein_research.db"

# Web Scraping Configuration
DEFAULT_TIMEOUT = 12
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
MAX_SEARCH_RESULTS_PER_QUERY = 4
MAX_TOTAL_SOURCES = 8
MAX_EXTRACT_CHARS = 4500

def get_gemini_api_key(runtime_key: str = None) -> str:
    """Retrieve Gemini API key with priority: runtime parameter > .env > empty string"""
    if runtime_key and runtime_key.strip():
        return runtime_key.strip()
    return os.getenv("GEMINI_API_KEY", "").strip()

def get_tavily_api_key(runtime_key: str = None) -> str:
    """Retrieve Tavily API key with priority: runtime parameter > .env > empty string"""
    if runtime_key and runtime_key.strip():
        return runtime_key.strip()
    return os.getenv("TAVILY_API_KEY", "").strip()
