from __future__ import annotations

import json
from typing import Optional

from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified
from pyrogram.types import CallbackQuery, Message

from CFG import OWNER_IDS
from utils import esc, log_to_chat, safe_reply

from .keyboard import (
    action_choice_keyboard,
    action_type_keyboard,
    confirm_delete_keyboard,
    condition_target_keyboard,
    draft_keyboard,
    home_keyboard,
    list_keyboard,
    match_type_keyboard,
    trigger_keyboard,
)
from .render import render_macro_json, render_macro_list, render_macro_preview, render_test_result
from .engine import test_macro
from .schema import ACTION_SCHEMAS
from .session import SessionStore
from .storage import MacroStorage
from .validator import validate_macro


def _is_owner(user_id: int) -> bool:
    return (not OWNER_IDS) or (user_id in OWNER_IDS)


def _home_text() -> str:
    return (
        "<b>FrogUBot: конструктор макросов</b>\n\n"
        "Создавай макросы через кнопки, черновики и JSON.\n"
        "Начни новый макрос или открой сохранённые."
    )


def _draft_text(session) -> str:
    macro = session.macro
    trig = macro.get("trigger") or {}
    conditions = macro.get("conditions") or []
    actions = macro.get("actions") or []

    status = "готов" if macro.get("name") and trig.get("type") and actions else "черновик"
    text = [
        "<b>Редактор макроса</b>",
        f"Статус: <b>{esc(status)}</b>",
        f"ID: <code>{esc(macro.get('id', ''))}</code>",
        f"Название: <b>{esc(macro.get('name') or '-')}</b>",
        f"Доступ: <b>{'публичный' if macro.get('is_public') else 'приватный'}</b>",
        f"Триггер: <code>{esc(trig.get('type', '-'))}</code>",
        f"Условия: <b>{len(conditions)}</b>",
        f"Действия: <b>{len(actions)}</b>",
    ]
    if session.awaiting:
        text.append("")
        text.append(f"Ожидаю ввод: <b>{esc(session.awaiting)}</b>")
    if session.last_error:
        text.append("")
        text.append(f"Последняя ошибка: <code>{esc(session.last_error)}</code>")
    return "\n".join(text)


async def _safe_edit(query: CallbackQuery, text: str, reply_markup=None):
    try:
        await query.message.edit_text(text, reply_markup=reply_markup)
    except MessageNotModified:
        pass


