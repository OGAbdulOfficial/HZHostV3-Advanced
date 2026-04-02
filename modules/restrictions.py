# modules/restrictions.py

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from utils.filters import is_approved

@Client.on_message(~is_approved & filters.private & ~filters.command("start"), group=-1)
async def restricted_message(client: Client, message: Message):
    """
    Catch-all handler for unapproved users sending messages (commands).
    Does NOT affect the /start command.
    """
    await message.reply_text(
        "🚫 **Access Denied!**\n\n"
        "Your account must be approved by an administrator before you can use this bot's features.\n\n"
        "Please use /start to apply for approval."
    )
    message.stop_propagation()

@Client.on_callback_query(~is_approved & ~filters.regex("^request_approval$"), group=-1)
async def restricted_callback(client: Client, callback_query: CallbackQuery):
    """
    Catch-all handler for unapproved users clicking buttons.
    Does NOT affect the 'Apply for Approval' button.
    """
    await callback_query.answer(
        "🚫 Access Denied!\n\nYour account is pending approval. Please wait for an administrator to review your request.",
        show_alert=True
    )
    callback_query.stop_propagation()
