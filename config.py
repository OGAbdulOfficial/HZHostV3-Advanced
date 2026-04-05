import os

from dotenv import load_dotenv


load_dotenv()


def _parse_admin_ids(raw_value: str) -> list[int]:
    admin_ids: list[int] = []
    for chunk in raw_value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            admin_ids.append(int(chunk))
        except ValueError:
            print(f"Warning: could not parse admin id '{chunk}'.")
    return admin_ids


def _parse_optional_chat_id(raw_value: str | None, env_name: str) -> int | None:
    if not raw_value:
        return None
    raw_value = raw_value.strip()
    if not raw_value:
        return None
    try:
        return int(raw_value)
    except ValueError:
        print(f"Warning: {env_name} is not a valid Telegram chat id.")
        return None


class Config:
    class Bot:
        API_ID = os.getenv("API_ID")
        API_HASH = os.getenv("API_HASH")
        BOT_TOKEN = os.getenv("BOT_TOKEN")
        BOT_USERNAME = os.getenv("BOT_USERNAME", "")

        ADMIN_STRING = os.getenv("ADMIN_ID", "0")
        ADMIN_IDS = _parse_admin_ids(ADMIN_STRING)

        MONGO_URI = os.getenv("MONGO_URI")
        MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "PyroHosterBot")

        FILEBROWSER_API_URL = os.getenv("FILEBROWSER_API_URL", "http://localhost:8080/api")
        FILEBROWSER_ADMIN_USER = os.getenv("FILEBROWSER_ADMIN_USER", "admin")
        FILEBROWSER_ADMIN_PASS = os.getenv("FILEBROWSER_ADMIN_PASS", "sunning112233#")
        FILEBROWSER_PUBLIC_URL = os.getenv("FILEBROWSER_PUBLIC_URL", "http://localhost:8080")
        PORT = os.getenv("PORT", "8080")

        REQUIRE_APPROVAL = os.getenv("REQUIRE_APPROVAL", "True").lower() == "true"
        HOST_APPROVAL_CHAT_ID = _parse_optional_chat_id(
            os.getenv("HOST_APPROVAL_CHAT_ID"),
            "HOST_APPROVAL_CHAT_ID",
        )

        OWNER_URL = os.getenv("OWNER_URL", "https://t.me/Cybrion")
        CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/The_Hacking_Zone")
        USERS_PAGE_SIZE = int(os.getenv("USERS_PAGE_SIZE", "10"))
        KEY_PREFIX = os.getenv("KEY_PREFIX", "HZ")

    class Premium:
        PLANS = {
            "1": {
                "name": "Additional Project Slot",
                "description": "Adds 1 project slot with 1GB RAM for 30 days.",
                "stars": 100,
                "duration_days": 30,
                "ram_mb": 1024,
            }
        }
        CURRENCY = "XTR"

    class User:
        FREE_USER_PROJECT_QUOTA = 1
        FREE_USER_RAM_MB = 512
        DEFAULT_PREMIUM_RAM_MB = 1024
        MAX_PROJECT_FILE_SIZE = 50 * 1024 * 1024
        RAM_CHOICES_MB = [256, 512, 1024, 1536, 2048, 3072, 4096]


config = Config()


if not all([config.Bot.API_ID, config.Bot.API_HASH, config.Bot.BOT_TOKEN, config.Bot.MONGO_URI]):
    raise RuntimeError(
        "CRITICAL ERROR: API_ID, API_HASH, BOT_TOKEN, and MONGO_URI must be set in your .env file."
    )

if not config.Bot.ADMIN_IDS:
    print("WARNING: No ADMIN_ID found. The admin panel will be inaccessible.")
