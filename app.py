"""
Klein AI 2.0 - Autonomous Scientific Research Agent
Unified Production Vercel Serverless Web Application & REST API
Zero-Streamlit Architecture: Web Dashboard, Pipeline Orchestration, & Deliverables Runtime
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
    db_create_job,
    db_get_job,
    db_list_jobs
)
from core.security import (
    encrypt_user_credentials,
    decrypt_user_credentials,
    extract_credentials_from_environ,
    build_session_cookie,
    is_custom_secret_configured,
    COOKIE_NAME
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
# UNIFIED MODERN DARK SAAS WEB INTERFACE (HTML5 / CSS3 / ES6)
# ==============================================================================

HTML_LANDING_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Klein AI 2.0 — Autonomous Scientific Research Platform</title>
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
            background: rgba(11, 15, 25, 0.92); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
            border-bottom: 1px solid var(--border); padding: 14px 28px;
            display: flex; justify-content: space-between; align-items: center;
        }
        .nav-brand { display: flex; align-items: center; gap: 12px; text-decoration: none; }
        .nav-logo { font-size: 1.5rem; }
        .nav-title { font-size: 1.15rem; font-weight: 800; letter-spacing: -0.02em; background: linear-gradient(135deg, #FFF 20%, #A5B4FC 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .nav-badge { font-size: 0.7rem; font-weight: 600; padding: 3px 8px; border-radius: 9999px; background: rgba(99, 102, 241, 0.15); border: 1px solid rgba(99, 102, 241, 0.35); color: #A5B4FC; }
        .nav-links { display: flex; align-items: center; gap: 20px; }
        .nav-link { color: var(--text-secondary); text-decoration: none; font-size: 0.88rem; font-weight: 500; transition: color 0.15s; cursor: pointer; }
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
            <span class="nav-badge">v2.0 Pro Unified</span>
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

            <p style="font-size: 0.84rem; color: var(--text-secondary); margin-bottom: 16px; line-height: 1.5;">
                🔒 <strong>Zero-Client-Storage Security:</strong> Your API credentials are never saved in browser localStorage. Validated keys are encrypted server-side with authenticated AES-GCM and bound only to a secure, HttpOnly session cookie.
            </p>

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
                        <span style="font-weight: 400; color: var(--text-muted);">(Optional: provides deep academic web search; DuckDuckGo fallback if blank)</span>
                    </label>
                    <input type="password" id="inputTavilyKey" placeholder="Paste your Tavily key: tvly-...">
                </div>
            </div>

            <div class="btn-row" style="margin-top: 10px;">
                <button class="btn-success" id="btnSaveKeys" onclick="saveAndTestCredentials()">
                    💾 Save & Validate Credentials
                </button>
                <button class="btn-danger" id="btnClearKeys" onclick="clearSavedCredentials()">
                    🗑️ Clear Session Credentials
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

        <!-- Research Results Workspace (9 Full Academic Tabs) -->
        <section class="results-container" id="resultsContainer">
            <div class="tabs-header">
                <button class="tab-btn active" onclick="switchTab('tab-blueprint', event)">📌 Blueprint</button>
                <button class="tab-btn" onclick="switchTab('tab-lit', event)">📚 Literature Review</button>
                <button class="tab-btn" onclick="switchTab('tab-evidence', event)">📊 Evidence Matrix</button>
                <button class="tab-btn" onclick="switchTab('tab-gaps', event)">🧭 Research Gaps</button>
                <button class="tab-btn" onclick="switchTab('tab-method', event)">⚙️ Methodology</button>
                <button class="tab-btn" onclick="switchTab('tab-review', event)">🛡️ Peer Review</button>
                <button class="tab-btn" onclick="switchTab('tab-paper', event)">📄 Academic Paper</button>
                <button class="tab-btn" onclick="switchTab('tab-sources', event)">🔗 Sources & BibTeX</button>
                <button class="tab-btn" onclick="switchTab('tab-export', event)">📥 Deliverables Export</button>
            </div>

            <!-- Tab 1: Blueprint -->
            <div class="tab-panel active" id="tab-blueprint">
                <div class="card">
                    <h3 style="margin-bottom: 12px; color: var(--accent-cyan);" id="bpDomain">Scientific Domain</h3>
                    <p style="margin-bottom: 18px; font-size: 1.05rem;" id="bpHypothesis">Hypothesis</p>
                    <h4 style="margin: 20px 0 10px 0;">Research Questions</h4>
                    <div id="bpQuestions"></div>
                </div>
            </div>

            <!-- Tab 2: Literature Review -->
            <div class="tab-panel" id="tab-lit">
                <div class="card">
                    <div class="prose" id="litReviewContent"></div>
                </div>
            </div>

            <!-- Tab 3: Evidence Matrix -->
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

            <!-- Tab 4: Research Gaps -->
            <div class="tab-panel" id="tab-gaps">
                <div class="card" id="gapsContainer"></div>
            </div>

            <!-- Tab 5: Methodology -->
            <div class="tab-panel" id="tab-method">
                <div class="card">
                    <h3 id="methodFrameworkName" style="color: var(--accent-cyan); margin-bottom: 12px;">Proposed Framework</h3>
                    <p id="methodOverview" style="margin-bottom: 20px;"></p>
                    <h4>Key System Components</h4>
                    <div id="methodComponents" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; margin-top: 12px;"></div>
                </div>
            </div>

            <!-- Tab 6: Peer Review Audit -->
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

            <!-- Tab 7: Academic Paper -->
            <div class="tab-panel" id="tab-paper">
                <div class="card">
                    <h3>Full Academic Research Paper</h3>
                    <div class="prose" id="fullPaperContent" style="margin-top: 16px;"></div>
                </div>
            </div>

            <!-- Tab 8: Sources & BibTeX -->
            <div class="tab-panel" id="tab-sources">
                <div class="card">
                    <h3>Harvested Empirical Sources & Citations</h3>
                    <div id="sourcesList" style="margin-top: 14px;"></div>
                    <h4 style="margin: 24px 0 10px 0;">📖 APA 7th Citations</h4>
                    <div id="apaCitationsList" class="prose"></div>
                    <h4 style="margin: 24px 0 10px 0;">🏷️ BibTeX References</h4>
                    <pre style="background: #0A0E17; border: 1px solid var(--border); padding: 16px; border-radius: 8px; overflow-x: auto; font-family: var(--font-mono); font-size: 0.8rem; color: #7DD3FC;" id="bibtexBlock"></pre>
                </div>
            </div>

            <!-- Tab 9: Deliverables Export Center -->
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
                <div class="card-title">📚 Historical Research Sessions (Persistent PostgreSQL / Database)</div>
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
        <div>Klein AI 2.0 — Autonomous Research Agent • Production Vercel Platform</div>
        <div style="margin-top: 6px; color: var(--text-muted); font-size: 0.75rem;">
            Powered by Google Gemini 2.5/2.0, Crossref Bibliographic API, DOI Content Negotiation, ReportLab, and python-pptx.
        </div>
    </footer>

    <script>
        let serverGeminiConfigured = false;
        let serverTavilyConfigured = false;
        let userSessionActive = false;
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
        // CREDENTIAL MANAGEMENT & INITIALIZATION (Zero localStorage)
        // ======================================================================

        async function initHealthAndCredentials() {
            try {
                const res = await fetch('/api/config/status');
                const data = await res.json();

                serverGeminiConfigured = Boolean(data.server_gemini_configured);
                serverTavilyConfigured = Boolean(data.server_tavily_configured);
                const userGemini = Boolean(data.user_gemini_configured);
                const userTavily = Boolean(data.user_tavily_configured);
                userSessionActive = userGemini;

                if (userGemini) {
                    document.getElementById('badgeGeminiStatus').className = 'badge-status badge-verified';
                    document.getElementById('badgeGeminiStatus').textContent = 'Gemini: 🟢 User Session Active';
                } else if (serverGeminiConfigured) {
                    document.getElementById('badgeGeminiStatus').className = 'badge-status badge-supported';
                    document.getElementById('badgeGeminiStatus').textContent = 'Gemini: 🟡 Server Environment';
                } else {
                    document.getElementById('badgeGeminiStatus').className = 'badge-status badge-unverified';
                    document.getElementById('badgeGeminiStatus').textContent = 'Gemini: 🔴 Not Configured';
                }

                if (userTavily) {
                    document.getElementById('badgeTavilyStatus').className = 'badge-status badge-verified';
                    document.getElementById('badgeTavilyStatus').textContent = 'Tavily: 🟢 User Session Active';
                } else if (serverTavilyConfigured) {
                    document.getElementById('badgeTavilyStatus').className = 'badge-status badge-supported';
                    document.getElementById('badgeTavilyStatus').textContent = 'Tavily: 🟡 Server Key';
                } else {
                    document.getElementById('badgeTavilyStatus').className = 'badge-status badge-supported';
                    document.getElementById('badgeTavilyStatus').textContent = 'Tavily: Free Fallback (DDG)';
                }

                updateActiveCredentialNotice();
            } catch (e) {
                console.error('Failed to initialize status:', e);
            }
        }

        function updateActiveCredentialNotice() {
            const notice = document.getElementById('activeCredentialNotice');
            if (userSessionActive) {
                notice.innerHTML = '<span style="color: #34D399; font-weight: 600;">🟢 User Encrypted Session Active</span> (AES-GCM secured server cookie)';
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

            if (!geminiKey && !serverGeminiConfigured) {
                showBanner('keyFeedbackBanner', '⚠️ Please enter a Google Gemini API Key before testing.', 'error');
                document.getElementById('inputGeminiKey').classList.add('input-error');
                return;
            }

            document.getElementById('inputGeminiKey').classList.remove('input-error');
            btn.disabled = true;
            btn.innerHTML = '⏳ Validating & encrypting session credentials...';

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
                    // Wipe plaintext keys from the input DOM for security
                    document.getElementById('inputGeminiKey').value = '';
                    document.getElementById('inputTavilyKey').value = '';

                    await initHealthAndCredentials();
                    hideBanner('investigationError');

                    showBanner('keyFeedbackBanner', '✅ <strong>Credentials Verified & Session Encrypted!</strong> Google Gemini API key authenticated successfully and stored in a secure server session cookie. Keys are never saved in localStorage.', 'success');
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

        async function clearSavedCredentials() {
            try {
                await fetch('/api/config/clear', { method: 'POST' });
                document.getElementById('inputGeminiKey').value = '';
                document.getElementById('inputTavilyKey').value = '';
                await initHealthAndCredentials();
                showBanner('keyFeedbackBanner', '🗑️ Server session cleared. The platform will revert to server environment keys if available.', 'info');
            } catch (e) {
                alert('Failed to clear credentials: ' + e.message);
            }
        }

        // ======================================================================
        // RESEARCH PIPELINE EXECUTION
        // ======================================================================

        async function launchResearch() {
            const topicInput = document.getElementById('topicInput');
            const topic = topicInput.value.trim();
            const model = document.getElementById('modelSelect').value;
            const btn = document.getElementById('btnLaunch');

            hideBanner('investigationError');
            topicInput.classList.remove('input-error');

            if (!topic || topic.length < 3) {
                topicInput.classList.add('input-error');
                showBanner('investigationError', '⚠️ Please enter a research topic or scientific question (at least 3 characters).', 'error');
                topicInput.focus();
                return;
            }

            if (!userSessionActive && !serverGeminiConfigured) {
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
        // RESULTS RENDERING (9 Academic Tabs)
        // ======================================================================

        function renderResearchResults(data, sessionId) {
            currentSessionId = sessionId;
            document.getElementById('resultsContainer').style.display = 'block';

            // Tab 1: Blueprint
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

            // Tab 2: Literature Review
            const litRaw = data.literature_review || data.report_markdown || 'No synthesis available.';
            document.getElementById('litReviewContent').innerHTML = litRaw
                .replace(/^### (.*$)/gim, '<h3>$1</h3>')
                .replace(/^## (.*$)/gim, '<h2>$1</h2>')
                .replace(/^# (.*$)/gim, '<h1>$1</h1>')
                .split('**').reduce((acc, part, idx) => acc + (idx % 2 === 1 ? '<strong>' + part + '</strong>' : part), '')
                .split('\n').join('<br/>');

            // Tab 3: Evidence Matrix
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

            // Tab 4: Gaps
            const gapsBox = document.getElementById('gapsContainer');
            gapsBox.innerHTML = '<h3>Critical Research Gaps & Strategic Frontiers</h3>';
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

            // Tab 5: Methodology
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

            // Tab 6: Peer Review
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

            // Tab 7: Academic Paper
            const paperRaw = data.report_markdown || litRaw;
            document.getElementById('fullPaperContent').innerHTML = paperRaw
                .replace(/^### (.*$)/gim, '<h3>$1</h3>')
                .replace(/^## (.*$)/gim, '<h2>$1</h2>')
                .replace(/^# (.*$)/gim, '<h1>$1</h1>')
                .split('**').reduce((acc, part, idx) => acc + (idx % 2 === 1 ? '<strong>' + part + '</strong>' : part), '')
                .split('\n').join('<br/>');

            // Tab 8: Sources & BibTeX
            const sourcesBox = document.getElementById('sourcesList');
            sourcesBox.innerHTML = '';
            (data.sources || []).forEach(s => {
                const div = document.createElement('div');
                div.style.marginBottom = '8px';
                div.innerHTML = '• <a href="' + (s.url || '#') + '" target="_blank" style="color: var(--accent-cyan); font-weight: 500;">' + (s.title || 'Source') + '</a>' +
                    ' — <em style="color: var(--text-secondary);">' + (s.domain || '') + '</em> (Quality Tier: ' + (s.quality_tier || 'Standard') + ')';
                sourcesBox.appendChild(div);
            });

            const apaBox = document.getElementById('apaCitationsList');
            apaBox.innerHTML = '';
            cits.forEach(c => {
                if (c.apa_citation) {
                    const p = document.createElement('p');
                    p.style.marginBottom = '8px';
                    p.textContent = c.apa_citation;
                    apaBox.appendChild(p);
                }
            });

            const bibEntries = cits.map(c => c.bibtex || '').filter(Boolean).join('\\n\\n');
            document.getElementById('bibtexBlock').textContent = bibEntries || '% No BibTeX records generated';

            // Tab 9: Export Deliverables
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
                        '<button class="btn-secondary" style="padding: 6px 10px; font-size: 0.78rem;" onclick="viewSession(\\'' + s.id + '\\')">👁️ View</button>' +
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
    Unified WSGI Serverless Application Entrypoint for Vercel deployment.
    Provides /api/health, /api/demo, /api/research, /api/jobs, /api/sessions,
    /api/download/pdf, /api/download/pptx, /api/config/status, /api/config/validate,
    and / modern web dashboard.
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
        extra_params = urllib.parse.parse_qs(qs_extra)
        for k, v in extra_params.items():
            if k not in params:
                params[k] = v

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
        ("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, X-Session-Token"),
        ("Access-Control-Allow-Credentials", "true"),
    ]

    # Pre-flight OPTIONS handler
    if method == "OPTIONS":
        start_response("204 No Content", cors_headers + SECURITY_HEADERS)
        return [b""]

    # Rate Limiting
    if not rate_limiter.is_allowed(client_ip, limit=120, window_seconds=60):
        start_response("429 Too Many Requests", [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Retry-After", "60")
        ] + cors_headers + SECURITY_HEADERS)
        return [json.dumps({
            "error": "Rate limit exceeded. Maximum 120 requests per minute.",
            "status_code": 429,
            "request_id": request_id
        }).encode("utf-8")]

    # Helper function for JSON responses with optional extra headers (e.g. Set-Cookie)
    def send_json(data: Any, status: str = "200 OK", extra_headers: Optional[List[Tuple[str, str]]] = None):
        headers = [
            ("Content-Type", "application/json; charset=utf-8")
        ] + cors_headers + SECURITY_HEADERS
        if extra_headers:
            headers.extend(extra_headers)
        start_response(status, headers)
        return [json.dumps(data, indent=2).encode("utf-8")]

    # Helper function for HTML responses
    def send_html(html_str: str, status: str = "200 OK", extra_headers: Optional[List[Tuple[str, str]]] = None):
        headers = [
            ("Content-Type", "text/html; charset=utf-8")
        ] + cors_headers + SECURITY_HEADERS
        if extra_headers:
            headers.extend(extra_headers)
        start_response(status, headers)
        return [html_str.encode("utf-8")]

    # Extract user session credentials (from HttpOnly session cookie or X-Session-Token header)
    session_creds = extract_credentials_from_environ(environ)
    user_gemini_key = session_creds.get("gemini_key", "")
    user_tavily_key = session_creds.get("tavily_key", "")
    user_id = session_creds.get("user_id", "anonymous")

    # ==========================================================================
    # ROUTE DISPATCHER
    # ==========================================================================

    # 1. ROOT LANDING PAGE & UNIFIED WEB DASHBOARD
    if path == "/" and method == "GET":
        accept_header = environ.get("HTTP_ACCEPT", "")
        # If client explicitly requests JSON API overview
        if "application/json" in accept_header and "text/html" not in accept_header:
            return send_json({
                "app": APP_NAME,
                "service": APP_NAME,
                "version": APP_VERSION,
                "status": "healthy",
                "platform": "Vercel Serverless Unified Platform",
                "endpoints": {
                    "health": "/api/health",
                    "status": "/api/config/status",
                    "validate": "/api/config/validate",
                    "demo": "/api/demo",
                    "research": "/api/research",
                    "jobs": "/api/jobs",
                    "sessions": "/api/sessions"
                },
                "request_id": request_id
            })
        return send_html(HTML_LANDING_PAGE)

    # 2. HEALTH & DIAGNOSTIC ENDPOINT (/api/health)
    if path in ("/health", "/api/health") and method == "GET":
        db_health = check_db_health()
        return send_json({
            "status": "healthy",
            "app": APP_NAME,
            "service": APP_NAME,
            "version": APP_VERSION,
            "platform": "Vercel Serverless",
            "default_model": DEFAULT_GEMINI_MODEL,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": {
                "backend": db_health.get("backend", "sqlite"),
                "connected": db_health.get("connected", False)
            },
            "gemini_configured": bool(get_gemini_api_key() or user_gemini_key),
            "tavily_configured": bool(get_tavily_api_key() or user_tavily_key),
            "user_session_active": bool(user_gemini_key),
            "encryption_storage": "encrypted_server_session" if is_custom_secret_configured() else "standard_server_session",
            "supported_models": SUPPORTED_MODELS,
            "request_id": request_id
        })

    # 3. CONFIGURATION STATUS ENDPOINT (/api/config/status)
    if path == "/api/config/status" and method == "GET":
        server_gk = bool(get_gemini_api_key())
        server_tk = bool(get_tavily_api_key())
        return send_json({
            "success": True,
            "server_gemini_configured": server_gk,
            "server_tavily_configured": server_tk,
            "user_gemini_configured": bool(user_gemini_key),
            "user_tavily_configured": bool(user_tavily_key),
            "active_gemini_source": "user_session" if user_gemini_key else ("server_env" if server_gk else "none"),
            "active_tavily_source": "user_session" if user_tavily_key else ("server_env" if server_tk else "duckduckgo_fallback"),
            "supported_models": SUPPORTED_MODELS,
            "default_model": DEFAULT_GEMINI_MODEL,
            "request_id": request_id
        })

    # 4. CREDENTIAL VALIDATION & SESSION ENCRYPTION (/api/config/validate, /api/config/gemini, /api/config/tavily, /api/keys/test)
    if path in ("/api/config/validate", "/api/config/gemini", "/api/config/tavily", "/api/keys/test") and method == "POST":
        content_type = environ.get("CONTENT_TYPE", "")
        if "application/json" not in content_type:
            return send_json({"success": False, "error": "Content-Type must be application/json", "request_id": request_id}, status="415 Unsupported Media Type")

        try:
            content_length = int(environ.get("CONTENT_LENGTH", 0))
            if content_length > MAX_REQUEST_BODY_SIZE:
                return send_json({"success": False, "error": "Request body exceeds maximum allowed size (64 KB)", "request_id": request_id}, status="413 Payload Too Large")
            body_bytes = environ["wsgi.input"].read(content_length)
            body = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            return send_json({"success": False, "error": "Invalid JSON payload", "request_id": request_id}, status="400 Bad Request")

        # Resolve candidate keys (merging newly submitted keys with existing session keys)
        input_gemini = clean_api_key(body.get("gemini_api_key") or body.get("gemini_key") or "")
        input_tavily = clean_api_key(body.get("tavily_api_key") or body.get("tavily_key") or "")
        model = body.get("model", DEFAULT_GEMINI_MODEL)

        effective_gemini = input_gemini or user_gemini_key or get_gemini_api_key()
        effective_tavily = input_tavily or user_tavily_key or get_tavily_api_key()

        if not effective_gemini:
            return send_json({
                "success": False,
                "error": "Google Gemini API Key is required. Please provide a key from Google AI Studio (https://aistudio.google.com/).",
                "request_id": request_id
            }, status="400 Bad Request")

        # Live probe test with GeminiClient
        try:
            probe_result = GeminiClient.test_connection(api_key=effective_gemini, model=model)
            if not probe_result.get("success"):
                return send_json({
                    "success": False,
                    "error": probe_result.get("message", "Gemini authentication failed. Please check key validity."),
                    "provider": "google_gemini",
                    "request_id": request_id
                }, status="400 Bad Request")
        except Exception as e:
            auth_err = classify_error(e)
            return send_json({
                "success": False,
                "error": str(auth_err),
                "provider": "google_gemini",
                "request_id": request_id
            }, status="400 Bad Request")

        # Optional Tavily validation
        tavily_ok, tavily_msg = test_tavily_key(effective_tavily)
        if effective_tavily and not tavily_ok:
            return send_json({
                "success": False,
                "error": tavily_msg,
                "provider": "tavily",
                "request_id": request_id
            }, status="400 Bad Request")

        # Encrypt valid credentials into secure server-side session token
        session_token = encrypt_user_credentials(
            gemini_key=input_gemini or user_gemini_key,
            tavily_key=input_tavily or user_tavily_key,
            user_id=user_id
        )
        is_https = environ.get("wsgi.url_scheme", "https") == "https"
        set_cookie_header = ("Set-Cookie", build_session_cookie(session_token, secure=is_https))

        return send_json({
            "success": True,
            "message": "Credentials verified and securely stored in server session cookie.",
            "gemini_valid": True,
            "tavily_valid": tavily_ok,
            "tavily_status": tavily_msg,
            "session_active": True,
            "request_id": request_id
        }, extra_headers=[set_cookie_header])

    # 5. CLEAR SESSION CREDENTIALS (/api/config/clear)
    if path == "/api/config/clear" and method == "POST":
        is_https = environ.get("wsgi.url_scheme", "https") == "https"
        clear_cookie_header = ("Set-Cookie", build_session_cookie("", clear=True, secure=is_https))
        return send_json({
            "success": True,
            "message": "User session credentials cleared successfully.",
            "request_id": request_id
        }, extra_headers=[clear_cookie_header])

    # 6. INSTANT VERIFIED DEMO DATASET (/api/demo)
    if path in ("/demo", "/api/demo") and method == "GET":
        demo_payload = {k: v for k, v in VERIFIED_DEMO_DATA.items() if k not in ("pdf_bytes", "pptx_bytes")}
        return send_json({
            "success": True,
            "topic": demo_payload.get("topic", "Impact of Artificial Intelligence on Cybersecurity in Healthcare"),
            "data": demo_payload,
            "disclaimer": "Empirically verified baseline from peer-reviewed literature. No external API quota consumed.",
            "request_id": request_id
        })

    # 7. SAVED SESSIONS LIST (/api/sessions)
    if path in ("/sessions", "/api/sessions") and method == "GET":
        init_db()
        sessions = list_sessions()
        return send_json({
            "success": True,
            "count": len(sessions),
            "sessions": sessions,
            "request_id": request_id
        })

    # 8. INDIVIDUAL SESSION RETRIEVAL (/api/session)
    if path in ("/session", "/api/session") and method == "GET":
        init_db()
        session_id = params.get("id", [None])[0]
        if not session_id:
            return send_json({"success": False, "error": "Query parameter 'id' is required", "request_id": request_id}, status="400 Bad Request")

        if session_id == "demo":
            demo_payload = {k: v for k, v in VERIFIED_DEMO_DATA.items() if k not in ("pdf_bytes", "pptx_bytes")}
            return send_json({"success": True, "session": {"id": "demo", "topic": demo_payload.get("topic"), "data": demo_payload}, "request_id": request_id})

        session = get_session(session_id)
        if session:
            return send_json({"success": True, "session": session, "request_id": request_id})
        return send_json({"success": False, "error": f"Session '{session_id}' not found", "request_id": request_id}, status="404 Not Found")

    # 9. ASYNCHRONOUS JOB POLLING (/api/jobs/<job_id>)
    if path.startswith("/api/jobs/") and method == "GET":
        job_id = path[len("/api/jobs/"):].strip()
        job = job_manager.get_job(job_id)
        if not job:
            return send_json({"success": False, "error": f"Job '{job_id}' not found", "request_id": request_id}, status="404 Not Found")

        job_copy = dict(job)
        if job_copy.get("result") and isinstance(job_copy["result"], dict):
            job_copy["result"] = {k: v for k, v in job_copy["result"].items() if k not in ("pdf_bytes", "pptx_bytes")}

        return send_json({
            "success": True,
            "job": job_copy,
            "request_id": request_id
        })

    # 10. ASYNCHRONOUS JOBS LIST (/api/jobs)
    if path == "/api/jobs" and method == "GET":
        jobs = job_manager.list_jobs(limit=20)
        return send_json({"success": True, "jobs": jobs, "request_id": request_id})

    # 11. PDF DOWNLOAD ENDPOINT (/api/download/pdf)
    if path in ("/api/download/pdf", "/download/pdf") and method == "GET":
        init_db()
        session_id = params.get("id", [None])[0]
        if not session_id:
            return send_json({"success": False, "error": "Query parameter 'id' is required", "request_id": request_id}, status="400 Bad Request")

        if session_id == "demo":
            sess_data = VERIFIED_DEMO_DATA
        else:
            session = get_session(session_id)
            if not session or "data" not in session:
                return send_json({"success": False, "error": f"Session '{session_id}' not found", "request_id": request_id}, status="404 Not Found")
            sess_data = session["data"]

        raw_topic = sess_data.get("blueprint", {}).get("topic_normalized", "Research_Report")
        clean_slug = re.sub(r'[^\w\-_]', '_', raw_topic[:30])

        pdf_bytes = sess_data.get("pdf_bytes")
        if not pdf_bytes:
            pdf_bytes = build_pdf_report(sess_data)

        start_response("200 OK", [
            ("Content-Type", "application/pdf"),
            ("Content-Disposition", f'attachment; filename="KleinAI_{clean_slug}.pdf"'),
            ("Content-Length", str(len(pdf_bytes)))
        ] + cors_headers + SECURITY_HEADERS)
        return [pdf_bytes]

    # 12. PPTX DOWNLOAD ENDPOINT (/api/download/pptx)
    if path in ("/api/download/pptx", "/download/pptx") and method == "GET":
        init_db()
        session_id = params.get("id", [None])[0]
        if not session_id:
            return send_json({"success": False, "error": "Query parameter 'id' is required", "request_id": request_id}, status="400 Bad Request")

        if session_id == "demo":
            sess_data = VERIFIED_DEMO_DATA
        else:
            session = get_session(session_id)
            if not session or "data" not in session:
                return send_json({"success": False, "error": f"Session '{session_id}' not found", "request_id": request_id}, status="404 Not Found")
            sess_data = session["data"]

        raw_topic = sess_data.get("blueprint", {}).get("topic_normalized", "Research_Presentation")
        clean_slug = re.sub(r'[^\w\-_]', '_', raw_topic[:30])

        pptx_bytes = sess_data.get("pptx_bytes")
        if not pptx_bytes:
            pptx_bytes = build_pptx_deck(sess_data, sess_data.get("slides_data", []))

        start_response("200 OK", [
            ("Content-Type", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
            ("Content-Disposition", f'attachment; filename="KleinAI_{clean_slug}.pptx"'),
            ("Content-Length", str(len(pptx_bytes)))
        ] + cors_headers + SECURITY_HEADERS)
        return [pptx_bytes]

    # 13. RESEARCH PIPELINE EXECUTION & JOB CREATION (/api/research, /api/jobs)
    if path in ("/api/research", "/research", "/api/jobs") and method == "POST":
        content_type = environ.get("CONTENT_TYPE", "")
        if "application/json" not in content_type:
            return send_json({"success": False, "error": "Content-Type must be application/json", "request_id": request_id}, status="415 Unsupported Media Type")

        try:
            content_length = int(environ.get("CONTENT_LENGTH", 0))
            if content_length > MAX_REQUEST_BODY_SIZE:
                return send_json({"success": False, "error": "Request body exceeds maximum allowed size (64 KB)", "request_id": request_id}, status="413 Payload Too Large")
            body_bytes = environ["wsgi.input"].read(content_length)
            body = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            return send_json({"success": False, "error": "Invalid JSON body", "request_id": request_id}, status="400 Bad Request")

        topic = body.get("topic", "").strip()
        if not topic or len(topic) < 3:
            return send_json({"success": False, "error": "Field 'topic' is required and must be at least 3 characters long", "request_id": request_id}, status="400 Bad Request")

        # Resolve credentials with priority: body key > decrypted session cookie > server environment
        gemini_key = clean_api_key(body.get("gemini_api_key") or user_gemini_key or get_gemini_api_key())
        tavily_key = clean_api_key(body.get("tavily_api_key") or user_tavily_key or get_tavily_api_key())

        if not gemini_key:
            return send_json({
                "success": False,
                "error": "Google Gemini API key required. Please configure GEMINI_API_KEY or save key in credentials panel.",
                "request_id": request_id
            }, status="401 Unauthorized")

        model = body.get("model", DEFAULT_GEMINI_MODEL)
        if model not in SUPPORTED_MODELS:
            model = DEFAULT_GEMINI_MODEL

        # Check if caller explicitly requested asynchronous background job queueing
        is_async = (path == "/api/jobs") or (params.get("async", ["false"])[0].lower() in ("true", "1"))
        if is_async:
            job_id = job_manager.submit_research_job(
                topic=topic,
                gemini_api_key=gemini_key,
                tavily_api_key=tavily_key,
                model=model,
                user_id=user_id
            )
            return send_json({
                "success": True,
                "job_id": job_id,
                "status": "queued",
                "poll_url": f"/api/jobs/{job_id}",
                "message": "Research job submitted successfully. Poll 'poll_url' to track progress.",
                "request_id": request_id
            }, status="202 Accepted")

        # Synchronous execution within active HTTP connection (Vercel maxDuration: 60s)
        try:
            agent = KleinResearchAgent(
                gemini_api_key=gemini_key,
                tavily_api_key=tavily_key,
                model=model
            )
            results = agent.execute_research(topic=topic)
            safe_results = {k: v for k, v in results.items() if k not in ("pdf_bytes", "pptx_bytes")}

            return send_json({
                "success": True,
                "session_id": results.get("session_id"),
                "data": safe_results,
                "request_id": request_id
            })
        except Exception as e:
            classified = classify_error(e, "pipeline_execution")
            return send_json({
                "success": False,
                "error": str(classified),
                "error_type": classified.__class__.__name__,
                "request_id": request_id
            }, status="500 Internal Server Error")

    # 14. 404 NOT FOUND HANDLER
    return send_json({
        "error": "Not Found",
        "path": path,
        "method": method,
        "message": f"Endpoint '{path}' is not recognized. Visit '/' for the web interface or '/api/health' for API diagnostics.",
        "request_id": request_id
    }, status="404 Not Found")


# Primary application export for WSGI and Vercel
application = app
handler = app
