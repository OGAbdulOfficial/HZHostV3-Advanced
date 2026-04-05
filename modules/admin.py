import asyncio
import secrets
import string

from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import CallbackQuery, Message

from config import config
from utils.database import (
    create_redeem_key,
    find_user_by_id,
    get_active_projects_count,
    get_all_projects_count,
    get_all_users,
    get_banned_users_count,
    get_first_locked_project,
    get_global_settings,
    get_last_premium_project,
    get_premium_users_count,
    get_project_by_id,
    get_recent_keys,
    get_user_projects,
    get_users_page,
    increase_user_project_quota,
    set_user_ban_status,
    update_global_setting,
    update_project_approval,
    update_project_config,
)
from utils.deployment_helper import stop_project
from utils.hosting_approval import get_project_approval_status
from utils.keyboard_helper import (
    admin_back_to_main_keyboard,
    admin_forcesub_keyboard,
    admin_keys_keyboard,
    admin_main_keyboard,
    admin_settings_keyboard,
    admin_stats_keyboard,
    admin_user_detail_keyboard,
    admin_user_management_keyboard,
    admin_users_list_keyboard,
)
from utils.theme import fmt_dt, neon_kv, neon_panel, neon_text
from utils.ui import edit_message_panel


ADMIN_IDS = config.Bot.ADMIN_IDS


def _generate_key_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    chunks = ["".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3)]
    return f"{config.Bot.KEY_PREFIX}-" + "-".join(chunks)


def _project_summary(project: dict) -> str:
    running = "🟢" if project.get("execution_info", {}).get("is_running") else "🔴"
    tier = "💎" if project.get("is_premium") else "🆓"
    approval = get_project_approval_status(project).upper()
    locked = " 🔒" if project.get("is_locked") else ""
    return f"{running} {tier} `{project['name']}` [{approval}]{locked}"


async def _show_admin_main(message):
    settings = await get_global_settings()
    await edit_message_panel(
        message,
        neon_panel(
            "ADMIN CONTROL",
            [
                neon_text("🌈", "Neon admin panel loaded."),
                neon_text("⚙️", "Manage users, hosting keys, maintenance, and broadcasts."),
                neon_kv(
                    "Maintenance",
                    "ON" if settings.get("maintenance_mode", False) else "OFF",
                ),
            ],
        ),
        reply_markup=admin_main_keyboard(settings.get("maintenance_mode", False)),
    )


async def _show_user_details(query: CallbackQuery, user_id: int):
    user = await find_user_by_id(user_id)
    if not user:
        await edit_message_panel(
            query.message,
            neon_panel(
                "USER NOT FOUND",
                [neon_text("❌", f"No user record found for `{user_id}`.")],
            ),
            reply_markup=admin_user_management_keyboard(),
        )
        return

    projects = await get_user_projects(user_id)
    current_quota = user.get("project_quota", config.User.FREE_USER_PROJECT_QUOTA)
    joined_at = user.get("joined_at")

    lines = [
        neon_kv("User ID", str(user_id)),
        neon_kv("Username", user.get("username") or "N/A"),
        neon_kv("Joined", fmt_dt(joined_at)),
        neon_kv("Quota", str(current_quota)),
        neon_kv("Premium RAM", f"{user.get('premium_slot_ram_mb', config.Premium.PLANS['1']['ram_mb'])} MB"),
        neon_kv("Keys Redeemed", str(user.get("keys_redeemed", 0))),
        neon_kv("Banned", "YES" if user.get("is_banned", False) else "NO"),
        neon_text("📦", "Projects:"),
    ]
    if projects:
        lines.extend(_project_summary(project) for project in projects[:10])
        if len(projects) > 10:
            lines.append(f"... and {len(projects) - 10} more")
    else:
        lines.append("No projects found.")

    await edit_message_panel(
        query.message,
        neon_panel("USER PROFILE", lines),
        reply_markup=admin_user_detail_keyboard(user_id, current_quota, user.get("is_banned", False)),
    )


async def _show_users_page(query: CallbackQuery, page: int):
    users, total = await get_users_page(page, config.Bot.USERS_PAGE_SIZE)
    lines = [
        neon_kv("Page", f"{page + 1}"),
        neon_kv("Total Users", str(total)),
        neon_text("🧑‍🤝‍🧑", "Recent users on this page:"),
    ]
    for user in users:
        username = user.get("username") or "N/A"
        banned = "🚫" if user.get("is_banned", False) else "✅"
        lines.append(
            f"{banned} `{user['_id']}`  `@{username}`"
            if username != "N/A"
            else f"{banned} `{user['_id']}`"
        )

    await edit_message_panel(
        query.message,
        neon_panel("USERS LIST", lines),
        reply_markup=admin_users_list_keyboard(page, total, config.Bot.USERS_PAGE_SIZE),
    )


