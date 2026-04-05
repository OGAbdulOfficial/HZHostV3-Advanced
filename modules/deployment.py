import asyncio
import os

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from utils.database import get_project_by_id, update_project_config
from utils.deployment_helper import (
    get_project_logs,
    get_project_status,
    get_project_usage,
    install_project_dependencies,
    restart_project,
    start_project,
    stop_project,
)
from utils.hosting_approval import get_project_approval_status
from utils.keyboard_helper import project_deployment_keyboard, project_management_keyboard
from utils.theme import neon_kv, neon_panel, neon_text
from utils.ui import edit_message_panel


def _hosting_approval_block_reason(project: dict) -> str | None:
    approval_status = get_project_approval_status(project)
    if approval_status == "pending":
        return "This project is waiting for hosting approval."
    if approval_status == "rejected":
        reason = project.get("approval_reason") or "No reason provided."
        return f"This project was rejected for hosting. Reason: {reason}"
    return None


def _deployment_panel_text(project: dict, status_text: str) -> str:
    return neon_panel(
        "DEPLOYMENT PANEL",
        [
            neon_kv("Project", project["name"]),
            neon_kv("Run Command", project.get("run_command", "python3 main.py")),
            neon_kv("RAM", f"{project.get('resource_limits', {}).get('ram', 0)} MB"),
            neon_text("📡", status_text),
        ],
    )


