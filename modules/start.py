# modules/start.py

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from config import config
from utils.database import add_user, find_user_by_id, get_global_settings

# In modules/start.py

# Define the keyboard layout
start_keyboard = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("👑 Owner", url="https://t.me/Cybrion"),
            InlineKeyboardButton("📢 Channel", url="https://t.me/The_Hacking_Zone")
        ],
        [
            InlineKeyboardButton("🚀 My Projects", callback_data="my_projects_list"),
            InlineKeyboardButton("⭐ Buy Slots", callback_data="buy_project_slot")
        ]
    ]
)

approval_keyboard = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("📝 Apply for Approval", callback_data="request_approval")
        ],
        [
            InlineKeyboardButton("👑 Owner", url="https://t.me/Cybrion")
        ]
    ]
)

@Client.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Add the user to the database
    await add_user(user_id, username)
    
    user_doc = await find_user_by_id(user_id)
    is_approved = user_doc.get("is_approved", False)
    
    settings = await get_global_settings()
    require_approval = settings.get("require_approval", config.Bot.REQUIRE_APPROVAL)

    if require_approval and not is_approved:
        unapproved_text = (
            "**👋 Welcome to the Python Project Hoster!**\n\n"
            "This bot is currently in **Restricted Mode**. To use our services, you must be approved by an administrator.\n\n"
            "**Why approval?**\n"
            "To prevent abuse and ensure high-quality service for all users.\n\n"
            "👇 **Apply below**"
        )
        await message.reply_text(unapproved_text, reply_markup=approval_keyboard)
        return

    # Updated start message to be more informative
    start_text = (
        "**👋 Welcome to the Python Project Hoster!**\n\n"
        "I'm your personal bot for securely deploying and managing your Python scripts and applications, right here from Telegram.\n\n"
        "**Key Features:**\n"
        "🚀 **Deploy Instantly:** Upload your code as a `.zip` or `.py` file.\n"
        "📂 **Easy Management:** Use the built-in web file manager to edit code live.\n"
        "🤖 **Full Control:** Start, stop, restart, and view logs for all your projects.\n\n"
        "**Project Tiers:**\n"
        f"🆓 **Free Tier:** You get **{config.User.FREE_USER_PROJECT_QUOTA} project slot** with **{config.User.FREE_USER_RAM_MB}MB RAM** to start.\n"
        f"⭐ **Premium Tier:** Need more power? Purchase additional slots for **{config.Premium.PLANS['1']['stars']} Stars**, each giving you **{config.Premium.PLANS['1']['ram_mb']}MB RAM** and renewing monthly.\n\n"
        "👇 **Get Started**\n"
        "Use **/newproject** to deploy your first application!"
    )
    
    await message.reply_text(
        text=start_text,
        reply_markup=start_keyboard,
        disable_web_page_preview=True
    )

@Client.on_callback_query(filters.regex("^request_approval$"))
async def request_approval_callback(client: Client, callback_query):
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or "No Username"
    first_name = callback_query.from_user.first_name
    
    user_doc = await find_user_by_id(user_id)
    if user_doc and user_doc.get("is_approved"):
        await callback_query.answer("You are already approved!", show_alert=True)
        return

    # Notify admins
    for admin_id in config.Bot.ADMIN_IDS:
        try:
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{user_id}"),
                        InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{user_id}")
                    ]
                ]
            )
            await client.send_message(
                chat_id=admin_id,
                text=(
                    "**🚀 New Approval Request!**\n\n"
                    f"**User ID:** `{user_id}`\n"
                    f"**First Name:** {first_name}\n"
                    f"**Username:** @{username}\n\n"
                    "Do you want to approve this user?"
                ),
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

    await callback_query.edit_message_text(
        "**✅ Application Sent!**\n\n"
        "Your request for approval has been sent to the administrators. You'll be notified once a decision is made.\n\n"
        "Please be patient.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👑 Owner", url="https://t.me/Cybrion")]])
    )