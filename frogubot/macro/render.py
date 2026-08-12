from __future__ import annotations

import json

from utils import esc


ACTION_TITLES = {
    "delete": "удалить сообщение",
    "reply": "ответить",
    "send_message": "отправить сообщение",
    "forward": "переслать",
    "api_request": "API-запрос",
    "set_variable": "задать переменную",
    "builtin": "встроенная функция",
    "run_python": "Python-код",
}


def _condition_to_text(cond: dict) -> str:
    return (
        f"{esc(cond.get('target', ''))} | "
        f"{esc(cond.get('match_type', ''))} | "
        f"{esc(cond.get('pattern', ''))}"
    )


def _action_to_text(action: dict) -> str:
    a_type = action.get("type", "")
    title = ACTION_TITLES.get(a_type, a_type)
    if a_type == "delete":
        return title
    if a_type == "reply":
        return f"{title}: {esc(action.get('text', ''))}"
    if a_type == "send_message":
        return (
            f"{title}: {esc(action.get('target_chat', ''))} - "
            f"{esc(action.get('text', ''))}"
        )
    if a_type == "forward":
        return f"{title}: {esc(action.get('target_chat', ''))}"
    if a_type == "api_request":
        return f"{title}: {esc(action.get('method', ''))} {esc(action.get('url', ''))}"
    if a_type == "set_variable":
        return f"{title}: {esc(action.get('key', ''))}"
    if a_type == "builtin":
        return f"{title}: {esc(action.get('name', ''))}"
    return esc(title)


def render_macro_preview(macro: dict) -> str:
    trigger = macro.get("trigger") or {}
    conditions = macro.get("conditions") or []
    actions = macro.get("actions") or []

    lines = [
        "<b>Предпросмотр макроса</b>",
        f"ID: <code>{esc(macro.get('id', ''))}</code>",
        f"Название: <b>{esc(macro.get('name', ''))}</b>",
        f"Включён: <b>{'да' if macro.get('enabled', True) else 'нет'}</b>",
        f"Доступ: <b>{'публичный' if macro.get('is_public') else 'приватный'}</b>",
        f"Триггер: <code>{esc(trigger.get('type', '-'))}</code>",
        "",
        f"<b>Условия</b> ({len(conditions)})",
    ]

    if conditions:
        for idx, cond in enumerate(conditions, start=1):
            lines.append(f"{idx}. {_condition_to_text(cond)}")
    else:
        lines.append("-")

    lines += ["", f"<b>Действия</b> ({len(actions)})"]
    if actions:
        for idx, action in enumerate(actions, start=1):
            lines.append(f"{idx}. {_action_to_text(action)}")
    else:
        lines.append("-")

    return "\n".join(lines)


def render_macro_list(macros: list[dict]) -> str:
    if not macros:
        return "<b>Мои макросы</b>\n\nСохранённых макросов пока нет."

    lines = ["<b>Мои макросы</b>", ""]
    for idx, macro in enumerate(macros, start=1):
        state = "вкл" if macro.get("enabled", True) else "выкл"
        lines.append(
            f"{idx}. <b>{esc(macro.get('name', 'Без названия'))}</b> "
            f"- <code>{esc(macro.get('id', ''))}</code> ({state})"
        )
    return "\n".join(lines)


def render_macro_json(macro: dict) -> str:
    payload = json.dumps(macro, ensure_ascii=False, indent=2, sort_keys=True)
    return f"<b>JSON макроса</b>\n<pre>{esc(payload)}</pre>"


def render_test_result(result) -> str:
    lines = ["<b>Тест макроса</b>", f"Сработал: <b>{'да' if result.matched else 'нет'}</b>"]
    if result.errors:
        lines += ["", "<b>Ошибки валидации</b>"] + [f"- {esc(item)}" for item in result.errors]
    if result.conditions:
        lines += ["", "<b>Условия</b>"]
        for item in result.conditions:
            mark = "OK" if item["matched"] else "NO"
            lines.append(f"- {mark}: {esc(item['condition'].get('target', ''))}")
    if result.actions:
        lines += ["", "<b>План действий</b>"]
        for action in result.actions:
            lines.append(f"- <code>{esc(json.dumps(action, ensure_ascii=False))}</code>")
    return "\n".join(lines)
