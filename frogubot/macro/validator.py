from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from .schema import ACTION_SCHEMAS, CONDITION_TARGETS, MATCH_TYPES, TRIGGER_TYPES, TRIGGER_SCOPES, SOURCE_TYPES


TRIGGER_KEYS = {k for k, _ in TRIGGER_TYPES}
TARGET_KEYS = {k for k, _ in CONDITION_TARGETS}
MATCH_KEYS = {k for k, _ in MATCH_TYPES}
ACTION_KEYS = set(ACTION_SCHEMAS.keys())
SCOPE_KEYS = {k for k, _ in TRIGGER_SCOPES}
SOURCE_KEYS = {k for k, _ in SOURCE_TYPES}


def validate_macro(macro: dict, is_admin: bool = False) -> list[str]:
    errors: list[str] = []

    if not isinstance(macro, dict):
        return ["Макрос должен быть JSON-объектом."]

    if not str(macro.get("id", "")).strip():
        errors.append("Не указан ID макроса.")

    name = str(macro.get("name", "")).strip()
    if not name:
        errors.append("Название макроса пустое.")

    trigger = macro.get("trigger") or {}
    trigger_type = trigger.get("type")
    if trigger_type not in TRIGGER_KEYS:
        errors.append("Некорректный тип триггера.")
    scope = trigger.get("scope") or {"chat_mode": "all"}
    if scope.get("chat_mode", "all") not in SCOPE_KEYS:
        errors.append("Некорректная область триггера.")
    source = trigger.get("source") or {"type": "any"}
    if source.get("type", "any") not in SOURCE_KEYS:
        errors.append("Некорректный источник триггера.")

    conditions = macro.get("conditions") or []
    if not isinstance(conditions, list):
        errors.append("Условия должны быть списком.")
    else:
        for idx, cond in enumerate(conditions, start=1):
            if not isinstance(cond, dict):
                errors.append(f"Условие #{idx}: должно быть объектом.")
                continue
            if cond.get("target") not in TARGET_KEYS:
                errors.append(f"Условие #{idx}: некорректное поле.")
            if cond.get("match_type") not in MATCH_KEYS:
                errors.append(f"Условие #{idx}: некорректный тип проверки.")
            pattern = cond.get("pattern", "")
            if cond.get("match_type") not in {"exists", "not_exists", "has_media", "is_reply", "is_forward", "is_admin", "is_owner"} and not str(pattern).strip():
                errors.append(f"Условие #{idx}: пустой шаблон.")
            if cond.get("match_type") == "regex":
                try:
                    re.compile(pattern)
                except re.error as exc:
                    errors.append(f"Условие #{idx}: ошибка regex: {exc}")

    actions = macro.get("actions") or []
    if not isinstance(actions, list) or not actions:
        errors.append("Нужно добавить хотя бы одно действие.")
    else:
        for idx, action in enumerate(actions, start=1):
            if not isinstance(action, dict):
                errors.append(f"Действие #{idx}: должно быть объектом.")
                continue
            a_type = action.get("type")
            if a_type not in ACTION_KEYS:
                errors.append(f"Действие #{idx}: некорректный тип.")
                continue

            schema = ACTION_SCHEMAS[a_type]["fields"]
            for field in schema:
                key = field["name"]
                if key not in action:
                    errors.append(f"Действие #{idx}: не заполнено поле '{key}'.")
                    continue

                if field["kind"] == "json":
                    value = action.get(key)
                    if not isinstance(value, (dict, list)):
                        errors.append(f"Действие #{idx}: поле '{key}' должно быть JSON-объектом или массивом.")

            if a_type == "api_request":
                url = str(action.get("url", "")).strip()
                parsed = urlparse(url)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    errors.append(f"Действие #{idx}: некорректный URL.")
                method = str(action.get("method", "")).upper()
                if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                    errors.append(f"Действие #{idx}: некорректный HTTP-метод.")

            if a_type == "builtin":
                fn_name = str(action.get("name", "")).strip()
                if not fn_name:
                    errors.append(f"Действие #{idx}: пустое имя встроенной функции.")

            if a_type == "run_python":
                if not is_admin:
                    errors.append(f"Действие #{idx}: run_python временно отключен из соображений безопасности.")
                else:
                    code = str(action.get("code", "")).strip()
                    if not code:
                        errors.append(f"Действие #{idx}: пустой Python-код.")
                    forbidden = re.compile(r"\b(import|exec|eval|open|__import__|subprocess|os\.system|shutil\.rmtree)\b")
                    if forbidden.search(code):
                        errors.append(f"Действие #{idx}: небезопасный Python-код запрещён.")

            for key, value in action.items():
                if isinstance(value, str) and "{{" in value:
                    for placeholder in re.findall(r"\{\{\s*(.*?)\s*\}\}", value):
                        if not placeholder or not re.fullmatch(r"[\w.]+(?:\([^{}]*\))?", placeholder):
                            errors.append(f"Действие #{idx}: некорректный placeholder '{placeholder}'.")

    return errors