async def _show_recent_keys(query: CallbackQuery):
    keys = await get_recent_keys()
    lines = [neon_text("🎟", "Latest generated keys:")]
    if not keys:
        lines.append("No keys have been generated yet.")
    else:
        for key in keys:
            lines.append(
                f"`{key['code']}` | slots={key.get('slots', 0)} | ram={key.get('ram_mb', 0)}MB | "
                f"status={key.get('status', 'active')} | exp={fmt_dt(key.get('expires_at'))}"
            )

    await edit_message_panel(
        query.message,
        neon_panel("KEY VAULT", lines),
        reply_markup=admin_keys_keyboard(),
    )


async def _run_broadcast(client: Client, query: CallbackQuery, broadcast_msg: Message):
    users = await get_all_users()
    total_users = len(users)
    status_msg = query.message
    await edit_message_panel(
        status_msg,
        neon_panel(
            "BROADCAST STARTED",
            [neon_text("📢", f"Sending message to {total_users} users...")],
        ),
    )

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
    await edit_message_panel(
        status_msg,
        neon_panel(
            "BROADCAST COMPLETE",
            [
                neon_kv("Sent", str(sent)),
                neon_kv("Failed", str(failed)),
                neon_kv("Time", f"{elapsed}s"),
            ],
        ),
        reply_markup=admin_back_to_main_keyboard(),
    )


@Client.on_message(filters.command("admin") & filters.user(ADMIN_IDS))
async def admin_panel(client: Client, message: Message):
    await _show_admin_main(message)


