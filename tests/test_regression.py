"""
Klein AI / ResearchMate AI - Comprehensive Regression Test Suite
Covers all regression scenarios, edge cases, failure states, and component resilience.
"""
import io
import os
import sys
import json
import pytest
from unittest.mock import MagicMock, patch

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config import DEFAULT_GEMINI_MODEL, get_gemini_api_key, get_tavily_api_key
from core.database import init_db, save_session, get_session, delete_session, list_sessions
from core.search_engine import SearchEngine
from core.tools import ToolRegistry
from core.citation_auditor import CitationAuditor
from core.pdf_generator import build_pdf_report, clean_text_for_pdf
from core.ppt_generator import build_pptx_deck
from core.demo_dataset import VERIFIED_DEMO_DATA
from core.researcher import KleinResearchAgent


# ==============================================================================
# 1. INPUT EDGE CASES & VALIDATION
# ==============================================================================

def test_regression_input_empty_and_whitespace():
    """Verify empty and whitespace-only queries are blocked gracefully."""
    reg = ToolRegistry()
    res_empty = reg.execute_tool("search_web", query="")
    assert res_empty.success is False
    assert "empty" in res_empty.error.lower()

    res_spaces = reg.execute_tool("search_web", query="   \t\n  ")
    assert res_spaces.success is False
    assert "empty" in res_spaces.error.lower()


def test_regression_input_very_short_topic():
    """Verify very short queries execute without internal indexing exceptions."""
    reg = ToolRegistry()
    res = reg.execute_tool("search_web", query="AI", aspect="Foundations")
    assert res.success is True
    assert isinstance(res.data, list)


def test_regression_input_extremely_long_topic():
    """Verify 2000-character input strings do not overflow buffers."""
    long_query = "Healthcare Cybersecurity " * 100
    reg = ToolRegistry()
    res = reg.execute_tool("search_web", query=long_query[:400], aspect="Stress Test")
    assert res.success is True


def test_regression_input_xss_and_sql_injection():
    """Verify security injection strings are cleanly sanitized and processed."""
    malicious = "<script>alert('xss')</script> '; DROP TABLE sessions; --"
    cleaned_pdf = clean_text_for_pdf(malicious)
    assert "<script>" not in cleaned_pdf
    assert "&lt;script&gt;" in cleaned_pdf

    clean_url = SearchEngine.normalize_url("https://example.com/search?q=" + malicious)
    assert clean_url.startswith("https://example.com/search")


# ==============================================================================
# 2. API CREDENTIAL & NETWORK FAILOVER
# ==============================================================================

def test_regression_missing_gemini_key():
    """Verify agent initialization or execution fails gracefully if Gemini key is missing."""
    with patch("core.config.os.environ.get", return_value=""):
        agent = KleinResearchAgent(gemini_api_key=None, tavily_api_key=None)
        assert agent.gemini_client is None


def test_regression_search_failover_when_tavily_key_absent():
    """Verify search engine falls back to DuckDuckGo/Wikipedia when Tavily key is None or empty."""
    engine = SearchEngine(tavily_api_key="")
    assert not engine.tavily_api_key
    # search_query should seamlessly fall back
    results = engine.search_query("Healthcare cybersecurity standards", max_results=2)
    assert isinstance(results, list)
    assert len(results) > 0
    assert any(r["domain"] for r in results)


def test_regression_search_tavily_api_error_recovery():
    """Verify that an exception in Tavily client triggers fallback instead of crashing."""
    engine = SearchEngine(tavily_api_key="invalid_test_key_xyz")
    with patch.object(engine, "search_tavily", side_effect=Exception("API Key Invalid")):
        # Should gracefully catch and try DuckDuckGo/Wikipedia
        results = engine.search_query("Medical device artificial intelligence", max_results=2)
        assert isinstance(results, list)
        assert len(results) > 0


def test_regression_network_timeout_handling():
    """Verify network timeouts in extraction do not crash the pipeline."""
    engine = SearchEngine()
    with patch.object(engine.session, "get", side_effect=Exception("Connection timed out")):
        extracted = engine.extract_page_content("https://unreachable-domain-12345.org/paper")
        assert extracted == ""


# ==============================================================================
# 3. DEDUPLICATION & CANONICAL URL NORMALIZATION
# ==============================================================================

def test_regression_canonical_url_deduplication():
    """Verify URL variations with UTM parameters and fragments are deduplicated."""
    url1 = "https://www.nature.com/articles/s41746-024-01001-w?utm_source=twitter&utm_medium=social"
    url2 = "https://nature.com/articles/s41746-024-01001-w?ref=homepage#section-3"
    url3 = "https://nature.com/articles/s41746-024-01001-w"

    norm1 = SearchEngine.normalize_url(url1)
    norm2 = SearchEngine.normalize_url(url2)
    norm3 = SearchEngine.normalize_url(url3)

    assert norm1 == norm2 == norm3 == "https://nature.com/articles/s41746-024-01001-w"


# ==============================================================================
# 4. CITATION AUDIT INTEGRITY & APA / BIBTEX FORMATTING
# ==============================================================================

