from __future__ import annotations

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .schema import ACTION_SCHEMAS, CONDITION_TARGETS, MATCH_TYPES, TRIGGER_TYPES


def _chunks(items, size=2):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def home_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Новый макрос", callback_data="macro:new")],
            [InlineKeyboardButton("Мои макросы", callback_data="macro:list")],
            [InlineKeyboardButton("Сбросить черновик", callback_data="macro:reset")],
        ]
    )


def draft_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Триггер", callback_data="macro:pick_trigger")],
            [InlineKeyboardButton("Условие", callback_data="macro:add_condition")],
            [InlineKeyboardButton("Действие", callback_data="macro:add_action")],
            [InlineKeyboardButton("Предпросмотр", callback_data="macro:preview")],
            [InlineKeyboardButton("Тест", callback_data="macro:test")],
            [InlineKeyboardButton("JSON", callback_data="macro:json")],
            [InlineKeyboardButton("Публичность", callback_data="macro:toggle_public")],
            [InlineKeyboardButton("Сохранить", callback_data="macro:save")],
            [InlineKeyboardButton("Назад", callback_data="macro:menu")],
            [InlineKeyboardButton("Отмена", callback_data="macro:cancel")],
        ]
    )


def trigger_keyboard():
    buttons = [
        InlineKeyboardButton(label, callback_data=f"macro:trigger:{key}")
        for key, label in TRIGGER_TYPES
    ]
    rows = [list(chunk) for chunk in _chunks(buttons, 2)]
    rows.append([InlineKeyboardButton("Назад", callback_data="macro:menu")])
    return InlineKeyboardMarkup(rows)


def condition_target_keyboard():
    buttons = [
        InlineKeyboardButton(label, callback_data=f"macro:cond_target:{key}")
        for key, label in CONDITION_TARGETS
    ]
    rows = [list(chunk) for chunk in _chunks(buttons, 2)]
    rows.append([InlineKeyboardButton("Назад", callback_data="macro:menu")])
    return InlineKeyboardMarkup(rows)


def match_type_keyboard():
    buttons = [
        InlineKeyboardButton(label, callback_data=f"macro:cond_match:{key}")
        for key, label in MATCH_TYPES
    ]
    rows = [list(chunk) for chunk in _chunks(buttons, 2)]
    rows.append([InlineKeyboardButton("Назад", callback_data="macro:menu")])
    return InlineKeyboardMarkup(rows)


def action_type_keyboard():
    buttons = [
        InlineKeyboardButton(schema["label"], callback_data=f"macro:action_type:{key}")
        for key, schema in ACTION_SCHEMAS.items()
    ]
    rows = [list(chunk) for chunk in _chunks(buttons, 2)]
    rows.append([InlineKeyboardButton("Назад", callback_data="macro:menu")])
    return InlineKeyboardMarkup(rows)


def action_choice_keyboard(field_name: str, choices: list[str]):
    buttons = [
        InlineKeyboardButton(choice, callback_data=f"macro:action_choice:{choice}")
        for choice in choices
    ]
    rows = [list(chunk) for chunk in _chunks(buttons, 2)]
    rows.append([InlineKeyboardButton("Назад", callback_data="macro:add_action")])
    return InlineKeyboardMarkup(rows)


def list_keyboard(macros: list[dict]):
    rows = []
    for macro in macros:
        mid = macro["id"]
        rows.append(
            [
                InlineKeyboardButton(
                    macro.get("name", "Без названия")[:20],
                    callback_data=f"macro:view:{mid}",
                ),
                InlineKeyboardButton("Удалить", callback_data=f"macro:delete:{mid}"),
            ]
        )
    rows.append([InlineKeyboardButton("Назад", callback_data="macro:menu")])
    return InlineKeyboardMarkup(rows)


def confirm_delete_keyboard(macro_id: str):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Да", callback_data=f"macro:delete_ok:{macro_id}"),
                InlineKeyboardButton("Нет", callback_data="macro:list"),
            ]
        ]
    )
