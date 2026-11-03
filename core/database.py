"""
Klein AI - SQLite Database for Research History and Storage
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from core.config import DB_PATH

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes tables for research sessions and logs."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS research_sessions (
            id TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            source_count INTEGER DEFAULT 0,
            summary TEXT,
            data_json TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_session(session_id: str, topic: str, status: str, source_count: int, summary: str, data: Dict[str, Any]):
    """Insert or update a research session."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO research_sessions (id, topic, created_at, status, source_count, summary, data_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            status = excluded.status,
            source_count = excluded.source_count,
            summary = excluded.summary,
            data_json = excluded.data_json
    """, (session_id, topic, now, status, source_count, summary, json.dumps(data, ensure_ascii=False)))
    conn.commit()
    conn.close()

def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve full session data by ID."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM research_sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row["id"],
            "topic": row["topic"],
            "created_at": row["created_at"],
            "status": row["status"],
            "source_count": row["source_count"],
            "summary": row["summary"],
            "data": json.loads(row["data_json"])
        }
    return None

def list_sessions(limit: int = 50) -> List[Dict[str, Any]]:
    """List recent research sessions for history tab."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, topic, created_at, status, source_count, summary
        FROM research_sessions
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_session(session_id: str):
    """Delete a research session by ID."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM research_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
