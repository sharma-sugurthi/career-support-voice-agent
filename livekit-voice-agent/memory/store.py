"""Per-user memory for the career agent.

Everything lives in one SQLite file (data/career.db by default) that is
created automatically on first use. Nothing to host, nothing to configure -
the Python agent IS the backend.

Provenance matters: every remembered fact records WHERE it came from
(`user_said`, `web:<url>`, or `inferred`). The prompts only present
`user_said` and `web:` facts as established truth - this is part of the
anti-hallucination design, not bookkeeping.
"""
import json
import sqlite3
import time
from pathlib import Path

VALID_SOURCES = ("user_said", "inferred")  # plus any "web:<url>"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    display_name TEXT,
    created_at REAL NOT NULL,
    last_seen_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS facts (
    user_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (user_id, key)
);
CREATE TABLE IF NOT EXISTS session_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    started_at REAL NOT NULL,
    summary TEXT NOT NULL,
    agent_path TEXT
);
CREATE INDEX IF NOT EXISTS idx_summaries_user ON session_summaries(user_id, started_at);
CREATE TABLE IF NOT EXISTS plans (
    user_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    content_json TEXT NOT NULL,
    sources_json TEXT NOT NULL DEFAULT '[]',
    updated_at REAL NOT NULL,
    PRIMARY KEY (user_id, kind, title)
);
CREATE TABLE IF NOT EXISTS chat_snapshots (
    user_id TEXT PRIMARY KEY,
    chat_ctx_json TEXT NOT NULL,
    updated_at REAL NOT NULL
);
"""


def _validate_source(source: str) -> str:
    if source in VALID_SOURCES or source.startswith("web:"):
        return source
    raise ValueError(
        f"Invalid fact source '{source}'. Use 'user_said', 'inferred', or 'web:<url>'."
    )


class MemoryStore:
    """Small synchronous SQLite wrapper. Calls are single fast statements, so
    using it from async code is fine in practice for a local file DB."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / "data" / "career.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    # ── users ──────────────────────────────────────────────────────────────

    def touch_user(self, user_id: str, display_name: str | None = None) -> bool:
        """Create the user if new; update last_seen. Returns True if returning user."""
        now = time.time()
        with self._connect() as conn:
            row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO users (id, display_name, created_at, last_seen_at) VALUES (?, ?, ?, ?)",
                    (user_id, display_name, now, now),
                )
                return False
            conn.execute(
                "UPDATE users SET last_seen_at = ?, display_name = COALESCE(?, display_name) WHERE id = ?",
                (now, display_name, user_id),
            )
            return True

    # ── facts (career profile with provenance) ─────────────────────────────

    def remember_fact(self, user_id: str, key: str, value: str, source: str = "user_said") -> None:
        source = _validate_source(source)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO facts (user_id, key, value, source, updated_at) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value, "
                "source = excluded.source, updated_at = excluded.updated_at",
                (user_id, key.strip().lower().replace(" ", "_"), value, source, time.time()),
            )

    def get_facts(self, user_id: str, established_only: bool = False) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT key, value, source, updated_at FROM facts WHERE user_id = ? ORDER BY updated_at",
                (user_id,),
            ).fetchall()
        facts = [dict(r) for r in rows]
        if established_only:
            facts = [f for f in facts if f["source"] == "user_said" or f["source"].startswith("web:")]
        return facts

    def forget_fact(self, user_id: str, key: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM facts WHERE user_id = ? AND key = ?",
                (user_id, key.strip().lower().replace(" ", "_")),
            )

    # ── session summaries ──────────────────────────────────────────────────

    def add_session_summary(self, user_id: str, summary: str, agent_path: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO session_summaries (user_id, started_at, summary, agent_path) VALUES (?, ?, ?, ?)",
                (user_id, time.time(), summary, agent_path),
            )

    def get_recent_summaries(self, user_id: str, limit: int = 3) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT started_at, summary, agent_path FROM session_summaries "
                "WHERE user_id = ? ORDER BY started_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── plans (roadmaps, budgets, schedules) ───────────────────────────────

    def save_plan(self, user_id: str, kind: str, title: str, content: dict | list | str,
                  sources: list[str] | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO plans (user_id, kind, title, content_json, sources_json, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id, kind, title) DO UPDATE SET content_json = excluded.content_json, "
                "sources_json = excluded.sources_json, updated_at = excluded.updated_at",
                (user_id, kind, title, json.dumps(content), json.dumps(sources or []), time.time()),
            )

    def get_plans(self, user_id: str, kind: str | None = None) -> list[dict]:
        query = "SELECT kind, title, content_json, sources_json, updated_at FROM plans WHERE user_id = ?"
        args: list = [user_id]
        if kind:
            query += " AND kind = ?"
            args.append(kind)
        with self._connect() as conn:
            rows = conn.execute(query + " ORDER BY updated_at DESC", args).fetchall()
        return [
            {
                "kind": r["kind"],
                "title": r["title"],
                "content": json.loads(r["content_json"]),
                "sources": json.loads(r["sources_json"]),
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    # ── chat snapshots (exact resume) ──────────────────────────────────────

    def save_chat_snapshot(self, user_id: str, chat_ctx_dict: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO chat_snapshots (user_id, chat_ctx_json, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET chat_ctx_json = excluded.chat_ctx_json, "
                "updated_at = excluded.updated_at",
                (user_id, json.dumps(chat_ctx_dict), time.time()),
            )

    def get_chat_snapshot(self, user_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT chat_ctx_json FROM chat_snapshots WHERE user_id = ?", (user_id,)
            ).fetchone()
        return json.loads(row["chat_ctx_json"]) if row else None

    # ── prompt context ─────────────────────────────────────────────────────

    def build_memory_context(self, user_id: str) -> str:
        """Human-readable block injected into the agent's instructions.
        Only established facts (user_said / web-sourced) are presented as truth."""
        facts = self.get_facts(user_id, established_only=True)
        summaries = self.get_recent_summaries(user_id, limit=2)
        if not facts and not summaries:
            return ""
        lines = ["What you already know about this returning user:"]
        for f in facts:
            lines.append(f"- {f['key'].replace('_', ' ')}: {f['value']}")
        if summaries:
            lines.append("Previous conversations, most recent first:")
            for s in summaries:
                lines.append(f"- {s['summary']}")
        lines.append(
            "Greet them as a returning user, briefly recall where you left off, "
            "and ask if they want to continue or start something new."
        )
        return "\n".join(lines)
