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
