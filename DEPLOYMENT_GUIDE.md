# Klein AI 2.0 — Production Deployment Guide

This guide covers production deployment of **Klein AI 2.0** as a unified web application on **Vercel** with managed **PostgreSQL** persistence and optional background queue infrastructure.

---

## 1. Architecture Overview

- **Primary Web Platform:** Vercel Serverless Functions (`app.py`, Python 3.12/3.13 WSGI).
- **Relational Database:** Managed PostgreSQL (Neon, Supabase, or AWS RDS).
- **Background Queue (Optional):** Upstash Redis or managed Redis.
- **Background Worker (Optional):** Standalone persistent container (`worker.py` on Railway, Render, or Docker).
- **AI Models:** Google Gemini 2.5 Flash, 2.0 Flash, 1.5 Pro via Google AI Studio.
- **Scholarly Search:** Tavily Search API with DuckDuckGo fallback.

---

## 2. Environment Variables Configuration

Configure the following environment variables in your Vercel Project Settings (**Settings → Environment Variables**):

| Variable | Description | Required? | Example |
|---|---|---|---|
| `GEMINI_API_KEY` | Google Gemini API key from Google AI Studio | **Yes** (or provided via user session) | `AIzaSy...` |
| `DATABASE_URL` | PostgreSQL connection string | **Recommended** (defaults to SQLite fallback) | `postgresql://user:pass@ep-xyz.neon.tech/neondb?sslmode=require` |
| `SECRET_KEY` | Master secret key for server-side session encryption | **Recommended** | `e1b78c9...32-char-random-string` |
| `TAVILY_API_KEY` | Tavily Search API key for deep academic search | Optional (defaults to DuckDuckGo) | `tvly-...` |
| `REDIS_URL` | Redis URL for distributed asynchronous background jobs | Optional | `rediss://default:pass@endpoint.upstash.io:6379` |
| `GEMINI_MODEL` | Default reasoning engine model | Optional (defaults to `gemini-2.5-flash`) | `gemini-2.5-flash` |
| `ALLOWED_ORIGINS` | Permitted CORS origins (comma-separated) | Optional | `https://kleinai.vercel.app,http://localhost:3000` |

---

## 3. Vercel Configuration (`vercel.json`)

Ensure your `vercel.json` matches this configuration:

```json
{
  "version": 2,
  "functions": {
    "app.py": {
      "maxDuration": 60
    }
  },
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/app.py?__path=/$1"
    }
  ]
}
```

> **Why `maxDuration: 60`?**
> The 17-step autonomous research pipeline synthesizes scholarly literature and verifies Crossref DOIs. Setting `maxDuration: 60` grants sufficient execution window on Vercel Hobby and Pro tiers.

---

## 4. Database Setup (Neon Serverless PostgreSQL)

1. Create a free account at [https://neon.tech/](https://neon.tech/).
2. Create a new project called `klein-ai-db`.
3. Copy the **Connection String** (e.g., `postgresql://...neon.tech/neondb?sslmode=require`).
4. In Vercel, add the environment variable `DATABASE_URL` with this connection string.
5. Klein AI will automatically run migrations upon startup (`research_sessions` and `research_jobs` tables).

---

## 5. Deploying to Vercel via Git

Deployments are automated through Git:

```bash
# Verify working tree is clean
git status

# Stage all files
git add .

# Commit changes
git commit -m "feat(vercel): complete vercel-first migration and remove streamlit dependency"

# Push to production branch
git push origin main
```

Vercel will detect the push, run the build using `requirements.txt`, and deploy the application in under 30 seconds.

---

## 6. Optional: Deploying Standalone Background Worker

For heavy batch workloads or asynchronous queueing:

1. Deploy `worker.py` to **Railway** or **Render**:
   - Runtime: Python 3.12 / 3.13
   - Start Command: `python worker.py`
2. Connect the worker to the same `DATABASE_URL` and `REDIS_URL`.
3. When users trigger asynchronous research (`POST /api/jobs`), the job is persisted to PostgreSQL, queued in Redis, and executed by the standalone worker while users monitor live progress on `https://kleinai.vercel.app/`.

---

## 7. Verification & Health Monitoring

After deployment, test the following endpoints:

- **Web Dashboard:** `https://kleinai.vercel.app/`
- **Health Check:** `https://kleinai.vercel.app/api/health`
- **Config Status:** `https://kleinai.vercel.app/api/config/status`
- **Demo Whitepaper PDF:** `https://kleinai.vercel.app/api/download/pdf?id=demo`
- **Demo Slides Deck:** `https://kleinai.vercel.app/api/download/pptx?id=demo`
