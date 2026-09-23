"""Tiny SQLite cache for full score responses, keyed by the normalized
query string (address/ZIP as typed). Avoids re-hitting five external APIs
for repeated demo queries and smooths over transient upstream slowness.

Weather changes fast, so the TTL is short (default 10 minutes) — this is a
freshness/latency tradeoff, not a correctness one.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

# Vercel's serverless filesystem is read-only outside /tmp, and /tmp is wiped
# between cold starts — that's fine here, since this cache is a best-effort
# latency optimization (see module docstring), never a correctness dependency.
if os.environ.get("VERCEL"):
    DB_PATH = Path("/tmp") / "emberready_cache.sqlite3"
else:
    DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "cache.sqlite3"
DEFAULT_TTL_SECONDS = 600


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS score_cache (
            query_key TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            expires_at REAL NOT NULL
        )
        """
    )
    return conn


def _normalize(query: str) -> str:
    return query.strip().lower()


def get_cached(query: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT payload, expires_at FROM score_cache WHERE query_key = ?",
            (_normalize(query),),
        ).fetchone()
        if row is None:
            return None
        payload, expires_at = row
        if time.time() > expires_at:
            conn.execute("DELETE FROM score_cache WHERE query_key = ?", (_normalize(query),))
            conn.commit()
            return None
        return json.loads(payload)
    finally:
        conn.close()


def set_cached(query: str, payload: dict, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO score_cache (query_key, payload, expires_at) VALUES (?, ?, ?)",
            (_normalize(query), json.dumps(payload), time.time() + ttl_seconds),
        )
        conn.commit()
    finally:
        conn.close()


def clear() -> None:
    conn = _connect()
    try:
        conn.execute("DELETE FROM score_cache")
        conn.commit()
    finally:
        conn.close()