@Client.on_callback_query(filters.regex(r"^admin_"))
async def admin_callback_router(client: Client, query: CallbackQuery):
    if query.from_user.id not in ADMIN_IDS:
        return await query.answer("Access denied.", show_alert=True)

    data = query.data.split("_")
    action = data[1]

    if action == "main":
        await _show_admin_main(query.message)
        return await query.answer("👑 Admin home")

    if action == "stats":
        settings = await get_global_settings()
        total_users = await get_all_users(count_only=True)
        total_bots = await get_all_projects_count()
        active_bots = await get_active_projects_count()
        premium_users = await get_premium_users_count()
        banned_users = await get_banned_users_count()
        text = neon_panel(
            "LIVE STATS",
            [
                neon_kv("Total Users", str(total_users)),
                neon_kv("Total Bots", str(total_bots)),
                neon_kv("Active Bots", str(active_bots)),
                neon_kv("Premium Users", str(premium_users)),
                neon_kv("Banned Users", str(banned_users)),
                neon_kv("Maintenance", "ON" if settings.get("maintenance_mode", False) else "OFF"),
            ],
        )
        await edit_message_panel(query.message, text, reply_markup=admin_stats_keyboard())
        return await query.answer("📊 Stats updated")

    if action == "users":
        await edit_message_panel(
            query.message,
            neon_panel(
                "USER TOOLS",
                [
                    neon_text("🔎", "Find a user by Telegram ID."),
                    neon_text("🧑‍🤝‍🧑", "Open paginated users list."),
                    neon_text("🚫", "Ban or unban directly from here."),
                ],
            ),
            reply_markup=admin_user_management_keyboard(),
        )
        return await query.answer("👥 User tools opened")

    if action == "userslist":
        page = int(data[2]) if len(data) > 2 else 0
        await _show_users_page(query, page)
        return await query.answer("🧑‍🤝‍🧑 Users list loaded")

    if action == "finduser":
        try:
            ask_msg = await client.ask(query.from_user.id, "Send the user ID.", timeout=60)
            await _show_user_details(query, int(ask_msg.text.strip()))
            return await query.answer("🔎 User loaded")
        except ValueError:
            return await query.answer("Invalid user ID.", show_alert=True)
        except asyncio.TimeoutError:
            return await query.answer("Timed out.", show_alert=True)

    if action == "viewuser":
        await _show_user_details(query, int(data[2]))
        return await query.answer("🔄 User refreshed")

    if action == "banprompt":
        try:
            ask_msg = await client.ask(
                query.from_user.id,
                "Send `user_id | reason` to ban a user.\nExample: `123456789 | spam uploads`",
                timeout=120,
            )
            raw = ask_msg.text.strip()
            user_id_raw, reason = raw.split("|", 1) if "|" in raw else (raw, "Banned by admin.")
            user_id = int(user_id_raw.strip())
            await set_user_ban_status(user_id, True, banned_by=query.from_user.id, reason=reason.strip())
            await edit_message_panel(
                query.message,
                neon_panel(
                    "USER BANNED",
                    [
                        neon_kv("User ID", str(user_id)),
                        neon_text("🚫", reason.strip()),
                    ],
                ),
                reply_markup=admin_back_to_main_keyboard(),
            )
            try:
                await client.send_message(user_id, "🚫 You have been banned from using this hosting bot.")
            except Exception:
                pass
            return await query.answer("User banned", show_alert=True)
        except ValueError:
            return await query.answer("Invalid format.", show_alert=True)
        except asyncio.TimeoutError:
            return await query.answer("Timed out.", show_alert=True)

    if action == "unbanprompt":
        try:
            ask_msg = await client.ask(query.from_user.id, "Send the user ID to unban.", timeout=60)
            user_id = int(ask_msg.text.strip())
            await set_user_ban_status(user_id, False)
            await edit_message_panel(
                query.message,
                neon_panel(
                    "USER UNBANNED",
                    [neon_kv("User ID", str(user_id)), neon_text("✅", "Access has been restored.")],
                ),
                reply_markup=admin_back_to_main_keyboard(),
            )
            try:
                await client.send_message(user_id, "✅ You have been unbanned and can use the hosting bot again.")
            except Exception:
                pass
            return await query.answer("User unbanned", show_alert=True)
        except ValueError:
            return await query.answer("Invalid user ID.", show_alert=True)
        except asyncio.TimeoutError:
            return await query.answer("Timed out.", show_alert=True)

    if action == "ban" and len(data) > 2:
        user_id = int(data[2])
        await set_user_ban_status(user_id, True, banned_by=query.from_user.id, reason="Banned by admin.")
        await _show_user_details(query, user_id)
        try:
            await client.send_message(user_id, "🚫 You have been banned from using this hosting bot.")
        except Exception:
            pass
        return await query.answer("User banned", show_alert=True)

    if action == "unban" and len(data) > 2:
        user_id = int(data[2])
        await set_user_ban_status(user_id, False)
        await _show_user_details(query, user_id)
        try:
            await client.send_message(user_id, "✅ You have been unbanned.")
        except Exception:
            pass
        return await query.answer("User unbanned", show_alert=True)

    if action == "changequota":
        mod_type = data[2]
        user_id = int(data[3])
        user = await find_user_by_id(user_id)
        if not user:
            return await query.answer("User not found.", show_alert=True)

        current_quota = user.get("project_quota", config.User.FREE_USER_PROJECT_QUOTA)
        if mod_type == "add":
            new_quota = await increase_user_project_quota(user_id, 1)
            project_to_unlock = await get_first_locked_project(user_id)
            if project_to_unlock:
                from datetime import datetime, timedelta

                project_id_str = str(project_to_unlock["_id"])
                new_expiry = datetime.utcnow() + timedelta(days=30)
                await update_project_config(project_id_str, {"is_locked": False, "expiry_date": new_expiry})
            await _show_user_details(query, user_id)
            return await query.answer(f"Slot added. New quota: {new_quota}", show_alert=True)

        if current_quota <= config.User.FREE_USER_PROJECT_QUOTA:
            return await query.answer("Cannot reduce below free quota.", show_alert=True)

        new_quota = await increase_user_project_quota(user_id, -1)
        project_to_lock = await get_last_premium_project(user_id)
        if project_to_lock:
            project_id_str = str(project_to_lock["_id"])
            await stop_project(project_id_str)
            await update_project_config(project_id_str, {"is_locked": True})
        await _show_user_details(query, user_id)
        return await query.answer(f"Slot removed. New quota: {new_quota}", show_alert=True)

    if action == "keys":
        await edit_message_panel(
            query.message,
            neon_panel(
                "KEY VAULT",
                [
                    neon_text("🎟", "Generate and manage premium slot keys."),
                    neon_text("🧠", "Keys can grant slots and RAM upgrades."),
                ],
            ),
            reply_markup=admin_keys_keyboard(),
        )
        return await query.answer("🎟 Key vault opened")

    if action == "genkey":
        try:
            slots_msg = await client.ask(query.from_user.id, "How many slots should the key grant?", timeout=60)
            slots = int(slots_msg.text.strip())
            ram_msg = await client.ask(query.from_user.id, "Send the RAM amount in MB for this key.", timeout=60)
            ram_mb = int(ram_msg.text.strip())
            days_msg = await client.ask(
                query.from_user.id,
                "Send validity in days, or `0` for no expiry.",
                timeout=60,
            )
            valid_days = int(days_msg.text.strip())
            code = _generate_key_code()
            key_doc = await create_redeem_key(
                code=code,
                slots=slots,
                ram_mb=ram_mb,
                created_by=query.from_user.id,
                valid_days=valid_days,
            )
            await edit_message_panel(
                query.message,
                neon_panel(
                    "KEY GENERATED",
                    [
                        neon_kv("Code", key_doc["code"]),
                        neon_kv("Slots", str(key_doc["slots"])),
                        neon_kv("RAM", f"{key_doc['ram_mb']} MB"),
                        neon_kv("Expires", fmt_dt(key_doc.get("expires_at"))),
                    ],
                    footer="Share this code with the user to unlock hosting benefits.",
                ),
                reply_markup=admin_keys_keyboard(),
            )
            return await query.answer("Key generated", show_alert=True)
        except ValueError:
            return await query.answer("Invalid numeric input.", show_alert=True)
        except asyncio.TimeoutError:
            return await query.answer("Timed out.", show_alert=True)

    if action == "listkeys":
        await _show_recent_keys(query)
        return await query.answer("Keys list updated")

    if action == "settings":
        settings = await get_global_settings()
        ram = settings.get("free_user_ram_mb", config.User.FREE_USER_RAM_MB)
        require_approval = settings.get("require_approval", config.Bot.REQUIRE_APPROVAL)
        maintenance_mode = settings.get("maintenance_mode", False)
        await edit_message_panel(
            query.message,
            neon_panel(
                "GLOBAL SETTINGS",
                [
                    neon_kv("Free RAM", f"{ram} MB"),
                    neon_kv("Hosting Approval", "ON" if require_approval else "OFF"),
                    neon_kv("Maintenance", "ON" if maintenance_mode else "OFF"),
                ],
            ),
            reply_markup=admin_settings_keyboard(ram, require_approval, maintenance_mode),
        )
        return await query.answer("⚙️ Settings opened")

    if action == "setfreeram":
        try:
            ask_ram = await client.ask(
                query.from_user.id,
                "Enter the new RAM amount in MB for free users.",
                timeout=60,
            )
            new_ram = int(ask_ram.text)
            if not (128 <= new_ram <= 4096):
                raise ValueError
            await update_global_setting("free_user_ram_mb", new_ram)
            settings = await get_global_settings()
            await edit_message_panel(
                query.message,
                neon_panel(
                    "FREE RAM UPDATED",
                    [neon_kv("Free User RAM", f"{new_ram} MB")],
                ),
                reply_markup=admin_settings_keyboard(
                    new_ram,
                    settings.get("require_approval", config.Bot.REQUIRE_APPROVAL),
                    settings.get("maintenance_mode", False),
                ),
            )
            return await query.answer("Free RAM updated", show_alert=True)
        except (ValueError, asyncio.TimeoutError):
            return await query.answer("Invalid RAM value or timeout.", show_alert=True)

    if action == "toggleapproval":
        settings = await get_global_settings()
        current_status = settings.get("require_approval", config.Bot.REQUIRE_APPROVAL)
        new_status = not current_status
        await update_global_setting("require_approval", new_status)
        settings = await get_global_settings()
        await edit_message_panel(
            query.message,
            neon_panel(
                "HOSTING APPROVAL TOGGLED",
                [neon_kv("State", "ON" if new_status else "OFF")],
            ),
            reply_markup=admin_settings_keyboard(
                settings.get("free_user_ram_mb", config.User.FREE_USER_RAM_MB),
                new_status,
                settings.get("maintenance_mode", False),
            ),
        )
        return await query.answer("Hosting approval toggled", show_alert=True)

    if action == "togglemaintenance":
        settings = await get_global_settings()
        current_status = settings.get("maintenance_mode", False)
        new_status = not current_status
        await update_global_setting("maintenance_mode", new_status)
        if new_status:
            await update_global_setting("maintenance_reason", "Admin enabled maintenance mode.")
        await _show_admin_main(query.message)
        return await query.answer(
            "Maintenance enabled" if new_status else "Maintenance disabled",
            show_alert=True,
        )

    if action == "forcesub":
        settings = await get_global_settings()
        pub_ch = settings.get("force_public_channel", "").strip()
        pub_link = settings.get("force_public_link", "").strip()
        priv_link = settings.get("force_private_link", "").strip()
        await edit_message_panel(
            query.message,
            neon_panel(
                "FORCE SUBSCRIBE",
                [
                    neon_kv("Public Channel", pub_ch or "Not Set"),
                    neon_kv("Public Link", "Saved" if pub_link else "Missing"),
                    neon_kv("Private Link", "Saved" if priv_link else "Missing"),
                ],
            ),
            reply_markup=admin_forcesub_keyboard(pub_ch, pub_link, priv_link),
        )
        return await query.answer("📢 Force-sub settings")

    if action == "fsubinfo":
        settings = await get_global_settings()
        pub_ch = settings.get("force_public_channel", "").strip() or "Not Set"
        pub_link = settings.get("force_public_link", "").strip() or "Missing"
        return await query.answer(
            f"Public channel: {pub_ch}\nPublic link: {pub_link}",
            show_alert=True,
        )

    if action == "setfspubch":
        try:
            msg = await client.ask(query.from_user.id, "Send the public channel ID or @username.", timeout=60)
            await update_global_setting("force_public_channel", msg.text.strip())
            query.data = "admin_forcesub"
            return await admin_callback_router(client, query)
        except asyncio.TimeoutError:
            return await query.answer("Timed out.", show_alert=True)

    if action == "setfspublink":
        try:
            msg = await client.ask(query.from_user.id, "Send the public invite link.", timeout=60)
            await update_global_setting("force_public_link", msg.text.strip())
            query.data = "admin_forcesub"
            return await admin_callback_router(client, query)
        except asyncio.TimeoutError:
            return await query.answer("Timed out.", show_alert=True)

    if action == "setfsprivlink":
        try:
            msg = await client.ask(query.from_user.id, "Send the private invite link.", timeout=60)
            await update_global_setting("force_private_link", msg.text.strip())
            query.data = "admin_forcesub"
            return await admin_callback_router(client, query)
        except asyncio.TimeoutError:
            return await query.answer("Timed out.", show_alert=True)

    if action == "clearfspub":
        await update_global_setting("force_public_channel", "")
        await update_global_setting("force_public_link", "")
        query.data = "admin_forcesub"
        return await admin_callback_router(client, query)

    if action == "clearfspriv":
        await update_global_setting("force_private_link", "")
        query.data = "admin_forcesub"
        return await admin_callback_router(client, query)

    if action == "broadcast":
        try:
            prompt = await client.ask(query.from_user.id, "Send the broadcast message or /cancel.", timeout=300)
            if prompt.text.strip().lower() == "/cancel":
                return await query.answer("Broadcast cancelled.", show_alert=True)

            confirm = await client.ask(query.from_user.id, "Send `yes` to confirm.", timeout=60)
            if confirm.text.strip().lower() != "yes":
                return await query.answer("Broadcast cancelled.", show_alert=True)

            await _run_broadcast(client, query, prompt)
            return await query.answer("Broadcast sent", show_alert=True)
        except asyncio.TimeoutError:
            return await query.answer("Broadcast timed out.", show_alert=True)

    if action == "hostapprove":
        project_id = data[2]
        project = await get_project_by_id(project_id)
        if not project:
            return await query.answer("Project not found.", show_alert=True)

        await update_project_approval(project_id, "approved", reviewed_by=query.from_user.id)
        await edit_message_panel(
            query.message,
            neon_panel(
                "HOSTING APPROVED",
                [
                    neon_kv("Project", project["name"]),
                    neon_kv("Owner", str(project["user_id"])),
                ],
            ),
            reply_markup=None,
        )
        try:
            await client.send_message(
                project["user_id"],
                f"✅ Your project `{project['name']}` has been approved for hosting.",
            )
        except Exception:
            pass
        return await query.answer("Hosting approved", show_alert=True)

    if action == "hostreject":
        project_id = data[2]
        project = await get_project_by_id(project_id)
        if not project:
            return await query.answer("Project not found.", show_alert=True)

        await stop_project(project_id)
        await update_project_approval(project_id, "rejected", reason="Rejected by admin.")
        await edit_message_panel(
            query.message,
            neon_panel(
                "HOSTING REJECTED",
                [
                    neon_kv("Project", project["name"]),
                    neon_text("❌", "Project was rejected and stopped if it was running."),
                ],
            ),
            reply_markup=None,
        )
        try:
            await client.send_message(
                project["user_id"],
                f"❌ Your project `{project['name']}` was rejected for hosting.",
            )
        except Exception:
            pass
        return await query.answer("Hosting rejected", show_alert=True)

    if action in {"approve", "reject"}:
        await edit_message_panel(
            query.message,
            neon_panel(
                "FLOW UPDATED",
                [
                    neon_text("ℹ️", "User approval has been removed."),
                    neon_text("📨", "Hosting approval is now handled per project."),
                ],
            ),
        )
        return await query.answer("Legacy approval removed", show_alert=True)

    await query.answer("Unknown admin action.", show_alert=True)
