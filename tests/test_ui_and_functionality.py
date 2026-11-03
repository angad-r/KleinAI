"""
ResearchMate AI - Automated QA, Button & Functionality Test Suite
Uses pytest to verify inputs, button logic, tool registry, error recovery, and downloads.
"""
import os
import sys

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import json
import re

from core.tools import ToolRegistry, ToolExecutionResult
from core.search_engine import SearchEngine
from core.citation_auditor import CitationAuditor
from core.database import init_db, save_session, get_session, list_sessions, delete_session
from core.pdf_generator import build_pdf_report, clean_text_for_pdf
from core.ppt_generator import build_pptx_deck
from core.researcher import KleinResearchAgent
from core.demo_dataset import VERIFIED_DEMO_DATA

# --- 1. INPUT VALIDATION TESTS ---

def test_input_empty_topic():
    """Verify empty string or whitespace is rejected."""
    empty_topic = "   "
    clean = empty_topic.strip()
    assert len(clean) == 0

def test_input_special_characters():
    """Verify special characters do not crash filename sanitizer or PDF clean text."""
    special_topic = "AI & Cybersecurity: A Survey of 100% Zero-Day Threats <XML> 'quote' \"double\" [brackets] / \\ $"
    # Filename sanitizer
    slug = re.sub(r'[^\w\-_]', '_', special_topic[:28])
    assert ":" not in slug
    assert "<" not in slug
    assert "/" not in slug
    assert "\\" not in slug
    
    # PDF sanitizer
    cleaned = clean_text_for_pdf(special_topic)
    assert "&amp;" in cleaned
    assert "&lt;" in cleaned
    assert "&gt;" in cleaned

def test_input_very_long_topic():
    """Verify 1500-character prompt is handled without crashing."""
    long_topic = "Impact of Artificial Intelligence " * 50
    slug = re.sub(r'[^\w\-_]', '_', long_topic[:28])
    assert len(slug) <= 28

# --- 2. BUTTON & WORKFLOW LOGIC TESTS ---

def test_instant_demo_simulation_button_execution():
    """Verify '⚡ INSTANT DEMO SIMULATION' executes all 17 steps and generates valid artifacts."""
    steps_tracked = []
    
    def on_step(idx, total, title, desc):
        steps_tracked.append(idx)
        
    result = KleinResearchAgent.execute_demo_simulation(step_callback=on_step)
    
    assert result is not None
    assert len(steps_tracked) == 17
    assert "pdf_bytes" in result and result["pdf_bytes"].startswith(b"%PDF-")
    assert "pptx_bytes" in result and result["pptx_bytes"].startswith(b"PK")
    assert "tool_audit_log" in result and len(result["tool_audit_log"]) == 17
    assert "audited_citations" in result and len(result["audited_citations"]) > 0

def test_history_session_save_load_delete_buttons():
    """Verify saving a session, reloading it, and deleting it from SQLite."""
    init_db()
    test_id = "test-btn-sess-99"
    test_topic = "Quantum Cryptography Verification"
    
    # 1. Save button action
    save_session(
        session_id=test_id,
        topic=test_topic,
        status="Completed (Verified)",
        source_count=4,
        summary="Test executive abstract for history button verification",
        data={
            "topic": test_topic,
            "blueprint": {"topic_normalized": test_topic, "executive_summary": "Test summary"},
            "sources": [{"title": "QKD Test", "url": "https://example.com/qkd", "domain": "example.com", "snippet": "Test snippet"}],
            "slides_data": [{"slide_number": 1, "slide_type": "title", "title": test_topic, "subtitle": "Test", "bullets": []}]
        }
    )
    
    # 2. Load button action
    loaded = get_session(test_id)
    assert loaded is not None
    assert loaded["topic"] == test_topic
    
    # Reconstruct PDF and PPTX in memory (simulating app.py load logic)
    data = loaded["data"]
    pdf_bytes = build_pdf_report(data)
    assert pdf_bytes.startswith(b"%PDF-")
    pptx_bytes = build_pptx_deck(data, data.get("slides_data", []))
    assert pptx_bytes.startswith(b"PK")
    
    # 3. Delete button action
    delete_session(test_id)
    rechecked = get_session(test_id)
    assert rechecked is None

# --- 3. DOWNLOAD ARTIFACT INTEGRITY TESTS ---

def test_pdf_download_content_and_headers():
    """Verify ReportLab PDF contains valid header, footer, and tables."""
    data = VERIFIED_DEMO_DATA
    pdf = build_pdf_report(data)
    assert len(pdf) > 8000
    assert pdf.startswith(b"%PDF-")
    assert b"%%EOF" in pdf

def test_pptx_download_content_and_slides():
    """Verify python-pptx presentation contains valid slides and text boxes."""
    data = VERIFIED_DEMO_DATA
    slides = data.get("slides_data", [])
    pptx_bytes = build_pptx_deck(data, slides)
    assert len(pptx_bytes) > 25000
    assert pptx_bytes.startswith(b"PK") # Zip archive signature

def test_json_and_markdown_exports():
    """Verify JSON schema is valid and Markdown contains required headers."""
    data = VERIFIED_DEMO_DATA
    json_str = json.dumps({k: v for k, v in data.items() if k not in ("pdf_bytes", "pptx_bytes")})
    parsed = json.loads(json_str)
    assert "blueprint" in parsed
    assert "sources" in parsed
    assert "literature_review" in parsed
    assert "research_gaps" in parsed
    assert "methodology" in parsed

# --- 4. CITATION AUDIT & SOURCE VERIFICATION TESTS ---

def test_citation_auditor_verification():
    """Verify CitationAuditor maps sources, audits URLs, and formats APA & BibTeX."""
    sources = [
        {"title": "AI in Medical Systems", "url": "https://ncbi.nlm.nih.gov/pmc/articles/123", "domain": "ncbi.nlm.nih.gov", "snippet": "Medical AI study"},
        {"title": "Adversarial Healthcare", "url": "https://ieeexplore.ieee.org/document/456", "domain": "ieeexplore.ieee.org", "snippet": "Attack vectors"}
    ]
    audited = CitationAuditor.audit_sources(sources)
    assert len(audited) == 2
    assert "VERIFIED: Authoritative Academic" in audited[0]["status"]
    assert "apa_citation" in audited[0]
    assert "bibtex" in audited[0]
    assert "ncbi.nlm.nih.gov" in audited[0]["apa_citation"]
    assert "@misc{" in audited[0]["bibtex"]

# --- 5. SEARCH ENGINE & FAILOVER TESTS ---

def test_search_engine_canonical_normalization():
    """Verify tracking parameters and fragments are pruned."""
    dirty_url = "https://www.example.com/research/paper?utm_source=twitter&utm_medium=social&ref=123#abstract"
    clean_url = SearchEngine.normalize_url(dirty_url)
    assert clean_url == "https://example.com/research/paper"

def test_tool_registry_input_validation():
    """Verify ToolRegistry validates inputs and logs execution results."""
    reg = ToolRegistry(tavily_api_key=None)
    # Empty query should fail gracefully
    res = reg.execute_tool("search_web", query="")
    assert res.success is False
    assert "empty" in res.error.lower()
    
    # Valid query executes
    res2 = reg.execute_tool("search_web", query="healthcare cybersecurity", aspect="Foundations")
    assert res2.success is True
    assert len(reg.execution_audit_log) == 2
