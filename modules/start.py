from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import config
from utils.database import add_user, get_global_settings


start_keyboard = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("Owner", url="https://t.me/Cybrion"),
            InlineKeyboardButton("Channel", url="https://t.me/The_Hacking_Zone"),
        ],
        [
            InlineKeyboardButton("My Projects", callback_data="my_projects_list"),
            InlineKeyboardButton("Buy Slots", callback_data="buy_project_slot"),
        ],
    ]
)


@Client.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.username

    await add_user(user_id, username)

    settings = await get_global_settings()
    hosting_approval_enabled = settings.get("require_approval", config.Bot.REQUIRE_APPROVAL)

    approval_note = (
        "\nNew projects require admin hosting approval before deployment.\n"
        if hosting_approval_enabled
        else "\nHosting approval is currently disabled.\n"
    )

    start_text = (
        "**Welcome to the Python Project Hoster!**\n\n"
        "Deploy and manage your Python projects directly from Telegram.\n\n"
        "**What you can do:**\n"
        "- Upload a `.zip` or `.py` project\n"
        "- Manage files from the built-in file manager\n"
        "- Start, stop, restart, and check logs for approved projects\n"
        f"{approval_note}\n"
        "**Project Tiers:**\n"
        f"- Free: {config.User.FREE_USER_PROJECT_QUOTA} slot with {config.User.FREE_USER_RAM_MB}MB RAM\n"
        f"- Premium: {config.Premium.PLANS['1']['stars']} Stars for 1 extra slot with {config.Premium.PLANS['1']['ram_mb']}MB RAM\n\n"
        "Use /newproject to upload your first application."
    )

    await message.reply_text(
        text=start_text,
        reply_markup=start_keyboard,
        disable_web_page_preview=True,
    )


@Client.on_callback_query(filters.regex("^request_approval$"))
async def request_approval_legacy_callback(client: Client, callback_query):
    await callback_query.answer(
        "Account approval is no longer required. Upload a project instead.",
        show_alert=True,
    )
    try:
        await callback_query.message.edit_text(
            "Account approval has been removed.\n\n"
            "Use /newproject to upload your code. If hosting approval is enabled, "
            "your project will be sent to admins for review before deployment.",
            reply_markup=start_keyboard,
        )
    except Exception:
        pass
