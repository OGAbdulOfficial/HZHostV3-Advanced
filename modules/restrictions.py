# modules/restrictions.py

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery

from utils.filters import is_approved, is_subscribed
from utils.database import get_global_settings
from utils.keyboard_helper import force_sub_required_keyboard

# ═══════════════════════════════════════════════════════════
# FORCE SUBSCRIBE GATE  (runs BEFORE approval check)
# ═══════════════════════════════════════════════════════════

FSUB_EXEMPT_CALLBACKS = filters.regex(
    r"^(request_approval|fsub_verify|noop)$"
)

@Client.on_message(
    ~is_subscribed & filters.private & ~filters.command("start"),
    group=-2   # highest priority group
)
async def force_sub_message_gate(client: Client, message: Message):
    """Block messages from users who haven't joined the required channel(s)."""
    settings = await get_global_settings()
    pub_link  = settings.get("force_public_link",  "").strip()
    priv_link = settings.get("force_private_link", "").strip()

    await message.reply_text(
        "🚫 **Access Restricted!**\n\n"
        "You must join our channel(s) before using this bot.\n\n"
        "👇 **Click below to join, then press ✅ I've Joined.**",
        reply_markup=force_sub_required_keyboard(pub_link or None, priv_link or None)
    )
    message.stop_propagation()


@Client.on_callback_query(
    ~is_subscribed & ~FSUB_EXEMPT_CALLBACKS,
    group=-2
)
async def force_sub_callback_gate(client: Client, callback_query: CallbackQuery):
    """Block button presses from users who haven't joined the required channel(s)."""
    settings = await get_global_settings()
    pub_link  = settings.get("force_public_link",  "").strip()
    priv_link = settings.get("force_private_link", "").strip()

    await callback_query.answer(
        "🚫 You must join our channel first!",
        show_alert=True
    )
    # Also update the message with join buttons so they can act
    try:
        await callback_query.message.edit_text(
            "🚫 **Access Restricted!**\n\n"
            "You must join our channel(s) before using this bot.\n\n"
            "👇 **Click below to join, then press ✅ I've Joined.**",
            reply_markup=force_sub_required_keyboard(pub_link or None, priv_link or None)
        )
    except Exception:
        pass
    callback_query.stop_propagation()


@Client.on_callback_query(filters.regex(r"^fsub_verify$"))
async def fsub_verify_callback(client: Client, callback_query: CallbackQuery):
    """
    User clicked 'I've Joined'.
    - Re-check the public channel (is_subscribed filter).
    - For private channels we trust the user and let them through.
    """
    settings = await get_global_settings()
    pub_ch    = settings.get("force_public_channel", "").strip()
    pub_link  = settings.get("force_public_link",    "").strip()
    priv_link = settings.get("force_private_link",   "").strip()

    user_id = callback_query.from_user.id
    passed  = True

    if pub_ch:
        try:
            from pyrogram.errors import UserNotParticipant
            member = await client.get_chat_member(pub_ch, user_id)
            if member.status.value in ("left", "banned", "kicked"):
                passed = False
        except UserNotParticipant:
            passed = False
        except Exception:
            pass  # fail-open

    if not passed:
        return await callback_query.answer(
            "❌ You still haven't joined the public channel. Please join and try again.",
            show_alert=True
        )

    # All good — tell them to send /start
    await callback_query.message.edit_text(
        "✅ **Verification successful!**\n\n"
        "You may now use the bot. Send /start to begin."
    )


# ═══════════════════════════════════════════════════════════
# APPROVAL GATE  (runs AFTER force-sub check)
# ═══════════════════════════════════════════════════════════

@Client.on_message(
    ~is_approved & filters.private & ~filters.command("start"),
    group=-1
)
async def restricted_message(client: Client, message: Message):
    """Catch-all for unapproved users sending messages."""
    await message.reply_text(
        "🚫 **Access Denied!**\n\n"
        "Your account must be approved by an administrator before you can use this bot's features.\n\n"
        "Please use /start to apply for approval."
    )
    message.stop_propagation()


@Client.on_callback_query(
    ~is_approved & ~filters.regex("^request_approval$"),
    group=-1
)
async def restricted_callback(client: Client, callback_query: CallbackQuery):
    """Catch-all for unapproved users clicking buttons."""
    await callback_query.answer(
        "🚫 Access Denied!\n\nYour account is pending approval. Please wait for an administrator to review your request.",
        show_alert=True
    )
    callback_query.stop_propagation()
