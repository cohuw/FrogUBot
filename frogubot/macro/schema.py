from __future__ import annotations

TRIGGER_TYPES = [
    ("message", "Сообщение"),
    ("edited_message", "Изменённое сообщение"),
    ("callback_query", "Нажатие кнопки"),
    ("scheduled", "По расписанию"),
    ("reaction", "Реакция"),
    ("member_join", "Участник вошёл"),
    ("member_leave", "Участник вышел"),
]

TRIGGER_SCOPES = [
    ("specific", "Конкретные чаты"),
    ("list", "Список чатов"),
    ("all", "Все чаты"),
    ("private", "Личные чаты"),
    ("channels", "Каналы"),
    ("groups", "Группы"),
]

SOURCE_TYPES = [
    ("any", "Любой пользователь"),
    ("user_id", "ID пользователя"),
    ("username", "Username"),
    ("list", "Список пользователей"),
    ("except", "Кроме указанных"),
]

CONDITION_TARGETS = [
    ("text", "Текст"),
    ("sender.id", "ID отправителя"),
    ("sender.username", "Username отправителя"),
    ("sender.first_name", "Имя отправителя"),
    ("chat.id", "ID чата"),
    ("chat.title", "Название чата"),
    ("message.id", "ID сообщения"),
    ("has_media", "Есть медиа"),
    ("caption", "Подпись"),
    ("command", "Команда"),
    ("is_reply", "Ответ"),
    ("is_forward", "Переслано"),
    ("is_admin", "Админ"),
    ("is_owner", "Владелец"),
]

MATCH_TYPES = [
    ("exact", "Равно"),
    ("contains", "Содержит"),
    ("starts_with", "Начинается с"),
    ("ends_with", "Заканчивается на"),
    ("regex", "Regex"),
    ("not_contains", "Не содержит"),
    ("not_exact", "Не равно"),
    ("in_list", "В списке"),
    ("not_in_list", "Не в списке"),
    ("greater", "Больше"),
    ("less", "Меньше"),
    ("between", "Между"),
    ("exists", "Существует"),
    ("not_exists", "Не существует"),
    ("has_media", "Есть медиа"),
    ("is_reply", "Ответ"),
    ("is_forward", "Переслано"),
    ("is_admin", "Админ"),
    ("is_owner", "Владелец"),
    ("time_range", "Диапазон времени"),
]

ACTION_SCHEMAS = {
    "reply": {
        "label": "Ответить",
        "fields": [
            {"name": "text", "label": "Текст", "kind": "text"},
        ],
    },
    "send_message": {
        "label": "Отправить сообщение",
        "fields": [
            {"name": "target_chat", "label": "Целевой чат", "kind": "text"},
            {"name": "text", "label": "Текст", "kind": "text"},
        ],
    },
    "delete": {
        "label": "Удалить сообщение",
        "fields": [],
    },
    "forward": {
        "label": "Переслать",
        "fields": [
            {"name": "target_chat", "label": "Целевой чат", "kind": "text"},
        ],
    },
    "api_request": {
        "label": "API-запрос",
        "fields": [
            {
                "name": "method",
                "label": "HTTP-метод",
                "kind": "choice",
                "choices": ["GET", "POST", "PUT", "PATCH", "DELETE"],
            },
            {"name": "url", "label": "URL", "kind": "text"},
            {"name": "headers_json", "label": "Заголовки JSON", "kind": "json"},
            {"name": "body_json", "label": "Тело JSON", "kind": "json"},
        ],
    },
    "set_variable": {
        "label": "Задать переменную",
        "fields": [
            {"name": "key", "label": "Ключ", "kind": "text"},
            {"name": "value", "label": "Значение", "kind": "text"},
        ],
    },
    "builtin": {
        "label": "Встроенная функция",
        "fields": [
            {"name": "name", "label": "Имя функции", "kind": "text"},
            {"name": "args_json", "label": "Аргументы JSON", "kind": "json"},
        ],
    },
    "run_python": {
        "label": "Python-код",
        "fields": [
            {"name": "code", "label": "Код", "kind": "text"},
        ],
    },
}


def action_types():
    return [(k, v["label"]) for k, v in ACTION_SCHEMAS.items()]
