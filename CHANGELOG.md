# Changelog — Klein AI 2.0.0

All notable changes to the **Klein AI** autonomous academic research platform are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] — 2026-11-04

### 🚀 Architecture & Pipeline Upgrades
- **17-Stage Orchestration Pipeline**: Expanded the autonomous multi-agent research workflow from 14 to 17 sequential steps, introducing dedicated empirical claim verification, independent peer review auditing, and standardized deliverable packaging.
- **Universal Persistence Engine (`core/database.py`)**:
  - Implemented dual-backend architecture supporting production PostgreSQL (via `DATABASE_URL` with `psycopg_pool.ConnectionPool`) and local SQLite fallback.
  - Added automated migration runner (`schema_migrations` table) for zero-downtime schema upgrades.
  - Enforced parameterized queries across all database operations, eliminating SQL injection vectors.
  - Standardized all stored timestamps to ISO 8601 UTC.
  - Migrated session identifiers from legacy 8-character substrings to cryptographic UUIDv4.
- **Distributed Background Job Queue (`core/job_queue.py` & `worker.py`)**:
  - Implemented `JobManager` providing asynchronous research execution, stage telemetry, log streaming, and status polling (`/api/jobs/<job_id>`).
  - Added native Redis support (via `REDIS_URL`) with graceful fallback to a thread-safe `ThreadPoolExecutor` worker pool.
  - Built standalone worker process entrypoint (`worker.py`) with POSIX signal handlers (`SIGINT`, `SIGTERM`) for background deployment on Railway, Render, or Docker.

### 🛡️ Application Security & Hardening
- **Server-Side Request Forgery (SSRF) Defense (`core/search_engine.py`)**:
  - Implemented strict DNS resolution and IP classification (`is_safe_url`) blocking loopback (`127.0.0.0/8`, `::1`), private networks (RFC 1918 `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local, multicast, and cloud instance metadata services (`169.254.169.254`).
  - Removed insecure `verify=False` and suppressed warnings; enforced strict TLS certificate verification across all outbound HTTP requests.
  - Implemented manual redirect follower limiting hops to 5 and re-verifying target IP safety on every hop to eliminate DNS rebinding attacks.
  - Enforced stream size limits (`MAX_SCRAPE_BYTES = 2MB`) and Content-Type filtering (`text/html`, `application/xhtml+xml`, `text/plain`).
- **Zero-Leakage Credential Masking (`core/config.py`)**:
  - Replaced leaky masking that revealed first 6 chars, last 4 chars, and character counts with a strict boolean status: `"Configured"` or `"Not Configured"`.
  - Sanitized placeholder strings (`your_gemini_api_key_here`, quotes, whitespace) at the configuration boundary.
- **REST API Rate Limiting & Validation (`app.py`)**:
  - Added thread-safe in-memory sliding-window rate limiter (15 req/min on `/api/research`, 120 req/min for general endpoints).
  - Enforced request body limit (`MAX_REQUEST_BODY_SIZE = 64KB`) with HTTP 413 Payload Too Large.
  - Validated `Content-Type: application/json` with HTTP 415 Unsupported Media Type.
  - Enforced research topic bounds (3 to 500 characters) and model whitelist against `SUPPORTED_MODELS`.
  - Applied HTTP security headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`, `Referrer-Policy`, and `Content-Security-Policy`.
  - Added `X-Request-ID` tracing on every request and response.

### 🔬 Citation & Research Integrity
- **Multi-Registry Citation Auditing (`core/citation_auditor.py`)**:
  - Replaced naive domain matching with authoritative DOI Content Negotiation (`https://doi.org/{doi}`) and Crossref Bibliographic API queries.
  - Introduced granular machine-readable verification tags: `URL_REACHABLE`, `METADATA_MATCHED`, `CONTENT_EXTRACTED`, `CLAIM_SUPPORTED`, `PARTIALLY_VERIFIED`, `UNVERIFIED`, `VERIFICATION_FAILED`.
  - Built `map_claims_to_evidence()` for automated claim-to-passage semantic matching with lexical overlap scoring and contradiction detection.
  - Implemented standards-compliant bibliographic formatters for **APA 7th Edition**, **IEEE**, **BibTeX** (`@misc` / `@article`), and **RIS** (Zotero / EndNote).
- **Authentic Benchmark Dataset (`core/demo_dataset.py`)**:
  - Replaced all synthetic citations with authentic, peer-reviewed, DOI-verified literature (`10.5220/0012937100004508`, `10.6028/NIST.SP.800-207`, `10.1016/j.array.2025.100586`, `10.1016/j.jbi.2021.103756`).
  - Labeled demo data with explicit `is_simulated_demo: True` flags to prevent misrepresentation as live research.
- **Independent Peer Review Agent (`core/gemini_client.py` & `core/tools.py`)**:
  - Added `review_research` tool and `perform_independent_review()` method providing automated peer review with quantitative scores (1-10), factuality index, novelty evaluation, strengths, limitations, and recommendations.

### 🎨 User Interface & Frontend Redesign
- **Linear/Notion/Perplexity-Inspired Dark SaaS Dashboard (`app.py`)**:
  - Completely revamped web frontend with sleek dark design tokens (`#0B0F19`, `#111827`, `#1E293B`, `#6366F1`, `#38BDF8`, `#10B981`).
  - Integrated live research progress bar with stage telemetry and real-time terminal log viewer polling `/api/jobs/<job_id>`.
  - Added multi-tab interactive results explorer: Blueprint, Literature Review, Evidence Matrix, Research Gaps, Methodology, Independent Review, and Export Center.
  - Added interactive Research Library modal listing historical sessions with instant reload and deliverable downloads.
- **Enhanced Document Generation (`core/pdf_generator.py` & `core/ppt_generator.py`)**:
  - Added Independent Peer Review & Verification Audit table to ReportLab PDF generator with running headers and page numbers.
  - Added secure on-demand streaming endpoints: `/api/download/pdf?id=<id>` and `/api/download/pptx?id=<id>`.

---

## [1.0.0] — 2026-11-03
- Baseline proof-of-concept release with Streamlit GUI, basic SQLite storage, heuristic citation auditing, and Gemini/Tavily integrations.
