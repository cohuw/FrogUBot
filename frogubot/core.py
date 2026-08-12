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

async def execute_action(client: Client, message: Message, action: dict):
    a_type = action.get("type")
    if a_type == "reply":
        await message.reply_text(action.get("text", ""))
    elif a_type == "send_message":
        chat_id = action.get("chat_id")
        if not chat_id: chat_id = message.chat.id
        await client.send_message(chat_id, action.get("text", ""))
    elif a_type == "delete_message":
        await message.delete()
    elif a_type == "forward_message":
        chat_id = action.get("chat_id")
        if not chat_id: chat_id = message.chat.id
        await message.forward(chat_id)
    elif a_type == "api_request":
        url = action.get("url")
        if url:
            async with httpx.AsyncClient(verify=False) as http_client:
                await http_client.request(
                    method=action.get("method", "GET"),
                    url=url,
                    json=action.get("payload")
                )
    # run_python is skipped due to security restrictions as requested
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
    
@app.on_message(~filters.me)
async def handle_message(client: Client, message: Message):
    if not macros_cache:
        return
    
    event_dict = to_dict(message)
    
    for row in macros_cache:
        if not row.get("enabled", True): continue
        macro = row.get("payload", {})
        
        start_time = time.time()
        try:
            result = test_macro(macro, event_dict)
            print(f"Testing macro '{macro.get('name')}' against message '{message.text}': matched={result.matched}")
            if not result.matched:
                if result.errors:
                    print(f"  Errors: {result.errors}")
                # Print why it failed matching
                print(f"  Trigger matched: {trigger_matches(macro, result.context)}")
                if trigger_matches(macro, result.context):
                    print(f"  Conditions: {result.conditions}")
            
            if result.matched:
                print(f"Macro matched: {macro.get('name', macro.get('id'))}")
                for action in result.actions:
                    await execute_action(client, message, action)
                duration = (time.time() - start_time) * 1000
                asyncio.create_task(report_run(macro.get("id", ""), "success", duration))
                break # Stop processing other macros for this event if one matches
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            asyncio.create_task(report_run(macro.get("id", ""), "error", duration, str(e)))

def main():
    print("Starting FrogUBot Client (Kurigram)...")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(sync_macros())
    print("FrogUBot is running! Press Ctrl+C to stop.")
    app.run()

if __name__ == "__main__":
    main()
