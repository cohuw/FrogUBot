import argparse
import json
from pathlib import Path

CONFIG_FILE = Path.home() / ".frogubot.json"

def setup_wizard():
    parser = argparse.ArgumentParser(description="Настройка FrogUBot")
    parser.add_argument("--api-id", type=int, help="Telegram API ID")
    parser.add_argument("--api-hash", type=str, help="Telegram API Hash")
    parser.add_argument("--key", type=str, help="FROGUBOT API KEY")
    args = parser.parse_args()

    config = {}
    if CONFIG_FILE.exists():
        try:
            config = json.loads(CONFIG_FILE.read_text())
        except:
            pass

    if args.api_id or args.api_hash or args.key:
        if args.api_id: config["api_id"] = args.api_id
        if args.api_hash: config["api_hash"] = args.api_hash
        if args.key: config["api_key"] = args.key
        CONFIG_FILE.write_text(json.dumps(config, indent=2))
        print(f"✅ Настройки успешно сохранены в {CONFIG_FILE} (тихий режим)")
        return

    print("=" * 40)
    print("🐸 FrogUBot Setup Wizard")
    print("=" * 40)
    print("Давайте настроим вашего юзербота.\n")

    print("Подсказка: Если у вас нет своих API_ID и API_HASH, просто нажмите Enter, чтобы использовать стандартные.")
    api_id = input(f"Telegram API_ID (текущий: {config.get('api_id', '17711477')}): ").strip()
    if api_id:
        try:
            config["api_id"] = int(api_id)
        except ValueError:
            print("Ошибка: API_ID должен быть числом.")
            return
        
    api_hash = input(f"Telegram API_HASH (текущий: {config.get('api_hash', 'bcf7bc9e630e4699a4d1db1f474df0c9')}): ").strip()
    if api_hash:
        config["api_hash"] = api_hash
        
    api_key = input(f"FROGUBOT API_KEY (выдается в главном боте): ").strip()
    if api_key:
        config["api_key"] = api_key
        
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    
    print("\n✅ Настройки успешно сохранены в", CONFIG_FILE)
    print("Теперь вы можете запустить бота командой: frogubot")

def start_bot():
    from .core import main
    main()

if __name__ == "__main__":
    setup_wizard()
