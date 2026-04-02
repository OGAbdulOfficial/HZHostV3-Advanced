# utils/filters.py

from pyrogram import filters
from pyrogram.errors import UserNotParticipant, ChatAdminRequired, ChannelPrivate
from config import config
from utils.database import find_user_by_id, get_global_settings


# ──────────────────────────────────────────────────────────
# is_approved filter
# ──────────────────────────────────────────────────────────

async def is_approved_func(_, client, update):
    """Returns True if the user is approved, or if approval is globally disabled."""
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


# ──────────────────────────────────────────────────────────
# is_subscribed filter  (Force Public Channel only)
# ──────────────────────────────────────────────────────────
# NOTE:
#   - For a public channel you CAN check membership via get_chat_member.
#   - For a private channel Telegram does NOT allow bots to check membership
#     without admin rights inside that channel; we only show the join button.
#     The user's self-verification happens when they press /start or the
#     "I've Joined" button again — we re-evaluate at that point.

async def is_subscribed_func(_, client, update):
    """
    Returns True if:
      • No Force-Sub public channel is configured, OR
      • The user is an admin, OR
      • The user IS a member of the configured public channel.
    """
    settings = await get_global_settings()
    pub_ch = settings.get("force_public_channel", "").strip()

    # Nothing configured → pass
    if not pub_ch:
        return True

    user_id = update.from_user.id if hasattr(update, "from_user") and update.from_user else None
    if not user_id:
        return False

    # Admins are never blocked
    if user_id in config.Bot.ADMIN_IDS:
        return True

    try:
        member = await client.get_chat_member(pub_ch, user_id)
        # member.status can be: owner, administrator, member, restricted, left, banned
        return member.status.value not in ("left", "banned", "kicked")
    except UserNotParticipant:
        return False
    except (ChatAdminRequired, ChannelPrivate):
        # Bot lacks perms or channel is private — fail-open so bot stays usable
        return True
    except Exception:
        return True  # fail-open on any other error

is_subscribed = filters.create(is_subscribed_func)
