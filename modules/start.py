from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from config import config
from utils.database import add_user, find_user_by_id, get_global_settings, get_user_projects
from utils.keyboard_helper import back_home_keyboard, start_keyboard
from utils.theme import neon_kv, neon_panel, neon_text
from utils.ui import edit_message_panel


async def _build_home_text(user, user_doc: dict | None):
    settings = await get_global_settings()
    projects = await get_user_projects(user.id)

    total_slots = (user_doc or {}).get("project_quota", config.User.FREE_USER_PROJECT_QUOTA)
    premium_ram = (user_doc or {}).get(
        "premium_slot_ram_mb",
        config.Premium.PLANS["1"]["ram_mb"],
    )
    hosting_approval = "ON" if settings.get("require_approval", config.Bot.REQUIRE_APPROVAL) else "OFF"

    display_name = user.first_name or "User"
    username = f"@{user.username}" if user.username else "No username"
    lines = [
        neon_text("🌌", "Welcome to the Neon Hosting Panel"),
        neon_kv("Name", display_name),
        neon_kv("User ID", str(user.id)),
        neon_kv("Username", username),
        neon_kv("Bots", str(len(projects))),
        neon_kv("Slots", str(total_slots)),
        neon_kv("Premium RAM", f"{premium_ram} MB"),
        neon_kv("Hosting Approval", hosting_approval),
        neon_text("⚡", "Use the glowing menu below to deploy, manage, and upgrade your bots."),
    ]
    return neon_panel("RGB NEON HOST", lines)


def _build_profile_text(user_doc: dict | None, project_count: int):
    user_doc = user_doc or {}
    total_slots = user_doc.get("project_quota", config.User.FREE_USER_PROJECT_QUOTA)
    used_slots = project_count
    free_slots = config.User.FREE_USER_PROJECT_QUOTA
    premium_slots = max(0, total_slots - free_slots)
    redeemed_keys = user_doc.get("keys_redeemed", 0)
    premium_ram = user_doc.get("premium_slot_ram_mb", config.Premium.PLANS["1"]["ram_mb"])

    return neon_panel(
        "USER PROFILE",
        [
            neon_kv("Total Slots", str(total_slots)),
            neon_kv("Used Slots", str(used_slots)),
            neon_kv("Free Slots", str(free_slots)),
            neon_kv("Premium Slots", str(premium_slots)),
            neon_kv("Redeemed Keys", str(redeemed_keys)),
            neon_kv("Premium RAM Limit", f"{premium_ram} MB"),
        ],
        footer="Slots control how many projects you can host at once.",
    )


def _build_help_text():
    return neon_panel(
        "HELP DESK",
        [
            neon_text("🚀", "Deploy Bot: starts the upload wizard for a new project."),
            neon_text("📦", "My Bots: opens the project list and management panel."),
            neon_text("🎟", "Redeem Key: unlocks extra slots or RAM from an admin key."),
            neon_text("💎", "Buy Slot: opens the Telegram Stars purchase flow."),
            neon_text("🧾", "Approved bots can be started, stopped, restarted, and monitored."),
        ],
        footer="Main commands: /start, /newproject, /myproject, /redeem, /admin",
    )


async def _get_profile_photo_id(client: Client, user_id: int) -> str | None:
    try:
        async for photo in client.get_chat_photos(user_id, limit=1):
            return photo.file_id
    except Exception:
        return None
    return None


@Client.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    await add_user(message.from_user.id, message.from_user.username)
    user_doc = await find_user_by_id(message.from_user.id)
    caption = await _build_home_text(message.from_user, user_doc)
    keyboard = start_keyboard()
    profile_photo_id = await _get_profile_photo_id(client, message.from_user.id)

    if profile_photo_id:
        await message.reply_photo(
            photo=profile_photo_id,
            caption=caption,
            reply_markup=keyboard,
        )
        return

    await message.reply_text(
        text=caption,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


@Client.on_callback_query(filters.regex(r"^menu_home$"))
async def home_menu_callback(client: Client, query: CallbackQuery):
    await add_user(query.from_user.id, query.from_user.username)
    user_doc = await find_user_by_id(query.from_user.id)
    text = await _build_home_text(query.from_user, user_doc)
    await edit_message_panel(query.message, text, reply_markup=start_keyboard())
    await query.answer("🏠 Home panel refreshed.")


@Client.on_callback_query(filters.regex(r"^menu_profile$"))
async def menu_profile_callback(client: Client, query: CallbackQuery):
    user_doc = await find_user_by_id(query.from_user.id)
    projects = await get_user_projects(query.from_user.id)
    await edit_message_panel(
        query.message,
        _build_profile_text(user_doc, len(projects)),
        reply_markup=back_home_keyboard(),
    )
    await query.answer("👤 Profile loaded.")


@Client.on_callback_query(filters.regex(r"^menu_help$"))
async def menu_help_callback(client: Client, query: CallbackQuery):
    await edit_message_panel(
        query.message,
        _build_help_text(),
        reply_markup=back_home_keyboard(),
    )
    await query.answer("🆘 Help opened.")


@Client.on_callback_query(filters.regex(r"^request_approval$"))
async def request_approval_legacy_callback(client: Client, callback_query: CallbackQuery):
    await callback_query.answer(
        "Account approval is no longer required. Upload a project instead.",
        show_alert=True,
    )
    await edit_message_panel(
        callback_query.message,
        neon_panel(
            "HOSTING APPROVAL ONLY",
            [
                neon_text("✅", "User approval has been removed."),
                neon_text("📨", "New projects are sent for hosting approval when required."),
                neon_text("🚀", "Use Deploy Bot to upload your next project."),
            ],
        ),
        reply_markup=start_keyboard(),
    )
