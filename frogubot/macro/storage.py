from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional


class MacroStorage:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)

    def _connect(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_sync(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS macro_drafts (
                    user_id INTEGER PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS macros (
                    macro_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_macros_user_id
                    ON macros(user_id);

                CREATE INDEX IF NOT EXISTS idx_macros_updated_at
                    ON macros(updated_at DESC);

                CREATE TABLE IF NOT EXISTS macro_runs (
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    macro_id TEXT NOT NULL,
                    user_id INTEGER,
                    status TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    error TEXT,
                    details TEXT,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_macro_runs_macro
                    ON macro_runs(macro_id, created_at DESC);
                """
            )

    async def init(self):
        await asyncio.to_thread(self._init_sync)

    def _save_draft_sync(self, user_id: int, payload: dict[str, Any]):
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO macro_drafts(user_id, payload, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (user_id, json.dumps(payload, ensure_ascii=False), time.time()),
            )

    async def save_draft(self, user_id: int, payload: dict[str, Any]):
        await asyncio.to_thread(self._save_draft_sync, user_id, payload)

    def _load_draft_sync(self, user_id: int) -> Optional[dict[str, Any]]:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT payload FROM macro_drafts WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if not row:
                return None
            return json.loads(row["payload"])

    async def load_draft(self, user_id: int) -> Optional[dict[str, Any]]:
        return await asyncio.to_thread(self._load_draft_sync, user_id)

    def _clear_draft_sync(self, user_id: int):
        with self._connection() as conn:
            conn.execute("DELETE FROM macro_drafts WHERE user_id = ?", (user_id,))

    async def clear_draft(self, user_id: int):
        await asyncio.to_thread(self._clear_draft_sync, user_id)

    def _save_macro_sync(self, macro: dict[str, Any]):
        macro_id = macro["id"]
        user_id = int(macro["meta"]["created_by"])
        name = macro.get("name", "").strip()
        enabled = 1 if macro.get("enabled", True) else 0
        created_at = float(macro["meta"].get("created_at", time.time()))
        updated_at = float(macro["meta"].get("updated_at", time.time()))
        payload = json.dumps(macro, ensure_ascii=False)

        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO macros(macro_id, user_id, name, enabled, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(macro_id) DO UPDATE SET
                    user_id = excluded.user_id,
                    name = excluded.name,
                    enabled = excluded.enabled,
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (macro_id, user_id, name, enabled, payload, created_at, updated_at),
            )

    async def save_macro(self, macro: dict[str, Any]):
        await asyncio.to_thread(self._save_macro_sync, macro)

    def _get_macro_sync(self, macro_id: str) -> Optional[dict[str, Any]]:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT payload FROM macros WHERE macro_id = ?",
                (macro_id,),
            ).fetchone()
            if not row:
                return None
            return json.loads(row["payload"])

    async def get_macro(self, macro_id: str, user_id: int | None = None) -> Optional[dict[str, Any]]:
        return await asyncio.to_thread(self._get_macro_sync, macro_id)

    def _delete_macro_sync(self, macro_id: str):
        with self._connection() as conn:
            conn.execute("DELETE FROM macros WHERE macro_id = ?", (macro_id,))

    async def delete_macro(self, macro_id: str, user_id: int | None = None):
        await asyncio.to_thread(self._delete_macro_sync, macro_id)

    def _list_macros_sync(self, user_id: int) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT payload
                FROM macros
                WHERE user_id = ?
                ORDER BY updated_at DESC
                """,
                (user_id,),
            ).fetchall()
            return [json.loads(row["payload"]) for row in rows]

    async def list_macros(self, user_id: int) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list_macros_sync, user_id)

    def _record_run_sync(self, macro_id: str, user_id: int | None, status: str, duration_ms: float, error: str | None, details: dict[str, Any] | None):
        with self._connection() as conn:
            conn.execute(
                "INSERT INTO macro_runs(macro_id,user_id,status,duration_ms,error,details,created_at) VALUES (?,?,?,?,?,?,?)",
                (macro_id, user_id, status, duration_ms, error, json.dumps(details or {}, ensure_ascii=False), time.time()),
            )

    async def record_run(self, macro_id: str, user_id: int | None, status: str, duration_ms: float, error: str | None = None, details: dict[str, Any] | None = None):
        await asyncio.to_thread(self._record_run_sync, macro_id, user_id, status, duration_ms, error, details)

    def _stats_sync(self, macro_id: str) -> dict[str, Any]:
        with self._connection() as conn:
            row = conn.execute("SELECT COUNT(*) total, SUM(status='success') success, SUM(status='error') errors, AVG(duration_ms) avg_duration_ms, MAX(created_at) last_run FROM macro_runs WHERE macro_id=?", (macro_id,)).fetchone()
            return dict(row) if row else {"total": 0, "success": 0, "errors": 0, "avg_duration_ms": None, "last_run": None}

    async def stats(self, macro_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._stats_sync, macro_id)
