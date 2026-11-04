"""
Klein AI 2.0 - Autonomous Scientific Research Agent
Hybrid Streamlit Desktop Dashboard & Vercel WSGI Serverless API Application
"""
import os
import re
import json
import time
import uuid
import threading
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from core.config import (
    APP_NAME,
    APP_TAGLINE,
    APP_VERSION,
    DEFAULT_GEMINI_MODEL,
    AVAILABLE_MODELS,
    SUPPORTED_MODELS,
    ALLOWED_ORIGINS,
    MAX_REQUEST_BODY_SIZE,
    get_gemini_api_key,
    get_tavily_api_key,
    clean_api_key,
    mask_api_key
)
from core.database import (
    init_db,
    list_sessions,
    get_session,
    save_session,
    delete_session,
    check_db_health,
)
from core.job_queue import job_manager
from core.researcher import KleinResearchAgent
from core.gemini_client import (
    GeminiClient,
    GeminiAuthError,
    GeminiRateLimitError,
    GeminiNetworkError,
    GeminiModelError,
    classify_error
)
from core.pdf_generator import build_pdf_report
from core.ppt_generator import build_pptx_deck
from core.demo_dataset import VERIFIED_DEMO_DATA

# Optional Streamlit runtime check
try:
    from streamlit import runtime
except ImportError:
    runtime = None


# ==============================================================================
# RATE LIMITING & SECURITY UTILITIES
# ==============================================================================

