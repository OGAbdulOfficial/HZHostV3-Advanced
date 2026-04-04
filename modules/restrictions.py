from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from utils.database import get_global_settings
from utils.filters import is_subscribed
from utils.keyboard_helper import force_sub_required_keyboard


FSUB_EXEMPT_CALLBACKS = filters.regex(r"^(fsub_verify|noop|request_approval)$")


@Client.on_message(~is_subscribed & filters.private & ~filters.command("start"), group=-2)
async def force_sub_message_gate(client: Client, message: Message):
    settings = await get_global_settings()
    pub_link = settings.get("force_public_link", "").strip()
    priv_link = settings.get("force_private_link", "").strip()

    await message.reply_text(
        "Access restricted.\n\n"
        "You must join the required channel(s) before using this bot.\n\n"
        "Click below to join, then press I've Joined.",
        reply_markup=force_sub_required_keyboard(pub_link or None, priv_link or None),
    )
    message.stop_propagation()


@Client.on_callback_query(~is_subscribed & ~FSUB_EXEMPT_CALLBACKS, group=-2)
async def force_sub_callback_gate(client: Client, callback_query: CallbackQuery):
    settings = await get_global_settings()
    pub_link = settings.get("force_public_link", "").strip()
    priv_link = settings.get("force_private_link", "").strip()

    await callback_query.answer("You must join our channel first.", show_alert=True)
    try:
        await callback_query.message.edit_text(
            "Access restricted.\n\n"
            "You must join the required channel(s) before using this bot.\n\n"
            "Click below to join, then press I've Joined.",
            reply_markup=force_sub_required_keyboard(pub_link or None, priv_link or None),
        )
    except Exception:
        pass
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
            "You still have not joined the public channel. Please join and try again.",
            show_alert=True,
        )

    await callback_query.message.edit_text(
        "Verification successful.\n\nYou can now use the bot. Send /start to continue."
    )