@Client.on_callback_query(filters.regex(r"^deployment_"))
async def deployment_menu_callback(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[1]
    project = await get_project_by_id(project_id)

    if not project or project["user_id"] != query.from_user.id:
        return await query.answer("Project not found or access denied.", show_alert=True)
    if project.get("is_locked", False):
        return await query.answer("Project is locked. Renew it to open deployment.", show_alert=True)

    block_reason = _hosting_approval_block_reason(project)
    if block_reason:
        return await query.answer(block_reason, show_alert=True)

    status_text = await get_project_status(project_id, project)
    await edit_message_panel(
        query.message,
        _deployment_panel_text(project, status_text),
        reply_markup=project_deployment_keyboard(project),
    )
    await query.answer("⚙️ Deployment panel ready.")


@Client.on_callback_query(filters.regex(r"^install_proj_"))
async def install_deps_callback(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[-1]
    project = await get_project_by_id(project_id)
    if not project or project["user_id"] != query.from_user.id:
        return await query.answer("Access denied.", show_alert=True)
    if project.get("is_locked", False):
        return await query.answer("Project is locked. Renew it first.", show_alert=True)

    block_reason = _hosting_approval_block_reason(project)
    if block_reason:
        return await query.answer(block_reason, show_alert=True)

    await query.answer("📦 Installing dependencies...")
    await edit_message_panel(
        query.message,
        neon_panel(
            "INSTALLING DEPENDENCIES",
            [
                neon_text("🧪", "Creating virtual environment if needed."),
                neon_text("📦", "Installing packages from `requirements.txt`."),
            ],
        ),
    )

    success, result_message = await install_project_dependencies(project_id, project)
    if success:
        await edit_message_panel(
            query.message,
            neon_panel(
                "DEPENDENCIES INSTALLED",
                [
                    neon_kv("Project", project["name"]),
                    neon_text("✅", result_message),
                ],
            ),
            reply_markup=project_deployment_keyboard(project),
        )
        return

    log_file_path = os.path.join(project["path"], "installation_error.log")
    try:
        with open(log_file_path, "w", encoding="utf-8") as file_obj:
            file_obj.write(result_message)

        await client.send_document(
            chat_id=query.from_user.id,
            document=log_file_path,
            caption="❌ Dependency install failed. Review the attached log.",
        )
    except Exception:
        pass

    await edit_message_panel(
        query.message,
        neon_panel(
            "INSTALL FAILED",
            [
                neon_text("❌", "Dependency installation failed."),
                neon_text("🧠", "Review the log file, fix requirements, and retry."),
            ],
        ),
        reply_markup=project_deployment_keyboard(project),
    )


@Client.on_callback_query(filters.regex(r"^start_proj_"))
async def start_project_callback(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[-1]
    project = await get_project_by_id(project_id)

    if not project or project["user_id"] != query.from_user.id:
        return await query.answer("Access denied.", show_alert=True)
    if project.get("is_locked", False):
        return await query.answer("Project is locked. Renew it first.", show_alert=True)

    block_reason = _hosting_approval_block_reason(project)
    if block_reason:
        return await query.answer(block_reason, show_alert=True)

    await query.answer("▶️ Starting project...")
    success, result_message = await start_project(project_id, project)
    refreshed_project = await get_project_by_id(project_id)

    await edit_message_panel(
        query.message,
        neon_panel(
            "START RESULT",
            [
                neon_kv("Project", project["name"]),
                neon_text("✅" if success else "❌", result_message),
            ],
        ),
        reply_markup=project_deployment_keyboard(refreshed_project or project),
    )


@Client.on_callback_query(filters.regex(r"^stop_proj_"))
async def stop_project_callback(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[-1]
    project = await get_project_by_id(project_id)

    if not project or project["user_id"] != query.from_user.id:
        return await query.answer("Access denied.", show_alert=True)

    await query.answer("⏹ Stopping project...")
    success, result_message = await stop_project(project_id)
    refreshed_project = await get_project_by_id(project_id) or project

    await edit_message_panel(
        query.message,
        neon_panel(
            "STOP RESULT",
            [
                neon_kv("Project", project["name"]),
                neon_text("✅" if success else "❌", result_message),
            ],
        ),
        reply_markup=project_deployment_keyboard(refreshed_project),
    )


@Client.on_callback_query(filters.regex(r"^restart_proj_"))
async def restart_project_callback(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[-1]
    project = await get_project_by_id(project_id)

    if not project or project["user_id"] != query.from_user.id:
        return await query.answer("Access denied.", show_alert=True)
    if project.get("is_locked", False):
        return await query.answer("Project is locked. Renew it first.", show_alert=True)

    block_reason = _hosting_approval_block_reason(project)
    if block_reason:
        return await query.answer(block_reason, show_alert=True)

    await query.answer("🔄 Restarting project...")
    success, result_message = await restart_project(project_id, project)
    refreshed_project = await get_project_by_id(project_id) or project

    await edit_message_panel(
        query.message,
        neon_panel(
            "RESTART RESULT",
            [
                neon_kv("Project", project["name"]),
                neon_text("✅" if success else "❌", result_message),
            ],
        ),
        reply_markup=project_deployment_keyboard(refreshed_project),
    )


@Client.on_callback_query(filters.regex(r"^logs_proj_"))
async def logs_project_callback(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[-1]
    project = await get_project_by_id(project_id)

    if not project or project["user_id"] != query.from_user.id:
        return await query.answer("Access denied.", show_alert=True)
    if project.get("is_locked", False):
        return await query.answer("Project is locked. Renew it first.", show_alert=True)

    await query.answer("📜 Fetching logs...")
    log_file_path = await get_project_logs(project_id)
    if os.path.exists(log_file_path) and os.path.getsize(log_file_path) > 0:
        await client.send_document(
            chat_id=query.from_user.id,
            document=log_file_path,
            caption=f"📜 Logs for `{project['name']}`.",
        )
        return

    await query.answer("No logs found yet.", show_alert=True)


@Client.on_callback_query(filters.regex(r"^status_proj_|usage_proj_"))
async def status_or_usage_callback(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[-1]
    project = await get_project_by_id(project_id)

    if not project or project["user_id"] != query.from_user.id:
        return await query.answer("Access denied.", show_alert=True)

    action = query.data.split("_")[0]
    if action == "status":
        await query.answer("📡 Fetching status...")
        status_text = await get_project_status(project_id, project, detailed=True)
        await edit_message_panel(
            query.message,
            neon_panel(
                "BOT STATUS",
                [
                    neon_kv("Project", project["name"]),
                    neon_text("📡", status_text),
                ],
            ),
            reply_markup=project_deployment_keyboard(project),
        )
    elif action == "usage":
        await query.answer("🧠 Reading usage...")
        usage_info = await get_project_usage(project_id)
        await edit_message_panel(
            query.message,
            neon_panel(
                "RESOURCE USAGE",
                [
                    neon_kv("Project", project["name"]),
                    neon_text("📊", usage_info),
                ],
            ),
            reply_markup=project_deployment_keyboard(project),
        )


@Client.on_callback_query(filters.regex(r"^editcmd_proj_"))
async def edit_cmd_callback(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[-1]
    project = await get_project_by_id(project_id)
    if not project or project["user_id"] != query.from_user.id:
        return await query.answer("Access denied.", show_alert=True)
    if project.get("is_locked", False):
        return await query.answer("Project is locked. Renew it first.", show_alert=True)

    try:
        command_msg = await client.ask(
            chat_id=query.from_user.id,
            text=neon_panel(
                "EDIT RUN COMMAND",
                [
                    neon_kv("Project", project["name"]),
                    neon_kv("Current", project.get("run_command", "python3 main.py")),
                    neon_text("✍️", "Example: `python3 bot.py`"),
                ],
            ),
            timeout=120,
        )
        new_command = command_msg.text.strip()
        if new_command:
            await update_project_config(project_id, {"run_command": new_command})
            project = await get_project_by_id(project_id)
            await edit_message_panel(
                query.message,
                neon_panel(
                    "RUN COMMAND UPDATED",
                    [
                        neon_kv("Project", project["name"]),
                        neon_kv("Command", new_command),
                    ],
                ),
                reply_markup=project_deployment_keyboard(project),
            )
        else:
            await query.answer("Invalid command.", show_alert=True)
    except asyncio.TimeoutError:
        await query.answer("Command edit timed out.", show_alert=True)


@Client.on_callback_query(filters.regex(r"^back_to_main_"))
async def back_to_main_menu(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[-1]
    project = await get_project_by_id(project_id)
    if not project or project["user_id"] != query.from_user.id:
        return await query.answer("Access denied.", show_alert=True)

    await edit_message_panel(
        query.message,
        neon_panel(
            "BOT CONTROL",
            [
                neon_kv("Project", project["name"]),
                neon_text("⚡", "Returning to the main control panel."),
            ],
        ),
        reply_markup=project_management_keyboard(project),
    )
    await query.answer()
