from __future__ import annotations

import random
import re
import uuid
from datetime import datetime
from typing import Any


PLACEHOLDER_RE = re.compile(r"\{\{\s*(.*?)\s*\}\}")


def _get_path(obj: Any, path: str):
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur


def _split_args(arg_string: str) -> list[str]:
    if not arg_string.strip():
        return []
    args = []
    current = []
    in_quote = False
    quote_char = ""
    escape = False

    for ch in arg_string:
        if escape:
            current.append(ch)
            escape = False
            continue
        if ch == "\\":
            current.append(ch)
            escape = True
            continue
        if ch in ("'", '"'):
            current.append(ch)
            if not in_quote:
                in_quote = True
                quote_char = ch
            elif quote_char == ch:
                in_quote = False
            continue
        if ch == "," and not in_quote:
            args.append("".join(current).strip())
            current = []
            continue
        current.append(ch)

    if current:
        args.append("".join(current).strip())
    return args


def _parse_literal(token: str, context: dict[str, Any]):
    token = token.strip()
    if not token:
        return ""
    if (token.startswith("'") and token.endswith("'")) or (
        token.startswith('"') and token.endswith('"')
    ):
        return token[1:-1]
    if token in context:
        return context[token]
    return _get_path(context, token)


def _resolve(expr: str, context: dict[str, Any]):
    expr = expr.strip()

    if expr == "time":
        return datetime.now().strftime("%H:%M:%S")
    if expr == "date":
        return datetime.now().strftime("%Y-%m-%d")
    if expr == "unix":
        return int(datetime.now().timestamp())
    if expr == "uuid":
        return str(uuid.uuid4())
    if expr == "random":
        return random.randint(0, 10**9)

    if "(" in expr and expr.endswith(")"):
        fn_name = expr[: expr.index("(")].strip()
        arg_string = expr[expr.index("(") + 1 : -1].strip()
        args = [_parse_literal(x, context) for x in _split_args(arg_string)]

        if fn_name == "upper":
            return str(args[0]).upper() if args else ""
        if fn_name == "lower":
            return str(args[0]).lower() if args else ""
        if fn_name == "title":
            return str(args[0]).title() if args else ""
        if fn_name == "replace":
            if len(args) >= 3:
                return str(args[0]).replace(str(args[1]), str(args[2]))
            return args[0] if args else ""
        if fn_name == "len":
            return len(args[0]) if args else 0
        if fn_name == "time":
            fmt = str(args[0]) if args else "%H:%M:%S"
            return datetime.now().strftime(fmt)

        return ""

    value = _get_path(context, expr)
    if value is None and expr in {"user", "sender"}:
        user = context.get("user") or context.get("sender")
        if user is None:
            return ""
        username = getattr(user, "username", None)
        return f"@{username}" if username else getattr(user, "first_name", "")
    if value is None and expr == "chat":
        chat = context.get("chat")
        return getattr(chat, "title", "") or getattr(chat, "id", "")
    if value is None and expr == "message":
        msg = context.get("message")
        return getattr(msg, "text", "") or getattr(msg, "caption", "")
    return value if value is not None else ""


def render_template(text: str, context: dict[str, Any]) -> str:
    def repl(match: re.Match):
        expr = match.group(1)
        try:
            value = _resolve(expr, context)
            return "" if value is None else str(value)
        except Exception:
            return match.group(0)

    return PLACEHOLDER_RE.sub(repl, text)