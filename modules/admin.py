import asyncio

from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import CallbackQuery, Message

from config import config
from utils.database import (
    find_user_by_id,
    get_active_projects_count,
    get_all_premium_projects_count,
    get_all_projects_count,
    get_all_users,
    get_first_locked_project,
    get_global_settings,
    get_last_premium_project,
    get_premium_users_count,
    get_project_by_id,
    get_user_projects,
    increase_user_project_quota,
    update_global_setting,
    update_project_approval,
    update_project_config,
)
from utils.deployment_helper import stop_project
from utils.hosting_approval import get_project_approval_status
from utils.keyboard_helper import (
    admin_back_to_main_keyboard,
    admin_forcesub_keyboard,
    admin_main_keyboard,
    admin_settings_keyboard,
    admin_stats_keyboard,
    admin_user_detail_keyboard,
    admin_user_management_keyboard,
)


ADMIN_IDS = config.Bot.ADMIN_IDS


@Client.on_callback_query(filters.regex(r"^noop$"))
async def noop_callback(client: Client, query: CallbackQuery):
    await query.answer()


@Client.on_message(filters.command("admin") & filters.user(ADMIN_IDS))
async def admin_panel(client: Client, message: Message):
    await message.reply_text(
        "Admin Panel\n\nChoose an option below.",
        reply_markup=admin_main_keyboard(),
    )


async def _edit_review_message(message: Message, text: str):
    try:
        if message.document:
            await message.edit_caption(caption=text, reply_markup=None)
        else:
            await message.edit_text(text, reply_markup=None)
    except Exception:
        try:
            await message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass


def _project_summary(project: dict) -> str:
    running = "RUN" if project.get("execution_info", {}).get("is_running") else "STOP"
    tier = "PREM" if project.get("is_premium") else "FREE"
    approval = get_project_approval_status(project).upper()
    locked = " LOCKED" if project.get("is_locked") else ""
    return f"- {project['name']} [{tier}] [{approval}] [{running}]{locked}"


