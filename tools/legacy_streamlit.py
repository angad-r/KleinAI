"""
Klein AI - Legacy Streamlit Desktop Dashboard (Development & Offline Archive)
Retained for offline local development experiments.
NOTE: This file is NOT used in Vercel production deployment.
Run offline via: pip install streamlit && streamlit run tools/legacy_streamlit.py
"""
import os
import sys
import re
from pathlib import Path
from datetime import datetime

# Add root directory to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from core.config import (
    APP_NAME,
    APP_TAGLINE,
    SUPPORTED_MODELS,
    DEFAULT_GEMINI_MODEL,
    get_gemini_api_key,
    get_tavily_api_key
)
from core.database import init_db, check_db_health, list_sessions, get_session
from core.researcher import KleinResearchAgent
from core.demo_dataset import VERIFIED_DEMO_DATA
from core.pdf_generator import build_pdf_report
from core.ppt_generator import build_pptx_deck


def main():
    import streamlit as st

    st.set_page_config(
        page_title=f"{APP_NAME} 2.0 — Legacy Dashboard",
        page_icon="🔬",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    init_db()

    if "research_data" not in st.session_state:
        st.session_state.research_data = None

    st.title("🔬 Klein AI — Legacy Local Dashboard")
    st.caption("Archived offline launcher. Production website runs at https://kleinai.vercel.app/")

    topic = st.text_input("Research Topic", "Zero-Trust Architecture Implementation in Healthcare")
    if st.button("Load Demo"):
        st.session_state.research_data = VERIFIED_DEMO_DATA
        st.success("Loaded demo dataset.")

    if st.session_state.research_data:
        st.json(st.session_state.research_data.get("blueprint", {}))


if __name__ == "__main__":
    main()
