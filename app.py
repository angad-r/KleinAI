"""
Klein AI - Autonomous Research Agent
Streamlit Main Web Application Dashboard
"""
import os
import re
import json
import streamlit as st
from pathlib import Path
from datetime import datetime

from core.config import (
    APP_NAME,
    APP_TAGLINE,
    APP_VERSION,
    DEFAULT_GEMINI_MODEL,
    AVAILABLE_MODELS,
    get_gemini_api_key,
    get_tavily_api_key,
    mask_api_key
)
from core.database import init_db, list_sessions, get_session, delete_session
from core.researcher import KleinResearchAgent
from core.gemini_client import (
    GeminiClient,
    GeminiAuthError,
    GeminiRateLimitError,
    GeminiNetworkError,
    GeminiModelError
)
from core.pdf_generator import build_pdf_report
from core.ppt_generator import build_pptx_deck

import urllib.parse
from streamlit import runtime
from core.demo_dataset import VERIFIED_DEMO_DATA

def render_streamlit_dashboard():
    """
    Interactive Streamlit Web Dashboard.
    Executed only when running within an active Streamlit runtime (e.g. `streamlit run app.py`).
    """
    # Page Configuration
    st.set_page_config(
        page_title=f"{APP_NAME} — Autonomous Research Agent",
        page_icon="🔬",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Load CSS Styles
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
        st.session_state.current_step_info = {"step": 0, "total": 17, "title": "Idle", "desc": "Ready to initiate research"}
    if "live_logs" not in st.session_state:
        st.session_state.live_logs = []
    if "topic_input_box" not in st.session_state:
        st.session_state["topic_input_box"] = "Impact of Artificial Intelligence on Cybersecurity in Healthcare Systems"
    
    # Sidebar Configuration
    with st.sidebar:
        st.markdown(f"""
        <div style="padding: 10px 0 16px 0;">
            <h2 style="margin: 0; font-size: 1.8rem; font-weight: 800; background: linear-gradient(135deg, #6366F1 0%, #38BDF8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{APP_NAME}</h2>
            <div style="font-size: 0.8rem; color: #94A3B8; font-weight: 500;">{APP_TAGLINE}</div>
            <div style="margin-top: 8px;">
                <span class="badge-pill badge-indigo">College Project</span>
                <span class="badge-pill badge-cyan">Team of 4</span>
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
            help="Required for reasoning, literature review, and synthesis. Free key at https://aistudio.google.com/"
        )
        
        env_tavily = get_tavily_api_key()
        tavily_key_input = st.text_input(
            "Tavily Search API Key",
            value=env_tavily,
            type="password",
            placeholder="Enter Tavily API key (optional)",
            help="Optional for Tavily search. If not provided, DuckDuckGo search is automatically used."
        )
        
        if tavily_key_input:
            st.caption("🟢 Using Tavily AI Search Engine")
        else:
            st.caption("🔵 Using DuckDuckGo Search (Auto-Fallback active)")
            
        selected_model = st.selectbox(
            "Gemini Reasoning Model",
            options=AVAILABLE_MODELS,
            index=AVAILABLE_MODELS.index(DEFAULT_GEMINI_MODEL) if DEFAULT_GEMINI_MODEL in AVAILABLE_MODELS else 0
        )
        
        # Settings & API Diagnostics Section
        st.markdown("---")
        st.subheader("🔍 Settings & API Diagnostics")
        
        is_gemini_configured = bool(gemini_key_input and gemini_key_input.strip())
        is_tavily_configured = bool(tavily_key_input and tavily_key_input.strip())
        
        diag_col1, diag_col2 = st.columns(2)
        with diag_col1:
            st.markdown("**Gemini API:**")
            st.markdown("**Selected Model:**")
            st.markdown("**Tavily Search:**")
        with diag_col2:
            if is_gemini_configured:
                st.markdown(f"🟢 `Configured`")
            else:
                st.markdown("🔴 `Missing`")
                
            st.markdown(f"`{selected_model}`")
            
            if is_tavily_configured:
                st.markdown(f"🟢 `Configured`")
            else:
                st.markdown("🔵 `DuckDuckGo`")
    
        with st.expander("🛠️ Connection Diagnostics", expanded=False):
            st.caption(f"Gemini Key: `{mask_api_key(gemini_key_input)}`")
            st.caption(f"Tavily Key: `{mask_api_key(tavily_key_input)}`")
            
            if st.button("⚡ Test Gemini Connection", key="btn_probe_gemini", use_container_width=True):
                if not is_gemini_configured:
                    st.warning("⚠️ Enter a Gemini API Key above to run connection test.")
                else:
                    with st.spinner("Probing Google Gemini endpoint..."):
                        probe_res = GeminiClient.test_connection(api_key=gemini_key_input, model=selected_model)
                    if probe_res["success"]:
                        st.success(f"✅ Connection: Success!\n\nVerified Model: `{probe_res['model']}`\nProbe Latency: Validated")
                    else:
                        st.error(f"❌ Connection: Failed!\n\n{probe_res['message']}")
        
        st.markdown("---")
        st.subheader("📚 Research History")
        
        history_sessions = list_sessions(limit=15)
        if history_sessions:
            for sess in history_sessions:
                sess_topic = sess.get("topic", "Untitled")
                created_at = sess.get("created_at", "")
                btn_label = f"📄 {sess_topic[:24]}..." if len(sess_topic) > 24 else f"📄 {sess_topic}"
                col_load, col_del = st.columns([4, 1])
                with col_load:
                    if st.button(btn_label, key=f"load_{sess['id']}", help=f"Loaded from {created_at}"):
                        loaded = get_session(sess["id"])
                        if loaded and loaded.get("data"):
                            data_bundle = loaded["data"]
                            # Re-generate pdf and pptx binaries in memory
                            data_bundle["pdf_bytes"] = build_pdf_report(data_bundle)
                            slides = data_bundle.get("slides_data", [])
                            if not slides:
                                slides = [
                                    {"slide_number": 1, "slide_type": "title", "title": data_bundle.get("topic", "Research Report"), "subtitle": "Loaded from ResearchMate AI Archive", "bullets": []},
                                    {"slide_number": 2, "slide_type": "content", "title": "Executive Summary", "subtitle": "Historical Archive", "bullets": [data_bundle.get("blueprint", {}).get("executive_summary", "")[:200]]}
                                ]
                            data_bundle["pptx_bytes"] = build_pptx_deck(data_bundle, slides)
                            st.session_state.research_data = data_bundle
                            st.rerun()
                with col_del:
                    if st.button("🗑️", key=f"del_{sess['id']}", help="Delete from database"):
                        delete_session(sess["id"])
                        st.rerun()
        else:
            st.caption("No past sessions stored in SQLite yet.")
    
        st.markdown("---")
        st.caption("Klein AI Autonomous Research Agent • v1.0.0")
    
    # Main Content Header
    st.markdown(f"""
    <div class="hero-container">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
                <div class="hero-title">{APP_NAME}</div>
                <div class="hero-tagline">{APP_TAGLINE}</div>
            </div>
            <div style="text-align: right;">
                <span class="badge-pill badge-green">Autonomous 17-Step Pipeline</span>
            </div>
        </div>
        <div style="color: #CBD5E1; font-size: 0.92rem; line-height: 1.6; max-width: 900px;">
            Enter any research topic below. <b>Klein AI</b> will autonomously understand the domain, draft a research plan, 
            formulate hypotheses, crawl the public web for peer-reviewed and authoritative sources, extract content, 
            perform cross-source synthesis, generate a scholarly literature review, pinpoint critical research gaps, 
            propose an original methodology & experimental benchmark, and export publication-ready <b>PDF reports</b> and <b>PowerPoint presentations</b>.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Preset Topics & Input
    st.markdown("##### 🔍 Enter Research Topic")
    
    # Example Preset Buttons
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        if st.button("🏥 AI Cybersecurity in Healthcare", key="preset_health"):
            st.session_state["topic_input_box"] = "Impact of Artificial Intelligence on Cybersecurity in Healthcare Systems"
            st.rerun()
    with col_p2:
        if st.button("🔐 Quantum ML & Cryptography", key="preset_quantum"):
            st.session_state["topic_input_box"] = "Quantum Machine Learning Algorithms for Post-Quantum Cryptography"
            st.rerun()
    with col_p3:
        if st.button("🤖 Autonomous Multi-Agent Systems", key="preset_agents"):
            st.session_state["topic_input_box"] = "Autonomous Multi-Agent Systems for Distributed Supply Chain Resilience"
            st.rerun()
    
    topic_input = st.text_input(
        label="Research Topic",
        key="topic_input_box",
        placeholder="e.g., Impact of Artificial Intelligence on Cybersecurity in Healthcare Systems",
        label_visibility="collapsed"
    )
    
    col_run, col_demo, col_clear = st.columns([3, 2, 1])
    with col_run:
        start_btn = st.button("🚀 START AUTONOMOUS RESEARCH (LIVE)", type="primary", use_container_width=True, disabled=st.session_state.is_researching)
    with col_demo:
        demo_btn = st.button("⚡ INSTANT DEMO SIMULATION", use_container_width=True, disabled=st.session_state.is_researching, help="Runs verified 17-step research pipeline with zero API key requirement.")
    with col_clear:
        if st.button("🔄 Reset View", use_container_width=True, disabled=st.session_state.is_researching):
            st.session_state.research_data = None
            st.session_state.live_logs = []
            st.rerun()
    
    # Execution Handler - Instant Demo Simulation
    if demo_btn:
        st.session_state.is_researching = True
        st.session_state.live_logs = []
        
        progress_bar = st.progress(0)
        status_box = st.empty()
        log_box = st.empty()
    
        def on_demo_step(step_idx: int, total: int, title: str, desc: str):
            pct = int((step_idx / total) * 100)
            progress_bar.progress(pct)
            status_box.markdown(f"""
            <div class="step-card step-card-active">
                <div style="font-weight: 700; color: #38BDF8; font-size: 0.95rem;">
                    Step {step_idx}/{total}: {title}
                </div>
                <div style="color: #E2E8F0; font-size: 0.85rem; margin-top: 3px;">
                    {desc}
                </div>
            </div>
            """, unsafe_allow_html=True)
    
        def on_demo_log(msg: str):
            now_str = datetime.now().strftime("%H:%M:%S")
            st.session_state.live_logs.append(f"[{now_str}] {msg}")
            recent = st.session_state.live_logs[-8:]
            log_box.markdown(
                f'<div class="terminal-box">' + "<br/>".join(recent) + '</div>',
                unsafe_allow_html=True
            )
    
        try:
            with st.spinner("Streaming Autonomous Research Pipeline..."):
                demo_results = KleinResearchAgent.execute_demo_simulation(
                    step_callback=on_demo_step,
                    log_callback=on_demo_log
                )
            st.session_state.research_data = demo_results
            st.session_state.is_researching = False
            progress_bar.progress(100)
            st.success("✅ Autonomous Research Pipeline Demo Completed! Artifacts compiled.")
            st.rerun()
        except Exception as e:
            st.session_state.is_researching = False
            st.error(f"❌ Demo simulation failed with error: {str(e)}")
            st.exception(e)
    
    # Execution Handler - Live Research Pipeline
    if start_btn:
        clean_gemini_key = get_gemini_api_key(gemini_key_input)
        if not topic_input or not topic_input.strip():
            st.error("⚠️ Please enter a research topic to proceed.")
        elif not clean_gemini_key:
            st.error(
                "⚠️ **Google Gemini API Key is missing or invalid.**\n\n"
                "A valid Gemini API key is required for live internet research. "
                "Please enter your API key in the left sidebar (free keys available at https://aistudio.google.com/), "
                "or click **⚡ INSTANT DEMO SIMULATION** to evaluate immediately without API credentials."
            )
        else:
            # Pre-flight credential validation probe
            with st.spinner("Validating Gemini API credentials & connectivity..."):
                probe_check = GeminiClient.test_connection(api_key=clean_gemini_key, model=selected_model)
            
            if not probe_check["success"]:
                st.error(f"❌ **API Credential Error:** {probe_check['message']}")
                if probe_check.get("category") == "AUTH_ERROR":
                    st.info(
                        "💡 **How to resolve:**\n\n"
                        "1. Open [Google AI Studio](https://aistudio.google.com/) and create a free Gemini API key.\n"
                        "2. Paste the new key into the **Google Gemini API Key** input in the left sidebar.\n"
                        "3. Or click **⚡ INSTANT DEMO SIMULATION** above to test the complete 17-step workflow immediately."
                    )
                elif probe_check.get("category") == "RATE_LIMIT":
                    st.info("💡 **Rate Limit:** Google AI Studio free tier limits requests per minute. Wait 30 seconds or switch model to `gemini-1.5-flash` in the sidebar.")
            else:
                st.session_state.is_researching = True
                st.session_state.live_logs = []
                
                # UI Placeholders for live progress
                progress_bar = st.progress(0)
                status_box = st.empty()
                log_box = st.empty()
    
                def on_step_progress(step_idx: int, total: int, title: str, desc: str):
                    pct = int((step_idx / total) * 100)
                    progress_bar.progress(pct)
                    status_box.markdown(f"""
                    <div class="step-card step-card-active">
                        <div style="font-weight: 700; color: #38BDF8; font-size: 0.95rem;">
                            Step {step_idx}/{total}: {title}
                        </div>
                        <div style="color: #E2E8F0; font-size: 0.85rem; margin-top: 3px;">
                            {desc}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    
                def on_log_message(msg: str):
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
                        tavily_api_key=tavily_key_input,
                        model=selected_model
                    )
                    
                    with st.spinner("Executing Autonomous Research Pipeline..."):
                        results = agent.execute_research(
                            topic=topic_input.strip(),
                            step_callback=on_step_progress,
                            log_callback=on_log_message
                        )
                    
                    st.session_state.research_data = results
                    st.session_state.is_researching = False
                    progress_bar.progress(100)
                    st.success("✅ Complete Autonomous Research Workflow Finished! Explore results and exports below.")
                    st.rerun()
                    
                except GeminiAuthError as e:
                    st.session_state.is_researching = False
                    st.error(f"❌ **Authentication Failed:** {str(e)}")
                except GeminiRateLimitError as e:
                    st.session_state.is_researching = False
                    st.error(f"⚠️ **Rate Limit Exceeded:** {str(e)}")
                except GeminiNetworkError as e:
                    st.session_state.is_researching = False
                    st.error(f"🌐 **Network Connectivity Error:** {str(e)}")
                except GeminiModelError as e:
                    st.session_state.is_researching = False
                    st.error(f"⚙️ **Model Configuration Error:** {str(e)}")
                except Exception as e:
                    st.session_state.is_researching = False
                    st.error(f"❌ Research failed with error: {str(e)}")
    
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
        pdf_bytes = data.get("pdf_bytes")
        pptx_bytes = data.get("pptx_bytes")
        
        st.markdown("---")
        
        # High-level Metrics Dashboard
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
            st.markdown(f"""
            <div class="stat-box">
                <div class="stat-value">2</div>
                <div class="stat-label">PDF & PPTX Decks</div>
            </div>
            """, unsafe_allow_html=True)
    
        st.markdown("<br/>", unsafe_allow_html=True)
    
        # Multi-Tab Interactive Workspace
        tab_overview, tab_matrix, tab_lit, tab_gaps, tab_method, tab_report, tab_sources, tab_tools, tab_export = st.tabs([
            "📊 Overview & Plan",
            "⚖️ Comparative Matrix",
            "📚 Literature Review",
            "🔍 Research Gaps",
            "⚙️ Proposed Methodology",
            "📄 Full Academic Paper",
            "🔗 Sources & Citations",
            "🔧 Tool Execution Audit",
            "📥 Export Center"
        ])
    
        # Tab 1: Overview & Plan
        with tab_overview:
            st.markdown(f"### {blueprint.get('topic_normalized', data.get('topic'))}")
            
            st.markdown("#### 📝 Executive Abstract")
            st.info(blueprint.get("executive_summary", "No summary available."))
            
            c_obj, c_rq = st.columns(2)
            with c_obj:
                st.markdown("#### 🎯 Research Objectives")
                for obj in blueprint.get("research_objectives", []):
                    st.markdown(f"- **{obj}**")
            with c_rq:
                st.markdown("#### ❓ Formal Research Questions")
                for idx, q in enumerate(blueprint.get("research_questions", []), 1):
                    st.markdown(f"- **RQ{idx}:** {q}")
    
            st.markdown("#### 🗺️ Autonomous Execution Roadmap")
            phases = blueprint.get("execution_phases", [])
            if phases:
                cols = st.columns(len(phases))
                for i, p in enumerate(phases):
                    with cols[i]:
                        st.markdown(f"""
                        <div class="feature-card">
                            <div class="badge-pill badge-indigo">Phase {p.get('phase', i+1)}</div>
                            <div style="font-weight: 700; margin: 8px 0 4px 0; font-size: 0.95rem; color: #F1F5F9;">{p.get('name')}</div>
                            <div style="font-size: 0.8rem; color: #94A3B8;">{p.get('description')}</div>
                        </div>
                        """, unsafe_allow_html=True)
    
        # Tab 2: Comparative Matrix
        with tab_matrix:
            st.markdown("### ⚖️ Cross-Source Comparative Synthesis")
            st.markdown("Synthesis of empirical findings, technical contrasts, and unresolved trade-offs discovered in public literature:")
            
            matrix_items = comparison.get("comparative_matrix", [])
            if matrix_items:
                for item in matrix_items:
                    with st.expander(f"📌 Dimension: {item.get('dimension')}", expanded=True):
                        col_trad, col_sota, col_lim = st.columns(3)
                        with col_trad:
                            st.markdown("**Conventional / Traditional Approach:**")
                            st.caption(item.get("traditional_approach"))
                        with col_sota:
                            st.markdown("**State-of-the-Art AI Approach:**")
                            st.caption(item.get("sota_ai_approach"))
                        with col_lim:
                            st.markdown("**Observed Limitations & Friction:**")
                            st.caption(item.get("observed_limitations"))
    
            c_con, c_deb = st.columns(2)
            with c_con:
                st.markdown("#### 🤝 Consensus Points Across Sources")
                for cp in comparison.get("consensus_points", []):
                    st.markdown(f"✅ {cp}")
            with c_deb:
                st.markdown("#### ⚔️ Active Debates & Controversies")
                for db in comparison.get("debates_and_disagreements", []):
                    st.markdown(f"⚡ {db}")
    
        # Tab 3: Literature Review
        with tab_lit:
            st.markdown("### 📚 Comprehensive Literature Review")
            st.markdown(lit_review)
    
        # Tab 4: Research Gaps
        with tab_gaps:
            st.markdown("### 🔍 Critical Research Gaps Identified")
            st.markdown("These represent structural, mathematical, empirical, or operational deficiencies in existing literature:")
            
            for g in gaps:
                st.markdown(f"""
                <div class="gap-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <div>
                            <span class="gap-id-badge">{g.get('gap_id', 'GAP')}</span>
                            <strong style="margin-left: 8px; font-size: 1.05rem; color: #F8FAFC;">{g.get('title')}</strong>
                        </div>
                        <span class="badge-pill badge-cyan">{g.get('category', 'Category')}</span>
                    </div>
                    <div style="color: #CBD5E1; font-size: 0.9rem; margin-top: 8px;">
                        {g.get('description')}
                    </div>
                    <div style="margin-top: 10px; padding: 8px; background: rgba(99, 102, 241, 0.1); border-radius: 6px; border-left: 3px solid #6366F1; font-size: 0.85rem; color: #A5B4FC;">
                        <b>Strategic Research Opportunity:</b> {g.get('opportunity')}
                    </div>
                </div>
                """, unsafe_allow_html=True)
    
        # Tab 5: Proposed Methodology & Experiments
        with tab_method:
            fname = methodology.get("framework_name", "Klein Framework")
            st.markdown(f"### ⚙️ Novel Proposed Methodology: `{fname}`")
            
            arch = methodology.get("system_architecture", {})
            if arch.get("overview"):
                st.markdown(f"**System Architecture Overview:**\n\n{arch.get('overview')}")
            
            comps = arch.get("components", [])
            if comps:
                st.markdown("#### 🧩 Architectural Components")
                comp_cols = st.columns(min(len(comps), 4))
                for idx, c in enumerate(comps):
                    with comp_cols[idx % len(comp_cols)]:
                        st.markdown(f"""
                        <div class="feature-card">
                            <div style="font-weight: 700; color: #38BDF8; font-size: 0.9rem;">{c.get('name')}</div>
                            <div style="color: #94A3B8; font-size: 0.82rem; margin-top: 6px;">{c.get('role')}</div>
                        </div>
                        """, unsafe_allow_html=True)
    
            if arch.get("workflow_pipeline"):
                st.markdown("#### 🔄 End-to-End Execution Pipeline")
                st.code(arch.get("workflow_pipeline"), language="text")
    
            st.markdown("#### 🧪 Proposed Experimental Design")
            experiments = methodology.get("proposed_experiments", [])
            for exp in experiments:
                with st.expander(f"🔬 {exp.get('experiment_id')}: {exp.get('title')}", expanded=True):
                    st.markdown(f"**Hypothesis:** {exp.get('hypothesis')}")
                    st.markdown(f"**Baselines for Comparison:** {', '.join(exp.get('baselines', []))}")
                    st.markdown(f"**Experimental Protocol:** {exp.get('procedure')}")
    
            st.markdown("#### 📈 Target Quantitative Evaluation Metrics")
            metrics = methodology.get("evaluation_metrics", [])
            if metrics:
                m_cols = st.columns(len(metrics))
                for i, m in enumerate(metrics):
                    with m_cols[i]:
                        st.markdown(f"""
                        <div class="stat-box">
                            <div style="font-size: 1.1rem; font-weight: 700; color: #10B981;">{m.get('target')}</div>
                            <div style="font-weight: 600; font-size: 0.85rem; color: #F1F5F9; margin-top: 4px;">{m.get('metric')}</div>
                            <div style="font-size: 0.75rem; color: #94A3B8; margin-top: 4px;">{m.get('rationale')}</div>
                        </div>
                        """, unsafe_allow_html=True)
    
        # Tab 6: Full Research Paper
        with tab_report:
            st.markdown("### 📄 Full Academic Research Report")
            st.markdown(full_report)
    
        # Tab 7: Sources & Citations
        with tab_sources:
            st.markdown("### 🔗 Harvested Empirical Sources")
            st.markdown(f"Total Sources Collected & Parsed: **{len(sources)}** (Filtered with Canonical URL Normalization)")
            for idx, src in enumerate(sources, 1):
                q_badge = src.get("quality_badge") or src.get("quality_tier", "Standard Quality")
                aspect_tag = src.get("aspect", "General Research")
                ext_status = src.get("extraction_status", "Parsed Content")
                st.markdown(f"""
                <div class="citation-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span class="citation-domain">{src.get('domain')} • {src.get('engine', 'Web')}</span>
                            <span class="badge-pill badge-cyan" style="margin-left: 6px;">{aspect_tag}</span>
                        </div>
                        <div>
                            <span class="badge-pill badge-green">{q_badge}</span>
                            <span class="badge-pill badge-indigo">Source #{idx}</span>
                        </div>
                    </div>
                    <div style="font-weight: 700; font-size: 1.05rem; color: #F8FAFC; margin: 6px 0 3px 0;">
                        <a href="{src.get('url')}" target="_blank" style="color: #38BDF8; text-decoration: none;">{src.get('title')}</a>
                    </div>
                    <div style="color: #94A3B8; font-size: 0.85rem; line-height: 1.5;">
                        {src.get('snippet', '')[:280]}...
                    </div>
                    <div style="margin-top: 8px; display: flex; justify-content: space-between; font-size: 0.75rem; color: #64748B;">
                        <span><code>{src.get('url')}</code></span>
                        <span style="color: #A5B4FC; font-weight: 600;">Status: {ext_status}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    
            # Scholarly APA & BibTeX Export
            audited_cits = data.get("audited_citations", [])
            if audited_cits:
                with st.expander("📖 View Verified Bibliographic Citations (APA 7th & BibTeX)", expanded=False):
                    st.markdown("##### 📚 APA 7th Edition References:")
                    for cit in audited_cits:
                        st.markdown(f"- {cit.get('apa_citation')}")
                    
                    st.markdown("##### 🏷️ BibTeX Format:")
                    all_bib = "\n\n".join([c.get("bibtex", "") for c in audited_cits])
                    st.code(all_bib, language="bibtex")
    
        # Tab 8: Tool Execution Audit
        with tab_tools:
            st.markdown("### 🔧 Autonomous Tool Calling Registry & Audit Trail")
            st.markdown("Audited record of all tool invocations executed by the autonomous agent with duration, parameters, and outcome verification:")
            
            tool_logs = data.get("tool_audit_log", [])
            if tool_logs:
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown(f"""
                    <div class="stat-box">
                        <div class="stat-value">{len(tool_logs)}</div>
                        <div class="stat-label">Total Tool Calls</div>
                    </div>
                    """, unsafe_allow_html=True)
                with c2:
                    total_duration = sum(t.get("duration_ms", 0) for t in tool_logs)
                    st.markdown(f"""
                    <div class="stat-box">
                        <div class="stat-value">{total_duration/1000:.2f}s</div>
                        <div class="stat-label">Total Execution Time</div>
                    </div>
                    """, unsafe_allow_html=True)
                with c3:
                    successful_calls = sum(1 for t in tool_logs if t.get("success", False))
                    st.markdown(f"""
                    <div class="stat-box">
                        <div class="stat-value">{successful_calls}/{len(tool_logs)}</div>
                        <div class="stat-label">Successful Invocations</div>
                    </div>
                    """, unsafe_allow_html=True)
    
                st.markdown("<br/>", unsafe_allow_html=True)
                
                for i, tl in enumerate(tool_logs, 1):
                    tool_icon = "✅" if tl.get("success") else "⚠️"
                    t_name = tl.get("tool", "unknown_tool")
                    summary = tl.get("summary", "")
                    dur = tl.get("duration_ms", 0.0)
                    st.markdown(f"""
                    <div class="step-card" style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <strong style="color: #38BDF8; font-family: 'JetBrains Mono', monospace;">#{i} {tool_icon} {t_name}()</strong>
                            <div style="font-size: 0.85rem; color: #CBD5E1; margin-top: 3px;">{summary}</div>
                        </div>
                        <div style="text-align: right;">
                            <span class="badge-pill badge-indigo">{dur:.1f} ms</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No tool audit trail stored for this session.")
    
        # Tab 9: Export Center
        with tab_export:
            st.markdown("### 📥 Download Research Deliverables")
            st.markdown("Instant publication-ready exports created specifically for presentation and college project evaluation:")
            
            col_pdf, col_ppt = st.columns(2)
            with col_pdf:
                # Ensure binaries are available
                if not pdf_bytes and data:
                    pdf_bytes = build_pdf_report(data)
                    data["pdf_bytes"] = pdf_bytes
                if not pptx_bytes and data:
                    pptx_bytes = build_pptx_deck(data, data.get("slides_data", []))
                    data["pptx_bytes"] = pptx_bytes
    
                raw_topic_slug = re.sub(r'[^\w\-_]', '_', blueprint.get('topic_normalized', 'Research_Report')[:28])
    
                st.markdown("""
                <div class="feature-card" style="text-align: center; padding: 24px;">
                    <div style="font-size: 3rem;">📕</div>
                    <div style="font-weight: 700; font-size: 1.2rem; margin-top: 8px;">Formal Academic PDF Report</div>
                    <div style="font-size: 0.85rem; color: #94A3B8; margin: 8px 0 16px 0;">
                        Complete multi-page whitepaper with abstract, comparative tables, methodology diagrams, running headers, and page numbering.
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if pdf_bytes:
                    st.download_button(
                        label="📥 Download PDF Whitepaper",
                        data=pdf_bytes,
                        file_name=f"ResearchMate_{raw_topic_slug}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key="dl_btn_pdf"
                    )
                else:
                    st.warning("PDF generating...")
    
            with col_ppt:
                st.markdown("""
                <div class="feature-card" style="text-align: center; padding: 24px;">
                    <div style="font-size: 3rem;">📊</div>
                    <div style="font-weight: 700; font-size: 1.2rem; margin-top: 8px;">PowerPoint Presentation (.pptx)</div>
                    <div style="font-size: 0.85rem; color: #94A3B8; margin: 8px 0 16px 0;">
                        10-slide 16:9 widescreen presentation deck formatted with dark title, structured cards, empirical findings, and conclusions.
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if pptx_bytes:
                    st.download_button(
                        label="📥 Download PowerPoint Deck (.pptx)",
                        data=pptx_bytes,
                        file_name=f"ResearchMate_{raw_topic_slug}.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        use_container_width=True,
                        key="dl_btn_pptx"
                    )
                else:
                    st.warning("Presentation generating...")
    
            st.markdown("---")
            col_md, col_json = st.columns(2)
            with col_md:
                st.download_button(
                    label="💾 Download Raw Markdown (.md)",
                    data=full_report,
                    file_name=f"ResearchMate_{raw_topic_slug}.md",
                    mime="text/markdown",
                    use_container_width=True,
                    key="dl_btn_md"
                )
            with col_json:
                json_str = json.dumps({k: v for k, v in data.items() if k not in ("pdf_bytes", "pptx_bytes")}, indent=2, ensure_ascii=False)
                st.download_button(
                    label="💾 Download Raw Data Schema (JSON)",
                    data=json_str,
                    file_name="researchmate_data.json",
                    mime="application/json",
                    use_container_width=True,
                    key="dl_btn_json"
                )


# ==============================================================================
# RUNTIME DISPATCHER
# ==============================================================================
try:
    if runtime.exists():
        render_streamlit_dashboard()
except Exception:
    # If streamlit runtime is not active, skip UI rendering so WSGI import succeeds
    pass

# ==============================================================================
# WSGI SERVERLESS APPLICATION ENTRYPOINT (VERCEL & REST API RUNTIME)
# ==============================================================================

HTML_LANDING_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Klein AI — Autonomous Research Agent</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🔬</text></svg>">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        body { background: #090d16; color: #f8fafc; min-height: 100vh; padding: 36px 16px; display: flex; flex-direction: column; align-items: center; }
        .container { max-width: 920px; width: 100%; margin: 0 auto; }
        .hero { text-align: center; margin-bottom: 32px; }
        .badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; background: rgba(99, 102, 241, 0.15); border: 1px solid rgba(99, 102, 241, 0.4); border-radius: 9999px; font-size: 0.8rem; font-weight: 600; color: #a5b4fc; margin-bottom: 16px; }
        h1 { font-size: 2.6rem; font-weight: 800; background: linear-gradient(135deg, #ffffff 30%, #a5b4fc 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px; letter-spacing: -0.02em; }
        .tagline { color: #94a3b8; font-size: 1.1rem; max-width: 680px; margin: 0 auto 24px auto; line-height: 1.5; }
        
        .status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; margin-bottom: 28px; }
        .status-card { background: #111827; border: 1px solid #1e293b; border-radius: 12px; padding: 14px 16px; }
        .status-label { font-size: 0.72rem; text-transform: uppercase; color: #64748b; font-weight: 700; letter-spacing: 0.05em; margin-bottom: 6px; }
        .status-value { font-size: 0.95rem; font-weight: 600; display: flex; align-items: center; gap: 8px; }
        .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
        .dot.green { background: #10b981; box-shadow: 0 0 8px #10b981; }
        .dot.amber { background: #f59e0b; box-shadow: 0 0 8px #f59e0b; }

        .card { background: #111827; border: 1px solid #1e293b; border-radius: 16px; padding: 24px; margin-bottom: 24px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3); }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
        .card-title { font-size: 1.25rem; font-weight: 700; display: flex; align-items: center; gap: 8px; }
        
        .input-group { margin-bottom: 16px; }
        label { display: block; font-size: 0.85rem; font-weight: 600; color: #94a3b8; margin-bottom: 6px; }
        input, select, textarea { width: 100%; background: #0b1120; border: 1px solid #1e293b; border-radius: 8px; padding: 12px 14px; color: #f8fafc; font-size: 0.95rem; outline: none; transition: border-color 0.2s; }
        input:focus, textarea:focus { border-color: #6366f1; }
        .btn-group { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 16px; }
        button { background: linear-gradient(135deg, #6366f1, #4f46e5); color: white; border: none; border-radius: 8px; padding: 12px 22px; font-size: 0.95rem; font-weight: 600; cursor: pointer; transition: transform 0.1s, opacity 0.2s; display: inline-flex; align-items: center; gap: 8px; }
        button:hover { opacity: 0.95; transform: translateY(-1px); }
        button.secondary { background: #1e293b; color: #f8fafc; border: 1px solid #334155; }
        button.secondary:hover { background: #334155; }
        button:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

        .output-box { margin-top: 16px; background: #05070d; border: 1px solid #1e293b; border-radius: 8px; padding: 16px; max-height: 440px; overflow-y: auto; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 0.85rem; line-height: 1.5; color: #38bdf8; display: none; white-space: pre-wrap; }
        .endpoints-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-top: 12px; }
        .endpoints-table th, .endpoints-table td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #1e293b; }
        .endpoints-table th { color: #64748b; font-size: 0.72rem; text-transform: uppercase; }
        .method { font-weight: 700; border-radius: 4px; padding: 2px 6px; font-size: 0.72rem; }
        .get { background: rgba(16, 185, 129, 0.15); color: #34d399; }
        .post { background: rgba(99, 102, 241, 0.15); color: #818cf8; }
        a { color: #818cf8; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .desktop-notice { background: rgba(56, 189, 248, 0.08); border: 1px dashed rgba(56, 189, 248, 0.3); border-radius: 12px; padding: 18px; text-align: center; font-size: 0.88rem; color: #7dd3fc; margin-top: 24px; line-height: 1.6; }
        code { background: #1e293b; padding: 2px 6px; border-radius: 4px; font-family: monospace; color: #f1f5f9; }
    </style>
</head>
<body>
    <div class="container">
        <div class="hero">
            <div class="badge">✨ Autonomous Multi-Agent Research System v1.0.0</div>
            <h1>Klein AI</h1>
            <p class="tagline">Autonomous academic literature synthesis, multi-tier source verification, research gap detection, and scholarly artifact generation.</p>
        </div>

        <div class="status-grid" id="statusGrid">
            <div class="status-card">
                <div class="status-label">Vercel Cloud Runtime</div>
                <div class="status-value"><span class="dot green"></span> Active (WSGI Python)</div>
            </div>
            <div class="status-card">
                <div class="status-label">Gemini Model</div>
                <div class="status-value" id="modelStatus">gemini-2.5-flash</div>
            </div>
            <div class="status-card">
                <div class="status-label">Gemini API Key</div>
                <div class="status-value" id="geminiStatus">Checking...</div>
            </div>
            <div class="status-card">
                <div class="status-label">Tavily Search API</div>
                <div class="status-value" id="tavilyStatus">Checking...</div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <div class="card-title">🔬 Autonomous Research API Console</div>
            </div>
            <div class="input-group">
                <label for="topicInput">Research Topic or Investigation Query</label>
                <input type="text" id="topicInput" placeholder="e.g., Impact of Artificial Intelligence on Cybersecurity in Healthcare" value="Impact of Artificial Intelligence on Cybersecurity in Healthcare">
            </div>
            <div class="input-group">
                <label for="apiKeyInput">Google Gemini API Key <span style="color: #64748b; font-weight: 400;">(Optional: uses GEMINI_API_KEY from environment if blank)</span></label>
                <input type="password" id="apiKeyInput" placeholder="Enter Gemini key or leave blank if configured in Vercel">
            </div>
            <div class="btn-group">
                <button id="btnResearch" onclick="executeResearch()">🚀 Execute Live Research</button>
                <button class="secondary" id="btnDemo" onclick="loadDemoData()">⚡ Instant Demo Simulation</button>
                <button class="secondary" onclick="checkHealth()">🔄 Re-check Health</button>
            </div>
            <div class="output-box" id="outputBox"></div>
        </div>

        <div class="card">
            <div class="card-header">
                <div class="card-title">📡 Available REST API Endpoints</div>
            </div>
            <table class="endpoints-table">
                <thead>
                    <tr><th>Method</th><th>Endpoint</th><th>Description</th></tr>
                </thead>
                <tbody>
                    <tr><td><span class="method get">GET</span></td><td><a href="/api/health" target="_blank">/api/health</a></td><td>System diagnostics, API configuration, and model status</td></tr>
                    <tr><td><span class="method get">GET</span></td><td><a href="/api/demo" target="_blank">/api/demo</a></td><td>Instant verified 5-phase research dataset for zero-quota demos</td></tr>
                    <tr><td><span class="method post">POST</span></td><td><code>/api/research</code></td><td>Trigger 17-step autonomous research pipeline (JSON payload: <code>{topic}</code>)</td></tr>
                    <tr><td><span class="method get">GET</span></td><td><a href="/api/sessions" target="_blank">/api/sessions</a></td><td>Retrieve persistent historical research sessions</td></tr>
                </tbody>
            </table>
        </div>

        <div class="desktop-notice">
            💻 <strong>Interactive Streamlit GUI:</strong> To access the desktop GUI with interactive step telemetry, PDF reports, and PowerPoint slide generation, run <code>streamlit run app.py</code> locally.
        </div>
    </div>

    <script>
        async function checkHealth() {
            try {
                const res = await fetch('/api/health');
                const data = await res.json();
                document.getElementById('geminiStatus').innerHTML = data.gemini_configured
                    ? '<span class="dot green"></span> Configured (' + data.gemini_masked_key + ')'
                    : '<span class="dot amber"></span> Not Configured';
                document.getElementById('tavilyStatus').innerHTML = data.tavily_configured
                    ? '<span class="dot green"></span> Configured'
                    : '<span class="dot amber"></span> Fallback Search (DuckDuckGo)';
                if (data.default_model) {
                    document.getElementById('modelStatus').textContent = data.default_model;
                }
            } catch (e) {
                console.error(e);
            }
        }

        async function loadDemoData() {
            const out = document.getElementById('outputBox');
            out.style.display = 'block';
            out.textContent = '⏳ Loading verified demo dataset...';
            try {
                const res = await fetch('/api/demo');
                const data = await res.json();
                out.textContent = JSON.stringify(data, null, 2);
            } catch (e) {
                out.textContent = '❌ Failed to load demo data: ' + e.message;
            }
        }

        async function executeResearch() {
            const topic = document.getElementById('topicInput').value.trim();
            const apiKey = (document.getElementById('apiKeyInput') ? document.getElementById('apiKeyInput').value.trim() : '');
            const out = document.getElementById('outputBox');
            const btn = document.getElementById('btnResearch');
            if (!topic) {
                alert('Please enter a research topic.');
                return;
            }
            btn.disabled = true;
            out.style.display = 'block';
            out.textContent = '🔬 Initiating autonomous multi-agent research on: "' + topic + '"...\nThis may take 30-90 seconds. Please wait...';
            try {
                const payload = { topic: topic };
                if (apiKey) payload.gemini_api_key = apiKey;
                const res = await fetch('/api/research', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                out.textContent = JSON.stringify(data, null, 2);
            } catch (e) {
                out.textContent = '❌ Execution error: ' + e.message;
            } finally {
                btn.disabled = false;
            }
        }

        checkHealth();
    </script>
</body>
</html>
"""


def app(environ, start_response):
    """
    WSGI Serverless Application Entrypoint for Vercel deployment and REST API.
    Provides /api/health, /api/demo, /api/research, /api/sessions, and / HTML landing page.
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

    # Strip trailing slash (unless root)
    if len(raw_path) > 1 and raw_path.endswith("/"):
        raw_path = raw_path[:-1]

    path = raw_path
    method = environ.get("REQUEST_METHOD", "GET").upper()

    cors_headers = [
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With"),
    ]

    # Preflight CORS
    if method == "OPTIONS":
        start_response("204 No Content", cors_headers)
        return [b""]

    def send_json(data, status="200 OK"):
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        headers = cors_headers + [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body)))
        ]
        start_response(status, headers)
        return [body]

    def send_html(html_str, status="200 OK"):
        body = html_str.encode("utf-8")
        headers = cors_headers + [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(body)))
        ]
        start_response(status, headers)
        return [body]

    # 1. ROOT LANDING PAGE & HEALTH CHECK
    if path in ("/", "/index.html", "/app.py") and method == "GET":
        accept_header = environ.get("HTTP_ACCEPT", "").lower()
        # If client explicitly requests JSON without accepting HTML, return diagnostic status
        if "application/json" in accept_header and "text/html" not in accept_header:
            gemini_key = get_gemini_api_key()
            tavily_key = get_tavily_api_key()
            return send_json({
                "status": "healthy",
                "app": APP_NAME,
                "tagline": APP_TAGLINE,
                "version": APP_VERSION,
                "gemini_configured": bool(gemini_key),
                "tavily_configured": bool(tavily_key),
                "default_model": DEFAULT_GEMINI_MODEL,
                "endpoints": {
                    "health": "/api/health",
                    "demo": "/api/demo",
                    "research": "/api/research",
                    "sessions": "/api/sessions"
                }
            })
        return send_html(HTML_LANDING_PAGE)

    # 2. SYSTEM HEALTH & DIAGNOSTICS
    if path in ("/health", "/api/health") and method == "GET":
        gemini_key = get_gemini_api_key()
        tavily_key = get_tavily_api_key()
        return send_json({
            "status": "healthy",
            "app": APP_NAME,
            "tagline": APP_TAGLINE,
            "version": APP_VERSION,
            "gemini_configured": bool(gemini_key),
            "tavily_configured": bool(tavily_key),
            "gemini_masked_key": mask_api_key(gemini_key) if gemini_key else "Not Configured",
            "default_model": DEFAULT_GEMINI_MODEL,
            "available_models": AVAILABLE_MODELS
        })

    # 3. VERIFIED DEMO DATASET
    if path in ("/demo", "/api/demo") and method == "GET":
        demo_payload = {k: v for k, v in VERIFIED_DEMO_DATA.items() if k not in ("pdf_bytes", "pptx_bytes")}
        return send_json({
            "success": True,
            "topic": demo_payload.get("topic"),
            "data": demo_payload
        })

    # 4. SAVED SESSIONS LIST
    if path in ("/sessions", "/api/sessions") and method == "GET":
        init_db()
        query_string = environ.get("QUERY_STRING", "")
        params = urllib.parse.parse_qs(query_string)
        session_id = params.get("id", [None])[0]

        if session_id:
            session = get_session(session_id)
            if session:
                if "data" in session and isinstance(session["data"], dict):
                    session["data"] = {k: v for k, v in session["data"].items() if k not in ("pdf_bytes", "pptx_bytes")}
                return send_json({"success": True, "session": session})
            return send_json({"success": False, "error": f"Session '{session_id}' not found"}, status="404 Not Found")

        sessions = list_sessions()
        return send_json({
            "success": True,
            "count": len(sessions),
            "sessions": sessions
        })

    # 5. LIVE AUTONOMOUS RESEARCH PIPELINE
    if path in ("/research", "/api/research") and method == "POST":
        try:
            content_length = int(environ.get("CONTENT_LENGTH", 0) or 0)
        except ValueError:
            content_length = 0

        body_bytes = environ["wsgi.input"].read(content_length) if content_length > 0 else b""
        try:
            payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception as e:
            return send_json({"success": False, "error": f"Invalid JSON payload: {str(e)}"}, status="400 Bad Request")

        topic = (payload.get("topic") or "").strip()
        if not topic:
            return send_json({"success": False, "error": "Field 'topic' is required."}, status="400 Bad Request")

        gemini_key = payload.get("gemini_api_key") or get_gemini_api_key()
        tavily_key = payload.get("tavily_api_key") or get_tavily_api_key()
        model = payload.get("model") or DEFAULT_GEMINI_MODEL

        if not gemini_key:
            return send_json({
                "success": False,
                "error": "Gemini API key is required. Configure GEMINI_API_KEY environment variable or pass 'gemini_api_key' in request body."
            }, status="400 Bad Request")

        try:
            agent = KleinResearchAgent(gemini_api_key=gemini_key, tavily_api_key=tavily_key, model=model)
            result = agent.execute_research(topic)
            cleaned = {k: v for k, v in result.items() if k not in ("pdf_bytes", "pptx_bytes")}
            return send_json({
                "success": True,
                "topic": topic,
                "data": cleaned
            })
        except GeminiAuthError as e:
            return send_json({"success": False, "error": f"API Credential Error: {str(e)}"}, status="401 Unauthorized")
        except Exception as e:
            return send_json({"success": False, "error": f"Research execution failed: {str(e)}"}, status="500 Internal Server Error")

    # 6. ROUTE NOT FOUND
    return send_json({"error": "Not Found", "path": path, "method": method}, status="404 Not Found")


# Export top-level application variables for Vercel and WSGI servers
application = app
handler = app
