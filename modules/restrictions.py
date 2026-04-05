from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from utils.database import find_user_by_id, get_global_settings
from utils.filters import is_admin_user, is_subscribed
from utils.keyboard_helper import force_sub_required_keyboard, support_links_keyboard
from utils.theme import neon_panel, neon_text
from utils.ui import edit_message_panel


FSUB_EXEMPT_CALLBACKS = filters.regex(r"^(fsub_verify)$")


async def _is_maintenance_mode() -> tuple[bool, str]:
    settings = await get_global_settings()
    return settings.get("maintenance_mode", False), settings.get(
        "maintenance_reason",
        "Upgrading services",
    )


@Client.on_message(filters.private, group=-4)
async def banned_message_gate(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else None
    if is_admin_user(user_id):
        return

    user = await find_user_by_id(user_id)
    if not user or not user.get("is_banned", False):
        return

    text = neon_panel(
        "ACCESS BLOCKED",
        [
            neon_text("🚫", "Your access to this hosting bot has been blocked."),
            neon_text("📝", user.get("ban_reason") or "No reason was provided."),
        ],
        footer="Contact the owner if you think this was a mistake.",
    )
    await message.reply_text(text, reply_markup=support_links_keyboard())
    message.stop_propagation()


@Client.on_callback_query(group=-4)
async def banned_callback_gate(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id if callback_query.from_user else None
    if is_admin_user(user_id):
        return

    user = await find_user_by_id(user_id)
    if not user or not user.get("is_banned", False):
        return

    await callback_query.answer("🚫 You are banned from using this bot.", show_alert=True)
    await edit_message_panel(
        callback_query.message,
        neon_panel(
            "ACCESS BLOCKED",
            [
                neon_text("🚫", "Your account is banned from the hosting system."),
                neon_text("📝", user.get("ban_reason") or "No reason was provided."),
            ],
            footer="Only the owner can restore access.",
        ),
        reply_markup=support_links_keyboard(),
    )
    callback_query.stop_propagation()


@Client.on_message(filters.private, group=-3)
async def maintenance_message_gate(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else None
    if is_admin_user(user_id):
        return

    maintenance_mode, reason = await _is_maintenance_mode()
    if not maintenance_mode:
        return

    text = neon_panel(
        "BOT UNDER MAINTENANCE",
        [
            neon_text("⚠️", "Bot Under Maintenance"),
            neon_text("🛠", reason),
            neon_text("⏳", "Please try again later."),
        ],
        footer="Admin tools remain available for operators.",
    )
    await message.reply_text(text, reply_markup=support_links_keyboard())
    message.stop_propagation()


@Client.on_callback_query(group=-3)
async def maintenance_callback_gate(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id if callback_query.from_user else None
    if is_admin_user(user_id):
        return

    maintenance_mode, reason = await _is_maintenance_mode()
    if not maintenance_mode:
        return

    await callback_query.answer("⚠️ Bot Under Maintenance", show_alert=True)
    await edit_message_panel(
        callback_query.message,
        neon_panel(
            "BOT UNDER MAINTENANCE",
            [
                neon_text("⚠️", "Bot Under Maintenance"),
                neon_text("🛠", reason),
            ],
            footer="Please wait until service is restored.",
        ),
        reply_markup=support_links_keyboard(),
    )
    callback_query.stop_propagation()


@Client.on_message(~is_subscribed & filters.private & ~filters.command("start"), group=-2)
async def force_sub_message_gate(client: Client, message: Message):
    settings = await get_global_settings()
    pub_link = settings.get("force_public_link", "").strip()
    priv_link = settings.get("force_private_link", "").strip()

    await message.reply_text(
        neon_panel(
            "JOIN REQUIRED CHANNELS",
            [
                neon_text("📢", "Join the required channels before using the bot."),
                neon_text("✨", "After joining, tap the verification button below."),
            ],
        ),
        reply_markup=force_sub_required_keyboard(pub_link or None, priv_link or None),
    )
    message.stop_propagation()


@Client.on_callback_query(~is_subscribed & ~FSUB_EXEMPT_CALLBACKS, group=-2)
async def force_sub_callback_gate(client: Client, callback_query: CallbackQuery):
    settings = await get_global_settings()
    pub_link = settings.get("force_public_link", "").strip()
    priv_link = settings.get("force_private_link", "").strip()

    await callback_query.answer("📢 Join the required channel first.", show_alert=True)
    await edit_message_panel(
        callback_query.message,
        neon_panel(
            "JOIN REQUIRED CHANNELS",
            [
                neon_text("📢", "Join the required channels before using the bot."),
                neon_text("✨", "After joining, tap the verification button below."),
            ],
        ),
        reply_markup=force_sub_required_keyboard(pub_link or None, priv_link or None),
    )
    callback_query.stop_propagation()


@Client.on_callback_query(filters.regex(r"^fsub_verify$"))
async def fsub_verify_callback(client: Client, callback_query: CallbackQuery):
    settings = await get_global_settings()
    pub_ch = settings.get("force_public_channel", "").strip()
    user_id = callback_query.from_user.id
    passed = True

    if pub_ch:
        try:
            from pyrogram.errors import UserNotParticipant

            member = await client.get_chat_member(pub_ch, user_id)
            if member.status.value in ("left", "banned", "kicked"):
                passed = False
        except UserNotParticipant:
            passed = False
        except Exception:
            pass

    if not passed:
        return await callback_query.answer(
            "❌ Public channel verification failed. Join first, then retry.",
            show_alert=True,
        )

    await edit_message_panel(
        callback_query.message,
        neon_panel(
            "VERIFICATION COMPLETE",
            [
                neon_text("✅", "Channel verification successful."),
                neon_text("🏠", "Send /start to open the home panel."),
            ],
        ),
        reply_markup=support_links_keyboard(),
    )
