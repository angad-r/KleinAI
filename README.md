# 🔬 Klein AI 2.0 — Autonomous Scientific Research Agent & SaaS Platform
> **"One Topic. Complete Research. Verified by Empirical Registries."**  
> *Production-Ready Autonomous Academic Research Engine & Whitepaper Publishing Platform.*

[![Live Application](https://img.shields.io/badge/Live_Deployment-Vercel-black?style=for-the-badge&logo=vercel)](https://kleinai.vercel.app/)
[![Python Version](https://img.shields.io/badge/Python-3.11_|_3.12_|_3.13-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Tests Passing](https://img.shields.io/badge/Tests-53%20Passed%20(100%25)-brightgreen?style=for-the-badge&logo=pytest)](TESTING_REPORT.md)
[![Security Rating](https://img.shields.io/badge/Security-A%2B%20Hardened-indigo?style=for-the-badge&logo=shield)](SECURITY_AUDIT.md)

---

## 1. Project Overview & Live Access

- **Live SaaS Deployment:** [https://kleinai.vercel.app/](https://kleinai.vercel.app/)
- **GitHub Repository:** [https://github.com/angad-r/KleinAI](https://github.com/angad-r/KleinAI)
- **Version:** `2.0.0 Pro`

**Klein AI 2.0** is an enterprise-grade autonomous scientific research platform that transforms a research question into a publication-standard academic whitepaper, an executive 16:9 presentation deck, and an audited evidence matrix.

Commanding an orchestrated multi-agent state machine, Klein AI crawls empirical literature, negotiates official DOI metadata from **Crossref** and **DOI.org**, maps generated research claims to exact textual evidence, identifies critical research gaps (`GAP-01` to `GAP-04`), formulates novel system architectures, and subjects all findings to an automated **Independent Peer Review Agent**.

---

## 2. Core Capabilities & What's New in 2.0

| Feature | Description |
| :--- | :--- |
| **17-Stage Multi-Agent Pipeline** | End-to-end investigation with state telemetry, adaptive query expansion, claim verification, and deliverable compilation. |
| **Crossref & DOI.org Verification** | Resolves real bibliographic metadata via DOI Content Negotiation (`Accept: application/vnd.citationstyles.csl+json`). |
| **Claim-to-Evidence Mapping** | Maps every synthesized claim to exact source passages with lexical overlap scoring and contradiction detection. |
| **Universal Database Persistence** | Managed PostgreSQL connection pooling (via `DATABASE_URL` with `psycopg-pool`) in production, with local SQLite fallback and automated migrations. |
| **Distributed Job Queue** | Asynchronous research execution via `JobManager` with Redis queue support (`REDIS_URL`) and `/api/jobs/<job_id>` progress streaming. |
| **Independent Peer Review Agent** | Autonomous critic that evaluates synthesized research on factuality, methodology, novelty, strengths, and limitations (1-10 scoring). |
| **Enterprise Security Hardening** | Strict SSRF defense blocking loopback/private/metadata IPs, strict TLS verification, zero-leakage masking, rate limiting, and security headers. |
| **Standards-Compliant Exports** | Formatted **APA 7th Edition**, **IEEE**, **BibTeX** (`@misc`), **RIS** (Zotero/EndNote), **ReportLab PDF**, and **python-pptx** decks. |
| **Linear/Perplexity Dark SaaS UI** | Responsive dark interface with interactive tabs, live terminal progress logs, and instant verified academic demo mode. |

---

## 3. System Architecture

```mermaid
flowchart TD
    subgraph UI["Client & Presentation Layer"]
        Browser["Modern Dark SaaS Interface (app.py)"]
        StreamlitGUI["Streamlit Desktop Dashboard (port 8501)"]
        REST_API["REST Endpoints (/api/research, /api/health)"]
    end

    subgraph Security["Application Security Gateway"]
        RateLimit["Rate Limiter (15 req/min Token Bucket)"]
        Validation["Request Size (64KB) & Content-Type Filter"]
        SecHeaders["Security Headers (nosniff, DENY, HSTS, CSP)"]
    end

    subgraph Queue["Job Orchestration & Telemetry"]
        JobMgr["JobManager (core/job_queue.py)"]
        RedisQ["Redis Queue / ThreadPool Worker"]
        Telemetry["Stage Telemetry & Event Streaming"]
    end

    subgraph Agent["Autonomous Research Pipeline (core/researcher.py)"]
        Blueprint["Step 1-3: Research Blueprint & Hypothesis"]
        Harvest["Step 4-7: Multi-Aspect Web Harvester & Deduplication"]
        Analysis["Step 8-10: Evidence Extraction & Comparative Matrix"]
        Synthesis["Step 11-14: Literature Review, Gaps & Methodology"]
        Verification["Step 15: DOI & Crossref Claim-to-Evidence Audit"]
        PeerReview["Step 16: Independent Critic & Peer Review Agent"]
        Deliverables["Step 17: PDF Whitepaper & PPTX Deck Compilation"]
    end

    subgraph External["Authoritative External Registries"]
        DOI_Org["DOI.org Content Negotiation"]
        Crossref["Crossref Bibliographic API"]
        Gemini["Google Gemini 2.5 / 2.0 Flash"]
        Tavily["Tavily Scholarly Search"]
        DDG["DuckDuckGo Fallback"]
    end

    subgraph Storage["Universal Persistence Engine"]
        PG["Neon / Supabase PostgreSQL (Production)"]
        SQLite["SQLite Embedded (Local Fallback)"]
    end

    UI --> Security
    Security --> Queue
    Queue --> Agent
    Agent --> External
    Agent --> Storage
```

---

## 4. 17-Stage Research Pipeline Breakdown

```
[01] Initialize Agent Orchestrator & Load Credentials
[02] Formulate Scientific Blueprint & Research Questions
[03] Classify Scientific Domain & Core Hypothesis
[04] Execute Aspect-Oriented Literature Search Queries
[05] Harvest Candidate Empirical Sources
[06] Canonical URL Deduplication & Domain Whitelist Scoring
[07] Adaptive Query Expansion (Refinement Loop)
[08] DOM Parsing & Deep Passage Text Extraction
[09] Extract Empirical Metrics, Baselines & Benchmark Datasets
[10] Synthesize Cross-Source Comparative Matrix & Divergent Findings
[11] Author Structured Multi-Section Academic Literature Review
[12] Discover Structural Research Gaps (GAP-01 to GAP-04)
[13] Propose Novel Methodology & Framework Architecture
[14] Design Experimental Verification Protocols & Target Metrics
[15] Audit Citations against Crossref & DOI.org with Claim Mapping
[16] Execute Independent Peer Review & Verification Audit
[17] Compile Academic PDF Whitepaper & PowerPoint Presentation Deck
```

---

## 5. Quickstart & Local Setup

### Prerequisites
- Python 3.11, 3.12, or 3.13
- Google Gemini API Key ([Get free key at Google AI Studio](https://aistudio.google.com/))

### Installation
```bash
# Clone the repository
git clone https://github.com/angad-r/KleinAI.git
cd KleinAI

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install production dependencies
pip install -r requirements.txt
```

### Configure Credentials
Create a `.env` file in the project root:
```env
GEMINI_API_KEY=your_gemini_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here  # Optional: falls back to DuckDuckGo
DATABASE_URL=postgresql://user:pass@ep-cool.neon.tech/neondb?sslmode=require  # Optional: falls back to SQLite
```

### Launch Interactive Streamlit Desktop Dashboard
```bash
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

### Launch Serverless Web Interface Locally
```bash
python -m waitress --port=5000 app:app
```
Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## 6. REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Minimal operational diagnostics without secret leakage. |
| `GET` | `/api/demo` | Instant verified academic dataset (zero quota consumption). |
| `POST` | `/api/research` | Submit research investigation (returns `202 Accepted` + `job_id`). |
| `GET` | `/api/jobs/<job_id>` | Poll research stage, logs, and completion result. |
| `GET` | `/api/sessions` | Retrieve persistent research session history. |
| `GET` | `/api/session?id=<id>` | Retrieve complete session data by UUID. |
| `GET` | `/api/download/pdf?id=<id>` | Stream formal academic ReportLab PDF report. |
| `GET` | `/api/download/pptx?id=<id>` | Stream 16:9 widescreen presentation deck. |

### Example Request (`POST /api/research`)
```bash
curl -X POST https://kleinai.vercel.app/api/research \
  -H "Content-Type: application/json" \
  -d '{"topic": "Zero-Trust Architecture in Critical Cloud Healthcare Systems"}'
```

Response:
```json
{
  "success": true,
  "job_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "queued",
  "poll_url": "/api/jobs/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "message": "Research job submitted successfully. Poll 'poll_url' to track progress."
}
```

---

## 7. Automated Test Suite

Run the full automated test suite (53 tests covering security, persistence, citation validation, deliverables, and REST API):

```bash
python -m pytest tests/ -v
```

Output:
```
============================= 53 passed in 57.45s =============================
```

---

## 8. Documentation Index

- [Comprehensive Code Audit (CODE_AUDIT.md)](CODE_AUDIT.md)
- [Security Hardening & Vulnerability Report (SECURITY_AUDIT.md)](SECURITY_AUDIT.md)
- [Automated Testing Report (TESTING_REPORT.md)](TESTING_REPORT.md)
- [Production Deployment Guide (DEPLOYMENT_GUIDE.md)](DEPLOYMENT_GUIDE.md)
- [Version 2.0.0 Changelog (CHANGELOG.md)](CHANGELOG.md)

---

## 9. License & Academic Attribution
Developed as an autonomous scientific research capstone project. Distributed under the **MIT License**.
All audited sample literature references authoritative publications via official Digital Object Identifiers (DOIs).
