# Klein AI 2.0 — Production Deployment & Operations Guide

This guide covers production deployment of **Klein AI 2.0** on **Vercel** (serverless API runtime), **Neon / Supabase** (PostgreSQL persistence), **Upstash** (Redis job queue), and standalone servers (Docker, Railway, Streamlit GUI).

---

## 1. System Architecture Overview

```
                      +---------------------------------------+
                      |       Client (Web Browser / API)      |
                      +---------------------------------------+
                                          |
                      HTTPS (TLS 1.3) / JSON / REST / WSS
                                          |
                                          v
                      +---------------------------------------+
                      |       Vercel Serverless Edge          |
                      |        app.py (WSGI Handler)          |
                      +---------------------------------------+
                                          |
                  +-----------------------+-----------------------+
                  |                                               |
                  v                                               v
    +---------------------------+                   +---------------------------+
    |   Neon / Supabase PG      |                   |    Upstash / Redis Queue  |
    |   (Universal DB Pool)     |                   |    (Job State & Events)   |
    +---------------------------+                   +---------------------------+
                  |                                               |
                  +-----------------------+-----------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |   Autonomous Multi-Agent Researcher   |
                      |   - Google Gemini 2.5 / 2.0 Flash     |
                      |   - Crossref & DOI.org Verification   |
                      |   - ReportLab PDF & python-pptx       |
                      +---------------------------------------+
```

---

## 2. Environment Variables Specification

Configure these environment variables in your deployment dashboard (e.g. Vercel Project Settings > Environment Variables):

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `GEMINI_API_KEY` | **Yes** | — | Google Gemini API key from [Google AI Studio](https://aistudio.google.com/). |
| `TAVILY_API_KEY` | Optional | `""` | Tavily search API key for real-time academic queries. Falls back to DuckDuckGo if unset. |
| `DATABASE_URL` | Recommended | `""` | Managed PostgreSQL connection string (Neon, Supabase, AWS RDS, CockroachDB). Falls back to SQLite if unset. |
| `REDIS_URL` | Optional | `""` | Redis connection URL for distributed background jobs (Upstash, Redis Cloud). Falls back to thread pool if unset. |
| `GEMINI_MODEL` | Optional | `gemini-2.5-flash` | Reasoning model. Supported: `gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-1.5-pro`, `gemini-1.5-flash`. |
| `ALLOWED_ORIGINS` | Optional | `https://kleinai.vercel.app` | Comma-separated list of permitted CORS origins. Use `*` to allow all origins. |
| `MAX_CONCURRENT_JOBS` | Optional | `4` | Maximum concurrent background research jobs per instance. |
| `JOB_TIMEOUT_SECONDS` | Optional | `300` | Research job execution timeout in seconds. |

---

## 3. Step-by-Step Vercel Deployment

Klein AI includes a preconfigured `vercel.json` optimized for serverless Python execution.

### Step 3.1: Connect Repository to Vercel
1. Navigate to the [Vercel Dashboard](https://vercel.com/new).
2. Import the GitHub repository: `https://github.com/angad-r/KleinAI`.
3. Set Framework Preset to **Other**.
4. Set Root Directory to `./`.

### Step 3.2: Set Environment Variables
Add the following in Vercel **Project Settings > Environment Variables**:
- `GEMINI_API_KEY`: `AIzaSy...`
- `TAVILY_API_KEY`: `tvly-...` (optional)
- `DATABASE_URL`: `postgresql://user:password@ep-cool-db.us-east-2.aws.neon.tech/neondb?sslmode=require`
- `ALLOWED_ORIGINS`: `https://kleinai.vercel.app,https://yourcustomdomain.com`

### Step 3.3: Deploy
Click **Deploy**. Vercel will install dependencies from `requirements.txt` using Python 3.12/3.13 and deploy the WSGI application entrypoint (`app.py`).

Verify the deployment:
```bash
# Check health diagnostics
curl -s https://kleinai.vercel.app/api/health

# Output:
# {
#   "status": "healthy",
#   "app": "Klein AI",
#   "version": "2.0.0",
#   "gemini_configured": true,
#   "tavily_configured": true,
#   "database_connected": true,
#   "database_backend": "postgresql",
#   "default_model": "gemini-2.5-flash"
# }
```

---

## 4. Database Setup (Neon PostgreSQL)

1. Create a free PostgreSQL instance at [Neon](https://neon.tech/) or [Supabase](https://supabase.com/).
2. Copy the Connection String URI with pooled connections:
   ```
   postgresql://username:password@ep-example-pooler.region.neon.tech/neondb?sslmode=require
   ```
3. Set `DATABASE_URL` in your environment.
4. Klein AI will automatically run migrations upon startup (`init_db()`), creating:
   - `schema_migrations`
   - `research_sessions`

---

## 5. Background Worker Deployment (Railway / Docker / VPS)

For long-running research pipelines exceeding serverless function execution limits (10-60 seconds), deploy `worker.py` on a standalone host with Redis.

### Dockerfile Example
```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run standalone worker
CMD ["python", "worker.py"]
```

Run worker:
```bash
export GEMINI_API_KEY="AIzaSy..."
export REDIS_URL="rediss://default:token@region.upstash.io:6379"
export DATABASE_URL="postgresql://..."

python worker.py
```

---

## 6. Local Development & Desktop GUI

### Run Streamlit Web Application
```bash
# Install dependencies
pip install -r requirements.txt

# Start interactive local dashboard on port 8501
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

### Run WSGI Server Locally (Waitress / Gunicorn)
```bash
# Windows / Linux with Waitress
pip install waitress
waitress-serve --port=5000 app:app
```
Open [http://localhost:5000](http://localhost:5000) for the modern dark SaaS UI.

---

## 7. Troubleshooting & Verification

### Verifying SSRF Protection
```bash
# Verify loopback target is blocked safely
python -c "from core.search_engine import SearchEngine; print(SearchEngine.is_safe_url('http://169.254.169.254/latest/meta-data/'))"
# Output: (False, 'Blocked target: IP 169.254.169.254 is link-local or cloud metadata')
```

### Verifying DOI Content Negotiation
```bash
python -c "from core.citation_auditor import CitationAuditor; print(CitationAuditor.query_doi_metadata('10.6028/NIST.SP.800-207'))"
```

### Running Test Suite
```bash
python -m pytest tests/ -v
# Output: 53 passed in ~57s
```
