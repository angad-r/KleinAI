"""
Klein AI - Autonomous Research Agent
Streamlit Main Web Application Dashboard
"""
import os
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
    get_tavily_api_key
)
from core.database import init_db, list_sessions, get_session, delete_session
from core.researcher import KleinResearchAgent
from core.pdf_generator import build_pdf_report
from core.ppt_generator import build_pptx_deck

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
        placeholder="AIzaSy...",
        help="Required for reasoning, literature review, and synthesis. Free key at https://aistudio.google.com/"
    )
    
    env_tavily = get_tavily_api_key()
    tavily_key_input = st.text_input(
        "Tavily Search API Key",
        value=env_tavily,
        type="password",
        placeholder="tvly-...",
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
                        if slides:
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
preset_topic = None
with col_p1:
    if st.button("🏥 AI Cybersecurity in Healthcare"):
        preset_topic = "Impact of Artificial Intelligence on Cybersecurity in Healthcare"
with col_p2:
    if st.button("🔐 Quantum ML & Cryptography"):
        preset_topic = "Quantum Machine Learning Algorithms for Post-Quantum Cryptography"
with col_p3:
    if st.button("🤖 Autonomous Multi-Agent Systems"):
        preset_topic = "Autonomous Multi-Agent Systems for Distributed Supply Chain Resilience"

default_input_val = preset_topic if preset_topic else ("Impact of Artificial Intelligence on Cybersecurity in Healthcare" if not st.session_state.research_data else "")

topic_input = st.text_input(
    label="Research Topic",
    value=default_input_val,
    placeholder="e.g., Impact of Artificial Intelligence on Cybersecurity in Healthcare",
    label_visibility="collapsed"
)

col_run, col_demo, col_clear = st.columns([3, 2, 1])
with col_run:
    start_btn = st.button("🚀 START AUTONOMOUS RESEARCH (LIVE)", type="primary", use_container_width=True)
with col_demo:
    demo_btn = st.button("⚡ INSTANT DEMO SIMULATION", use_container_width=True, help="Runs verified 17-step research pipeline with zero API key requirement.")
with col_clear:
    if st.button("🔄 Reset View", use_container_width=True):
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

# Execution Handler - Live Research Pipeline
if start_btn:
    if not topic_input or not topic_input.strip():
        st.error("⚠️ Please enter a research topic to proceed.")
    elif not gemini_key_input:
        st.error("⚠️ Google Gemini API Key is required for live internet research. Please enter it in the left sidebar, or click '⚡ INSTANT DEMO SIMULATION' to evaluate immediately.")
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
                gemini_api_key=gemini_key_input,
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
            
        except Exception as e:
            st.session_state.is_researching = False
            st.error(f"❌ Research failed with error: {str(e)}")
            st.exception(e)

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
                    file_name=f"Klein_Research_{blueprint.get('topic_normalized', 'Report')[:30].replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
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
                    file_name=f"Klein_Presentation_{blueprint.get('topic_normalized', 'Deck')[:30].replace(' ', '_')}.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True
                )
            else:
                st.warning("Presentation generating...")

        st.markdown("---")
        col_md, col_json = st.columns(2)
        with col_md:
            st.download_button(
                label="💾 Download Raw Markdown (.md)",
                data=full_report,
                file_name=f"Klein_Report_{blueprint.get('topic_normalized', 'Report')[:25].replace(' ', '_')}.md",
                mime="text/markdown",
                use_container_width=True
            )
        with col_json:
            json_str = json.dumps({k: v for k, v in data.items() if k not in ("pdf_bytes", "pptx_bytes")}, indent=2, ensure_ascii=False)
            st.download_button(
                label="💾 Download Raw Data Schema (JSON)",
                data=json_str,
                file_name="klein_research_data.json",
                mime="application/json",
                use_container_width=True
            )
