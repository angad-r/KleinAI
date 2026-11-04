# CODE_AUDIT.md — Klein AI Architecture & Security Audit

**Audit Date:** November 2026  
**Auditor:** Senior Backend, Security & AI Systems Engineering  
**Scope:** Klein AI Autonomous Scientific Research Platform  
**Target Architecture:** Vercel Serverless / Hybrid Cloud + Streamlit Local Dashboard  

---

## 1. Executive Summary

Klein AI is designed as an autonomous multi-agent scientific research platform that accepts a research topic, performs web and scholarly literature discovery, extracts evidence, detects research gaps, formulates novel methodologies, and generates publication deliverables (Markdown whitepaper, ReportLab PDF, and python-pptx slide deck).

While the system demonstrated functional proof-of-concept workflows, an exhaustive architectural and security inspection identified critical deficiencies across five key dimensions:
1. **Application Security & Network Isolation:** Insecure TLS (`verify=False`), lack of Server-Side Request Forgery (SSRF) defenses, lack of IP blocklists, and unmetered endpoints.
2. **Persistence & Serverless Deployment:** Dependence on local ephemeral SQLite (`klein_research.db`) in a serverless environment (Vercel) where container filesystems are read-only or reset on cold start.
3. **Citation & Research Integrity:** Trivial heuristic "verification" based only on domain substring matching and content character length; hardcoded publication years; lack of real Crossref / OpenAlex / DOI metadata cross-checking; lack of claim-to-evidence passage validation.
4. **API Reliability & Synchronous Execution:** Long-running synchronous HTTP requests (30–90 seconds) exceeding serverless execution timeouts; lack of background job queue abstraction.
5. **UI & Data Presentation:** Deployed landing page functioned as a rudimentary API test console rather than a data-rich academic research platform.

---

## 2. Component-by-Component Architectural Audit

| Component | File Path | Existing Implementation | Confirmed Vulnerabilities / Flaws | Severity |
| :--- | :--- | :--- | :--- | :--- |
| **Scraping Engine** | `core/search_engine.py` | `requests.get()` with BS4 DOM parsing; Tavily, DuckDuckGo, Wikipedia fallbacks | • `verify=False` disables TLS certificate verification.<br>• `urllib3.disable_warnings` masks insecure connections.<br>• No validation against private/loopback/cloud metadata IPs (SSRF).<br>• No response streaming or size caps (DoS via oversized payloads). | **CRITICAL** |
| **Database & Persistence** | `core/database.py` | SQLite file `klein_research.db` in workspace root | • Ephemeral storage on Vercel serverless (data loss on instance cycle).<br>• No PostgreSQL / `DATABASE_URL` support.<br>• No connection pooling or migration mechanism.<br>• Local system timestamps without UTC.<br>• Truncated 8-char session IDs (`uuid[:8]`). | **HIGH** |
| **Citation Auditor** | `core/citation_auditor.py` | Regex URL check + domain string matching (`ncbi`, `ieee`, `.edu`) | • Sources marked "VERIFIED" without checking claim support or actual publication.<br>• Publication year hardcoded to `2025` in APA and BibTeX.<br>• No integration with Crossref, OpenAlex, or DOI resolution APIs.<br>• No passage-level claim-to-evidence mapping. | **HIGH** |
| **API Entrypoint** | `app.py` | WSGI callable `app` + Streamlit dashboard dispatcher | • Wildcard CORS (`*`) on all routes without origin filtering.<br>• No rate limiting on expensive AI endpoints.<br>• Synchronous research execution in HTTP handler (timeout hazard).<br>• Masked key diagnostics leaked character count and prefixes/suffixes. | **HIGH** |
| **Research Orchestrator**| `core/researcher.py` | 17-step synchronous pipeline invoking `gemini_client` and `tools.py` | • Monolithic single-thread execution.<br>• No job queue or checkpoint persistence.<br>• No independent review/verification agent stage before synthesis. | **MEDIUM** |
| **Model Configuration** | `core/config.py` | Hardcoded `DEFAULT_GEMINI_MODEL` and fallback model lists | • Inconsistent model names between UI, documentation, and backend.<br>• No runtime validation of configured model availability. | **MEDIUM** |
| **Demo Dataset** | `core/demo_dataset.py` | Pre-computed JSON dataset for zero-quota simulations | • Synthetic/unverified document identifiers and claims without DOI resolution.<br>• Needed explicit labeling as a simulated demo. | **MEDIUM** |
| **User Interface** | `app.py` (HTML & Streamlit) | Basic dark-mode console with topic input & raw JSON box | • Lacked structured academic views: Literature Explorer, Comparative Matrix, Evidence Inspector, Research Library, Analytics. | **MEDIUM** |

---

## 3. Detailed Security Findings

### SEC-01: Insecure TLS Certificate Verification (`verify=False`)
- **Location:** `core/search_engine.py:179`
- **Issue:** Web page DOM extraction explicitly disabled certificate validation:
  ```python
  resp = self.session.get(url, timeout=DEFAULT_TIMEOUT, verify=False)
  ```
- **Risk:** Man-in-the-Middle (MitM) attacks. An attacker on the local network or upstream DNS can intercept requests, inject malicious payloads, or manipulate research evidence.
- **Remediation:** Remove `verify=False`, enforce strict certificate verification, and reject unverified HTTPS connections.

