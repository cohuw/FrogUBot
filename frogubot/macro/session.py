from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from utils import short_id


def make_blank_macro(user_id: int) -> dict[str, Any]:
    return {
        "id": short_id("macro"),
        "name": "",
        "enabled": True,
        "is_public": False,
        "trigger": {},
        "conditions": [],
        "actions": [],
        "meta": {
            "created_by": user_id,
            "created_at": time.time(),
            "updated_at": time.time(),
        },
    }


@dataclass
class DraftSession:
    user_id: int
    macro: dict[str, Any] = field(default_factory=dict)

    stage: str = "home"
    awaiting: Optional[str] = None

    pending_kind: Optional[str] = None
    pending_item: dict[str, Any] = field(default_factory=dict)
    pending_fields: list[dict[str, Any]] = field(default_factory=list)
    pending_field_index: int = 0

    last_error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "macro": self.macro,
            "stage": self.stage,
            "awaiting": self.awaiting,
            "pending_kind": self.pending_kind,
            "pending_item": self.pending_item,
            "pending_fields": self.pending_fields,
            "pending_field_index": self.pending_field_index,
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DraftSession":
        return cls(
            user_id=int(data["user_id"]),
            macro=data.get("macro") or {},
            stage=data.get("stage", "home"),
            awaiting=data.get("awaiting"),
            pending_kind=data.get("pending_kind"),
            pending_item=data.get("pending_item") or {},
            pending_fields=data.get("pending_fields") or [],
            pending_field_index=int(data.get("pending_field_index", 0)),
            last_error=data.get("last_error"),
        )


class SessionStore:
    def __init__(self, storage):
        self.storage = storage
        self._sessions: dict[int, DraftSession] = {}
        self._lock = asyncio.Lock()

    async def get(self, user_id: int) -> DraftSession:
        async with self._lock:
            if user_id in self._sessions:
                return self._sessions[user_id]

        draft = await self.storage.load_draft(user_id)
        if draft:
            session = DraftSession.from_dict(draft)
        else:
            session = DraftSession(user_id=user_id, macro=make_blank_macro(user_id))
            await self.storage.save_draft(user_id, session.to_dict())

        async with self._lock:
            self._sessions[user_id] = session
        return session

    async def save(self, session: DraftSession):
        session.macro.setdefault("meta", {})
        session.macro["meta"]["updated_at"] = time.time()
        async with self._lock:
            self._sessions[session.user_id] = session
        await self.storage.save_draft(session.user_id, session.to_dict())

    async def reset(self, user_id: int) -> DraftSession:
        session = DraftSession(user_id=user_id, macro=make_blank_macro(user_id))
        async with self._lock:
            self._sessions[user_id] = session
        await self.storage.save_draft(user_id, session.to_dict())
        return session

    async def clear(self, user_id: int):
        async with self._lock:
            self._sessions.pop(user_id, None)
        await self.storage.clear_draft(user_id)
