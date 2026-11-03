# 📖 Klein AI — Comprehensive Project Documentation

## 1. Project Overview & Identity
- **Project Name:** Klein AI (formerly ResearchMate AI)
- **Tagline:** One Topic. Complete Research. Powered by AI.
- **Classification:** Autonomous Scientific Research Agent & Whitepaper Generation System
- **Evaluation Purpose:** College Capstone Project Deliverable (4-Member Team)

---

## 2. Problem Statement
Modern academic and technical research requires extensive manual synthesis across fragmented scientific databases, preprints, whitepapers, and regulatory standards. Researchers and students spend up to 70% of their time performing repetitive manual tasks:
1. Discovering authoritative peer-reviewed papers.
2. Filtering out promotional or paywalled content.
3. Manually mapping points of consensus and disagreement across multiple sources.
4. Identifying unresolved research gaps.
5. Drafting formal literature reviews and formatting citations.
6. Assembling PowerPoint presentation decks and publication-ready PDF whitepapers.

**Klein AI solves this by automating the entire lifecycle from a single user prompt.**

---

## 3. Core Objectives
1. **Zero-Manual-Upload Autonomous Research:** Crawl the live internet dynamically using Tavily AI Search, DuckDuckGo, and scholarly indices without requiring manual PDF uploads.
2. **Multi-Aspect Cross-Source Synthesis:** Contrast traditional rule-based paradigms against state-of-the-art AI architectures, identifying empirical contradictions and consensus.
3. **Structured Tool Calling & Auditing:** Decouple reasoning from execution via a formal Python Tool Registry with input validation, bounded timeouts, and execution tracking.
4. **Automated Deliverable Generation:** Compile publication-standard multi-page PDF reports (ReportLab) and 16:9 widescreen PowerPoint presentation decks (`python-pptx`) instantly.
5. **Bibliographic Integrity & Verification:** Audit all references against real retrieved URLs, preventing AI hallucination in citations.

---

## 4. Key Architectural Modules

### `core/tools.py` — Tool Registry & Execution Engine
Decoupled tool calling interface with strict input verification:
- `search_web(query, aspect)`: Aspect-driven query search.
- `extract_webpage(url)`: Robust DOM text scraping with noise and boilerplate decomposition.
- `analyse_source(source)`: Authority scoring (`.edu`, `.gov`, `ncbi`, `ieee`) and empirical data extraction.
- `compare_sources(topic, sources)`: Cross-source matrix generation.
- `generate_literature_review(data)`: Thematic review synthesis with in-text citations.
- `identify_research_gaps(data)`: Taxonomy of structural, algorithmic, and deployment gaps (`GAP-01` to `GAP-04`).
- `propose_methodology(data)`: Novel architectural framework and pipeline components.
- `audit_citations(sources)`: Bibliographic validation and APA/BibTeX formatting.
- `generate_report(data)`: Scholarly markdown whitepaper generation.
- `generate_presentation(data)`: PowerPoint deck builder.

### `core/researcher.py` — Autonomous Orchestrator
Manages the 17-step state machine with adaptive decision loops:
- **Adaptive Query Expansion:** If initial search yields fewer than 4 unique authoritative sources, the agent autonomously formulates secondary fallback queries.
- **Canonical URL Deduplication:** Normalizes URLs by stripping tracking parameters (`utm_*`, `ref`, `fbclid`) and deduplicates based on semantic title hashing.
- **Inaccessible Source Recovery:** Gracefully falls back to search snippets if a page is paywalled or protected without crashing.
- **Audit Logging:** Records every tool call with latency in milliseconds.

### `core/search_engine.py` — Multi-Tier Web Search Engine
- Primary: **Tavily AI Search** (Deep research mode).
- Automatic Fallback 1: **DuckDuckGo Search (`ddgs`)** (Zero-config free web search).
- Automatic Fallback 2: **Wikipedia Scholarly API** (Guaranteed encyclopedic and technical fallback).
- Content Scraper: **BeautifulSoup4** with ad-blocking decomposition and paragraph cleaning.

### `core/pdf_generator.py` — Publication PDF Engine
- Built with **ReportLab**.
- Custom `NumberedCanvas` dynamically computes "Page X of Y" and running headers on pages 2+.
- Clean typography (Helvetica), styled metadata boxes, comparative tables, and callout blocks.
- Smart unicode sanitization prevents `UnicodeEncodeError`.

### `core/ppt_generator.py` — Presentation Deck Builder
- Built with **`python-pptx`**.
- 16:9 Widescreen format (13.333" x 7.5").
- Dark slate `#0F172A` title slide with indigo accent cards and formatted takeaways.

### `core/database.py` — SQLite Persistence
- Embedded SQLite database (`klein_research.db`).
- Archives all completed research sessions with 1-click reload and inspection capabilities.

---

## 5. Security & Verification
- **API Key Masking:** All API keys are password-masked in the UI.
- **Zero Committed Secrets:** `.env` and `klein_research.db` are strictly excluded in `.gitignore`.
- **Bounded Exponential Backoff:** API calls retry up to 3 times with random jitter during transient spikes.
- **Input Sanitization:** URL schemes and search query inputs are validated before execution.

---

## 6. How to Run & Verify
```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run unit & smoke tests
python test_system.py

# 3. Run formal E2E test
python test_e2e_topic.py

# 4. Launch web application
streamlit run app.py
```
Open **`http://localhost:8501`** in any web browser.