### SEC-02: Server-Side Request Forgery (SSRF) & Unrestricted URL Ingestion
- **Location:** `core/search_engine.py:170-205`
- **Issue:** `extract_page_content` accepted any user- or search-provided URL. There was no validation ensuring the resolved IP address is a public IP.
- **Risk:** Attackers can submit topics or manipulate search responses to target `http://127.0.0.1:8501`, internal microservices, or cloud metadata endpoints (`http://169.254.169.254/latest/meta-data/` on AWS/GCP/Vercel) to exfiltrate infrastructure credentials.
- **Remediation:** Implement a comprehensive SSRF defense filter before issuing any HTTP request:
  - Validate URL scheme (strictly `http://` and `https://`).
  - Resolve hostname to IP addresses and block: `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, `::1`, and IPv6 unique local / link-local addresses.
  - Follow redirects manually or re-validate redirect destination IPs to prevent DNS rebinding or redirect-based SSRF.
  - Enforce max response size limit (e.g., 2 MB) using response streaming.

### SEC-03: Secret Exposure & Diagnostic Information Disclosure
- **Location:** `core/config.py:52-60` and `app.py:1038`
- **Issue:** `mask_api_key()` revealed the first 6 and last 4 characters along with the total character count:
  `AIzaSy...UkBx (39 chars)`
- **Risk:** Reduces entropy for brute-forcing and exposes provider-specific key structure in public health checks.
- **Remediation:** Health and diagnostic endpoints must report only boolean `configured: true/false`. Never expose prefixes, suffixes, or lengths.

### SEC-04: Ephemeral Database in Serverless Environments
- **Location:** `core/database.py`
- **Issue:** SQLite file `klein_research.db` is stored locally. On Vercel, serverless containers are ephemeral and stateless; any session saved to SQLite is lost when the instance scales down or terminates.
- **Remediation:** Introduce an abstracted database layer supporting **PostgreSQL** via `DATABASE_URL` (with connection pooling via `psycopg`), automated schema migrations, and UTC timestamps, while preserving SQLite for local desktop development.

### SEC-05: Missing Rate Limiting and Wildcard CORS
- **Location:** `app.py:990-1015`
- **Issue:** All WSGI routes sent `Access-Control-Allow-Origin: *` and permitted unlimited calls to `/api/research`.
- **Risk:** Automated scraping, resource exhaustion, and Denial-of-Wallet through unbounded Gemini API requests.
- **Remediation:** Restrict CORS to configured allowed origins and add in-memory / token-bucket rate limiting to research execution routes.

---

## 4. Research Integrity Weaknesses

1. **Heuristic Citation Tagging:** Sources were categorized as "Authoritative Academic" if their domain string contained words like `ncbi`, `ieee`, or `.edu`. A malicious or low-quality blog on a `.edu` personal domain or an irrelevant PubMed paper would be marked fully verified.
2. **No Claim-to-Evidence Verification:** The orchestrator extracted text from sources and independently asked Gemini to write a literature review. It did not cross-verify each generated sentence against direct quotations or extracted passages from the cited documents.
3. **Hardcoded Bibliographic Information:** The year `2025` was hardcoded into APA and BibTeX formats, producing incorrect metadata for foundational papers published earlier.
4. **Lack of Metadata API Cross-Validation:** No integration with authoritative scholarly metadata registries (Crossref, OpenAlex, Semantic Scholar, or official DOI content negotiation).

---

## 5. Architectural Upgrade Plan (Klein AI 2.0)

1. **Phase 2 (Security & API Reliability):**
   - Safe HTTP client in `core/search_engine.py` with DNS resolution checking, private IP blocklist, redirect validation, and stream size limiting.
   - Minimalist, leak-free `/api/health` diagnostics.
   - Configurable CORS origin whitelist and sliding-window rate limiting on research submission.
   - Request-ID injection on all responses for auditability.
2. **Phase 3 (Persistent Database Architecture):**
   - Universal database adapter (`core/database.py`) connecting to PostgreSQL (`DATABASE_URL`) with connection pooling, automatic schema creation/migrations, parameterized queries, UUIDv4 session keys, and SQLite local fallback.
3. **Phase 4 (Scholarly Citation & Verification Engine):**
   - Crossref and OpenAlex API integrations in `core/citation_auditor.py`.
   - Discrete verification statuses: `URL_REACHABLE`, `METADATA_MATCHED`, `CONTENT_EXTRACTED`, `CLAIM_SUPPORTED`, `PARTIALLY_VERIFIED`, `UNVERIFIED`, `VERIFICATION_FAILED`.
   - Real metadata extraction (DOI, Authors, Year, Journal/Publisher).
   - Claim-to-evidence passage matching algorithm.
   - Proper APA 7th, IEEE, BibTeX, and RIS output generation without hardcoding.
4. **Phase 5 (Research Orchestration & Background Execution):**
   - Async job abstraction supporting Redis-backed or in-memory queued execution.
   - Independent Reviewer validation stage.
   - Checkpoint persistence and structured job status tracking (`queued`, `running`, `completed`, `failed`).
5. **Phase 6 (SaaS User Interface Redesign):**
   - Modern, scientific, data-focused dark-mode UI inspired by Linear, Notion, and Perplexity.
   - Distinct views: Dashboard, New Research, Library, Evidence Explorer, Comparative Matrix, Research Gaps, Analytics, Export Center.
6. **Phase 7 (Artifact Exports):**
   - Enhanced ReportLab PDF and PowerPoint deck compilation with verified metadata and clickable references.
7. **Phase 8 (Demo Dataset Validation):**
   - Replace synthetic entries with genuine, DOI-verified scientific literature, explicitly labeled as `SIMULATED DEMO`.
8. **Phase 9 & 10 (Verification & Documentation):**
   - Comprehensive automated test suite and production deployment guides.
