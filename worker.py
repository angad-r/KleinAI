"""
Klein AI - Standalone Background Research Worker Entrypoint (Version 2.0)
Continuously consumes and executes queued scientific research jobs from Redis or PostgreSQL.
Suitable for persistent background workers on Railway, Render, Fly.io, or Docker containers.
"""
import os
import sys
import time
import json
import signal
from datetime import datetime, timezone

from core.config import REDIS_URL, JOB_TIMEOUT_SECONDS, get_gemini_api_key, get_tavily_api_key
from core.job_queue import job_manager
from core.researcher import KleinResearchAgent
from core.database import init_db, db_list_jobs

running = True


def handle_shutdown(signum, frame):
    global running
    print(f"\n[Worker] Received signal {signum}. Shutting down worker gracefully...")
    running = False


signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


def process_single_job(job_id: str):
    """Fetches and executes a single queued research job."""
    job_data = job_manager.get_job(job_id)
    if not job_data or job_data.get("status") != "queued":
        return

    topic = job_data.get("topic")
    model = job_data.get("model")
    print(f"[Worker] Processing job {job_id} for topic: '{topic}'")

    job_manager.update_progress(job_id, "Worker Initializing", 5, "Starting autonomous agent...")
    try:
        agent = KleinResearchAgent(
            gemini_api_key=get_gemini_api_key(),
            tavily_api_key=get_tavily_api_key(),
            model=model
        )

        def on_step(idx, total, title, desc):
            pct = int(10 + (idx / total) * 85)
            job_manager.update_progress(job_id, title, pct, f"{title}: {desc}")

        def on_log(msg):
            job_manager.update_progress(job_id, "In Progress", -1, msg)

        result = agent.execute_research(
            topic=topic,
            step_callback=on_step,
            log_callback=on_log
        )
        job_manager.mark_completed(job_id, result)
        print(f"[Worker] Job {job_id} completed successfully.")
    except Exception as e:
        job_manager.mark_failed(job_id, str(e))
        print(f"[Worker] Job {job_id} failed: {e}")


def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Klein AI Background Research Worker 2.0 started.")
    init_db()

    client = None
    if REDIS_URL:
        try:
            import redis
            client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=10)
            client.ping()
            print(f"[Worker] Connected to Redis queue at {REDIS_URL.split('@')[-1]}")
        except Exception as e:
            print(f"[Worker] Redis connection failed: {e}. Falling back to database polling.")
            client = None
    else:
        print("[Worker] REDIS_URL not configured. Operating in database queue polling mode.")

    while running:
        if client:
            try:
                # Pop job ID from active queue with 5 second timeout
                item = client.brpop("jobs:active", timeout=5)
                if item:
                    _, job_id = item
                    process_single_job(job_id)
            except Exception as e:
                print(f"[Worker] Redis queue error: {e}")
                time.sleep(2)
        else:
            # Poll PostgreSQL/SQLite for queued jobs
            try:
                jobs = db_list_jobs(limit=5)
                queued_jobs = [j for j in jobs if j.get("status") == "queued"]
                if queued_jobs:
                    for j in queued_jobs:
                        process_single_job(j["id"])
                else:
                    time.sleep(3)
            except Exception as e:
                print(f"[Worker] Database polling error: {e}")
                time.sleep(5)

    print("[Worker] Worker exited cleanly.")


if __name__ == "__main__":
    main()
