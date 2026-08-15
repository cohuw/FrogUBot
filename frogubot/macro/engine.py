"""Pure macro runtime primitives.

The engine deliberately has no Telegram dependency.  Production adapters can
turn the returned action plan into Pyrogram calls, while preview/test mode can
run safely without sending, deleting or executing anything.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from .templates import render_template
from .validator import validate_macro


def _get(value: Any, path: str, default: Any = None) -> Any:
    cur = value
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part, default)
        else:
            cur = getattr(cur, part, default)
        if cur is None:
            return default
    return cur


def build_context(event: Any, macro: dict[str, Any] | None = None, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the stable context exposed to conditions and templates."""
    if isinstance(event, dict):
        message = event.get("message", event)
        chat = event.get("chat") or _get(message, "chat", {}) or {}
        sender = event.get("sender") or event.get("from_user") or _get(message, "from_user", {}) or {}
    else:
        message = event
        chat = _get(event, "chat", {}) or {}
        sender = _get(event, "from_user", {}) or {}
    if not isinstance(message, dict) and message is None:
        message = {}
    return {
        "message": message,
        "chat": chat,
        "sender": sender,
        "user": sender,
        "trigger": (event.get("trigger") if isinstance(event, dict) else None) or {},
        "match": {},
        "variables": variables or {},
        "macro": macro or {},
        "client": (event.get("client") if isinstance(event, dict) else None),
        "timestamp": time.time(),
    }


def _value(context: dict[str, Any], target: str) -> Any:
    if target == "text":
        return _get(context, "message.text", _get(context, "message.caption", ""))
    if target == "caption":
        return _get(context, "message.caption", "")
    if target == "command":
        text = str(_get(context, "message.text", ""))
        return text.split()[0] if text.startswith("/") else ""
    if target in {"has_media", "is_reply", "is_forward", "is_admin", "is_owner"}:
        return bool(_get(context, f"message.{target}", _get(context, target, False)))
    return _get(context, target, "")


def _as_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


import functools

@functools.lru_cache(maxsize=1024)
def _compile_regex(pattern: str):
    try:
        return re.compile(pattern)
    except re.error:
        return None

def condition_matches(condition: dict[str, Any], context: dict[str, Any]) -> tuple[bool, dict[str, str]]:
    target, op = condition.get("target", ""), condition.get("match_type", "")
    actual, expected = _value(context, target), condition.get("pattern", "")
    captures: dict[str, str] = {}
    if op == "exists":
        return actual is not None and actual != "", captures
    if op == "not_exists":
        return actual is None or actual == "", captures
    if op in {"has_media", "is_reply", "is_forward", "is_admin", "is_owner"}:
        return bool(actual) == (str(expected).lower() not in {"0", "false", "no"}), captures
    if op == "regex":
        pattern = _compile_regex(str(expected))
        match = pattern.search(str(actual or "")) if pattern else None
        if match:
            captures.update({k: v for k, v in match.groupdict().items() if v is not None})
        return bool(match), captures
    if op in {"in_list", "not_in_list"}:
        values = expected if isinstance(expected, list) else [x.strip() for x in str(expected).split(",")]
        result = str(actual) in {str(x) for x in values}
        return (not result if op == "not_in_list" else result), captures
    if op in {"greater", "less", "between"}:
        number = _as_number(actual)
        bounds = expected if isinstance(expected, list) else [x.strip() for x in str(expected).split(",")]
        nums = [_as_number(x) for x in bounds]
        if number is None or any(x is None for x in nums):
            return False, captures
        return ((number > nums[0]) if op == "greater" else (number < nums[0]) if op == "less" else nums[0] <= number <= nums[-1]), captures
    actual_s, expected_s = str(actual or ""), str(expected)
    result = {"exact": actual_s == expected_s, "contains": expected_s in actual_s, "starts_with": actual_s.startswith(expected_s), "ends_with": actual_s.endswith(expected_s)}.get(op, False)
    return (not result if op in {"not_contains", "not_exact"} else result), captures


def trigger_matches(macro: dict[str, Any], context: dict[str, Any]) -> bool:
    trigger = macro.get("trigger") or {}
    event_type = _get(context, "trigger.type", None) or context.get("event_type")
    if event_type and trigger.get("type") != event_type:
        return False
    scope = trigger.get("scope") or {"chat_mode": "all"}
    mode, chat = scope.get("chat_mode", "all"), context.get("chat") or {}
    chat_id = _get(chat, "id")
    if mode == "specific" and chat_id not in scope.get("chat_ids", []): return False
    if mode == "list" and chat_id not in scope.get("chat_ids", []): return False
    chat_type = str(_get(chat, "type", ""))
    if mode == "private" and chat_type not in {"private", "bot"}: return False
    if mode == "groups" and chat_type not in {"group", "supergroup"}: return False
    if mode == "channels" and chat_type != "channel": return False
    source = trigger.get("source") or {"type": "any"}
    sender_id, username = _get(context, "sender.id"), str(_get(context, "sender.username", ""))
    source_type = source.get("type", "any")
    if source_type == "user_id" and sender_id not in source.get("user_ids", [source.get("value")]): return False
    if source_type == "username" and username.lower() != str(source.get("value", "")).lstrip("@").lower(): return False
    if source_type == "list" and sender_id not in source.get("user_ids", []): return False
    if source_type == "except" and sender_id in source.get("user_ids", []): return False
    return True


def select_macros(macros: list[dict[str, Any]], context: dict[str, Any], mode: str = "all") -> list[dict[str, Any]]:
    """Return enabled matching macros in deterministic priority order."""
    matches = [m for m in macros if m.get("enabled", True) and trigger_matches(m, context)]
    matches.sort(key=lambda item: (-int((item.get("trigger") or {}).get("priority", item.get("priority", 0))), str(item.get("id", ""))))
    if mode == "first":
        return matches[:1]
    if mode == "highest_priority":
        return matches[:1]
    return matches


@dataclass
class TestResult:
    matched: bool
    conditions: list[dict[str, Any]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def test_macro(macro: dict[str, Any], event: Any, variables: dict[str, Any] | None = None) -> TestResult:
    errors = validate_macro(macro)
    context = build_context(event, macro, variables)
    if errors:
        return TestResult(False, context=context, errors=errors)
    context["event_type"] = event.get("event_type") if isinstance(event, dict) else None
    if not trigger_matches(macro, context):
        return TestResult(False, context=context)
    condition_results = []
    all_match = True
    for condition in macro.get("conditions", []):
        ok, captures = condition_matches(condition, context)
        context["match"].update(captures)
        condition_results.append({"condition": condition, "matched": ok, "captures": captures})
        all_match = all_match and ok
    if not all_match:
        return TestResult(False, condition_results, context=context)
    actions = []
    for action in macro.get("actions", []):
        rendered = {key: render_template(value, context) if isinstance(value, str) else value for key, value in action.items()}
        actions.append(rendered)
        if rendered.get("type") == "set_variable" and rendered.get("key"):
            context.setdefault("variables", {})[rendered["key"]] = rendered.get("value", "")
    return TestResult(True, condition_results, actions, context)
