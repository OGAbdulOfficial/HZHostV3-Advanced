# utils/filters.py

from pyrogram import filters
from pyrogram.types import Message, CallbackQuery
from config import config
from utils.database import find_user_by_id, get_global_settings

async def is_approved_func(_, client, update):
    """Filter function that returns True if the user is approved, or if approval is disabled."""
    # Check global settings instead of only config
    settings = await get_global_settings()
    if not settings.get("require_approval", config.Bot.REQUIRE_APPROVAL):
        return True
    
    user_id = update.from_user.id if hasattr(update, "from_user") and update.from_user else None
    if not user_id:
        return False

    # Admins are always approved
    if user_id in config.Bot.ADMIN_IDS:
        return True

    user_doc = await find_user_by_id(user_id)
    if not user_doc:
        return False
    
    return user_doc.get("is_approved", False)

is_approved = filters.create(is_approved_func)
