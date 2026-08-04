"""
Ground Truth Database — SQLite-backed store for human-verified agent responses.

Architecture:
  GT DB → Memory Cache → Gemini API

GT DB entries are verified by human feedback (3 positive signals default).
Once verified, they supersede both the memory cache and Gemini calls,
giving sub-millisecond response times for known ticker+agent+params combos.

Tables:
  ground_truth  — verified agent memos with vote counts
  feedback      — individual votes and textual signals
  agent_calls   — call log for admin metrics (source, timing)
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

DB_PATH = Path("cardinal_gt.db")
APPROVAL_THRESHOLD = 3  # positive signals needed to mark an entry as verified


# ── initialisation ────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create tables if they don't exist. Called once on app startup."""
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS ground_truth (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker           TEXT NOT NULL,
                agent            TEXT NOT NULL,
                params_hash      TEXT NOT NULL,
                memo             TEXT NOT NULL,
                verdict          TEXT,
                approval_count   INTEGER DEFAULT 0,
                rejection_count  INTEGER DEFAULT 0,
                is_verified      INTEGER DEFAULT 0,
                response_time_ms INTEGER,
                created_at       TEXT DEFAULT (datetime('now')),
                updated_at       TEXT DEFAULT (datetime('now'))
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_gt_unique
                ON ground_truth(ticker, agent, params_hash);

            CREATE TABLE IF NOT EXISTS feedback (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker       TEXT NOT NULL,
                agent        TEXT NOT NULL,
                params_hash  TEXT NOT NULL,
                vote         TEXT NOT NULL,
                comment      TEXT,
                created_at   TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_feedback_lookup
                ON feedback(ticker, agent, params_hash);

            CREATE TABLE IF NOT EXISTS agent_calls (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker           TEXT NOT NULL,
                agent            TEXT NOT NULL,
                response_time_ms INTEGER,
                source           TEXT NOT NULL,
                created_at       TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_calls_agent
                ON agent_calls(agent, created_at);
        """)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── verdict extraction ────────────────────────────────────────────────────────

def extract_verdict(memo: str, agent: str) -> str | None:
    """Pull a short verdict string from the memo text for display in admin."""
    if agent == "messi":
        m = re.search(r"\[(BUY|HOLD|SELL)\]", memo)
        return m.group(1) if m else None
    if agent == "iniesta":
        m = re.search(r"\b(BULLISH|BEARISH|NEUTRAL)\b", memo)
        return m.group(1) if m else None
    if agent == "xavi":
        m = re.search(r"\b(overvalued|undervalued|fairly valued)\b", memo, re.IGNORECASE)
        return m.group(1).upper() if m else None
    if agent == "busquets":
        m = re.search(r"\b(no genuine edge|genuine edge)\b", memo, re.IGNORECASE)
        return m.group(1).upper() if m else None
    return None


# ── read ──────────────────────────────────────────────────────────────────────

def get_verified_entry(agent: str, ticker: str, params_hash: str) -> dict | None:
    """
    Return a verified GT entry if one exists for this (agent, ticker, params).
    Returns None if no verified entry found.
    """
    with _conn() as c:
        row = c.execute("""
            SELECT * FROM ground_truth
            WHERE agent = ? AND ticker = ? AND params_hash = ? AND is_verified = 1
            LIMIT 1
        """, (agent, ticker.upper(), params_hash)).fetchone()
        return dict(row) if row else None


def get_entry_counts(agent: str, ticker: str, params_hash: str) -> dict:
    """Return approval/rejection counts for a memo (for display after generation)."""
    with _conn() as c:
        row = c.execute("""
            SELECT approval_count, rejection_count, is_verified, id
            FROM ground_truth
            WHERE agent = ? AND ticker = ? AND params_hash = ?
            LIMIT 1
        """, (agent, ticker.upper(), params_hash)).fetchone()
        if row:
            return {
                "id": row["id"],
                "approval_count": row["approval_count"],
                "rejection_count": row["rejection_count"],
                "is_verified": bool(row["is_verified"]),
            }
        return {"id": None, "approval_count": 0, "rejection_count": 0, "is_verified": False}


# ── write ─────────────────────────────────────────────────────────────────────

def upsert_entry(
    agent: str,
    ticker: str,
    params_hash: str,
    memo: str,
    response_time_ms: int | None = None,
) -> int:
    """
    Insert a new GT entry or update memo/timing on conflict.
    Does NOT overwrite approval counts — those are only updated via feedback.
    Returns the entry ID.
    """
    verdict = extract_verdict(memo, agent)
    with _conn() as c:
        c.execute("""
            INSERT INTO ground_truth (ticker, agent, params_hash, memo, verdict, response_time_ms)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker, agent, params_hash) DO UPDATE SET
                memo             = excluded.memo,
                verdict          = excluded.verdict,
                response_time_ms = excluded.response_time_ms,
                updated_at       = datetime('now')
        """, (ticker.upper(), agent, params_hash, memo, verdict, response_time_ms))
        row = c.execute("""
            SELECT id FROM ground_truth
            WHERE ticker = ? AND agent = ? AND params_hash = ?
        """, (ticker.upper(), agent, params_hash)).fetchone()
        return row["id"]


def add_feedback(
    agent: str,
    ticker: str,
    params_hash: str,
    vote: str,
    comment: str | None = None,
) -> dict:
    """
    Record a feedback vote ('positive' or 'negative').
    If approval_count reaches APPROVAL_THRESHOLD, marks entry as verified.
    Returns updated counts.
    """
    with _conn() as c:
        c.execute("""
            INSERT INTO feedback (ticker, agent, params_hash, vote, comment)
            VALUES (?, ?, ?, ?, ?)
        """, (ticker.upper(), agent, params_hash, vote, comment))

        if vote == "positive":
            c.execute("""
                UPDATE ground_truth
                SET approval_count = approval_count + 1,
                    is_verified    = CASE
                        WHEN approval_count + 1 >= ? THEN 1
                        ELSE is_verified
                    END,
                    updated_at = datetime('now')
                WHERE ticker = ? AND agent = ? AND params_hash = ?
            """, (APPROVAL_THRESHOLD, ticker.upper(), agent, params_hash))
        else:
            c.execute("""
                UPDATE ground_truth
                SET rejection_count = rejection_count + 1,
                    updated_at      = datetime('now')
                WHERE ticker = ? AND agent = ? AND params_hash = ?
            """, (ticker.upper(), agent, params_hash))

        row = c.execute("""
            SELECT approval_count, rejection_count, is_verified
            FROM ground_truth
            WHERE ticker = ? AND agent = ? AND params_hash = ?
        """, (ticker.upper(), agent, params_hash)).fetchone()

        if row:
            return {
                "approval_count": row["approval_count"],
                "rejection_count": row["rejection_count"],
                "is_verified": bool(row["is_verified"]),
                "threshold": APPROVAL_THRESHOLD,
            }
        return {"approval_count": 0, "rejection_count": 0, "is_verified": False, "threshold": APPROVAL_THRESHOLD}


def log_call(agent: str, ticker: str, response_time_ms: int, source: str) -> None:
    """Log a call for metrics. source: 'gemini' | 'cache' | 'gt_db'"""
    with _conn() as c:
        c.execute("""
            INSERT INTO agent_calls (ticker, agent, response_time_ms, source)
            VALUES (?, ?, ?, ?)
        """, (ticker.upper(), agent, response_time_ms, source))


# ── admin queries ─────────────────────────────────────────────────────────────

def list_entries(
    limit: int = 100,
    offset: int = 0,
    agent: str | None = None,
    ticker: str | None = None,
    verified_only: bool = False,
) -> list[dict]:
    query = "SELECT * FROM ground_truth WHERE 1=1"
    params: list = []
    if agent:
        query += " AND agent = ?"
        params.append(agent)
    if ticker:
        query += " AND ticker = ?"
        params.append(ticker.upper())
    if verified_only:
        query += " AND is_verified = 1"
    query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    with _conn() as c:
        return [dict(r) for r in c.execute(query, params).fetchall()]


def delete_entry(entry_id: int) -> bool:
    with _conn() as c:
        c.execute("DELETE FROM ground_truth WHERE id = ?", (entry_id,))
        return True


def get_metrics() -> dict:
    with _conn() as c:
        def scalar(sql: str, params: list | None = None) -> int:
            row = c.execute(sql, params or []).fetchone()
            return row[0] if row else 0

        total_calls      = scalar("SELECT COUNT(*) FROM agent_calls")
        gt_entries       = scalar("SELECT COUNT(*) FROM ground_truth")
        verified         = scalar("SELECT COUNT(*) FROM ground_truth WHERE is_verified = 1")
        total_feedback   = scalar("SELECT COUNT(*) FROM feedback")
        positive         = scalar("SELECT COUNT(*) FROM feedback WHERE vote = 'positive'")
        gemini_calls     = scalar("SELECT COUNT(*) FROM agent_calls WHERE source = 'gemini'")
        cache_hits       = scalar("SELECT COUNT(*) FROM agent_calls WHERE source = 'cache'")
        gt_hits          = scalar("SELECT COUNT(*) FROM agent_calls WHERE source = 'gt_db'")

        agent_stats = [dict(r) for r in c.execute("""
            SELECT agent,
                   COUNT(*) as total_calls,
                   ROUND(AVG(response_time_ms)) as avg_ms,
                   SUM(CASE WHEN source='gemini' THEN 1 ELSE 0 END) as gemini_calls,
                   SUM(CASE WHEN source='cache'  THEN 1 ELSE 0 END) as cache_hits,
                   SUM(CASE WHEN source='gt_db'  THEN 1 ELSE 0 END) as gt_hits
            FROM agent_calls GROUP BY agent ORDER BY total_calls DESC
        """).fetchall()]

        recent_calls = [dict(r) for r in c.execute("""
            SELECT ticker, agent, response_time_ms, source, created_at
            FROM agent_calls ORDER BY created_at DESC LIMIT 25
        """).fetchall()]

        recent_feedback = [dict(r) for r in c.execute("""
            SELECT ticker, agent, vote, comment, created_at
            FROM feedback ORDER BY created_at DESC LIMIT 25
        """).fetchall()]

        return {
            "total_calls":    total_calls,
            "gt_entries":     gt_entries,
            "verified":       verified,
            "total_feedback": total_feedback,
            "positive":       positive,
            "approval_rate":  round(positive / total_feedback * 100, 1) if total_feedback else 0,
            "gemini_calls":   gemini_calls,
            "cache_hits":     cache_hits,
            "gt_hits":        gt_hits,
            "agent_stats":    agent_stats,
            "recent_calls":   recent_calls,
            "recent_feedback": recent_feedback,
            "approval_threshold": APPROVAL_THRESHOLD,
        }


# Auto-initialise on import — idempotent, safe to call multiple times
init_db()