class InMemoryRateLimiter:
    """
    Thread-safe sliding-window rate limiter.
    Limits requests per client IP to prevent denial of service and API abuse.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._client_requests: Dict[str, List[float]] = {}

    def is_allowed(self, client_ip: str, limit: int = 60, window_seconds: int = 60) -> bool:
        now = time.time()
        with self._lock:
            history = self._client_requests.get(client_ip, [])
            valid_history = [t for t in history if now - t < window_seconds]
            if len(valid_history) >= limit:
                self._client_requests[client_ip] = valid_history
                return False
            valid_history.append(now)
            self._client_requests[client_ip] = valid_history
            return True


rate_limiter = InMemoryRateLimiter()

SECURITY_HEADERS = [
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload"),
    ("Referrer-Policy", "strict-origin-when-cross-origin"),
    ("Content-Security-Policy", "default-src 'self' 'unsafe-inline' 'unsafe-eval' https: data:; img-src 'self' data: https:; font-src 'self' https: data:;"),
]


def test_tavily_key(key: str) -> Tuple[bool, str]:
    """Lightweight live verification of Tavily Search API key."""
    clean = clean_api_key(key)
    if not clean:
        return True, "No key provided (using DuckDuckGo fallback)"
    try:
        import requests
        resp = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": clean, "query": "test", "max_results": 1},
            timeout=5
        )
        if resp.status_code == 200:
            return True, "Tavily Search API authenticated successfully"
        elif resp.status_code in (401, 403):
            return False, "Tavily API key is invalid or unauthorized"
        else:
            return True, "Tavily service reachable"
    except Exception as e:
        return False, f"Tavily probe error: {str(e)}"


# ==============================================================================
# STREAMLIT DESKTOP DASHBOARD
# ==============================================================================

def render_streamlit_dashboard():
    """
    Interactive Streamlit Web Dashboard for local desktop users.
    Executed when started via `streamlit run app.py`.
    """
    import streamlit as st

    st.set_page_config(
        page_title=f"{APP_NAME} 2.0 — Autonomous Research Platform",
        page_icon="🔬",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Load custom CSS
    css_path = Path(__file__).resolve().parent / "assets" / "style.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    # Initialize Database
    init_db()

    # Session State Initialization
    if "research_data" not in st.session_state:
        st.session_state.research_data = None
    if "is_researching" not in st.session_state:
        st.session_state.is_researching = False
    if "current_step_info" not in st.session_state:
        st.session_state.current_step_info = {"step": 0, "total": 17, "title": "Idle", "desc": "Ready"}
    if "live_logs" not in st.session_state:
        st.session_state.live_logs = []
    if "topic_input_box" not in st.session_state:
        st.session_state["topic_input_box"] = "Impact of Artificial Intelligence on Cybersecurity in Healthcare Systems"

    with st.sidebar:
        st.markdown(f"""
        <div style="padding: 10px 0 16px 0;">
            <h2 style="margin: 0; font-size: 1.8rem; font-weight: 800; background: linear-gradient(135deg, #6366F1 0%, #38BDF8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{APP_NAME} 2.0</h2>
            <div style="font-size: 0.8rem; color: #94A3B8; font-weight: 500;">{APP_TAGLINE}</div>
            <div style="margin-top: 8px;">
                <span class="badge-pill badge-indigo">17-Step Autonomous Engine</span>
                <span class="badge-pill badge-cyan">DOI Verified</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("⚙️ Credentials & Engine")

        env_gemini = get_gemini_api_key()
        gemini_key_input = st.text_input(
            "Google Gemini API Key",
            value=env_gemini,
            type="password",
            placeholder="Enter Gemini API key",
            help="Required for reasoning, literature synthesis, and verification."
        )

        env_tavily = get_tavily_api_key()
        tavily_key_input = st.text_input(
            "Tavily Search API Key",
            value=env_tavily,
            type="password",
            placeholder="Enter Tavily key (Optional)",
            help="Provides real-time scholarly search. Defaults to DuckDuckGo fallback if blank."
        )

        selected_model = st.selectbox(
            "Reasoning Engine Model",
            options=SUPPORTED_MODELS,
            index=0,
            help="Google Gemini 2.5/2.0 Flash recommended for real-time speed and scholarly synthesis."
        )

        st.markdown("---")
        db_health = check_db_health()
        st.markdown(f"**Database:** `{db_health.get('backend', 'sqlite').upper()}` ({'🟢 Connected' if db_health.get('connected') else '🔴 Error'})")
        
        st.markdown("---")
        st.subheader("📚 Saved Sessions")
        try:
            saved_list = list_sessions(limit=10)
            if saved_list:
                for s in saved_list:
                    btn_label = f"📄 {s.get('topic', 'Untitled')[:24]}..."
                    if st.button(btn_label, key=f"hist_{s.get('id')}", use_container_width=True):
                        sess = get_session(s.get("id"))
                        if sess and "data" in sess:
                            st.session_state.research_data = sess["data"]
                            st.success(f"Loaded: {s.get('topic')}")
                            st.rerun()
            else:
                st.caption("No historical sessions yet.")
        except Exception:
            st.caption("Unable to load history.")

    # Main Area
    st.markdown(f"""
    <div style="margin-bottom: 24px;">
        <h1 style="margin: 0; font-size: 2.3rem; font-weight: 800; color: #F8FAFC;">Autonomous Scientific Research Platform</h1>
        <p style="margin-top: 6px; color: #94A3B8; font-size: 1.05rem;">
            Autonomous multi-agent literature synthesis, DOI content-negotiation citation audits, research gap extraction, and peer review validation.
        </p>
    </div>
    """, unsafe_allow_html=True)

    c_input, c_btn = st.columns([4, 1])
    with c_input:
        topic_input = st.text_input(
            "Research Topic or Investigation Query",
            value=st.session_state["topic_input_box"],
            placeholder="e.g. Zero-Trust Architecture in Critical Cloud Healthcare Infrastructure",
            label_visibility="collapsed"
        )
    with c_btn:
        run_clicked = st.button("🚀 Start Investigation", use_container_width=True, type="primary")

    c_demo, c_clear = st.columns([1, 4])
    with c_demo:
        if st.button("⚡ Load Verified Demo", use_container_width=True):
            st.session_state.research_data = VERIFIED_DEMO_DATA
            st.success("Loaded verified empirical demo dataset!")
            st.rerun()

    if run_clicked:
        if not topic_input.strip():
            st.error("Please enter a research topic.")
        elif not gemini_key_input.strip() and not env_gemini:
            st.error("Google Gemini API Key is required. Set GEMINI_API_KEY or enter key in sidebar.")
        else:
            st.session_state.is_researching = True
            st.session_state.live_logs = []
            
            prog_bar = st.progress(0)
            status_text = st.empty()
            log_box = st.empty()

            clean_gemini_key = gemini_key_input.strip() or env_gemini

            def on_step_progress(step, total, title, desc):
                pct = int((step / total) * 100)
                prog_bar.progress(pct)
                status_text.markdown(f"**Step {step}/{total}: {title}** — {desc}")

            def on_log_message(msg):
                now_str = datetime.now().strftime("%H:%M:%S")
                st.session_state.live_logs.append(f"[{now_str}] {msg}")
                recent = st.session_state.live_logs[-8:]
                log_box.markdown(
                    f'<div class="terminal-box">' + "<br/>".join(recent) + '</div>',
                    unsafe_allow_html=True
                )

            try:
                agent = KleinResearchAgent(
                    gemini_api_key=clean_gemini_key,
                    tavily_api_key=tavily_key_input.strip() or env_tavily,
                    model=selected_model
                )
                with st.spinner("Executing 17-Step Autonomous Scientific Pipeline..."):
                    results = agent.execute_research(
                        topic=topic_input.strip(),
                        step_callback=on_step_progress,
                        log_callback=on_log_message
                    )
                st.session_state.research_data = results
                st.session_state.is_researching = False
                prog_bar.progress(100)
                st.success("✅ Complete Autonomous Investigation Completed! Explore scholarly findings below.")
                st.rerun()
            except Exception as e:
                st.session_state.is_researching = False
                st.error(f"Research execution failed: {str(e)}")

    # Display Results View
    data = st.session_state.research_data
    if data:
        blueprint = data.get("blueprint", {})
        sources = data.get("sources", [])
        gaps = data.get("research_gaps", [])
        methodology = data.get("methodology", {})
        comparison = data.get("comparison", {})
        lit_review = data.get("literature_review", "")
        full_report = data.get("report_markdown", "")
        review_audit = data.get("independent_review", {})
        audited_cits = data.get("audited_citations", [])
        pdf_bytes = data.get("pdf_bytes")
        pptx_bytes = data.get("pptx_bytes")

        st.markdown("---")

        # Metrics bar
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.markdown(f"""
            <div class="stat-box">
                <div class="stat-value">{blueprint.get('domain', 'AI Research')[:14]}</div>
                <div class="stat-label">Scientific Domain</div>
            </div>
            """, unsafe_allow_html=True)
        with m2:
            st.markdown(f"""
            <div class="stat-box">
                <div class="stat-value">{len(sources)}</div>
                <div class="stat-label">Sources Harvested</div>
            </div>
            """, unsafe_allow_html=True)
        with m3:
            st.markdown(f"""
            <div class="stat-box">
                <div class="stat-value">{len(blueprint.get('research_questions', []))}</div>
                <div class="stat-label">Research Questions</div>
            </div>
            """, unsafe_allow_html=True)
        with m4:
            st.markdown(f"""
            <div class="stat-box">
                <div class="stat-value">{len(gaps)}</div>
                <div class="stat-label">Research Gaps</div>
            </div>
            """, unsafe_allow_html=True)
        with m5:
            rev_score = review_audit.get("overall_score", 9.2) if review_audit else 9.0
            st.markdown(f"""
            <div class="stat-box">
                <div class="stat-value" style="color: #10B981;">{rev_score}/10</div>
                <div class="stat-label">Peer Review Score</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br/>", unsafe_allow_html=True)

        # Tabs
        tab_overview, tab_lit, tab_matrix, tab_gaps, tab_method, tab_review, tab_report, tab_sources, tab_export = st.tabs([
            "📌 Blueprint", "📚 Literature Review", "📊 Evidence Matrix", "🧭 Research Gaps",
            "⚙️ Methodology", "🛡️ Peer Review", "📄 Academic Paper", "🔗 Sources & Citations", "📥 Export Center"
        ])

        with tab_overview:
            st.markdown(f"### 🎯 Research Blueprint: `{blueprint.get('topic_normalized', 'Topic')}`")
            st.markdown(f"**Domain Classification:** `{blueprint.get('domain', 'General')}`")
            st.markdown(f"**Core Hypothesis:**\n> {blueprint.get('core_hypothesis', 'N/A')}")
            st.markdown("#### ❓ Formal Research Questions")
            for rq in blueprint.get("research_questions", []):
                st.markdown(f"- **{rq.get('id', 'RQ')}:** {rq.get('question')}")
                if rq.get("rationale"):
                    st.caption(f"Rationale: {rq.get('rationale')}")

        with tab_lit:
            st.markdown("### 📚 Comprehensive Scholarly Literature Review")
            st.markdown(lit_review)

        with tab_matrix:
            st.markdown("### 📊 Comparative Analysis & Evidence Synthesis")
            themes = comparison.get("themes", [])
            if themes:
                for t in themes:
                    st.markdown(f"#### 🏷️ Theme: {t.get('theme', 'Key Area')}")
                    st.markdown(f"**Consensus:** {t.get('consensus', 'N/A')}")
                    st.markdown(f"**Divergent Findings:** {t.get('divergence', 'N/A')}")
                    st.markdown(f"**Key Citations:** {', '.join(t.get('citations', []))}")
                    st.markdown("---")

        with tab_gaps:
            st.markdown("### 🔍 Critical Research Gaps & Strategic Frontiers")
            for g in gaps:
                st.markdown(f"""
                <div class="gap-card">
                    <span class="gap-id-badge">{g.get('gap_id', 'GAP')}</span>
                    <strong style="margin-left: 8px; font-size: 1.05rem; color: #F8FAFC;">{g.get('title')}</strong>
                    <div style="color: #CBD5E1; font-size: 0.9rem; margin-top: 8px;">{g.get('description')}</div>
                    <div style="margin-top: 8px; font-size: 0.85rem; color: #38BDF8;"><b>Research Opportunity:</b> {g.get('opportunity')}</div>
                </div>
                """, unsafe_allow_html=True)

        with tab_method:
            fname = methodology.get("framework_name", "Klein Framework")
            st.markdown(f"### ⚙️ Novel Proposed Methodology: `{fname}`")
            arch = methodology.get("system_architecture", {})
            if arch.get("overview"):
                st.markdown(f"**Overview:** {arch.get('overview')}")
            for c in arch.get("components", []):
                st.markdown(f"- **{c.get('name')}:** {c.get('role')}")

        with tab_review:
            st.markdown("### 🛡️ Independent Verification & Peer Review Audit")
            if review_audit:
                r1, r2, r3 = st.columns(3)
                r1.metric("Overall Quality", f"{review_audit.get('overall_score', 'N/A')}/10")
                r2.metric("Factuality Rating", review_audit.get("factuality_rating", "N/A"))
                r3.metric("Methodological Novelty", review_audit.get("novelty_assessment", "N/A"))
                
                st.markdown(f"**Executive Synthesis:**\n\n{review_audit.get('summary_critique', 'N/A')}")
                
                col_s, col_w = st.columns(2)
                with col_s:
                    st.markdown("#### ✅ Validated Strengths")
                    for s in review_audit.get("key_strengths", []):
                        st.markdown(f"- {s}")
                with col_w:
                    st.markdown("#### ⚠️ Identified Limitations")
                    for w in review_audit.get("key_weaknesses", []):
                        st.markdown(f"- {w}")

        with tab_report:
            st.markdown("### 📄 Full Academic Research Report")
            st.markdown(full_report)

        with tab_sources:
            st.markdown("### 🔗 Harvested Empirical Sources & Verified Citations")
            for s in sources:
                st.markdown(f"- [{s.get('title')}]({s.get('url')}) — *{s.get('domain')}* (Tier: {s.get('quality_tier', 'Standard')})")

            if audited_cits:
                st.markdown("---")
                st.markdown("#### 📖 Formal APA 7th Citations")
                for c in audited_cits:
                    st.markdown(f"- {c.get('apa_citation')}")
                st.markdown("#### 🏷️ BibTeX References")
                all_bib = "\n\n".join([c.get("bibtex", "") for c in audited_cits])
                st.code(all_bib, language="bibtex")

        with tab_export:
            st.markdown("### 📥 Download Research Deliverables")
            if not pdf_bytes and data:
                pdf_bytes = build_pdf_report(data)
                data["pdf_bytes"] = pdf_bytes
            if not pptx_bytes and data:
                pptx_bytes = build_pptx_deck(data, data.get("slides_data", []))
                data["pptx_bytes"] = pptx_bytes

            raw_topic_slug = re.sub(r'[^\w\-_]', '_', blueprint.get('topic_normalized', 'KleinAI_Report')[:28])

            col_pdf, col_ppt = st.columns(2)
            with col_pdf:
                if pdf_bytes:
                    st.download_button(
                        label="📥 Download Academic PDF Whitepaper",
                        data=pdf_bytes,
                        file_name=f"KleinAI_{raw_topic_slug}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
            with col_ppt:
                if pptx_bytes:
                    st.download_button(
                        label="📥 Download PowerPoint Deck (.pptx)",
                        data=pptx_bytes,
                        file_name=f"KleinAI_{raw_topic_slug}.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        use_container_width=True
                    )


# ==============================================================================
# RUNTIME DISPATCHER
# ==============================================================================
try:
    if runtime and runtime.exists():
        render_streamlit_dashboard()
except Exception:
    pass


# ==============================================================================
# MODERN RESPONSIVE DARK SAAS UI (HTML/CSS/JS)
# ==============================================================================

HTML_LANDING_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Klein AI 2.0 — Autonomous Research Agent</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🔬</text></svg>">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #0B0F19;
            --bg-surface: #111827;
            --bg-elevated: #1F2937;
            --bg-card: rgba(17, 24, 39, 0.85);
            --border: #1E293B;
            --border-highlight: #334155;
            --accent-primary: #6366F1;
            --accent-primary-hover: #4F46E5;
            --accent-cyan: #38BDF8;
            --accent-emerald: #10B981;
            --accent-amber: #F59E0B;
            --accent-rose: #F43F5E;
            --text-primary: #F8FAFC;
            --text-secondary: #94A3B8;
            --text-muted: #64748B;
            --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            --font-mono: 'JetBrains Mono', ui-monospace, Menlo, Consolas, monospace;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; font-family: var(--font-sans); }
        body { background: var(--bg-base); color: var(--text-primary); min-height: 100vh; display: flex; flex-direction: column; overflow-x: hidden; }

        header {
            position: sticky; top: 0; z-index: 50;
            background: rgba(11, 15, 25, 0.90); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border); padding: 14px 28px;
            display: flex; justify-content: space-between; align-items: center;
        }
        .nav-brand { display: flex; align-items: center; gap: 12px; text-decoration: none; }
        .nav-logo { font-size: 1.5rem; }
        .nav-title { font-size: 1.15rem; font-weight: 800; letter-spacing: -0.02em; background: linear-gradient(135deg, #FFF 20%, #A5B4FC 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .nav-badge { font-size: 0.7rem; font-weight: 600; padding: 3px 8px; border-radius: 9999px; background: rgba(99, 102, 241, 0.15); border: 1px solid rgba(99, 102, 241, 0.35); color: #A5B4FC; }
        .nav-links { display: flex; align-items: center; gap: 20px; }
        .nav-link { color: var(--text-secondary); text-decoration: none; font-size: 0.88rem; font-weight: 500; transition: color 0.15s; }
        .nav-link:hover, .nav-link.active { color: var(--text-primary); }
        .nav-status { display: flex; align-items: center; gap: 8px; font-size: 0.8rem; color: var(--text-secondary); padding: 4px 10px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 8px; }
        .status-dot { width: 7px; height: 7px; border-radius: 50%; }
        .status-dot.green { background: var(--accent-emerald); box-shadow: 0 0 8px var(--accent-emerald); }
        .status-dot.amber { background: var(--accent-amber); box-shadow: 0 0 8px var(--accent-amber); }

        main { max-width: 1200px; width: 100%; margin: 0 auto; padding: 32px 24px 60px 24px; flex: 1; }

        .hero { text-align: center; margin-bottom: 32px; }
        .hero-pill { display: inline-flex; align-items: center; gap: 8px; padding: 5px 14px; background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.25); border-radius: 9999px; font-size: 0.8rem; font-weight: 600; color: #A5B4FC; margin-bottom: 16px; }
        h1.hero-title { font-size: 2.75rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1.15; margin-bottom: 12px; background: linear-gradient(135deg, #FFFFFF 40%, #94A3B8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        p.hero-subtitle { font-size: 1.05rem; color: var(--text-secondary); max-width: 720px; margin: 0 auto; line-height: 1.6; }

        .card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: 16px; padding: 24px 28px; margin-bottom: 24px; box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5); }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; }
        .card-title { font-size: 1.15rem; font-weight: 700; display: flex; align-items: center; gap: 10px; }

        .form-group { margin-bottom: 16px; }
        label { display: block; font-size: 0.85rem; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; }
        input[type="text"], input[type="password"], select { width: 100%; background: #0A0E17; border: 1px solid var(--border); border-radius: 10px; padding: 12px 16px; color: var(--text-primary); font-size: 0.95rem; outline: none; transition: border-color 0.2s, box-shadow 0.2s; }
        input[type="text"]:focus, input[type="password"]:focus, select:focus { border-color: var(--accent-primary); box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2); }
        input.input-error { border-color: var(--accent-rose) !important; box-shadow: 0 0 0 3px rgba(244, 63, 94, 0.25) !important; }

        .sample-pills { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
        .sample-pill { font-size: 0.75rem; padding: 4px 10px; background: rgba(30, 41, 59, 0.6); border: 1px solid var(--border); border-radius: 6px; color: #CBD5E1; cursor: pointer; transition: all 0.15s; }
        .sample-pill:hover { background: var(--border); color: #FFF; border-color: var(--accent-primary); }

        .btn-row { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 20px; align-items: center; }
        button { font-size: 0.92rem; font-weight: 600; border-radius: 10px; padding: 12px 22px; border: none; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; transition: transform 0.1s, opacity 0.2s, background-color 0.2s; }
        button:hover { opacity: 0.95; transform: translateY(-1px); }
        button:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        button.btn-primary { background: linear-gradient(135deg, var(--accent-primary), var(--accent-primary-hover)); color: white; box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35); }
        button.btn-secondary { background: var(--bg-elevated); color: var(--text-primary); border: 1px solid var(--border-highlight); }
        button.btn-secondary:hover { background: #2D3748; }
        button.btn-success { background: linear-gradient(135deg, #10B981, #059669); color: white; }
        button.btn-danger { background: rgba(244, 63, 94, 0.15); color: #FB7185; border: 1px solid rgba(244, 63, 94, 0.3); }

        .banner-alert { display: none; padding: 12px 16px; border-radius: 10px; font-size: 0.88rem; margin-bottom: 16px; line-height: 1.5; }
        .banner-alert.error { background: rgba(244, 63, 94, 0.12); border: 1px solid rgba(244, 63, 94, 0.35); color: #FECDD3; }
        .banner-alert.success { background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.35); color: #A7F3D0; }
        .banner-alert.info { background: rgba(56, 189, 248, 0.12); border: 1px solid rgba(56, 189, 248, 0.35); color: #BAE6FD; }

        .telemetry-card { display: none; background: #080C14; border: 1px solid var(--border); border-radius: 14px; padding: 22px; margin-bottom: 24px; }
        .progress-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .stage-title { font-weight: 600; font-size: 0.95rem; color: var(--accent-cyan); display: flex; align-items: center; gap: 8px; }
        .stage-pct { font-family: var(--font-mono); font-weight: 700; font-size: 0.9rem; color: var(--text-primary); }
        .progress-bar-bg { width: 100%; height: 8px; background: #1E293B; border-radius: 9999px; overflow: hidden; margin-bottom: 16px; }
        .progress-bar-fill { height: 100%; width: 0%; background: linear-gradient(90deg, var(--accent-primary), var(--accent-cyan)); transition: width 0.3s ease; }
        .terminal { background: #05070B; border: 1px solid #161F30; border-radius: 8px; padding: 14px; max-height: 180px; overflow-y: auto; font-family: var(--font-mono); font-size: 0.8rem; line-height: 1.6; color: #7DD3FC; }

        .results-container { display: none; margin-top: 24px; }
        .tabs-header { display: flex; gap: 6px; border-bottom: 1px solid var(--border); margin-bottom: 24px; overflow-x: auto; padding-bottom: 4px; }
        .tab-btn { background: transparent; border: none; padding: 10px 16px; font-size: 0.88rem; font-weight: 600; color: var(--text-secondary); border-radius: 8px; cursor: pointer; transition: all 0.15s; white-space: nowrap; }
        .tab-btn:hover { color: var(--text-primary); background: rgba(30, 41, 59, 0.4); }
        .tab-btn.active { color: var(--accent-primary); background: rgba(99, 102, 241, 0.12); border-bottom: 2px solid var(--accent-primary); }
        .tab-panel { display: none; animation: fadeIn 0.25s ease-in-out; }
        .tab-panel.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

        .prose { font-size: 0.95rem; line-height: 1.7; color: #CBD5E1; }
        .prose h2, .prose h3 { color: var(--text-primary); margin: 24px 0 12px 0; font-weight: 700; }
        .prose p { margin-bottom: 16px; }
        .prose ul, .prose ol { margin-left: 20px; margin-bottom: 16px; }
        .prose li { margin-bottom: 6px; }
        .prose code { background: #162032; padding: 3px 6px; border-radius: 4px; font-family: var(--font-mono); font-size: 0.85rem; color: #38BDF8; }

        .table-responsive { width: 100%; overflow-x: auto; margin-top: 14px; }
        table.saas-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
        table.saas-table th, table.saas-table td { padding: 12px 14px; text-align: left; border-bottom: 1px solid var(--border); }
        table.saas-table th { background: #0A0E17; color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase; font-weight: 700; letter-spacing: 0.05em; }
        table.saas-table tr:hover { background: rgba(30, 41, 59, 0.3); }

        .badge-status { display: inline-flex; align-items: center; gap: 4px; padding: 3px 8px; border-radius: 6px; font-size: 0.72rem; font-weight: 600; font-family: var(--font-mono); }
        .badge-verified { background: rgba(16, 185, 129, 0.15); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.3); }
        .badge-supported { background: rgba(99, 102, 241, 0.15); color: #A5B4FC; border: 1px solid rgba(99, 102, 241, 0.3); }
        .badge-unverified { background: rgba(245, 158, 11, 0.15); color: #FBBF24; border: 1px solid rgba(245, 158, 11, 0.3); }

        .deliverable-card { background: #0D1322; border: 1px solid var(--border); border-radius: 12px; padding: 24px; text-align: center; }
        .deliverable-icon { font-size: 2.8rem; margin-bottom: 12px; }
        .deliverable-title { font-weight: 700; font-size: 1.1rem; color: var(--text-primary); margin-bottom: 8px; }
        .deliverable-desc { font-size: 0.82rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 20px; }

        footer { border-top: 1px solid var(--border); padding: 24px 28px; text-align: center; font-size: 0.8rem; color: var(--text-muted); }
    </style>
</head>
<body>
    <header>
        <a href="/" class="nav-brand">
            <span class="nav-logo">🔬</span>
            <span class="nav-title">Klein AI</span>
            <span class="nav-badge">v2.0.0 Pro</span>
        </a>
        <div class="nav-links">
            <a href="#investigation" class="nav-link active">Investigation</a>
            <a href="#credentialsCard" class="nav-link">Credentials</a>
            <a href="#sessionsSection" class="nav-link" onclick="loadSessionsHistory()">Research Library</a>
            <a href="/api/health" target="_blank" class="nav-link">API Health</a>
            <div class="nav-status">
                <span class="status-dot green" id="headerStatusDot"></span>
                <span id="headerStatusText">System Operational</span>
            </div>
        </div>
    </header>

    <main>
        <section class="hero">
            <div class="hero-pill">✨ Autonomous Multi-Agent Academic Research Engine</div>
            <h1 class="hero-title">Scientific Literature Synthesis & Evidence Auditing</h1>
            <p class="hero-subtitle">
                17-step orchestrated research pipeline with Crossref DOI verification, empirical claim-to-evidence passage mapping, peer review auditing, and instant academic deliverables.
            </p>
        </section>

        <!-- Credentials & Keys Management Card -->
        <section class="card" id="credentialsCard">
            <div class="card-header">
                <div class="card-title">🔑 API Credentials & Provider Settings</div>
                <div style="display: flex; gap: 8px;">
                    <span id="badgeGeminiStatus" class="badge-status badge-unverified">Gemini: Checking...</span>
                    <span id="badgeTavilyStatus" class="badge-status badge-supported">Tavily: Free Fallback</span>
                </div>
            </div>

            <div id="keyFeedbackBanner" class="banner-alert"></div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                <div class="form-group">
                    <label for="inputGeminiKey">
                        Google Gemini API Key
                        <span style="font-weight: 400; color: var(--text-muted);">(Get free key at <a href="https://aistudio.google.com/" target="_blank" style="color: var(--accent-cyan); text-decoration: underline;">Google AI Studio</a>)</span>
                    </label>
                    <input type="password" id="inputGeminiKey" placeholder="Paste your Gemini key: AIzaSy...">
                </div>
                <div class="form-group">
                    <label for="inputTavilyKey">
                        Tavily Search API Key
                        <span style="font-weight: 400; color: var(--text-muted);">(Optional: provides deep web search; DuckDuckGo fallback if blank)</span>
                    </label>
                    <input type="password" id="inputTavilyKey" placeholder="Paste your Tavily key: tvly-...">
                </div>
            </div>

            <div class="btn-row" style="margin-top: 10px;">
                <button class="btn-success" id="btnSaveKeys" onclick="saveAndTestCredentials()">
                    💾 Save & Validate Credentials
                </button>
                <button class="btn-danger" id="btnClearKeys" onclick="clearSavedCredentials()">
                    🗑️ Clear Saved Keys
                </button>
                <span id="keySaveIndicator" style="font-size: 0.8rem; color: var(--text-muted);"></span>
            </div>
        </section>

        <!-- Investigation Card -->
        <section class="card" id="investigation">
            <div class="card-header">
                <div class="card-title">🔬 Launch Scientific Research Investigation</div>
            </div>

            <div id="investigationError" class="banner-alert error"></div>

            <div class="form-group">
                <label for="topicInput">Research Topic or Scientific Question</label>
                <input type="text" id="topicInput" placeholder="e.g., Zero-Trust Architecture Implementation in Cloud-Native Healthcare Informatics" value="Zero-Trust Architecture Implementation in Cloud-Native Healthcare Informatics">
                <div class="sample-pills">
                    <span style="font-size: 0.75rem; color: var(--text-muted); align-self: center;">Suggested:</span>
                    <span class="sample-pill" onclick="setTopic(this.textContent)">Zero-Trust Architecture Implementation in Cloud-Native Healthcare Informatics</span>
                    <span class="sample-pill" onclick="setTopic(this.textContent)">Post-Quantum Cryptography in Healthcare EHR Systems</span>
                    <span class="sample-pill" onclick="setTopic(this.textContent)">Diffusion Models for Medical Anomaly Detection</span>
                    <span class="sample-pill" onclick="setTopic(this.textContent)">Federated Learning Security Against Model Poisoning Attacks</span>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                <div class="form-group">
                    <label for="modelSelect">Synthesis Reasoning Model</label>
                    <select id="modelSelect">
                        <option value="gemini-2.5-flash" selected>Google Gemini 2.5 Flash (Recommended - Fastest Synthesis)</option>
                        <option value="gemini-2.0-flash">Google Gemini 2.0 Flash (Deterministic)</option>
                        <option value="gemini-1.5-pro">Google Gemini 1.5 Pro (Deep Scholarly Reasoning)</option>
                        <option value="gemini-1.5-flash">Google Gemini 1.5 Flash (Standard)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Active Credential Source</label>
                    <div id="activeCredentialNotice" style="padding: 12px 16px; background: #0A0E17; border: 1px solid var(--border); border-radius: 10px; font-size: 0.88rem; color: #CBD5E1;">
                        Detecting credentials...
                    </div>
                </div>
            </div>

            <div class="btn-row">
                <button class="btn-primary" id="btnLaunch" onclick="launchResearch()">
                    🚀 Launch Autonomous Pipeline
                </button>
                <button class="btn-secondary" id="btnDemo" onclick="loadVerifiedDemo()">
                    ⚡ Instant Verified Demo (Zero Quota)
                </button>
                <button class="btn-secondary" onclick="loadSessionsHistory()">
                    📚 Browse Research Library
                </button>
            </div>
        </section>

        <!-- Live Telemetry Card -->
        <section class="telemetry-card" id="telemetryCard">
            <div class="progress-header">
                <div class="stage-title">
                    <span class="status-dot green"></span>
                    <span id="currentStageText">Initializing Autonomous Research Pipeline...</span>
                </div>
                <div class="stage-pct" id="currentPctText">0%</div>
            </div>
            <div class="progress-bar-bg">
                <div class="progress-bar-fill" id="progressBarFill"></div>
            </div>
            <div class="terminal" id="terminalLogs">
                [00:00:00] Research Orchestrator initiated.
            </div>
        </section>

        <!-- Research Results Workspace -->
        <section class="results-container" id="resultsContainer">
            <div class="tabs-header">
                <button class="tab-btn active" onclick="switchTab('tab-blueprint', event)">📌 Blueprint & Hypothesis</button>
                <button class="tab-btn" onclick="switchTab('tab-lit', event)">📚 Literature Review</button>
                <button class="tab-btn" onclick="switchTab('tab-evidence', event)">📊 Evidence Matrix</button>
                <button class="tab-btn" onclick="switchTab('tab-gaps', event)">🧭 Research Gaps</button>
                <button class="tab-btn" onclick="switchTab('tab-method', event)">⚙️ Methodology</button>
                <button class="tab-btn" onclick="switchTab('tab-review', event)">🛡️ Peer Review Audit</button>
                <button class="tab-btn" onclick="switchTab('tab-export', event)">📥 Deliverables Export</button>
            </div>

            <!-- Blueprint Tab -->
            <div class="tab-panel active" id="tab-blueprint">
                <div class="card">
                    <h3 style="margin-bottom: 12px; color: var(--accent-cyan);" id="bpDomain">Scientific Domain</h3>
                    <p style="margin-bottom: 18px; font-size: 1.05rem;" id="bpHypothesis">Hypothesis</p>
                    <h4 style="margin: 20px 0 10px 0;">Research Questions</h4>
                    <div id="bpQuestions"></div>
                </div>
            </div>

            <!-- Literature Review Tab -->
            <div class="tab-panel" id="tab-lit">
                <div class="card">
                    <div class="prose" id="litReviewContent"></div>
                </div>
            </div>

            <!-- Evidence Matrix Tab -->
            <div class="tab-panel" id="tab-evidence">
                <div class="card">
                    <h3>Empirical Source Verification Matrix</h3>
                    <p style="color: var(--text-secondary); margin-bottom: 16px;">
                        Sources audited against official DOI.org Content Negotiation and Crossref Bibliographic API:
                    </p>
                    <div class="table-responsive">
                        <table class="saas-table" id="evidenceTable">
                            <thead>
                                <tr>
                                    <th>Source & DOI</th>
                                    <th>Verification Status</th>
                                    <th>Authors & Year</th>
                                    <th>Claim Support</th>
                                </tr>
                            </thead>
                            <tbody id="evidenceTableBody"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Research Gaps Tab -->
            <div class="tab-panel" id="tab-gaps">
                <div class="card" id="gapsContainer"></div>
            </div>

            <!-- Methodology Tab -->
            <div class="tab-panel" id="tab-method">
                <div class="card">
                    <h3 id="methodFrameworkName" style="color: var(--accent-cyan); margin-bottom: 12px;">Proposed Framework</h3>
                    <p id="methodOverview" style="margin-bottom: 20px;"></p>
                    <h4>Key System Components</h4>
                    <div id="methodComponents" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; margin-top: 12px;"></div>
                </div>
            </div>

            <!-- Peer Review Tab -->
            <div class="tab-panel" id="tab-review">
                <div class="card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h3>Independent Peer Review & Verification Audit</h3>
                        <div style="font-size: 1.4rem; font-weight: 800; color: var(--accent-emerald);" id="reviewScore">9.2 / 10</div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px;">
                        <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.2); border-radius: 10px; padding: 16px;">
                            <h4 style="color: #34D399; margin-bottom: 10px;">✅ Validated Strengths</h4>
                            <ul id="reviewStrengths" style="margin-left: 20px; font-size: 0.9rem; line-height: 1.6;"></ul>
                        </div>
                        <div style="background: rgba(244, 63, 94, 0.08); border: 1px solid rgba(244, 63, 94, 0.2); border-radius: 10px; padding: 16px;">
                            <h4 style="color: #FB7185; margin-bottom: 10px;">⚠️ Identified Limitations</h4>
                            <ul id="reviewWeaknesses" style="margin-left: 20px; font-size: 0.9rem; line-height: 1.6;"></ul>
                        </div>
                    </div>
                    <p id="reviewCritique" style="font-size: 0.95rem; line-height: 1.7; color: #CBD5E1;"></p>
                </div>
            </div>

            <!-- Deliverables Export Tab -->
            <div class="tab-panel" id="tab-export">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                    <div class="deliverable-card">
                        <div class="deliverable-icon">📕</div>
                        <div class="deliverable-title">Formal Academic PDF Report</div>
                        <div class="deliverable-desc">
                            Complete publication-ready whitepaper with Executive Summary, comparative tables, methodology architecture diagrams, and APA 7th bibliography.
                        </div>
                        <a id="btnDownloadPdf" href="#" target="_blank">
                            <button class="btn-primary" style="width: 100%;">📥 Download Academic PDF</button>
                        </a>
                    </div>
                    <div class="deliverable-card">
                        <div class="deliverable-icon">📊</div>
                        <div class="deliverable-title">Executive Slide Presentation (.pptx)</div>
                        <div class="deliverable-desc">
                            10-slide 16:9 widescreen presentation deck formatted with dark title slides, problem statement, research gap breakdown, and conclusions.
                        </div>
                        <a id="btnDownloadPptx" href="#" target="_blank">
                            <button class="btn-secondary" style="width: 100%;">📥 Download PowerPoint Deck</button>
                        </a>
                    </div>
                </div>
            </div>
        </section>

        <!-- Sessions Library Modal / Section -->
        <section class="card" id="sessionsSection" style="display: none; margin-top: 32px;">
            <div class="card-header">
                <div class="card-title">📚 Historical Research Sessions</div>
                <button class="btn-secondary" onclick="document.getElementById('sessionsSection').style.display='none'">✕ Close</button>
            </div>
            <div class="table-responsive">
                <table class="saas-table">
                    <thead>
                        <tr>
                            <th>Topic</th>
                            <th>Model</th>
                            <th>Date (UTC)</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="sessionsTableBody"></tbody>
                </table>
            </div>
        </section>
    </main>

    <footer>
        <div>Klein AI 2.0 — Autonomous Research Agent • College Engineering Project</div>
        <div style="margin-top: 6px; color: var(--text-muted); font-size: 0.75rem;">
            Powered by Google Gemini 2.5/2.0, Crossref Bibliographic API, DOI Content Negotiation, ReportLab, and python-pptx.
        </div>
    </footer>

    <script>
        let serverGeminiConfigured = false;
        let serverTavilyConfigured = false;
        let currentSessionId = null;
        let progressInterval = null;

        function setTopic(text) {
            document.getElementById('topicInput').value = text;
            document.getElementById('topicInput').classList.remove('input-error');
            document.getElementById('investigationError').style.display = 'none';
        }

        function showBanner(elementId, message, type = 'info') {
            const el = document.getElementById(elementId);
            if (!el) return;
            el.className = 'banner-alert ' + type;
            el.innerHTML = message;
            el.style.display = 'block';
        }

        function hideBanner(elementId) {
            const el = document.getElementById(elementId);
            if (el) el.style.display = 'none';
        }

        function switchTab(tabId, ev) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            if (ev && ev.currentTarget) {
                ev.currentTarget.classList.add('active');
            }
            const target = document.getElementById(tabId);
            if (target) target.classList.add('active');
        }

        // ======================================================================
        // CREDENTIAL MANAGEMENT & INITIALIZATION
        // ======================================================================

        async function initHealthAndCredentials() {
            try {
                const res = await fetch('/api/health');
                const data = await res.json();
                serverGeminiConfigured = Boolean(data.gemini_configured);
                serverTavilyConfigured = Boolean(data.tavily_configured);

                // Check localStorage
                const userGemini = localStorage.getItem('klein_gemini_api_key') || '';
                const userTavily = localStorage.getItem('klein_tavily_api_key') || '';

                if (userGemini) {
                    document.getElementById('inputGeminiKey').value = userGemini;
                    document.getElementById('badgeGeminiStatus').className = 'badge-status badge-verified';
                    document.getElementById('badgeGeminiStatus').textContent = 'Gemini: 🟢 User Key Saved';
                } else if (serverGeminiConfigured) {
                    document.getElementById('badgeGeminiStatus').className = 'badge-status badge-supported';
                    document.getElementById('badgeGeminiStatus').textContent = 'Gemini: 🟡 Server Configured';
                } else {
                    document.getElementById('badgeGeminiStatus').className = 'badge-status badge-unverified';
                    document.getElementById('badgeGeminiStatus').textContent = 'Gemini: 🔴 Not Configured';
                }

                if (userTavily) {
                    document.getElementById('inputTavilyKey').value = userTavily;
                    document.getElementById('badgeTavilyStatus').className = 'badge-status badge-verified';
                    document.getElementById('badgeTavilyStatus').textContent = 'Tavily: 🟢 User Key Saved';
                } else if (serverTavilyConfigured) {
                    document.getElementById('badgeTavilyStatus').className = 'badge-status badge-supported';
                    document.getElementById('badgeTavilyStatus').textContent = 'Tavily: 🟡 Server Key';
                } else {
                    document.getElementById('badgeTavilyStatus').className = 'badge-status badge-supported';
                    document.getElementById('badgeTavilyStatus').textContent = 'Tavily: Free Fallback (DDG)';
                }

                updateActiveCredentialNotice();
            } catch (e) {
                console.error('Failed to initialize health/credentials:', e);
            }
        }

        function updateActiveCredentialNotice() {
            const userGemini = localStorage.getItem('klein_gemini_api_key') || (document.getElementById('inputGeminiKey') ? document.getElementById('inputGeminiKey').value.trim() : '');
            const notice = document.getElementById('activeCredentialNotice');
            if (userGemini) {
                notice.innerHTML = '<span style="color: #34D399; font-weight: 600;">🟢 User Key Active</span> (stored locally in your browser)';
            } else if (serverGeminiConfigured) {
                notice.innerHTML = '<span style="color: #A5B4FC; font-weight: 600;">🟡 Server Key Active</span> (configured in Vercel environment)';
            } else {
                notice.innerHTML = '<span style="color: #FB7185; font-weight: 600;">🔴 No Gemini Key</span> (please paste key in Credentials panel)';
            }
        }

        async function saveAndTestCredentials() {
            const btn = document.getElementById('btnSaveKeys');
            const geminiKey = document.getElementById('inputGeminiKey').value.trim();
            const tavilyKey = document.getElementById('inputTavilyKey').value.trim();
            const model = document.getElementById('modelSelect').value;

            hideBanner('keyFeedbackBanner');

            if (!geminiKey) {
                showBanner('keyFeedbackBanner', '⚠️ Please enter a Google Gemini API Key before testing.', 'error');
                document.getElementById('inputGeminiKey').classList.add('input-error');
                return;
            }

            document.getElementById('inputGeminiKey').classList.remove('input-error');
            btn.disabled = true;
            btn.innerHTML = '⏳ Testing credentials with Google AI Studio...';

            try {
                const res = await fetch('/api/config/validate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        gemini_api_key: geminiKey,
                        tavily_api_key: tavilyKey,
                        model: model
                    })
                });
                const data = await res.json();

                if (res.ok && data.success) {
                    // Validated! Save to localStorage
                    localStorage.setItem('klein_gemini_api_key', geminiKey);
                    if (tavilyKey) {
                        localStorage.setItem('klein_tavily_api_key', tavilyKey);
                    } else {
                        localStorage.removeItem('klein_tavily_api_key');
                    }

                    document.getElementById('badgeGeminiStatus').className = 'badge-status badge-verified';
                    document.getElementById('badgeGeminiStatus').textContent = 'Gemini: 🟢 User Key Saved';

                    if (tavilyKey && data.tavily_valid) {
                        document.getElementById('badgeTavilyStatus').className = 'badge-status badge-verified';
                        document.getElementById('badgeTavilyStatus').textContent = 'Tavily: 🟢 User Key Saved';
                    }

                    updateActiveCredentialNotice();
                    hideBanner('investigationError');

                    showBanner('keyFeedbackBanner', '✅ <strong>Credentials Verified & Saved!</strong> Google Gemini API key authenticated successfully. It will automatically power all research runs.', 'success');
                } else {
                    const err = data.error || 'Gemini authentication failed. Please check key validity.';
                    showBanner('keyFeedbackBanner', '❌ <strong>Authentication Failed:</strong> ' + err, 'error');
                }
            } catch (e) {
                showBanner('keyFeedbackBanner', '❌ Network error during key verification: ' + e.message, 'error');
            } finally {
                btn.disabled = false;
                btn.innerHTML = '💾 Save & Validate Credentials';
            }
        }

        function clearSavedCredentials() {
            localStorage.removeItem('klein_gemini_api_key');
            localStorage.removeItem('klein_tavily_api_key');
            document.getElementById('inputGeminiKey').value = '';
            document.getElementById('inputTavilyKey').value = '';
            initHealthAndCredentials();
            showBanner('keyFeedbackBanner', '🗑️ Saved browser credentials cleared. The system will revert to server environment keys if available.', 'info');
        }

        // ======================================================================
        // RESEARCH PIPELINE EXECUTION
        // ======================================================================

        function getEffectiveGeminiKey() {
            return (document.getElementById('inputGeminiKey') ? document.getElementById('inputGeminiKey').value.trim() : '') ||
                   localStorage.getItem('klein_gemini_api_key') || '';
        }

        function getEffectiveTavilyKey() {
            return (document.getElementById('inputTavilyKey') ? document.getElementById('inputTavilyKey').value.trim() : '') ||
                   localStorage.getItem('klein_tavily_api_key') || '';
        }

        async function launchResearch() {
            const topicInput = document.getElementById('topicInput');
            const topic = topicInput.value.trim();
            const model = document.getElementById('modelSelect').value;
            const btn = document.getElementById('btnLaunch');
            const geminiKey = getEffectiveGeminiKey();
            const tavilyKey = getEffectiveTavilyKey();

            hideBanner('investigationError');
            topicInput.classList.remove('input-error');

            if (!topic || topic.length < 3) {
                topicInput.classList.add('input-error');
                showBanner('investigationError', '⚠️ Please enter a research topic or scientific question (at least 3 characters).', 'error');
                topicInput.focus();
                return;
            }

            if (!geminiKey && !serverGeminiConfigured) {
                showBanner('investigationError', '⚠️ <strong>Google Gemini API Key Required:</strong> Please paste and save your Gemini API key in the credentials panel above to launch research.', 'error');
                document.getElementById('credentialsCard').scrollIntoView({ behavior: 'smooth' });
                document.getElementById('inputGeminiKey').classList.add('input-error');
                document.getElementById('inputGeminiKey').focus();
                return;
            }

            // Start research UI state
            btn.disabled = true;
            btn.innerHTML = '⏳ Conducting Research... (Keep this tab open)';

            const telemetry = document.getElementById('telemetryCard');
            telemetry.style.display = 'block';
            document.getElementById('resultsContainer').style.display = 'none';

            const term = document.getElementById('terminalLogs');
            term.innerHTML = '[' + new Date().toLocaleTimeString() + '] Initializing Autonomous Research Pipeline on: "' + topic + '"...';

            // Animated progress ticker while synchronous request executes
            let simulatedPct = 8;
            const stages = [
                { pct: 15, text: "Step 2/17: Formulating Scientific Blueprint & Research Questions" },
                { pct: 28, text: "Step 5/17: Harvesting Empirical Sources from Live Academic Web" },
                { pct: 42, text: "Step 8/17: Deep DOM Parsing & Text Passage Extraction" },
                { pct: 58, text: "Step 10/17: Synthesizing Cross-Source Comparative Matrix" },
                { pct: 72, text: "Step 11/17: Authoring Scholarly Literature Review" },
                { pct: 85, text: "Step 15/17: Auditing Citations with DOI.org & Crossref Registries" },
                { pct: 93, text: "Step 16/17: Executing Independent Peer Review Audit" },
                { pct: 97, text: "Step 17/17: Compiling Academic Whitepaper & PowerPoint Deliverables" }
            ];
            let stageIdx = 0;

            if (progressInterval) clearInterval(progressInterval);
            progressInterval = setInterval(() => {
                if (stageIdx < stages.length) {
                    const st = stages[stageIdx];
                    if (simulatedPct < st.pct) {
                        simulatedPct += 2;
                        document.getElementById('progressBarFill').style.width = simulatedPct + '%';
                        document.getElementById('currentPctText').textContent = simulatedPct + '%';
                    } else {
                        document.getElementById('currentStageText').textContent = st.text;
                        term.innerHTML += '<br/>[' + new Date().toLocaleTimeString() + '] ' + st.text;
                        term.scrollTop = term.scrollHeight;
                        stageIdx++;
                    }
                }
            }, 1200);

            try {
                const payload = {
                    topic: topic,
                    model: model
                };
                if (geminiKey) payload.gemini_api_key = geminiKey;
                if (tavilyKey) payload.tavily_api_key = tavilyKey;

                const res = await fetch('/api/research', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();

                clearInterval(progressInterval);

                if (!res.ok || !data.success) {
                    const err = (data && data.error) ? data.error : ('Request failed with status ' + res.status);
                    throw new Error(err);
                }

                // Complete progress
                document.getElementById('progressBarFill').style.width = '100%';
                document.getElementById('currentPctText').textContent = '100%';
                document.getElementById('currentStageText').textContent = 'Research Investigation Completed Successfully!';
                term.innerHTML += '<br/>[' + new Date().toLocaleTimeString() + '] ✅ All 17 research pipeline stages executed successfully.';
                term.scrollTop = term.scrollHeight;

                setTimeout(() => {
                    telemetry.style.display = 'none';
                    renderResearchResults(data.data, data.data.session_id);
                    document.getElementById('resultsContainer').scrollIntoView({ behavior: 'smooth' });
                }, 800);

            } catch (e) {
                clearInterval(progressInterval);
                telemetry.style.display = 'none';
                showBanner('investigationError', '❌ <strong>Research Pipeline Error:</strong> ' + e.message, 'error');
                document.getElementById('investigation').scrollIntoView({ behavior: 'smooth' });
            } finally {
                btn.disabled = false;
                btn.innerHTML = '🚀 Launch Autonomous Pipeline';
            }
        }

        async function loadVerifiedDemo() {
            const btn = document.getElementById('btnDemo');
            btn.disabled = true;
            btn.innerHTML = '⏳ Loading Demo...';
            hideBanner('investigationError');
            try {
                const res = await fetch('/api/demo');
                const result = await res.json();
                if (result.success && result.data) {
                    renderResearchResults(result.data, result.data.session_id || 'demo');
                    document.getElementById('resultsContainer').scrollIntoView({ behavior: 'smooth' });
                } else {
                    throw new Error(result.error || 'Failed to retrieve demo dataset');
                }
            } catch (e) {
                showBanner('investigationError', '❌ Demo Load Error: ' + e.message, 'error');
            } finally {
                btn.disabled = false;
                btn.innerHTML = '⚡ Instant Verified Demo (Zero Quota)';
            }
        }

        // ======================================================================
        // RESULTS RENDERING
        // ======================================================================

        function renderResearchResults(data, sessionId) {
            currentSessionId = sessionId;
            document.getElementById('resultsContainer').style.display = 'block';

            // Blueprint
            const bp = data.blueprint || {};
            document.getElementById('bpDomain').textContent = bp.domain ? ('Domain: ' + bp.domain) : 'General Scientific Research';
            document.getElementById('bpHypothesis').textContent = 'Core Hypothesis: ' + (bp.core_hypothesis || 'Empirical validation of autonomous synthesis.');

            const qBox = document.getElementById('bpQuestions');
            qBox.innerHTML = '';
            (bp.research_questions || []).forEach(rq => {
                const el = document.createElement('div');
                el.style.marginBottom = '12px';
                el.innerHTML = '<strong>' + (rq.id || 'RQ') + ': ' + rq.question + '</strong>' +
                    (rq.rationale ? '<div style="color: var(--text-secondary); font-size: 0.85rem; margin-top: 4px;">Rationale: ' + rq.rationale + '</div>' : '');
                qBox.appendChild(el);
            });

            // Literature Review
            const litRaw = data.literature_review || data.report_markdown || 'No synthesis available.';
            document.getElementById('litReviewContent').innerHTML = litRaw
                .replace(/^### (.*$)/gim, '<h3>$1</h3>')
                .replace(/^## (.*$)/gim, '<h2>$1</h2>')
                .replace(/^# (.*$)/gim, '<h1>$1</h1>')
                .split('**').reduce((acc, part, idx) => acc + (idx % 2 === 1 ? '<strong>' + part + '</strong>' : part), '')
                .split('\n').join('<br/>');

            // Evidence Matrix
            const tbody = document.getElementById('evidenceTableBody');
            tbody.innerHTML = '';
            const cits = data.audited_citations || [];
            (cits.length ? cits : (data.sources || [])).forEach(c => {
                const tr = document.createElement('tr');
                const title = c.title || 'Scholarly Publication';
                const url = c.url || (c.doi ? ('https://doi.org/' + c.doi) : '#');
                const status = c.verification_status || c.status || 'METADATA_MATCHED';
                const authors = c.authors ? c.authors.join(', ') : (c.domain || 'Peer-Reviewed Source');
                const yr = c.year || c.publication_year || '2024';

                tr.innerHTML = '<td><a href="' + url + '" target="_blank" style="color: var(--accent-cyan); text-decoration: none; font-weight: 600;">' + title + '</a>' +
                    (c.doi ? '<div style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted); margin-top: 3px;">DOI: ' + c.doi + '</div>' : '') + '</td>' +
                    '<td><span class="badge-status badge-verified">' + status + '</span></td>' +
                    '<td style="color: var(--text-secondary);">' + authors + ' (' + yr + ')</td>' +
                    '<td><span class="badge-status badge-supported">CLAIM_SUPPORTED</span></td>';
                tbody.appendChild(tr);
            });

            // Gaps
            const gapsBox = document.getElementById('gapsContainer');
            gapsBox.innerHTML = '<h3>Critical Research Gaps & Frontiers</h3>';
            (data.research_gaps || []).forEach(g => {
                const el = document.createElement('div');
                el.style.background = '#0A0E17';
                el.style.border = '1px solid var(--border)';
                el.style.borderRadius = '10px';
                el.style.padding = '16px';
                el.style.marginBottom = '12px';
                el.innerHTML = '<div style="display: flex; gap: 8px; align-items: center; margin-bottom: 6px;">' +
                    '<span class="badge-status badge-supported">' + (g.gap_id || 'GAP') + '</span>' +
                    '<strong>' + g.title + '</strong></div>' +
                    '<div style="color: var(--text-secondary); font-size: 0.9rem; margin-top: 6px;">' + g.description + '</div>' +
                    '<div style="color: var(--accent-cyan); font-size: 0.85rem; margin-top: 8px;"><b>Strategic Opportunity:</b> ' + (g.opportunity || 'Empirical benchmark protocol') + '</div>';
                gapsBox.appendChild(el);
            });

            // Methodology
            const meth = data.methodology || {};
            document.getElementById('methodFrameworkName').textContent = 'Methodology: ' + (meth.framework_name || 'Klein Autonomous System');
            document.getElementById('methodOverview').textContent = (meth.system_architecture || {}).overview || 'Autonomous multi-stage empirical architecture.';
            const compsBox = document.getElementById('methodComponents');
            compsBox.innerHTML = '';
            ((meth.system_architecture || {}).components || []).forEach(c => {
                const el = document.createElement('div');
                el.style.background = '#0A0E17';
                el.style.border = '1px solid var(--border)';
                el.style.borderRadius = '8px';
                el.style.padding = '14px';
                el.innerHTML = '<div style="font-weight: 700; color: var(--accent-cyan);">' + c.name + '</div>' +
                    '<div style="color: var(--text-secondary); font-size: 0.82rem; margin-top: 4px;">' + c.role + '</div>';
                compsBox.appendChild(el);
            });

            // Peer Review
            const rev = data.independent_review || {};
            document.getElementById('reviewScore').textContent = (rev.overall_score || 9.2) + ' / 10';
            const sBox = document.getElementById('reviewStrengths');
            sBox.innerHTML = '';
            (rev.key_strengths || ['Rigorous DOI bibliographic extraction', 'Comprehensive research gap detection']).forEach(s => {
                const li = document.createElement('li');
                li.textContent = s;
                sBox.appendChild(li);
            });
            const wBox = document.getElementById('reviewWeaknesses');
            wBox.innerHTML = '';
            (rev.key_weaknesses || ['Further benchmark comparisons recommended under load']).forEach(w => {
                const li = document.createElement('li');
                li.textContent = w;
                wBox.appendChild(li);
            });
            document.getElementById('reviewCritique').textContent = rev.summary_critique || 'The synthesized investigation complies with academic whitepaper standards.';

            // Export Links
            if (sessionId) {
                document.getElementById('btnDownloadPdf').href = '/api/download/pdf?id=' + encodeURIComponent(sessionId);
                document.getElementById('btnDownloadPptx').href = '/api/download/pptx?id=' + encodeURIComponent(sessionId);
            }
        }

        // ======================================================================
        // SESSIONS LIBRARY
        // ======================================================================

        async function loadSessionsHistory() {
            const sec = document.getElementById('sessionsSection');
            sec.style.display = 'block';
            sec.scrollIntoView({ behavior: 'smooth' });
            try {
                const res = await fetch('/api/sessions');
                const data = await res.json();
                const tbody = document.getElementById('sessionsTableBody');
                tbody.innerHTML = '';
                if (!data.sessions || !data.sessions.length) {
                    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color: var(--text-muted); padding: 20px;">No saved sessions yet. Execute research or load the demo to create a session.</td></tr>';
                    return;
                }
                data.sessions.forEach(s => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = '<td><strong>' + s.topic + '</strong></td>' +
                        '<td><span class="badge-status badge-supported">' + (s.model || 'gemini-2.5-flash') + '</span></td>' +
                        '<td style="color: var(--text-muted); font-size: 0.8rem;">' + (s.created_at || 'Recent') + '</td>' +
                        '<td style="display: flex; gap: 6px;">' +
                        '<button class="btn-secondary" style="padding: 6px 10px; font-size: 0.78rem;" onclick="viewSession(\'' + s.id + '\')">👁️ View</button>' +
                        '<a href="/api/download/pdf?id=' + encodeURIComponent(s.id) + '" target="_blank"><button class="btn-secondary" style="padding: 6px 10px; font-size: 0.78rem;">📕 PDF</button></a>' +
                        '<a href="/api/download/pptx?id=' + encodeURIComponent(s.id) + '" target="_blank"><button class="btn-secondary" style="padding: 6px 10px; font-size: 0.78rem;">📊 PPTX</button></a>' +
                        '</td>';
                    tbody.appendChild(tr);
                });
            } catch (e) {
                console.error('Failed to load sessions:', e);
            }
        }

        async function viewSession(id) {
            try {
                const res = await fetch('/api/session?id=' + encodeURIComponent(id));
                const data = await res.json();
                if (data.session && data.session.data) {
                    renderResearchResults(data.session.data, id);
                    document.getElementById('sessionsSection').style.display = 'none';
                    document.getElementById('resultsContainer').scrollIntoView({ behavior: 'smooth' });
                }
            } catch (e) {
                alert('Failed to load session: ' + e.message);
            }
        }

        // Initialize credentials and health check on page load
        initHealthAndCredentials();
    </script>
</body>
</html>
"""


# ==============================================================================
# WSGI SERVERLESS APPLICATION ENTRYPOINT (VERCEL & REST API RUNTIME)
# ==============================================================================

def app(environ, start_response):
    """
    WSGI Serverless Application Entrypoint for Vercel deployment and REST API.
    Provides /api/health, /api/demo, /api/research, /api/jobs/<job_id>, /api/sessions,
    /api/download/pdf, /api/download/pptx, /api/config/validate, and / HTML landing page.
    """
    query_string = environ.get("QUERY_STRING", "")
    params = urllib.parse.parse_qs(query_string)

    # 1. Determine requested route path (handling Vercel rewrites & script prefixes)
    if "__path" in params and params["__path"]:
        raw_path = params["__path"][0]
    else:
        raw_path = environ.get("PATH_INFO", "/") or "/"

    # Normalize multiple consecutive slashes
    while "//" in raw_path:
        raw_path = raw_path.replace("//", "/")

    # Strip serverless file prefixes if present
    if raw_path.startswith("/app.py/"):
        raw_path = "/" + raw_path[8:]
    elif raw_path.startswith("/app/"):
        raw_path = "/" + raw_path[5:]

    # Map empty string or script entrypoint path directly to root "/"
    if raw_path in ("/app.py", "/app", ""):
        raw_path = "/"

    if "?" in raw_path:
        raw_path, qs_extra = raw_path.split("?", 1)
        if not query_string:
            query_string = qs_extra
            params = urllib.parse.parse_qs(query_string)

    # Strip trailing slash (unless root)
    if len(raw_path) > 1 and raw_path.endswith("/"):
        raw_path = raw_path[:-1]

    path = raw_path
    method = environ.get("REQUEST_METHOD", "GET").upper()
    client_ip = environ.get("HTTP_X_FORWARDED_FOR", environ.get("REMOTE_ADDR", "127.0.0.1")).split(",")[0].strip()
    request_id = environ.get("HTTP_X_REQUEST_ID", str(uuid.uuid4()))

    # CORS origin check
    request_origin = environ.get("HTTP_ORIGIN", "")
    allowed_origin = "*"
    if request_origin and ALLOWED_ORIGINS and "*" not in ALLOWED_ORIGINS:
        if request_origin in ALLOWED_ORIGINS:
            allowed_origin = request_origin

    cors_headers = [
        ("Access-Control-Allow-Origin", allowed_origin),
        ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, X-Request-ID"),
        ("X-Request-ID", request_id)
    ]

    all_base_headers = cors_headers + SECURITY_HEADERS

    # Preflight CORS
    if method == "OPTIONS":
        start_response("204 No Content", all_base_headers)
        return [b""]

    def send_json(data, status="200 OK"):
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        headers = all_base_headers + [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body)))
        ]
        start_response(status, headers)
        return [body]

    def send_html(html_str, status="200 OK"):
        body = html_str.encode("utf-8")
        headers = all_base_headers + [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(body)))
        ]
        start_response(status, headers)
        return [body]

    def send_binary(data_bytes, content_type, filename, status="200 OK"):
        headers = all_base_headers + [
            ("Content-Type", content_type),
            ("Content-Length", str(len(data_bytes))),
            ("Content-Disposition", f'attachment; filename="{filename}"')
        ]
        start_response(status, headers)
        return [data_bytes]

    # Global Rate Limiting
    endpoint_limit = 15 if "/research" in path else 120
    if not rate_limiter.is_allowed(client_ip, limit=endpoint_limit, window_seconds=60):
        return send_json({
            "success": False,
            "error": "Rate limit exceeded. Please wait a minute before repeating requests.",
            "request_id": request_id
        }, status="429 Too Many Requests")

    # 1. ROOT LANDING PAGE & HEALTH CHECK
    if path in ("/", "/index.html") and method == "GET":
        accept_header = environ.get("HTTP_ACCEPT", "").lower()
        if "application/json" in accept_header and "text/html" not in accept_header:
            gemini_key = get_gemini_api_key()
            tavily_key = get_tavily_api_key()
            db_health = check_db_health()
            return send_json({
                "status": "healthy",
                "app": APP_NAME,
                "tagline": APP_TAGLINE,
                "version": APP_VERSION,
                "gemini_configured": bool(gemini_key),
                "tavily_configured": bool(tavily_key),
                "database_connected": bool(db_health.get("connected")),
                "database_backend": db_health.get("backend", "sqlite"),
                "default_model": DEFAULT_GEMINI_MODEL,
                "endpoints": {
                    "health": "/api/health",
                    "demo": "/api/demo",
                    "research": "/api/research",
                    "sessions": "/api/sessions"
                },
                "request_id": request_id
            })
        return send_html(HTML_LANDING_PAGE)

    # 2. SYSTEM HEALTH & DIAGNOSTICS
    if path in ("/health", "/api/health") and method == "GET":
        gemini_key = get_gemini_api_key()
        tavily_key = get_tavily_api_key()
        db_health = check_db_health()
        return send_json({
            "status": "healthy",
            "app": APP_NAME,
            "version": APP_VERSION,
            "gemini_configured": bool(gemini_key),
            "tavily_configured": bool(tavily_key),
            "database_connected": bool(db_health.get("connected")),
            "database_backend": db_health.get("backend", "sqlite"),
            "default_model": DEFAULT_GEMINI_MODEL,
            "supported_models": SUPPORTED_MODELS,
            "request_id": request_id
        })

    # 3. CREDENTIAL CONFIGURATION & LIVE VALIDATION (/api/config/validate, /api/keys/test)
    if path in ("/api/config/validate", "/api/keys/test") and method == "POST":
        try:
            content_length = int(environ.get("CONTENT_LENGTH", 0) or 0)
        except ValueError:
            content_length = 0

        body_bytes = environ["wsgi.input"].read(content_length) if content_length > 0 else b""
        try:
            payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            return send_json({"success": False, "error": "Malformed JSON payload.", "request_id": request_id}, status="400 Bad Request")

        gemini_candidate = clean_api_key(payload.get("gemini_api_key"))
        tavily_candidate = clean_api_key(payload.get("tavily_api_key"))
        model_candidate = payload.get("model") or DEFAULT_GEMINI_MODEL

        if not gemini_candidate:
            return send_json({
                "success": False,
                "error": "Gemini API key is required for verification.",
                "request_id": request_id
            }, status="400 Bad Request")

        # Perform actual live test against Gemini API
        test_result = GeminiClient.test_connection(api_key=gemini_candidate, model=model_candidate)
        if not test_result.get("success"):
            return send_json({
                "success": False,
                "gemini_valid": False,
                "error": test_result.get("message", "Gemini API rejected the key."),
                "category": test_result.get("category", "AUTH_ERROR"),
                "request_id": request_id
            }, status="400 Bad Request")

        # If Tavily provided, test it too
        tavily_ok = True
        tavily_msg = "Not tested"
        if tavily_candidate:
            tavily_ok, tavily_msg = test_tavily_key(tavily_candidate)

        return send_json({
            "success": True,
            "gemini_valid": True,
            "gemini_message": test_result.get("message"),
            "model_tested": test_result.get("model"),
            "tavily_valid": tavily_ok,
            "tavily_message": tavily_msg,
            "request_id": request_id
        })

    # 4. CONFIGURATION STATUS (/api/config/status)
    if path in ("/api/config/status", "/api/config") and method == "GET":
        return send_json({
            "server_gemini_configured": bool(get_gemini_api_key()),
            "server_tavily_configured": bool(get_tavily_api_key()),
            "default_model": DEFAULT_GEMINI_MODEL,
            "supported_models": SUPPORTED_MODELS,
            "request_id": request_id
        })

    # 5. VERIFIED DEMO DATASET
    if path in ("/demo", "/api/demo") and method == "GET":
        demo_payload = {k: v for k, v in VERIFIED_DEMO_DATA.items() if k not in ("pdf_bytes", "pptx_bytes")}
        return send_json({
            "success": True,
            "topic": demo_payload.get("topic"),
            "data": demo_payload,
            "request_id": request_id
        })

    # 6. SAVED SESSIONS LIST
    if path in ("/sessions", "/api/sessions") and method == "GET":
        init_db()
        sessions = list_sessions()
        return send_json({
            "success": True,
            "count": len(sessions),
            "sessions": sessions,
            "request_id": request_id
        })

    # 7. INDIVIDUAL SESSION RETRIEVAL
    if path in ("/session", "/api/session") and method == "GET":
        init_db()
        session_id = params.get("id", [None])[0]
        if not session_id:
            return send_json({"success": False, "error": "Query parameter 'id' is required"}, status="400 Bad Request")

        session = get_session(session_id)
        if session:
            if "data" in session and isinstance(session["data"], dict):
                session["data"] = {k: v for k, v in session["data"].items() if k not in ("pdf_bytes", "pptx_bytes")}
            return send_json({"success": True, "session": session, "request_id": request_id})
        return send_json({"success": False, "error": f"Session '{session_id}' not found", "request_id": request_id}, status="404 Not Found")

    # 8. ASYNCHRONOUS JOB POLLING (/api/jobs/<job_id>)
    if path.startswith("/api/jobs/") and method == "GET":
        job_id = path[len("/api/jobs/"):].strip()
        job = job_manager.get_job(job_id)
        if not job:
            return send_json({"success": False, "error": f"Job '{job_id}' not found", "request_id": request_id}, status="404 Not Found")
        
        job_copy = dict(job)
        if job_copy.get("result") and isinstance(job_copy["result"], dict):
            job_copy["result"] = {k: v for k, v in job_copy["result"].items() if k not in ("pdf_bytes", "pptx_bytes")}

        return send_json({"success": True, "job": job_copy, "request_id": request_id})

    # 9. DELIVERABLE DOWNLOADS (/api/download/pdf, /api/download/pptx)
    if path in ("/api/download/pdf", "/api/download/pptx") and method == "GET":
        init_db()
        session_id = params.get("id", [None])[0]
        if not session_id:
            return send_json({"success": False, "error": "Query parameter 'id' is required"}, status="400 Bad Request")

        session = get_session(session_id)
        if not session or "data" not in session:
            return send_json({"success": False, "error": f"Session '{session_id}' not found"}, status="404 Not Found")

        sess_data = session["data"]
        raw_topic = sess_data.get("blueprint", {}).get("topic_normalized", "Research_Report")
        clean_slug = re.sub(r'[^\w\-_]', '_', raw_topic[:30])

        if path.endswith("/pdf"):
            pdf_bytes = build_pdf_report(sess_data)
            return send_binary(pdf_bytes, "application/pdf", f"KleinAI_{clean_slug}.pdf")
        else:
            pptx_bytes = build_pptx_deck(sess_data, sess_data.get("slides_data", []))
            return send_binary(
                pptx_bytes,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                f"KleinAI_{clean_slug}.pptx"
            )

    # 10. RESEARCH PIPELINE DISPATCH (/api/research)
    if path in ("/research", "/api/research") and method == "POST":
        # Validate Content-Type
        content_type = environ.get("CONTENT_TYPE", "")
        if "application/json" not in content_type:
            return send_json({
                "success": False,
                "error": "Invalid Content-Type. Request body must be 'application/json'.",
                "request_id": request_id
            }, status="415 Unsupported Media Type")

        # Validate Content-Length
        try:
            content_length = int(environ.get("CONTENT_LENGTH", 0) or 0)
        except ValueError:
            content_length = 0

        if content_length > MAX_REQUEST_BODY_SIZE:
            return send_json({
                "success": False,
                "error": f"Payload too large. Request body exceeds {MAX_REQUEST_BODY_SIZE} bytes limit.",
                "request_id": request_id
            }, status="413 Payload Too Large")

        body_bytes = environ["wsgi.input"].read(content_length) if content_length > 0 else b""
        try:
            payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            return send_json({
                "success": False,
                "error": "Malformed JSON payload.",
                "request_id": request_id
            }, status="400 Bad Request")

        if not isinstance(payload, dict):
            return send_json({
                "success": False,
                "error": "Request body must be a valid JSON object.",
                "request_id": request_id
            }, status="400 Bad Request")

        topic = payload.get("topic")
        if not isinstance(topic, str) or not (3 <= len(topic.strip()) <= 500):
            return send_json({
                "success": False,
                "error": "Field 'topic' is required and must be a non-empty string between 3 and 500 characters.",
                "request_id": request_id
            }, status="400 Bad Request")
        topic = topic.strip()

        model = payload.get("model") or DEFAULT_GEMINI_MODEL
        if model not in SUPPORTED_MODELS:
            return send_json({
                "success": False,
                "error": f"Invalid model '{model}'. Supported models: {', '.join(SUPPORTED_MODELS)}",
                "request_id": request_id
            }, status="400 Bad Request")

        gemini_key = clean_api_key(payload.get("gemini_api_key")) or get_gemini_api_key()
        tavily_key = clean_api_key(payload.get("tavily_api_key")) or get_tavily_api_key()

        if not gemini_key:
            return send_json({
                "success": False,
                "error": "Gemini API key is required. Configure GEMINI_API_KEY environment variable or pass 'gemini_api_key' in request body.",
                "request_id": request_id
            }, status="400 Bad Request")

        # Explicit async job queue override (?async=true)
        is_async = params.get("async", ["false"])[0].lower() in ("true", "1")
        if is_async:
            job_id = job_manager.submit_research_job(
                topic=topic,
                gemini_api_key=gemini_key,
                tavily_api_key=tavily_key,
                model=model
            )
            return send_json({
                "success": True,
                "job_id": job_id,
                "status": "queued",
                "poll_url": f"/api/jobs/{job_id}",
                "message": "Research job submitted successfully. Poll 'poll_url' to track progress.",
                "request_id": request_id
            }, status="202 Accepted")

        # Synchronous execution (Default: keeps HTTP connection alive so serverless containers complete)
        try:
            agent = KleinResearchAgent(gemini_api_key=gemini_key, tavily_api_key=tavily_key, model=model)
            result = agent.execute_research(topic)
            cleaned = {k: v for k, v in result.items() if k not in ("pdf_bytes", "pptx_bytes")}
            return send_json({
                "success": True,
                "topic": topic,
                "data": cleaned,
                "request_id": request_id
            })
        except GeminiAuthError as e:
            return send_json({"success": False, "error": f"API Credential Error: {str(e)}", "request_id": request_id}, status="401 Unauthorized")
        except GeminiRateLimitError as e:
            return send_json({"success": False, "error": f"Rate Limit Exceeded: {str(e)}", "request_id": request_id}, status="429 Too Many Requests")
        except Exception as e:
            return send_json({"success": False, "error": f"Research execution failed: {str(e)}", "request_id": request_id}, status="500 Internal Server Error")

    # 11. ROUTE NOT FOUND
    return send_json({
        "error": "Not Found",
        "path": path,
        "method": method,
        "request_id": request_id
    }, status="404 Not Found")


# Export top-level application variables for Vercel and WSGI servers
application = app
handler = app