def register_macro_handlers(app: Client, storage: MacroStorage):
    sessions = SessionStore(storage)

    async def show_home(query_or_message, session=None, note: Optional[str] = None):
        text = _home_text()
        if note:
            text += f"\n\n{note}"

        if isinstance(query_or_message, CallbackQuery):
            await _safe_edit(query_or_message, text, reply_markup=home_keyboard())
        else:
            await query_or_message.reply_text(text, reply_markup=home_keyboard())

    async def show_editor(query_or_message, session):
        text = _draft_text(session)
        markup = draft_keyboard()
        if isinstance(query_or_message, CallbackQuery):
            await _safe_edit(query_or_message, text, reply_markup=markup)
        else:
            await query_or_message.reply_text(text, reply_markup=markup)

    async def ask_text(query: CallbackQuery, session, stage: str, text: str, markup=None):
        session.stage = stage
        session.awaiting = stage
        session.last_error = None
        await sessions.save(session)
        await _safe_edit(query, text, reply_markup=markup)

    async def ask_message(message: Message, session, stage: str, text: str, markup=None):
        session.stage = stage
        session.awaiting = stage
        session.last_error = None
        await sessions.save(session)
        await message.reply_text(text, reply_markup=markup)

    async def finish_condition(user_id: int, session, query_or_message):
        session.macro.setdefault("conditions", []).append(session.pending_item)
        session.pending_item = {}
        session.pending_kind = None
        session.pending_fields = []
        session.pending_field_index = 0
        session.stage = "home"
        session.awaiting = None
        await sessions.save(session)
        if isinstance(query_or_message, CallbackQuery):
            await _safe_edit(query_or_message, _draft_text(session), reply_markup=draft_keyboard())
        else:
            await query_or_message.reply_text("Условие добавлено.", reply_markup=draft_keyboard())

    async def finish_action(user_id: int, session, query_or_message):
        session.macro.setdefault("actions", []).append(session.pending_item)
        session.pending_item = {}
        session.pending_kind = None
        session.pending_fields = []
        session.pending_field_index = 0
        session.stage = "home"
        session.awaiting = None
        await sessions.save(session)
        if isinstance(query_or_message, CallbackQuery):
            await _safe_edit(query_or_message, _draft_text(session), reply_markup=draft_keyboard())
        else:
            await query_or_message.reply_text("Действие добавлено.", reply_markup=draft_keyboard())

    @app.on_message(filters.private & filters.command("start"))
    async def start_command(client: Client, message: Message):
        if not message.from_user or not _is_owner(message.from_user.id):
            return await message.reply_text("Нет доступа.")
        await show_home(message)

    @app.on_message(filters.private & filters.command("macros"))
    async def macros_command(client: Client, message: Message):
        if not message.from_user or not _is_owner(message.from_user.id):
            return await message.reply_text("Нет доступа.")
        session = await sessions.get(message.from_user.id)
        await show_editor(message, session)

    @app.on_message(filters.private & filters.text & ~filters.command(["start", "macros"]))
    async def text_router(client: Client, message: Message):
        if not message.from_user or not _is_owner(message.from_user.id):
            return
        session = await sessions.get(message.from_user.id)
        if not session.awaiting:
            return

        text = message.text.strip()

        try:
            if session.awaiting == "await_name":
                session.macro["name"] = text
                session.stage = "home"
                session.awaiting = None
                await sessions.save(session)
                await message.reply_text("Название сохранено.", reply_markup=draft_keyboard())
                return

            if session.awaiting == "await_condition_pattern":
                pending = session.pending_item
                pending["pattern"] = text
                session.last_error = None
                await sessions.save(session)
                await finish_condition(message.from_user.id, session, message)
                return

            if session.awaiting == "await_test_event":
                try:
                    event = json.loads(text)
                except json.JSONDecodeError as exc:
                    return await message.reply_text(
                        f"Некорректный JSON события: <code>{esc(exc)}</code>",
                        reply_markup=draft_keyboard(),
                    )
                result = test_macro(session.macro, event, session.macro.get("runtime_variables"))
                session.awaiting = None
                session.stage = "home"
                await sessions.save(session)
                return await message.reply_text(render_test_result(result), reply_markup=draft_keyboard())

            if session.awaiting.startswith("await_action_field:"):
                field_name = session.awaiting.split(":", 1)[1]
                field_def = session.pending_fields[session.pending_field_index]
                kind = field_def.get("kind", "text")

                if kind == "json":
                    try:
                        parsed = json.loads(text)
                    except json.JSONDecodeError as exc:
                        session.last_error = f"Ошибка JSON в поле {field_name}: {exc}"
                        await sessions.save(session)
                        return await message.reply_text(
                            f"Некорректный JSON для <b>{esc(field_name)}</b>.\nОтправь валидный JSON ещё раз.",
                            reply_markup=draft_keyboard(),
                        )
                    session.pending_item[field_name] = parsed
                else:
                    session.pending_item[field_name] = text

                session.pending_field_index += 1
                session.last_error = None

                if session.pending_field_index >= len(session.pending_fields):
                    await sessions.save(session)
                    await finish_action(message.from_user.id, session, message)
                    return

                next_def = session.pending_fields[session.pending_field_index]
                next_name = next_def["name"]
                next_kind = next_def.get("kind", "text")

                await sessions.save(session)

                if next_kind == "choice":
                    await message.reply_text(
                        f"Выбери значение для <b>{esc(next_name)}</b>:",
                        reply_markup=action_choice_keyboard(
                            next_name, next_def.get("choices", [])
                        ),
                    )
                else:
                    await message.reply_text(
                        f"Отправь значение для <b>{esc(next_name)}</b>.",
                        reply_markup=draft_keyboard(),
                    )
                session.awaiting = f"await_action_field:{next_name}"
                await sessions.save(session)
                return

        except Exception as exc:
            session.last_error = str(exc)
            await sessions.save(session)
            await message.reply_text(f"Ошибка: <code>{esc(exc)}</code>", reply_markup=draft_keyboard())

    @app.on_callback_query(filters.regex(r"^macro:"))
    async def macro_router(client: Client, query: CallbackQuery):
        if not query.from_user or not _is_owner(query.from_user.id):
            return await query.answer("Нет доступа.", show_alert=True)

        session = await sessions.get(query.from_user.id)
        parts = query.data.split(":")

        try:
            action = parts[1]

            if action == "menu":
                await query.answer()
                return await _safe_edit(query, _home_text(), reply_markup=home_keyboard())

            if action == "new":
                session = await sessions.reset(query.from_user.id)
                session.stage = "await_name"
                session.awaiting = "await_name"
                await sessions.save(session)
                await query.answer("Черновик создан.")
                return await _safe_edit(
                    query,
                    "<b>Новый макрос</b>\nОтправь название макроса.",
                    reply_markup=draft_keyboard(),
                )

            if action == "reset":
                await sessions.reset(query.from_user.id)
                await query.answer("Черновик сброшен.")
                return await _safe_edit(query, _home_text(), reply_markup=home_keyboard())

            if action == "cancel":
                await sessions.clear(query.from_user.id)
                await query.answer("Отменено.")
                return await _safe_edit(query, _home_text(), reply_markup=home_keyboard())

            if action == "pick_trigger":
                await query.answer()
                session.stage = "pick_trigger"
                await sessions.save(session)
                return await _safe_edit(
                    query,
                    "<b>Выбери триггер</b>",
                    reply_markup=trigger_keyboard(),
                )

            if action == "trigger":
                trigger_type = parts[2]
                session.macro["trigger"] = {"type": trigger_type}
                session.stage = "home"
                session.awaiting = None
                await sessions.save(session)
                await query.answer(f"Триггер: {trigger_type}")
                return await _safe_edit(query, _draft_text(session), reply_markup=draft_keyboard())

            if action == "add_condition":
                session.pending_kind = "condition"
                session.pending_item = {}
                session.stage = "pick_condition_target"
                await sessions.save(session)
                await query.answer()
                return await _safe_edit(
                    query,
                    "<b>Выбери поле для условия</b>",
                    reply_markup=condition_target_keyboard(),
                )

            if action == "cond_target":
                target = parts[2]
                session.pending_item["target"] = target
                session.stage = "pick_condition_match"
                await sessions.save(session)
                await query.answer(f"Поле: {target}")
                return await _safe_edit(
                    query,
                    "<b>Выбери тип проверки</b>",
                    reply_markup=match_type_keyboard(),
                )

            if action == "cond_match":
                match_type = parts[2]
                session.pending_item["match_type"] = match_type
                session.stage = "await_condition_pattern"
                session.awaiting = "await_condition_pattern"
                await sessions.save(session)
                await query.answer(f"Проверка: {match_type}")
                return await _safe_edit(
                    query,
                    "<b>Отправь шаблон</b>\nПример: <code>hello</code> или <code>^buy \\d+</code>",
                    reply_markup=draft_keyboard(),
                )

            if action == "add_action":
                session.pending_kind = "action"
                session.pending_item = {}
                session.pending_fields = []
                session.pending_field_index = 0
                session.stage = "pick_action_type"
                await sessions.save(session)
                await query.answer()
                return await _safe_edit(
                    query,
                    "<b>Выбери действие</b>",
                    reply_markup=action_type_keyboard(),
                )

            if action == "action_type":
                a_type = parts[2]
                schema = ACTION_SCHEMAS[a_type]
                session.pending_item["type"] = a_type
                session.pending_fields = list(schema["fields"])
                session.pending_field_index = 0
                session.stage = "home"
                await sessions.save(session)

                if not session.pending_fields:
                    await query.answer(f"Действие: {a_type}")
                    await finish_action(query.from_user.id, session, query)
                    return

                field = session.pending_fields[0]
                field_name = field["name"]
                if field.get("kind") == "choice":
                    session.awaiting = f"await_action_field:{field_name}"
                    await sessions.save(session)
                    await query.answer(f"Действие: {a_type}")
                    return await _safe_edit(
                        query,
                        f"Выбери значение для <b>{esc(field_name)}</b>:",
                        reply_markup=action_choice_keyboard(
                            field_name, field.get("choices", [])
                        ),
                    )

                session.awaiting = f"await_action_field:{field_name}"
                await sessions.save(session)
                await query.answer(f"Действие: {a_type}")
                return await _safe_edit(
                    query,
                    f"Отправь значение для <b>{esc(field_name)}</b>.",
                    reply_markup=draft_keyboard(),
                )

            if action == "action_choice":
                if not session.awaiting or not session.awaiting.startswith("await_action_field:"):
                    return await query.answer("Нет ожидаемого поля действия.", show_alert=True)

                field_name = session.awaiting.split(":", 1)[1]
                value = parts[2]
                session.pending_item[field_name] = value
                session.pending_field_index += 1
                await sessions.save(session)

                if session.pending_field_index >= len(session.pending_fields):
                    await query.answer(f"{field_name}: {value}")
                    return await finish_action(query.from_user.id, session, query)

                next_def = session.pending_fields[session.pending_field_index]
                next_name = next_def["name"]
                next_kind = next_def.get("kind", "text")
                session.awaiting = f"await_action_field:{next_name}"
                await sessions.save(session)

                await query.answer(f"{field_name}: {value}")
                if next_kind == "choice":
                    return await _safe_edit(
                        query,
                        f"Выбери значение для <b>{esc(next_name)}</b>:",
                        reply_markup=action_choice_keyboard(
                            next_name, next_def.get("choices", [])
                        ),
                    )
                return await _safe_edit(
                    query,
                    f"Отправь значение для <b>{esc(next_name)}</b>.",
                    reply_markup=draft_keyboard(),
                )

            if action == "preview":
                await query.answer()
                return await _safe_edit(
                    query,
                    render_macro_preview(session.macro),
                    reply_markup=draft_keyboard(),
                )

            if action == "json":
                await query.answer()
                return await _safe_edit(query, render_macro_json(session.macro), reply_markup=draft_keyboard())

            if action == "toggle_public":
                session.macro["is_public"] = not bool(session.macro.get("is_public", False))
                await sessions.save(session)
                await query.answer("Публичный" if session.macro["is_public"] else "Приватный")
                return await _safe_edit(query, _draft_text(session), reply_markup=draft_keyboard())

            if action == "test":
                session.awaiting = "await_test_event"
                session.stage = "test"
                await sessions.save(session)
                await query.answer()
                return await _safe_edit(
                    query,
                    "<b>Тест макроса</b>\nОтправь тестовое событие JSON, например:\n<pre>{\"event_type\":\"message\",\"message\":{\"text\":\"hello\"}}</pre>",
                    reply_markup=draft_keyboard(),
                )

            if action == "save":
                errors = validate_macro(session.macro)
                if errors:
                    session.last_error = "\n".join(errors)
                    await sessions.save(session)
                    return await query.answer("Сначала исправь ошибки.", show_alert=True)

                await storage.save_macro(session.macro)
                await storage.clear_draft(query.from_user.id)
                await log_to_chat(
                    client,
                    (
                        "Макрос сохранён\n"
                        f"Название: <b>{esc(session.macro.get('name', ''))}</b>\n"
                        f"ID: <code>{esc(session.macro.get('id', ''))}</code>"
                    ),
                )
                await sessions.reset(query.from_user.id)
                await query.answer("Сохранено.")
                return await _safe_edit(
                    query,
                    "<b>Сохранено.</b>\nМакрос отправлен в хранилище.",
                    reply_markup=home_keyboard(),
                )

            if action == "list":
                macros = await storage.list_macros(query.from_user.id)
                await query.answer()
                return await _safe_edit(
                    query,
                    render_macro_list(macros),
                    reply_markup=list_keyboard(macros),
                )

            if action == "view":
                macro_id = parts[2]
                macro = await storage.get_macro(macro_id, query.from_user.id)
                if not macro:
                    return await query.answer("Макрос не найден.", show_alert=True)
                await query.answer()
                return await _safe_edit(
                    query,
                    render_macro_preview(macro),
                    reply_markup=draft_keyboard(),
                )

            if action == "delete":
                macro_id = parts[2]
                macro = await storage.get_macro(macro_id, query.from_user.id)
                if not macro:
                    return await query.answer("Макрос не найден.", show_alert=True)
                await query.answer()
                return await _safe_edit(
                    query,
                    f"Удалить макрос <b>{esc(macro.get('name', ''))}</b>?",
                    reply_markup=confirm_delete_keyboard(macro_id),
                )

            if action == "delete_ok":
                macro_id = parts[2]
                await storage.delete_macro(macro_id, query.from_user.id)
                await query.answer("Удалено.")
                macros = await storage.list_macros(query.from_user.id)
                return await _safe_edit(
                    query,
                    render_macro_list(macros),
                    reply_markup=list_keyboard(macros),
                )

            await query.answer("Неизвестное действие.", show_alert=True)

        except Exception as exc:
            session.last_error = str(exc)
            await sessions.save(session)
            await query.answer("Ошибка конструктора макросов.", show_alert=True)
            try:
                await query.message.reply_text(f"<code>{esc(exc)}</code>")
            except Exception:
                pass
