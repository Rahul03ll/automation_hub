"""
SQLite-backed persistence for API keys and job metadata/history.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import ADMIN_API_KEY, APP_DB_PATH


def _conn() -> sqlite3.Connection:
    db_path = Path(APP_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path), check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ensure_schema(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS api_keys (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          key_hash TEXT NOT NULL UNIQUE,
          name TEXT NOT NULL,
          is_active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          last_used_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          job_id TEXT NOT NULL UNIQUE,
          job_type TEXT NOT NULL,
          status TEXT NOT NULL,
          request_json TEXT,
          result_json TEXT,
          error_text TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    con.commit()


def init_db() -> None:
    con = _conn()
    _ensure_schema(con)
    cur = con.cursor()

    if ADMIN_API_KEY:
        key_hash = _hash_key(ADMIN_API_KEY)
        cur.execute("SELECT id FROM api_keys WHERE key_hash = ?", (key_hash,))
        if cur.fetchone() is None:
            now = datetime.utcnow().isoformat()
            cur.execute(
                "INSERT INTO api_keys (key_hash, name, is_active, created_at) VALUES (?, ?, 1, ?)",
                (key_hash, "bootstrap-admin", now),
            )
            con.commit()
    con.close()


def validate_api_key(raw_key: str) -> bool:
    key_hash = _hash_key(raw_key)
    con = _conn()
    _ensure_schema(con)
    cur = con.cursor()
    cur.execute("SELECT id FROM api_keys WHERE key_hash = ? AND is_active = 1", (key_hash,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE api_keys SET last_used_at = ? WHERE id = ?", (datetime.utcnow().isoformat(), row["id"]))
        con.commit()
    con.close()
    return row is not None


def create_api_key(name: str) -> dict:
    raw = secrets.token_urlsafe(32)
    key_hash = _hash_key(raw)
    now = datetime.utcnow().isoformat()
    con = _conn()
    _ensure_schema(con)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO api_keys (key_hash, name, is_active, created_at) VALUES (?, ?, 1, ?)",
        (key_hash, name, now),
    )
    con.commit()
    api_key_id = cur.lastrowid
    con.close()
    return {"id": api_key_id, "name": name, "api_key": raw}


def has_api_keys() -> bool:
    con = _conn()
    _ensure_schema(con)
    cur = con.cursor()
    cur.execute("SELECT COUNT(1) AS n FROM api_keys WHERE is_active = 1")
    n = int(cur.fetchone()["n"])
    con.close()
    return n > 0


def insert_job(job_id: str, job_type: str, status: str, request_payload: dict) -> None:
    now = datetime.utcnow().isoformat()
    con = _conn()
    _ensure_schema(con)
    cur = con.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO jobs (job_id, job_type, status, request_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM jobs WHERE job_id = ?), ?), ?)
        """,
        (job_id, job_type, status, json.dumps(request_payload), job_id, now, now),
    )
    con.commit()
    con.close()


def update_job(job_id: str, status: str, result: Optional[dict] = None, error: Optional[str] = None) -> None:
    con = _conn()
    _ensure_schema(con)
    cur = con.cursor()
    cur.execute(
        """
        UPDATE jobs
        SET status = ?, result_json = ?, error_text = ?, updated_at = ?
        WHERE job_id = ?
        """,
        (
            status,
            json.dumps(result) if result is not None else None,
            error,
            datetime.utcnow().isoformat(),
            job_id,
        ),
    )
    con.commit()
    con.close()


def list_jobs(limit: int = 50) -> list[dict]:
    con = _conn()
    _ensure_schema(con)
    cur = con.cursor()
    cur.execute(
        "SELECT job_id, job_type, status, request_json, result_json, error_text, created_at, updated_at "
        "FROM jobs ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = cur.fetchall()
    con.close()
    items = []
    for r in rows:
        items.append(
            {
                "job_id": r["job_id"],
                "job_type": r["job_type"],
                "status": r["status"],
                "request": json.loads(r["request_json"]) if r["request_json"] else None,
                "result": json.loads(r["result_json"]) if r["result_json"] else None,
                "error": r["error_text"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
        )
    return items
