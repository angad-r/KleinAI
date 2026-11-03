"""
Klein AI - System Verification and Smoke Test Script
Tests database, search engine, PDF generator, and PPTX generator in isolation.
"""
import sys
from datetime import datetime

def test_database():
    print("Testing SQLite Database...")
    from core.database import init_db, save_session, get_session, list_sessions, delete_session
    init_db()
    test_id = "test-session-001"
    save_session(
        session_id=test_id,
        topic="Test Research Topic",
        status="Completed",
        source_count=5,
        summary="Test executive summary",
        data={"blueprint": {"topic_normalized": "Test Topic"}, "sources": []}
    )
    loaded = get_session(test_id)
    assert loaded is not None, "Failed to load saved session"
    assert loaded["topic"] == "Test Research Topic"
    sessions = list_sessions()
    assert any(s["id"] == test_id for s in sessions), "Session not found in list"
    delete_session(test_id)
    print(" SQLite Database OK!")

def test_pdf_generator():
    print("Testing ReportLab PDF Generator...")
    from core.pdf_generator import build_pdf_report
    dummy_bundle = {
        "topic": "Impact of Artificial Intelligence on Cybersecurity in Healthcare",
        "blueprint": {
            "topic_normalized": "Impact of Artificial Intelligence on Cybersecurity in Healthcare",
            "domain": "Healthcare AI & Cybersecurity",
            "executive_summary": "Autonomous test executive summary verifying ReportLab document compilation.",
            "research_questions": [
                "RQ1: How do AI models detect zero-day healthcare malware?",
                "RQ2: What are the adversarial vulnerabilities in IoMT ecosystems?"
            ]
        },
        "comparison": {
            "comparative_matrix": [
                {
                    "dimension": "Threat Detection",
                    "traditional_approach": "Static signature matching",
                    "sota_ai_approach": "Deep anomaly autoencoders",
                    "observed_limitations": "Adversarial evasion"
                }
            ],
            "consensus_points": ["AI significantly reduces alert triage time."],
            "debates_and_disagreements": ["Centralized vs Federated learning privacy."]
        },
        "literature_review": "### Foundational Paradigms\n\nAI integration across Electronic Health Record (EHR) networks introduces unprecedented defensive agility.",
        "research_gaps": [
            {
                "gap_id": "GAP-01",
                "title": "Adversarial Robustness in Medical Edge Devices",
                "category": "Algorithmic Robustness",
                "description": "IoMT devices lack computational headroom for heavy defenses.",
                "impact_severity": "Critical",
                "opportunity": "Quantized lightweight defense layers."
            }
        ],
        "methodology": {
            "framework_name": "Klein-HealthShield Architecture",
            "system_architecture": {
                "overview": "Multi-tier federated zero-trust defensive framework for IoMT.",
                "components": [{"name": "Edge Agent", "role": "Local telemetry filtering"}],
                "workflow_pipeline": "Ingestion -> Anomaly Scoring -> Quarantine"
            },
            "proposed_experiments": [
                {
                    "experiment_id": "EXP-1",
                    "title": "IoMT Attack Detection Under Noise",
                    "hypothesis": "Detection accuracy exceeds 98%.",
                    "baselines": ["Random Forest Baseline"],
                    "procedure": "Inject packet anomalies across standard dataset."
                }
            ],
            "evaluation_metrics": [
                {"metric": "Balanced F1-Score", "target": "> 97.5%", "rationale": "High imbalance resilience"}
            ]
        },
        "sources": [
            {
                "title": "Cybersecurity in Medical Cyber-Physical Systems: A Survey",
                "url": "https://example.com/cybersecurity-healthcare",
                "domain": "example.com",
                "snippet": "Analysis of IoMT cyber threats and AI mitigations."
            }
        ]
    }
    pdf_bytes = build_pdf_report(dummy_bundle)
    assert pdf_bytes is not None and len(pdf_bytes) > 1000, "PDF bytes generation failed"
    print(f" PDF Generation OK! ({len(pdf_bytes)} bytes)")

def test_ppt_generator():
    print("Testing python-pptx PowerPoint Generator...")
    from core.ppt_generator import build_pptx_deck
    dummy_bundle = {
        "topic": "Impact of Artificial Intelligence on Cybersecurity in Healthcare",
        "blueprint": {
            "topic_normalized": "Impact of Artificial Intelligence on Cybersecurity in Healthcare",
            "domain": "Healthcare AI & Cybersecurity"
        }
    }
    dummy_slides = [
        {"slide_number": 1, "slide_type": "title", "title": "Impact of AI in Healthcare Cybersecurity", "subtitle": "Klein AI Autonomous Research Deck", "bullets": []},
        {"slide_number": 2, "slide_type": "content", "title": "Executive Summary", "subtitle": "Problem & Motivation", "bullets": ["Healthcare networks are primary targets for ransomware.", "AI provides real-time proactive telemetry defense."]},
        {"slide_number": 3, "slide_type": "content", "title": "Proposed Framework", "subtitle": "Klein-HealthShield Core", "bullets": ["Federated anomaly detection.", "Zero-overhead edge verification."]}
    ]
    pptx_bytes = build_pptx_deck(dummy_bundle, dummy_slides)
    assert pptx_bytes is not None and len(pptx_bytes) > 1000, "PPTX bytes generation failed"
    print(f" PPTX Generation OK! ({len(pptx_bytes)} bytes)")

def test_search_engine_fallback():
    print("Testing Search Engine DuckDuckGo Fallback...")
    from core.search_engine import SearchEngine
    # Initialize without Tavily key to test auto-fallback
    engine = SearchEngine(tavily_api_key=None)
    results = engine.search_query("artificial intelligence cybersecurity healthcare", max_results=2)
    print(f" Search Engine Query returned {len(results)} results via {results[0].get('engine') if results else 'None'}")
    print(" Search Engine OK!")

if __name__ == "__main__":
    print("=== Running Klein AI Smoke Tests ===")
    test_database()
    test_pdf_generator()
    test_ppt_generator()
    test_search_engine_fallback()
    print("=== All Core Modules Verified Successfully! ===")