@Client.on_callback_query(filters.regex(r"^admin_"))
async def admin_callback_router(client: Client, query: CallbackQuery):
    if query.from_user.id not in ADMIN_IDS:
        return await query.answer("Access denied.", show_alert=True)

    data = query.data.split("_")
    action = data[1]

    if action == "main":
        await query.message.edit_text("Admin Panel\n\nWelcome.", reply_markup=admin_main_keyboard())

    elif action == "stats":
        total_users = await get_all_users(count_only=True)
        premium_users = await get_premium_users_count()
        total_projects = await get_all_projects_count()
        premium_projects = await get_all_premium_projects_count()
        active_projects = await get_active_projects_count()
        text = (
            "**Bot Statistics**\n\n"
            f"Total Users: `{total_users}`\n"
            f"Premium Users: `{premium_users}`\n"
            f"Total Projects: `{total_projects}`\n"
            f"Premium Projects: `{premium_projects}`\n"
            f"Active Projects: `{active_projects}`"
        )
        await query.message.edit_text(text, reply_markup=admin_stats_keyboard())

    elif action == "users":
        await query.message.edit_text(
            "User Management\n\nSend a user's Telegram ID to inspect their account.",
            reply_markup=admin_user_management_keyboard(),
        )

    elif action == "finduser":
        try:
            ask_msg = await client.ask(query.from_user.id, "Send the user ID.", timeout=60)
            await _show_user_details(client, query, int(ask_msg.text))
        except ValueError:
            await query.message.reply_text("Invalid ID.")
        except asyncio.TimeoutError:
            await query.message.reply_text("Timed out.")

    elif action == "viewuser":
        await _show_user_details(client, query, int(data[2]))

    elif action == "changequota":
        mod_type = data[2]
        user_id = int(data[3])
        user = await find_user_by_id(user_id)
        current_quota = user.get("project_quota", config.User.FREE_USER_PROJECT_QUOTA)

        if mod_type == "add":
            new_quota = await increase_user_project_quota(user_id, 1)
            project_to_unlock = await get_first_locked_project(user_id)
            if project_to_unlock:
                from datetime import datetime, timedelta

                project_id_str = str(project_to_unlock["_id"])
                new_expiry = datetime.utcnow() + timedelta(days=30)
                await update_project_config(
                    project_id_str,
                    {"is_locked": False, "expiry_date": new_expiry},
                )
                await query.answer(
                    f"Quota added. Project '{project_to_unlock['name']}' unlocked for 30 days.",
                    show_alert=True,
                )
                await client.send_message(
                    user_id,
                    f"An admin adjusted your quota. Project `{project_to_unlock['name']}` was unlocked.",
                )
            else:
                await query.answer(f"Quota increased to {new_quota}.", show_alert=True)

        elif mod_type == "remove":
            if current_quota <= config.User.FREE_USER_PROJECT_QUOTA:
                return await query.answer(
                    "Cannot reduce quota below the free tier limit.",
                    show_alert=True,
                )

            new_quota = await increase_user_project_quota(user_id, -1)
            project_to_lock = await get_last_premium_project(user_id)
            if project_to_lock:
                project_id_str = str(project_to_lock["_id"])
                await stop_project(project_id_str)
                await update_project_config(project_id_str, {"is_locked": True})
                await query.answer(
                    f"Quota reduced. Project '{project_to_lock['name']}' was locked.",
                    show_alert=True,
                )
                await client.send_message(
                    user_id,
                    f"An admin adjusted your quota. Project `{project_to_lock['name']}` is now locked.",
                )
            else:
                await query.answer(f"Quota reduced to {new_quota}.", show_alert=True)

        await _show_user_details(client, query, user_id)

    elif action == "settings":
        settings = await get_global_settings()
        ram = settings.get("free_user_ram_mb", config.User.FREE_USER_RAM_MB)
        require_approval = settings.get("require_approval", config.Bot.REQUIRE_APPROVAL)
        await query.message.edit_text(
            "Global Settings\n\nManage bot-wide configuration here.",
            reply_markup=admin_settings_keyboard(ram, require_approval),
        )

    elif action == "setfreeram":
        try:
            ask_ram = await client.ask(
                query.from_user.id,
                "Enter the new RAM amount in MB for free users.",
                timeout=60,
            )
            new_ram = int(ask_ram.text)
            if not (50 <= new_ram <= 1024):
                raise ValueError("RAM must be between 50 and 1024 MB.")
            await update_global_setting("free_user_ram_mb", new_ram)
            await query.answer(f"Free user RAM set to {new_ram} MB.", show_alert=True)
        except (ValueError, asyncio.TimeoutError) as error:
            await query.message.reply_text(f"Operation failed: {error}")
        query.data = "admin_settings"
        await admin_callback_router(client, query)

    elif action == "toggleapproval":
        settings = await get_global_settings()
        current_status = settings.get("require_approval", config.Bot.REQUIRE_APPROVAL)
        new_status = not current_status
        await update_global_setting("require_approval", new_status)
        await query.answer(
            f"Hosting approval {'enabled' if new_status else 'disabled'}.",
            show_alert=True,
        )
        query.data = "admin_settings"
        await admin_callback_router(client, query)

    elif action == "forcesub":
        settings = await get_global_settings()
        pub_ch = settings.get("force_public_channel", "").strip()
        pub_link = settings.get("force_public_link", "").strip()
        priv_link = settings.get("force_private_link", "").strip()
        await query.message.edit_text(
            "Force Subscribe Settings\n\n"
            "Public channels can be verified by the bot. Private channels only show an invite link.",
            reply_markup=admin_forcesub_keyboard(pub_ch, pub_link, priv_link),
        )

    elif action == "setfspubch":
        try:
            msg = await client.ask(
                query.from_user.id,
                "Send the public channel ID or @username to verify.",
                timeout=60,
            )
            await update_global_setting("force_public_channel", msg.text.strip())
            await query.answer("Public channel saved.", show_alert=True)
        except asyncio.TimeoutError:
            await query.message.reply_text("Timed out.")
        query.data = "admin_forcesub"
        await admin_callback_router(client, query)

    elif action == "setfspublink":
        try:
            msg = await client.ask(
                query.from_user.id,
                "Send the public invite link users should open.",
                timeout=60,
            )
            await update_global_setting("force_public_link", msg.text.strip())
            await query.answer("Public invite link saved.", show_alert=True)
        except asyncio.TimeoutError:
            await query.message.reply_text("Timed out.")
        query.data = "admin_forcesub"
        await admin_callback_router(client, query)

    elif action == "setfsprivlink":
        try:
            msg = await client.ask(
                query.from_user.id,
                "Send the private invite link.",
                timeout=60,
            )
            await update_global_setting("force_private_link", msg.text.strip())
            await query.answer("Private invite link saved.", show_alert=True)
        except asyncio.TimeoutError:
            await query.message.reply_text("Timed out.")
        query.data = "admin_forcesub"
        await admin_callback_router(client, query)

    elif action == "clearfspub":
        await update_global_setting("force_public_channel", "")
        await update_global_setting("force_public_link", "")
        await query.answer("Public force-sub cleared.", show_alert=True)
        query.data = "admin_forcesub"
        await admin_callback_router(client, query)

    elif action == "clearfspriv":
        await update_global_setting("force_private_link", "")
        await query.answer("Private force-sub cleared.", show_alert=True)
        query.data = "admin_forcesub"
        await admin_callback_router(client, query)

    elif action == "broadcast":
        try:
            prompt = await client.ask(
                query.from_user.id,
                "Send the message to broadcast or /cancel.",
                timeout=300,
            )
            if prompt.text == "/cancel":
                return await prompt.reply_text(
                    "Broadcast cancelled.",
                    reply_markup=admin_main_keyboard(),
                )

            confirm = await client.ask(
                query.from_user.id,
                "Send `yes` to confirm the broadcast.",
                timeout=60,
            )
            if confirm.text.lower() != "yes":
                return await confirm.reply_text(
                    "Broadcast cancelled.",
                    reply_markup=admin_main_keyboard(),
                )

            await _run_broadcast(client, query, prompt)
        except asyncio.TimeoutError:
            await query.message.reply_text(
                "Timed out. Broadcast cancelled.",
                reply_markup=admin_main_keyboard(),
            )

    elif action == "hostapprove":
        project_id = data[2]
        project = await get_project_by_id(project_id)
        if not project:
            return await query.answer("Project not found.", show_alert=True)

        await update_project_approval(project_id, "approved", reviewed_by=query.from_user.id)
        await _edit_review_message(
            query.message,
            f"Hosting approved for project `{project['name']}` ({project_id}).",
        )
        try:
            await client.send_message(
                project["user_id"],
                f"Your project `{project['name']}` has been approved for hosting. You can deploy it now.",
            )
        except Exception:
            pass

    elif action == "hostreject":
        project_id = data[2]
        project = await get_project_by_id(project_id)
        if not project:
            return await query.answer("Project not found.", show_alert=True)

        await stop_project(project_id)
        await update_project_approval(
            project_id,
            "rejected",
            reason="Rejected by an admin.",
        )
        await _edit_review_message(
            query.message,
            f"Hosting rejected for project `{project['name']}` ({project_id}).",
        )
        try:
            await client.send_message(
                project["user_id"],
                f"Your project `{project['name']}` was rejected for hosting. "
                "Update it and send it for approval again.",
            )
        except Exception:
            pass

    elif action in {"approve", "reject"}:
        await _edit_review_message(
            query.message,
            "User approval has been removed. Hosting approval is now project-based.",
        )

    await query.answer()