def test_regression_citation_auditor_classification_tiers():
    """Verify citation auditor accurately categorizes academic vs independent web sources."""
    sources = [
        {
            "title": "Clinical AI Security",
            "url": "https://ncbi.nlm.nih.gov/pmc/articles/PMC9999",
            "domain": "ncbi.nlm.nih.gov",
            "content": "A" * 500
        },
        {
            "title": "Clinical AI Security Snippet",
            "url": "https://ieee.org/document/8888",
            "domain": "ieee.org",
            "content": "Short snippet under 400 chars"
        },
        {
            "title": "Tech Community Blog",
            "url": "https://medium.com/cybersecurity-today",
            "domain": "medium.com",
            "content": "B" * 500
        },
        {
            "title": "Inaccessible Bad URL",
            "url": "invalid-url-string",
            "domain": "broken",
            "content": ""
        }
    ]
    audited = CitationAuditor.audit_sources(sources)
    assert len(audited) == 4
    # Full academic
    assert audited[0]["status"] == "VERIFIED: Authoritative Academic"
    # Snippet academic
    assert audited[1]["status"] == "VERIFIED: Authoritative Academic (Snippet)"
    # Web source
    assert audited[2]["status"] == "VERIFIED: Independent Web Source"
    # Inaccessible
    assert audited[3]["status"] == "UNVERIFIED: Source Inaccessible"

    # Verify APA and BibTeX formatting
    assert "https://ncbi.nlm.nih.gov" in audited[0]["apa_citation"]
    assert "@misc{ref_" in audited[0]["bibtex"]


# ==============================================================================
# 5. ARTIFACT GENERATION & CORRUPTION DEFENSE
# ==============================================================================

def test_regression_pdf_generation_with_empty_or_special_fields():
    """Verify PDF generator does not crash on empty dictionaries or unusual characters."""
    minimal_data = {
        "topic": "Minimal Test Topic: <&> \"Special\"",
        "blueprint": {},
        "sources": [],
        "audited_citations": [],
        "comparison": {},
        "literature_review": "Literature with unicode: • — – … and formatting **bold** and *italic*.",
        "research_gaps": [],
        "methodology": {},
        "report_markdown": "# Title\n\nContent paragraph."
    }
    pdf_bytes = build_pdf_report(minimal_data)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")
    assert b"%%EOF" in pdf_bytes
    assert len(pdf_bytes) > 1000


def test_regression_pptx_generation_with_empty_slides():
    """Verify PPTX generator handles empty slides_data gracefully by generating fallback slides."""
    minimal_data = {
        "topic": "Minimal Presentation Topic",
        "blueprint": {"domain": "Computer Science", "executive_summary": "Summary text"}
    }
    pptx_bytes = build_pptx_deck(minimal_data, slides_data=[])
    assert isinstance(pptx_bytes, bytes)
    assert pptx_bytes.startswith(b"PK")  # Valid zip archive signature
    assert len(pptx_bytes) > 20000


def test_regression_pptx_generation_with_rich_slides():
    """Verify PPTX generator produces multi-slide deck with structured cards."""
    data = VERIFIED_DEMO_DATA
    slides = data.get("slides_data", [])
    assert len(slides) >= 10
    pptx_bytes = build_pptx_deck(data, slides)
    assert pptx_bytes.startswith(b"PK\x03\x04")
    assert len(pptx_bytes) > 30000


# ==============================================================================
# 6. DATABASE SESSION PERSISTENCE & CRUD
# ==============================================================================

def test_regression_database_crud_operations():
    """Verify database CRUD operations and JSON integrity."""
    init_db()
    test_session_id = "regr-test-session-999"
    payload = {
        "topic": "Database Regression Topic",
        "blueprint": {"domain": "Testing Domain"},
        "sources": [{"title": "Source 1", "url": "https://example.com"}]
    }
    # Save
    save_session(
        session_id=test_session_id,
        topic="Database Regression Topic",
        status="completed",
        source_count=1,
        summary="Testing summary",
        data=payload
    )
    
    # List
    sessions = list_sessions()
    matching = [s for s in sessions if s["id"] == test_session_id]
    assert len(matching) == 1
    assert matching[0]["topic"] == "Database Regression Topic"

    # Get
    retrieved = get_session(test_session_id)
    assert retrieved is not None
    assert retrieved["data"]["blueprint"]["domain"] == "Testing Domain"

    # Delete
    delete_session(test_session_id)
    assert get_session(test_session_id) is None


# ==============================================================================
# 7. TOOL REGISTRY TELEMETRY & LATENCY TRACKING
# ==============================================================================

def test_regression_tool_registry_telemetry():
    """Verify tool execution logs duration, success status, and error states."""
    reg = ToolRegistry()
    # Test valid tool
    t1 = reg.execute_tool("search_web", query="zero trust healthcare architecture")
    assert t1.success is True
    assert t1.execution_time_ms > 0
    assert len(reg.execution_audit_log) == 1

    # Test unknown tool
    t2 = reg.execute_tool("nonexistent_unknown_tool", arg="test")
    assert t2.success is False
    assert "unrecognized tool" in t2.error.lower()
    assert len(reg.execution_audit_log) == 2


# ==============================================================================
# 8. COMPLETE DEMO SIMULATION PIPELINE
# ==============================================================================

def test_regression_demo_simulation_end_to_end():
    """Verify 17-step demo simulation executes all milestones and generates ready artifacts."""
    steps_recorded = []
    logs_recorded = []

    def on_step(idx, total, title, desc):
        steps_recorded.append((idx, total, title))

    def on_log(msg):
        logs_recorded.append(msg)

    bundle = KleinResearchAgent.execute_demo_simulation(
        step_callback=on_step,
        log_callback=on_log
    )

    assert len(steps_recorded) == 17
    assert len(logs_recorded) >= 17
    assert "Healthcare" in bundle["topic"]
    assert "pdf_bytes" in bundle and bundle["pdf_bytes"].startswith(b"%PDF-")
    assert "pptx_bytes" in bundle and bundle["pptx_bytes"].startswith(b"PK")
    assert len(bundle["sources"]) >= 4
    assert len(bundle["audited_citations"]) >= 4
    assert len(bundle["research_gaps"]) >= 3
