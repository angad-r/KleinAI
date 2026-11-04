"""
Klein AI - Universal Database Persistence Engine (Version 2.0)
Supports PostgreSQL (via DATABASE_URL with connection pooling) in production
and SQLite in local development and testing.
Enforces parameterized queries, UTC timestamps, schema migrations, and full UUID session IDs.
"""
import os
import json
import uuid
import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from core.config import DATABASE_URL, DB_PATH

# Global connection pool for PostgreSQL
_PG_POOL = None


def get_utc_now_iso() -> str:
    """Returns current UTC timestamp in standardized ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def is_postgres_configured() -> bool:
    """Returns True if a valid PostgreSQL DATABASE_URL is configured."""
    return bool(DATABASE_URL and (DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")))


def get_pg_pool():
    """Initializes and returns a psycopg connection pool for PostgreSQL."""
    global _PG_POOL
    if _PG_POOL is None and is_postgres_configured():
        try:
            from psycopg_pool import ConnectionPool
            # Standardize postgres:// to postgresql://
            conn_url = DATABASE_URL
            if conn_url.startswith("postgres://"):
                conn_url = "postgresql://" + conn_url[len("postgres://"):]
            
            _PG_POOL = ConnectionPool(
                conninfo=conn_url,
                min_size=1,
                max_size=5,
                timeout=10.0,
                open=True
            )
        except Exception as e:
            print(f"[Database] Warning: Failed to initialize PostgreSQL pool: {e}. Falling back to SQLite.")
            _PG_POOL = None
    return _PG_POOL


def get_sqlite_connection():
    """Returns a SQLite connection configured with Row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> bool:
    """
    Initializes database schema and executes migrations.
    Applies to PostgreSQL when configured; otherwise initializes SQLite.
    Returns True if database is healthy and ready.
    """
    pool = get_pg_pool()
    if pool is not None:
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    # Migration tracking table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS schema_migrations (
                            version VARCHAR(64) PRIMARY KEY,
                            applied_at TIMESTAMP WITH TIME ZONE NOT NULL
                        )
                    """)
                    
                    # Core sessions table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS research_sessions (
                            id VARCHAR(64) PRIMARY KEY,
                            topic TEXT NOT NULL,
                            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                            updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
                            status VARCHAR(32) NOT NULL,
                            source_count INTEGER DEFAULT 0,
                            summary TEXT,
                            data_json TEXT NOT NULL,
                            user_id VARCHAR(64) DEFAULT 'anonymous'
                        )
                    """)

                    # Persistent background research jobs table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS research_jobs (
                            id VARCHAR(64) PRIMARY KEY,
                            topic TEXT NOT NULL,
                            status VARCHAR(32) NOT NULL,
                            progress INTEGER DEFAULT 0,
                            stage TEXT,
                            logs_json TEXT,
                            result_json TEXT,
                            error TEXT,
                            model VARCHAR(64),
                            user_id VARCHAR(64) DEFAULT 'anonymous',
                            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                            updated_at TIMESTAMP WITH TIME ZONE NOT NULL
                        )
                    """)
                    
                    # Record baseline migration
                    cur.execute("""
                        INSERT INTO schema_migrations (version, applied_at)
                        VALUES (%s, %s)
                        ON CONFLICT (version) DO NOTHING
                    """, ("v2_0_initial_pg_schema", datetime.now(timezone.utc)))
                    conn.commit()
            return True
        except Exception as e:
            print(f"[Database] PostgreSQL initialization error: {e}. Using SQLite fallback.")
    
    # SQLite local fallback
    try:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS research_sessions (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL,
                source_count INTEGER DEFAULT 0,
                summary TEXT,
                data_json TEXT NOT NULL,
                user_id TEXT DEFAULT 'anonymous'
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS research_jobs (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER DEFAULT 0,
                stage TEXT,
                logs_json TEXT,
                result_json TEXT,
                error TEXT,
                model TEXT,
                user_id TEXT DEFAULT 'anonymous',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        # If older schema exists without updated_at or user_id, add them safely
        try:
            cur.execute("ALTER TABLE research_sessions ADD COLUMN updated_at TEXT")
        except sqlite3.OperationalError:
            pass  # Already exists
        try:
            cur.execute("ALTER TABLE research_sessions ADD COLUMN user_id TEXT DEFAULT 'anonymous'")
        except sqlite3.OperationalError:
            pass  # Already exists

        now = get_utc_now_iso()
        cur.execute("""
            INSERT OR IGNORE INTO schema_migrations (version, applied_at)
            VALUES (?, ?)
        """, ("v2_0_initial_sqlite_schema", now))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[Database] SQLite initialization error: {e}")
        return False


class DBHealthResult(dict):
    """Health check result behaving as both a dictionary and a 2-tuple for backwards compatibility."""
    def __iter__(self):
        yield self.get("connected", False)
        yield self.get("message", "")


def check_db_health() -> DBHealthResult:
    """Tests connectivity to the active database backend."""
    pool = get_pg_pool()
    if pool is not None:
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return DBHealthResult({"connected": True, "backend": "postgresql", "message": "PostgreSQL (Connected)"})
        except Exception as e:
            return DBHealthResult({"connected": False, "backend": "postgresql", "message": f"PostgreSQL Error: {e}"})

    try:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        conn.close()
        return DBHealthResult({"connected": True, "backend": "sqlite", "message": "SQLite (Local Persistent)"})
    except Exception as e:
        return DBHealthResult({"connected": False, "backend": "sqlite", "message": f"SQLite Error: {e}"})


def save_session(
    session_id: str,
    topic: str,
    status: str,
    source_count: int,
    summary: str,
    data: Dict[str, Any],
    user_id: str = "anonymous"
) -> bool:
    """
    Persists or updates a research session.
    Uses parameterized SQL and never silently claims success on persistence failure.
    """
    init_db()
    now_utc = get_utc_now_iso()
    serialized_data = json.dumps(data, ensure_ascii=False)

    pool = get_pg_pool()
    if pool is not None:
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO research_sessions (id, topic, created_at, updated_at, status, source_count, summary, data_json, user_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            updated_at = EXCLUDED.updated_at,
                            status = EXCLUDED.status,
                            source_count = EXCLUDED.source_count,
                            summary = EXCLUDED.summary,
                            data_json = EXCLUDED.data_json
                    """, (session_id, topic, datetime.now(timezone.utc), datetime.now(timezone.utc), status, source_count, summary, serialized_data, user_id))
                    conn.commit()
            return True
        except Exception as e:
            print(f"[Database] PostgreSQL save_session failed: {e}")
            # Fall through to SQLite backup if configured
            pass

    try:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO research_sessions (id, topic, created_at, updated_at, status, source_count, summary, data_json, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                updated_at = excluded.updated_at,
                status = excluded.status,
                source_count = excluded.source_count,
                summary = excluded.summary,
                data_json = excluded.data_json
        """, (session_id, topic, now_utc, now_utc, status, source_count, summary, serialized_data, user_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[Database] SQLite save_session failed: {e}")
        return False


def get_session(session_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve full session data by ID, optionally scoped to user_id."""
    init_db()
    pool = get_pg_pool()
    if pool is not None:
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    if user_id:
                        cur.execute("SELECT * FROM research_sessions WHERE id = %s AND user_id = %s", (session_id, user_id))
                    else:
                        cur.execute("SELECT * FROM research_sessions WHERE id = %s", (session_id,))
                    row = cur.fetchone()
                    if row:
                        # Row tuple: id, topic, created_at, updated_at, status, source_count, summary, data_json, user_id
                        return {
                            "id": row[0],
                            "topic": row[1],
                            "created_at": row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2]),
                            "updated_at": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
                            "status": row[4],
                            "source_count": row[5],
                            "summary": row[6],
                            "data": json.loads(row[7]),
                            "user_id": row[8]
                        }
        except Exception as e:
            print(f"[Database] PostgreSQL get_session failed: {e}")

    try:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        if user_id:
            cur.execute("SELECT * FROM research_sessions WHERE id = ? AND user_id = ?", (session_id, user_id))
        else:
            cur.execute("SELECT * FROM research_sessions WHERE id = ?", (session_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            return {
                "id": row["id"],
                "topic": row["topic"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"] if "updated_at" in row.keys() else row["created_at"],
                "status": row["status"],
                "source_count": row["source_count"],
                "summary": row["summary"],
                "data": json.loads(row["data_json"]),
                "user_id": row["user_id"] if "user_id" in row.keys() else "anonymous"
            }
        return None
    except Exception as e:
        print(f"[Database] SQLite get_session failed: {e}")
        return None


def list_sessions(limit: int = 50, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """List recent research sessions for history library, optionally scoped to user_id."""
    init_db()
    pool = get_pg_pool()
    if pool is not None:
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    if user_id:
                        cur.execute("""
                            SELECT id, topic, created_at, updated_at, status, source_count, summary, user_id
                            FROM research_sessions
                            WHERE user_id = %s
                            ORDER BY created_at DESC
                            LIMIT %s
                        """, (user_id, limit))
                    else:
                        cur.execute("""
                            SELECT id, topic, created_at, updated_at, status, source_count, summary, user_id
                            FROM research_sessions
                            ORDER BY created_at DESC
                            LIMIT %s
                        """, (limit,))
                    rows = cur.fetchall()
                    return [
                        {
                            "id": r[0],
                            "topic": r[1],
                            "created_at": r[2].isoformat() if hasattr(r[2], "isoformat") else str(r[2]),
                            "updated_at": r[3].isoformat() if hasattr(r[3], "isoformat") else str(r[3]),
                            "status": r[4],
                            "source_count": r[5],
                            "summary": r[6],
                            "user_id": r[7]
                        }
                        for r in rows
                    ]
        except Exception as e:
            print(f"[Database] PostgreSQL list_sessions failed: {e}")

    try:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        if user_id:
            cur.execute("""
                SELECT id, topic, created_at, updated_at, status, source_count, summary, user_id
                FROM research_sessions
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit))
        else:
            cur.execute("""
                SELECT id, topic, created_at, updated_at, status, source_count, summary, user_id
                FROM research_sessions
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[Database] SQLite list_sessions failed: {e}")
        return []


def delete_session(session_id: str, user_id: Optional[str] = None) -> bool:
    """Delete a research session by ID, optionally scoped to user_id."""
    init_db()
    pool = get_pg_pool()
    if pool is not None:
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    if user_id:
                        cur.execute("DELETE FROM research_sessions WHERE id = %s AND user_id = %s", (session_id, user_id))
                    else:
                        cur.execute("DELETE FROM research_sessions WHERE id = %s", (session_id,))
                    conn.commit()
            return True
        except Exception as e:
            print(f"[Database] PostgreSQL delete_session failed: {e}")

    try:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        if user_id:
            cur.execute("DELETE FROM research_sessions WHERE id = ? AND user_id = ?", (session_id, user_id))
        else:
            cur.execute("DELETE FROM research_sessions WHERE id = ?", (session_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[Database] SQLite delete_session failed: {e}")
        return False


# ==============================================================================
# PERSISTENT RESEARCH JOBS MANAGEMENT
# ==============================================================================

def db_create_job(
    job_id: str,
    topic: str,
    model: Optional[str] = None,
    user_id: str = "anonymous",
    stage: str = "Queued in Research Engine"
) -> bool:
    """Inserts a new research job record into persistent storage."""
    init_db()
    now = get_utc_now_iso()
    initial_logs = json.dumps([f"[{now}] Research job queued."])
    pool = get_pg_pool()
    if pool is not None:
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO research_jobs (
                            id, topic, status, progress, stage, logs_json,
                            result_json, error, model, user_id, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            topic = EXCLUDED.topic,
                            status = EXCLUDED.status,
                            updated_at = EXCLUDED.updated_at
                    """, (job_id, topic, "queued", 0, stage, initial_logs, None, None, model, user_id, now, now))
                    conn.commit()
            return True
        except Exception as e:
            print(f"[Database] PostgreSQL db_create_job error: {e}")

    try:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO research_jobs (
                id, topic, status, progress, stage, logs_json,
                result_json, error, model, user_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (job_id, topic, "queued", 0, stage, initial_logs, None, None, model, user_id, now, now))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[Database] SQLite db_create_job error: {e}")
        return False


def db_get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a research job by ID, returning parsed logs and result."""
    init_db()
    pool = get_pg_pool()
    if pool is not None:
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, topic, status, progress, stage, logs_json,
                               result_json, error, model, user_id, created_at, updated_at
                        FROM research_jobs
                        WHERE id = %s
                    """, (job_id,))
                    row = cur.fetchone()
                    if row:
                        return {
                            "id": row[0],
                            "topic": row[1],
                            "status": row[2],
                            "progress": int(row[3] or 0),
                            "stage": row[4],
                            "logs": json.loads(row[5]) if row[5] else [],
                            "result": json.loads(row[6]) if row[6] else None,
                            "error": row[7],
                            "model": row[8],
                            "user_id": row[9],
                            "created_at": row[10].isoformat() if hasattr(row[10], "isoformat") else str(row[10]),
                            "updated_at": row[11].isoformat() if hasattr(row[11], "isoformat") else str(row[11])
                        }
        except Exception as e:
            print(f"[Database] PostgreSQL db_get_job error: {e}")

    try:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, topic, status, progress, stage, logs_json,
                   result_json, error, model, user_id, created_at, updated_at
            FROM research_jobs
            WHERE id = ?
        """, (job_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            return {
                "id": row["id"],
                "topic": row["topic"],
                "status": row["status"],
                "progress": int(row["progress"] or 0),
                "stage": row["stage"],
                "logs": json.loads(row["logs_json"]) if row["logs_json"] else [],
                "result": json.loads(row["result_json"]) if row["result_json"] else None,
                "error": row["error"],
                "model": row["model"],
                "user_id": row["user_id"],
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"])
            }
    except Exception as e:
        print(f"[Database] SQLite db_get_job error: {e}")

    return None


def db_update_job_progress(
    job_id: str,
    stage: str,
    progress: int,
    log_msg: Optional[str] = None,
    status: str = "running"
) -> bool:
    """Updates job progress percentage, stage, and appends to the log stream."""
    existing = db_get_job(job_id)
    if not existing:
        return False

    logs = existing.get("logs", [])
    now = get_utc_now_iso()
    if log_msg:
        logs.append(f"[{now}] {log_msg}")
        if len(logs) > 60:
            logs = logs[-60:]
    logs_json = json.dumps(logs)
    clamped_prog = min(max(int(progress), 0), 100) if progress >= 0 else existing.get("progress", 0)

    pool = get_pg_pool()
    if pool is not None:
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE research_jobs
                        SET status = %s, progress = %s, stage = %s, logs_json = %s, updated_at = %s
                        WHERE id = %s
                    """, (status, clamped_prog, stage, logs_json, now, job_id))
                    conn.commit()
            return True
        except Exception as e:
            print(f"[Database] PostgreSQL db_update_job_progress error: {e}")

    try:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE research_jobs
            SET status = ?, progress = ?, stage = ?, logs_json = ?, updated_at = ?
            WHERE id = ?
        """, (status, clamped_prog, stage, logs_json, now, job_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[Database] SQLite db_update_job_progress error: {e}")
        return False


def db_complete_job(job_id: str, result: Dict[str, Any]) -> bool:
    """Marks a job as completed and stores sanitized research results."""
    existing = db_get_job(job_id)
    logs = existing.get("logs", []) if existing else []
    now = get_utc_now_iso()
    logs.append(f"[{now}] ✅ Scientific deliverables compiled successfully.")
    logs_json = json.dumps(logs)

    # Sanitize result to ensure JSON serializable
    safe_result = {k: v for k, v in result.items() if k not in ("pdf_bytes", "pptx_bytes")}
    result_json = json.dumps(safe_result)

    pool = get_pg_pool()
    if pool is not None:
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE research_jobs
                        SET status = %s, progress = 100, stage = %s, logs_json = %s,
                            result_json = %s, updated_at = %s
                        WHERE id = %s
                    """, ("completed", "Research Investigation Completed", logs_json, result_json, now, job_id))
                    conn.commit()
            return True
        except Exception as e:
            print(f"[Database] PostgreSQL db_complete_job error: {e}")

    try:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE research_jobs
            SET status = ?, progress = 100, stage = ?, logs_json = ?,
                result_json = ?, updated_at = ?
            WHERE id = ?
        """, ("completed", "Research Investigation Completed", logs_json, result_json, now, job_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[Database] SQLite db_complete_job error: {e}")
        return False


def db_fail_job(job_id: str, error_message: str) -> bool:
    """Marks a job as failed with an error message."""
    existing = db_get_job(job_id)
    logs = existing.get("logs", []) if existing else []
    now = get_utc_now_iso()
    logs.append(f"[{now}] ❌ ERROR: {error_message}")
    logs_json = json.dumps(logs)

    pool = get_pg_pool()
    if pool is not None:
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE research_jobs
                        SET status = %s, stage = %s, error = %s, logs_json = %s, updated_at = %s
                        WHERE id = %s
                    """, ("failed", "Research Execution Failed", error_message, logs_json, now, job_id))
                    conn.commit()
            return True
        except Exception as e:
            print(f"[Database] PostgreSQL db_fail_job error: {e}")

    try:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE research_jobs
            SET status = ?, stage = ?, error = ?, logs_json = ?, updated_at = ?
            WHERE id = ?
        """, ("failed", "Research Execution Failed", error_message, logs_json, now, job_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[Database] SQLite db_fail_job error: {e}")
        return False


def db_list_jobs(limit: int = 20) -> List[Dict[str, Any]]:
    """Lists recent research jobs without bulky result payloads."""
    init_db()
    pool = get_pg_pool()
    if pool is not None:
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, topic, status, progress, stage, error, model,
                               user_id, created_at, updated_at, (result_json IS NOT NULL) AS has_result
                        FROM research_jobs
                        ORDER BY created_at DESC
                        LIMIT %s
                    """, (limit,))
                    rows = cur.fetchall()
                    return [
                        {
                            "id": r[0],
                            "topic": r[1],
                            "status": r[2],
                            "progress": int(r[3] or 0),
                            "stage": r[4],
                            "error": r[5],
                            "model": r[6],
                            "user_id": r[7],
                            "created_at": r[8].isoformat() if hasattr(r[8], "isoformat") else str(r[8]),
                            "updated_at": r[9].isoformat() if hasattr(r[9], "isoformat") else str(r[9]),
                            "has_result": bool(r[10])
                        }
                        for r in rows
                    ]
        except Exception as e:
            print(f"[Database] PostgreSQL db_list_jobs error: {e}")

    try:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, topic, status, progress, stage, error, model,
                   user_id, created_at, updated_at, (result_json IS NOT NULL) AS has_result
            FROM research_jobs
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "id": r["id"],
                "topic": r["topic"],
                "status": r["status"],
                "progress": int(r["progress"] or 0),
                "stage": r["stage"],
                "error": r["error"],
                "model": r["model"],
                "user_id": r["user_id"],
                "created_at": str(r["created_at"]),
                "updated_at": str(r["updated_at"]),
                "has_result": bool(r["has_result"])
            }
            for r in rows
        ]
    except Exception as e:
        print(f"[Database] SQLite db_list_jobs error: {e}")
        return []