async def _show_user_details(client: Client, query: CallbackQuery, user_id: int):
    user = await find_user_by_id(user_id)
    if not user:
        return await query.message.edit_text(
            f"User `{user_id}` not found.",
            reply_markup=admin_user_management_keyboard(),
        )

    projects = await get_user_projects(user_id)
    project_list = "\n".join(_project_summary(project) for project in projects) or "No projects found."

    current_quota = user.get("project_quota", config.User.FREE_USER_PROJECT_QUOTA)
    joined_at = user.get("joined_at")
    joined_str = joined_at.strftime("%Y-%m-%d") if joined_at else "N/A"

    text = (
        f"**User Details: `{user_id}`**\n\n"
        f"Username: `@{user.get('username', 'N/A')}`\n"
        f"Joined: `{joined_str}`\n"
        f"Project Quota: `{current_quota}`\n\n"
        f"Projects:\n{project_list}"
    )

    await query.message.edit_text(
        text,
        reply_markup=admin_user_detail_keyboard(user_id, current_quota, True),
    )


async def _run_broadcast(client: Client, query: CallbackQuery, broadcast_msg: Message):
    users = await get_all_users()
    total_users = len(users)
    status_msg = await query.message.edit_text(f"Starting broadcast to `{total_users}` users...")

    sent = 0
    failed = 0
    start_time = asyncio.get_event_loop().time()

    for user in users:
        try:
            await broadcast_msg.copy(user["_id"])
            sent += 1
            await asyncio.sleep(0.05)
        except FloodWait as error:
            await asyncio.sleep(error.value)
            await broadcast_msg.copy(user["_id"])
            sent += 1
        except Exception:
            failed += 1

    elapsed = int(asyncio.get_event_loop().time() - start_time)
    await status_msg.edit_text(
        f"Broadcast complete.\n\nSent: `{sent}`\nFailed: `{failed}`\nTime: `{elapsed}`s.",
        reply_markup=admin_back_to_main_keyboard(),
    )
