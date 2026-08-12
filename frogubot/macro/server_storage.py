from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any, Optional

from .storage import MacroStorage


class ServerStorageError(RuntimeError):
    pass


class ServerMacroStorage(MacroStorage):
    def __init__(
        self,
        db_path: str,
        server_url: str,
        timeout: float = 10.0,
    ):
        super().__init__(db_path)
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout

    def _request_sync(
        self,
        method: str,
        path: str,
        user_id: int,
        body: dict[str, Any] | None = None,
    ) -> Any:
        payload = None
        headers = {"X-User-ID": str(user_id), "Accept": "application/json"}
        if body is not None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            f"{self.server_url}{path}",
            data=payload,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = response.read()
                if not data:
                    return None
                return json.loads(data.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            message = exc.read().decode("utf-8", errors="replace")
            raise ServerStorageError(f"Сервер вернул {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            raise ServerStorageError(f"Сервер недоступен: {exc.reason}") from exc

    async def _request(
        self,
        method: str,
        path: str,
        user_id: int,
        body: dict[str, Any] | None = None,
    ) -> Any:
        return await asyncio.to_thread(self._request_sync, method, path, user_id, body)

    @staticmethod
    def _from_server(item: dict[str, Any] | None) -> Optional[dict[str, Any]]:
        if not item:
            return None
        macro = item.get("payload") or {}
        if not isinstance(macro, dict):
            return None
        macro.setdefault("id", item.get("id"))
        macro.setdefault("name", item.get("name", ""))
        macro.setdefault("enabled", item.get("enabled", True))
        macro.setdefault("is_public", item.get("is_public", False))
        return macro

    @staticmethod
    def _to_server(macro: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        user_id = int((macro.get("meta") or {}).get("created_by") or 0)
        if user_id <= 0:
            raise ServerStorageError("У макроса нет владельца в meta.created_by")
        body = {
            "id": macro["id"],
            "name": (macro.get("name") or "Без названия").strip(),
            "payload": macro,
            "is_public": bool(macro.get("is_public", False)),
            "enabled": bool(macro.get("enabled", True)),
        }
        return user_id, body

    async def save_macro(self, macro: dict[str, Any]):
        user_id, body = self._to_server(macro)
        existing = await self.get_macro(macro["id"], user_id)
        method = "PATCH" if existing else "POST"
        path = f"/api/v1/macros/{macro['id']}" if existing else "/api/v1/macros"
        await self._request(method, path, user_id, body)

    async def get_macro(self, macro_id: str, user_id: int | None = None) -> Optional[dict[str, Any]]:
        if not user_id:
            raise ServerStorageError("Для поиска макроса на сервере нужен user_id")
        item = await self._request("GET", f"/api/v1/macros/{macro_id}", user_id)
        return self._from_server(item)

    async def delete_macro(self, macro_id: str, user_id: int | None = None):
        if not user_id:
            raise ServerStorageError("Для удаления макроса на сервере нужен user_id")
        await self._request("DELETE", f"/api/v1/macros/{macro_id}", user_id)

    async def list_macros(self, user_id: int) -> list[dict[str, Any]]:
        items = await self._request("GET", "/api/v1/macros", user_id)
        return [macro for macro in (self._from_server(item) for item in items or []) if macro]

    async def record_run(
        self,
        macro_id: str,
        user_id: int | None,
        status: str,
        duration_ms: float,
        error: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        if not user_id:
            raise ServerStorageError("Для записи запуска макроса на сервере нужен user_id")
        await self._request(
            "POST",
            f"/api/v1/macros/{macro_id}/runs",
            user_id,
            {
                "status": status,
                "duration_ms": duration_ms,
                "error": error,
                "details": details or {},
            },
        )

    async def stats(self, macro_id: str, user_id: int | None = None) -> dict[str, Any]:
        if not user_id:
            raise ServerStorageError("Для статистики макроса на сервере нужен user_id")
        return await self._request("GET", f"/api/v1/macros/{macro_id}/stats", user_id)
