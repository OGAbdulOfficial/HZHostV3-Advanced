from pyrogram import filters
from pyrogram.errors import ChannelPrivate, ChatAdminRequired, UserNotParticipant

from config import config
from utils.database import find_user_by_id, get_global_settings


def is_admin_user(user_id: int | None) -> bool:
    return bool(user_id and user_id in config.Bot.ADMIN_IDS)


async def is_approved_func(_, client, update):
    settings = await get_global_settings()
    if not settings.get("require_approval", config.Bot.REQUIRE_APPROVAL):
        return True

    user_id = update.from_user.id if hasattr(update, "from_user") and update.from_user else None
    if not user_id:
        return False
    if is_admin_user(user_id):
        return True

    user_doc = await find_user_by_id(user_id)
    if not user_doc:
        return False
    return user_doc.get("is_approved", False)


is_approved = filters.create(is_approved_func)


async def is_banned_func(_, client, update):
    user_id = update.from_user.id if hasattr(update, "from_user") and update.from_user else None
    if not user_id or is_admin_user(user_id):
        return False

    user_doc = await find_user_by_id(user_id)
    return bool(user_doc and user_doc.get("is_banned", False))


is_banned = filters.create(is_banned_func)


async def is_subscribed_func(_, client, update):
    settings = await get_global_settings()
    pub_ch = settings.get("force_public_channel", "").strip()

    if not pub_ch:
        return True

    user_id = update.from_user.id if hasattr(update, "from_user") and update.from_user else None
    if not user_id:
        return False
    if is_admin_user(user_id):
        return True

    try:
        member = await client.get_chat_member(pub_ch, user_id)
        return member.status.value not in ("left", "banned", "kicked")
    except UserNotParticipant:
        return False
    except (ChatAdminRequired, ChannelPrivate):
        return True
    except Exception:
        return True


is_subscribed = filters.create(is_subscribed_func)
