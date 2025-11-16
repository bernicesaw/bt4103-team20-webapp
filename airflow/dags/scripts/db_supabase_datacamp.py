from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List

from sqlalchemy import create_engine, text

# Fully-qualified table name in Supabase (demo table, similar schema to coursera_demo/codecademy_demo)
TABLE_FQN = "public.datacamp_demo"


# --- Connection helpers -------------------------------------------------------


def _resolve_db_url() -> str:
    """
    Accept both env vars:
      - SUPABASE_DB_URL         (SQLAlchemy form)
      - SUPABASE_POOLER_URL     (webapp form)
    Force psycopg2 driver and sslmode=require.
    """
    url = os.getenv("SUPABASE_DB_URL") or os.getenv("SUPABASE_POOLER_URL")
    if not url:
        raise RuntimeError(
            "Missing DB URL. Set SUPABASE_DB_URL or SUPABASE_POOLER_URL in the environment."
        )

    # ensure psycopg2 dialect
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://") :]

    # enforce SSL for Supabase
    if "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"

    return url


def _get_engine():
    url = _resolve_db_url()
    # fail fast on bad creds/network
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})


# --- DDL ----------------------------------------------------------------------


DDL_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_FQN} (
    course_id TEXT PRIMARY KEY,
    title TEXT,
    provider TEXT,
    url TEXT,
    price TEXT,
    duration TEXT,
    level TEXT,
    language TEXT,
    rating NUMERIC,
    reviews_count INTEGER,
    last_updated DATE,
    keyword TEXT,
    description TEXT,
    what_you_will_learn TEXT,
    skills TEXT,
    recommended_experience TEXT
);
"""


def ensure_table_exists() -> None:
    """
    Create the demo table if it doesn't exist.
    Also runs a quick SELECT 1 so we fail with a clear error if connection is bad.
    """
    eng = _get_engine()
    with eng.begin() as conn:
        conn.execute(text("SELECT 1"))
        conn.execute(text(DDL_SQL))


# --- Upsert -------------------------------------------------------------------


_COLUMNS: List[str] = [
    "course_id",
    "title",
    "provider",
    "url",
    "price",
    "duration",
    "level",
    "language",
    "rating",
    "reviews_count",
    "last_updated",
    "keyword",
    "description",
    "what_you_will_learn",
    "skills",
    "recommended_experience",
]

_INSERT_SQL = f"""
INSERT INTO {TABLE_FQN} ({", ".join(_COLUMNS)})
VALUES ({", ".join(f":{c}" for c in _COLUMNS)})
ON CONFLICT (course_id) DO UPDATE SET
{", ".join(f"{c}=EXCLUDED.{c}" for c in _COLUMNS if c != "course_id")};
"""


def _coerce_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure all expected columns exist (None if missing)."""
    return {c: row.get(c) for c in _COLUMNS}


def upsert_rows(rows: Iterable[Dict[str, Any]], chunk_size: int = 1000) -> int:
    """
    Batch upsert rows into Supabase. Returns number of rows processed.
    Expects keys matching _COLUMNS (use transform_for_db to shape data).
    """
    batch: List[Dict[str, Any]] = []
    total = 0
    eng = _get_engine()

    with eng.begin() as conn:
        for r in rows:
            batch.append(_coerce_row(r))
            if len(batch) >= chunk_size:
                conn.execute(text(_INSERT_SQL), batch)
                total += len(batch)
                batch = []
        if batch:
            conn.execute(text(_INSERT_SQL), batch)
            total += len(batch)

    return total
