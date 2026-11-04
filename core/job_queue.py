"""
Klein AI - Distributed & Local Background Research Job Queue (Version 2.0)
Provides asynchronous job submission, execution progress tracking, bounded concurrency,
PostgreSQL database persistence (via core.database), and Redis-backed queue pub/sub when configured.
Enforces that job progress and status survive across serverless function instances.
"""
import os
import json
import uuid
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor

from core.config import REDIS_URL, MAX_CONCURRENT_JOBS, JOB_TIMEOUT_SECONDS
from core.database import (
    db_create_job,
    db_get_job,
    db_update_job_progress,
    db_complete_job,
    db_fail_job,
    db_list_jobs
)


class JobManager:
    """
    Manages asynchronous research job lifecycles.
    Supports status polling, step progress reporting, checkpoints, and failure recovery.
    Backed by PostgreSQL / SQLite and optional Redis queue.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._memory_jobs: Dict[str, Dict[str, Any]] = {}
        self._executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS, thread_name_prefix="klein-worker")
        self._redis_client = None
        self._init_redis()

    def _init_redis(self):
        if REDIS_URL:
            try:
                import redis
                client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=5)
                client.ping()
                self._redis_client = client
                print(f"[JobQueue] Connected to Redis at {REDIS_URL.split('@')[-1]}")
            except Exception as e:
                print(f"[JobQueue] Redis connection failed ({e}). Defaulting to database persistence.")
                self._redis_client = None

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_job(self, topic: str, user_id: str = "anonymous", model: Optional[str] = None) -> str:
        """Initializes a new job entry in database and returns its UUIDv4 identifier."""
        job_id = str(uuid.uuid4())
        job_data = {
            "id": job_id,
            "topic": topic,
            "status": "queued",
            "progress": 0,
            "stage": "Queued in Research Engine",
            "logs": [f"[{self._now_iso()}] Research investigation queued."],
            "created_at": self._now_iso(),
            "updated_at": self._now_iso(),
            "user_id": user_id,
            "model": model,
            "result": None,
            "error": None
        }

        # 1. Persist to PostgreSQL / SQLite
        db_create_job(job_id=job_id, topic=topic, model=model, user_id=user_id)

        # 2. Publish to Redis if configured
        if self._redis_client:
            try:
                self._redis_client.setex(f"job:{job_id}", JOB_TIMEOUT_SECONDS * 4, json.dumps(job_data))
                self._redis_client.lpush("jobs:active", job_id)
            except Exception as e:
                print(f"[JobQueue] Redis set error: {e}")

        # 3. Cache in memory
        with self._lock:
            self._memory_jobs[job_id] = job_data

        return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves current job status, progress, logs, and result from DB or Redis."""
        if not job_id:
            return None

        # 1. Try Redis
        if self._redis_client:
            try:
                raw = self._redis_client.get(f"job:{job_id}")
                if raw:
                    return json.loads(raw)
            except Exception as e:
                print(f"[JobQueue] Redis get error: {e}")

        # 2. Try PostgreSQL / SQLite DB
        db_job = db_get_job(job_id)
        if db_job:
            with self._lock:
                self._memory_jobs[job_id] = db_job
            return db_job

        # 3. Fallback to memory
        with self._lock:
            return self._memory_jobs.get(job_id)

    def update_progress(self, job_id: str, stage: str, progress: int, log_msg: Optional[str] = None):
        """Updates in-flight job progress percentage, stage description, and log stream."""
        # 1. Update in DB
        db_update_job_progress(job_id, stage=stage, progress=progress, log_msg=log_msg)

        # 2. Update memory & Redis
        with self._lock:
            job = self._memory_jobs.get(job_id)
            if job:
                job["status"] = "running"
                if stage and stage != "Research in progress":
                    job["stage"] = stage
                if progress >= 0:
                    job["progress"] = min(max(int(progress), 0), 100)
                job["updated_at"] = self._now_iso()
                if log_msg:
                    job["logs"].append(f"[{self._now_iso()}] {log_msg}")
                    if len(job["logs"]) > 60:
                        job["logs"] = job["logs"][-60:]

                if self._redis_client:
                    try:
                        self._redis_client.setex(f"job:{job_id}", JOB_TIMEOUT_SECONDS * 4, json.dumps(job))
                    except Exception:
                        pass

    def mark_completed(self, job_id: str, result: Dict[str, Any]):
        """Marks job as completed and stores sanitized research results."""
        # 1. Update in DB
        db_complete_job(job_id, result)

        # 2. Update memory & Redis
        with self._lock:
            job = self._memory_jobs.get(job_id)
            if job:
                job["status"] = "completed"
                job["stage"] = "Research Investigation Completed"
                job["progress"] = 100
                job["updated_at"] = self._now_iso()
                job["logs"].append(f"[{self._now_iso()}] Scientific deliverables compiled successfully.")
                job["result"] = result

                if self._redis_client:
                    try:
                        self._redis_client.setex(f"job:{job_id}", JOB_TIMEOUT_SECONDS * 4, json.dumps(job))
                        self._redis_client.lrem("jobs:active", 0, job_id)
                    except Exception:
                        pass

    def mark_failed(self, job_id: str, error_message: str):
        """Marks job as failed with a sanitized error description."""
        # 1. Update in DB
        db_fail_job(job_id, error_message)

        # 2. Update memory & Redis
        with self._lock:
            job = self._memory_jobs.get(job_id)
            if job:
                job["status"] = "failed"
                job["stage"] = "Research Execution Failed"
                job["updated_at"] = self._now_iso()
                job["error"] = error_message
                job["logs"].append(f"[{self._now_iso()}] ERROR: {error_message}")

                if self._redis_client:
                    try:
                        self._redis_client.setex(f"job:{job_id}", JOB_TIMEOUT_SECONDS * 4, json.dumps(job))
                        self._redis_client.lrem("jobs:active", 0, job_id)
                    except Exception:
                        pass

    def list_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Lists active and recent research jobs from database."""
        db_jobs = db_list_jobs(limit=limit)
        if db_jobs:
            return db_jobs

        with self._lock:
            items = list(self._memory_jobs.values())
            items.sort(key=lambda j: j.get("created_at", ""), reverse=True)
            summary_list = []
            for j in items[:limit]:
                copy_j = {k: v for k, v in j.items() if k != "result"}
                copy_j["has_result"] = bool(j.get("result"))
                summary_list.append(copy_j)
            return summary_list

    def submit_research_job(
        self,
        topic: str,
        gemini_api_key: Optional[str] = None,
        tavily_api_key: Optional[str] = None,
        model: Optional[str] = None,
        user_id: str = "anonymous"
    ) -> str:
        """
        Submits a research job and dispatches worker task.
        """
        job_id = self.create_job(topic, user_id=user_id, model=model)

        def worker_task():
            from core.researcher import KleinResearchAgent
            try:
                self.update_progress(job_id, "Initializing Agent Orchestrator", 5, "Configuring tools and clients...")
                agent = KleinResearchAgent(
                    gemini_api_key=gemini_api_key,
                    tavily_api_key=tavily_api_key,
                    model=model
                )

                def on_step(idx, total, title, desc):
                    pct = int(10 + (idx / total) * 85)
                    self.update_progress(job_id, title, pct, f"{title}: {desc}")

                def on_log(msg):
                    self.update_progress(job_id, "Research in progress", -1, msg)

                result = agent.execute_research(
                    topic=topic,
                    step_callback=on_step,
                    log_callback=on_log
                )
                self.mark_completed(job_id, result)
            except Exception as e:
                self.mark_failed(job_id, str(e))

        self._executor.submit(worker_task)
        return job_id


# Singleton instance
job_manager = JobManager()
