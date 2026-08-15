import asyncio
import os
import sys
import time
import httpx
import json
from pathlib import Path

# Add root to sys.path to import bots module
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from .macro.engine import test_macro, trigger_matches

CONFIG_FILE = Path.home() / ".frogubot.json"
def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except:
            pass
    return {}

def save_config(config):
    CONFIG_FILE.write_text(json.dumps(config))

cfg = load_config()

API_URL = os.getenv("FROGUBOT_API_URL", cfg.get("api_url", "https://api_server_frogubot.cohuw.com/api/v1"))
API_KEY = os.getenv("FROGUBOT_API_KEY", cfg.get("api_key", ""))

API_ID = os.getenv("TELEGRAM_API_ID", cfg.get("api_id", 17711477))
API_HASH = os.getenv("TELEGRAM_API_HASH", cfg.get("api_hash", "bcf7bc9e630e4699a4d1db1f474df0c9"))

app = Client("frogubot_session", api_id=API_ID, api_hash=API_HASH)

macros_cache = []

async def sync_macros():
    global macros_cache
    if not API_KEY:
        print("FROGUBOT_API_KEY is not set. Running without macros.")
        return
    
    async with httpx.AsyncClient(verify=False) as client:
        try:
            response = await client.get(
                f"{API_URL}/sync/macros",
                headers={"X-Api-Key": API_KEY}
            )
            response.raise_for_status()
            macros_cache = response.json()
            print(f"Successfully synced {len(macros_cache)} macros.")
        except Exception as e:
            print(f"Failed to sync macros: {e}")

async def report_run(macro_id: str, status: str, duration_ms: float, error: str = "", details: dict = None):
    if not API_KEY: return
    async with httpx.AsyncClient(verify=False) as client:
        try:
            await client.post(
                f"{API_URL}/macros/runs",
                headers={"X-Api-Key": API_KEY},
                json={
                    "macro_id": macro_id,
                    "status": status,
                    "duration_ms": duration_ms,
                    "error": error,
                    "details": details or {}
                }
            )
        except Exception as e:
            print(f"Failed to report run: {e}")

def get_safe_globals():
    return {
        "__builtins__": {
            "print": print, "len": len, "range": range, "str": str, "int": int, "float": float,
            "bool": bool, "list": list, "dict": dict, "set": set, "tuple": tuple,
            "enumerate": enumerate, "zip": zip, "sum": sum, "min": min, "max": max,
            "abs": abs, "round": round, "any": any, "all": all, "isinstance": isinstance,
            "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
        },
        "re": __import__("re"),
        "json": __import__("json"),
        "math": __import__("math"),
        "time": __import__("time"),
        "random": __import__("random"),
        "datetime": __import__("datetime"),
        "asyncio": __import__("asyncio"),
    }

async def execute_python_code(client: Client, message: Message, code: str, context: dict):
    wrapper = "async def __macro_run(client, message, context):\n"
    for line in code.splitlines():
        wrapper += f"    {line}\n"
    if not code.strip():
        wrapper += "    pass\n"

    safe_globals = get_safe_globals()
    exec(wrapper, safe_globals)
    func = safe_globals["__macro_run"]
    await func(client, message, context)


async def execute_action(client: Client, message: Message, action: dict, context: dict):
    a_type = action.get("type")
    if a_type == "reply":
        await message.reply_text(action.get("text", ""))
    elif a_type == "send_message":
        chat_id = action.get("target_chat") or action.get("chat_id")
        if not chat_id: chat_id = message.chat.id
        await client.send_message(chat_id, action.get("text", ""))
    elif a_type == "delete" or a_type == "delete_message":
        await message.delete()
    elif a_type == "forward" or a_type == "forward_message":
        chat_id = action.get("target_chat") or action.get("chat_id")
        if not chat_id: chat_id = message.chat.id
        await message.forward(chat_id)
    elif a_type == "api_request":
        url = action.get("url")
        if url:
            async with httpx.AsyncClient(verify=False) as http_client:
                await http_client.request(
                    method=action.get("method", "GET"),
                    url=url,
                    json=action.get("body_json") or action.get("payload")
                )
    elif a_type == "run_python":
        code = action.get("code", "")
        await execute_python_code(client, message, code, context)
    elif a_type == "set_variable":
        pass  # Handled in engine
    else:
        print(f"Unknown action type: {a_type}")

def to_dict(msg: Message) -> dict:
    chat_type = str(msg.chat.type).split(".")[-1].lower() if msg.chat else ""
    return {
        "event_type": "message",
        "message": {
            "text": msg.text or msg.caption or "",
            "caption": msg.caption or "",
            "chat": {"id": msg.chat.id, "type": chat_type},
            "from_user": {"id": msg.from_user.id if msg.from_user else 0, "username": msg.from_user.username if msg.from_user else ""}
        },
        "chat": {"id": msg.chat.id, "type": chat_type},
        "sender": {"id": msg.from_user.id if msg.from_user else 0, "username": msg.from_user.username if msg.from_user else ""}
    }

@app.on_message(filters.private & ~filters.me, group=-1)
async def intercept_helper_bot(client: Client, message: Message):
    global API_KEY
    text = str(message.text or "")
    if "[FROG_AUTH_TOKEN]" in text:
        token = text.split("[FROG_AUTH_TOKEN] ")[-1].split("\n")[0].strip()
        API_KEY = token
        
        cfg = load_config()
        cfg["api_key"] = token
        save_config(cfg)
        
        print(f"[{time.strftime('%H:%M:%S')}] Received new API key via PM. Syncing macros...")
        await sync_macros()
        
        await message.delete()
        message.stop_propagation()

@app.on_message(filters.me & filters.command("sync", prefixes="."))
async def manual_sync_command(client: Client, message: Message):
    await message.edit_text("🔄 Синхронизация макросов...")
    await sync_macros()
    await message.edit_text(f"✅ Успешно загружено {len(macros_cache)} макросов!")
    
async def run_macro_task(client: Client, message: Message, macro: dict, event_dict: dict):
    start_time = time.time()
    try:
        result = test_macro(macro, event_dict)
        if not result.matched:
            return

        async def _execute_all():
            for action in result.actions:
                await execute_action(client, message, action, result.context)
        
        # Таймаут макроса 30 секунд, чтобы не вешал бота
        await asyncio.wait_for(_execute_all(), timeout=30.0)
        
        duration = (time.time() - start_time) * 1000
        asyncio.create_task(report_run(macro.get("id", ""), "success", duration))

    except asyncio.TimeoutError:
        duration = (time.time() - start_time) * 1000
        asyncio.create_task(report_run(macro.get("id", ""), "error", duration, "Execution timeout (30s)"))
    except FloodWait as e:
        duration = (time.time() - start_time) * 1000
        asyncio.create_task(report_run(macro.get("id", ""), "error", duration, f"FloodWait: {e.value}s"))
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        asyncio.create_task(report_run(macro.get("id", ""), "error", duration, str(e)))


@app.on_message(~filters.me)
async def handle_message(client: Client, message: Message):
    if not macros_cache:
        return
    
    event_dict = to_dict(message)
    
    for row in macros_cache:
        if not row.get("enabled", True): continue
        macro = row.get("payload", {})
        
        # Каждый макрос крутится параллельно в своей задаче
        asyncio.create_task(run_macro_task(client, message, macro, event_dict))

def main():
    print("Starting FrogUBot Client (Kurigram)...")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(sync_macros())
    print("FrogUBot is running! Press Ctrl+C to stop.")
    app.run()

if __name__ == "__main__":
    main()
