import asyncio
import os

from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified
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


def _hosting_approval_block_reason(project: dict) -> str | None:
    approval_status = get_project_approval_status(project)
    if approval_status == "pending":
        return "This project is waiting for hosting approval."
    if approval_status == "rejected":
        reason = project.get("approval_reason") or "No reason provided."
        return f"This project was rejected for hosting. Reason: {reason}"
    return None


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
    keyboard = project_deployment_keyboard(project)
    text = f"Deployment menu for `{project['name']}`\n\n{status_text}"
    try:
        await query.message.edit_text(text, reply_markup=keyboard)
    except MessageNotModified:
        pass
    await query.answer()


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

    await query.answer("Installing dependencies...")
    try:
        await query.message.edit_text(
            "Setting up the virtual environment and installing dependencies from `requirements.txt`..."
        )
    except MessageNotModified:
        pass

    success, message = await install_project_dependencies(project_id, project)
    if success:
        await query.message.edit_text(f"Installation complete.\n\n{message}")
        return

    log_file_path = os.path.join(project["path"], "installation_error.log")
    try:
        with open(log_file_path, "w", encoding="utf-8") as file_obj:
            file_obj.write(message)

        await client.send_document(
            chat_id=query.from_user.id,
            document=log_file_path,
            caption="Installation failed. See the attached log file.",
        )
        await query.message.delete()
    except Exception:
        await query.message.edit_text(f"Installation failed.\n\n```\n{message[:3000]}\n```")

    keyboard = project_deployment_keyboard(project)
    await client.send_message(
        query.from_user.id,
        "Fix your `requirements.txt` and try again.",
        reply_markup=keyboard,
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

    await query.answer("Starting project...")
    try:
        success, message = await start_project(project_id, project)
        await query.message.reply_text(
            f"Project `{project['name']}` started.\n`{message}`"
            if success
            else f"Failed to start project `{project['name']}`.\nReason: {message}"
        )
    except Exception as error:
        await query.message.reply_text(f"An error occurred: {error}")


@Client.on_callback_query(filters.regex(r"^stop_proj_"))
async def stop_project_callback(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[-1]
    project = await get_project_by_id(project_id)

    if not project or project["user_id"] != query.from_user.id:
        return await query.answer("Access denied.", show_alert=True)

    await query.answer("Stopping project...")
    success, message = await stop_project(project_id)
    await query.message.reply_text(
        f"Project `{project['name']}` stopped.\n`{message}`"
        if success
        else f"Failed to stop project `{project['name']}`.\nReason: {message}"
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

    await query.answer("Restarting project...")
    success, message = await restart_project(project_id, project)
    await query.message.reply_text(
        f"Project `{project['name']}` restarted."
        if success
        else f"Failed to restart project `{project['name']}`.\nReason: {message}"
    )


@Client.on_callback_query(filters.regex(r"^logs_proj_"))
async def logs_project_callback(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[-1]
    project = await get_project_by_id(project_id)

    if not project or project["user_id"] != query.from_user.id:
        return await query.answer("Access denied.", show_alert=True)

    if project.get("is_locked", False):
        return await query.answer("Project is locked. Renew it first.", show_alert=True)

    await query.answer("Fetching logs...")
    log_file_path = await get_project_logs(project_id)
    if os.path.exists(log_file_path) and os.path.getsize(log_file_path) > 0:
        await client.send_document(
            chat_id=query.from_user.id,
            document=log_file_path,
            caption=f"Logs for `{project['name']}`.",
        )
    else:
        await query.message.reply_text("No logs found for this project yet.")


@Client.on_callback_query(filters.regex(r"^status_proj_|usage_proj_"))
async def status_or_usage_callback(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[-1]
    project = await get_project_by_id(project_id)

    if not project or project["user_id"] != query.from_user.id:
        return await query.answer("Access denied.", show_alert=True)

    action = query.data.split("_")[0]
    if action == "status":
        await query.answer("Fetching status...")
        status_text = await get_project_status(project_id, project, detailed=True)
        keyboard = project_deployment_keyboard(project)
        await query.message.edit_text(status_text, reply_markup=keyboard)
    elif action == "usage":
        await query.answer("Checking usage...")
        usage_info = await get_project_usage(project_id)
        await query.message.edit_text(usage_info)


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
            text=(
                f"Enter the new run command for `{project['name']}`.\n"
                f"Current: `{project.get('run_command', 'python3 main.py')}`\n\n"
                "Example: `python3 bot.py`"
            ),
            timeout=120,
        )
        new_command = command_msg.text.strip()
        if new_command:
            await update_project_config(project_id, {"run_command": new_command})
            await command_msg.reply_text(f"Run command updated to: `{new_command}`")
        else:
            await command_msg.reply_text("Invalid command. Nothing changed.")
    except asyncio.TimeoutError:
        await query.message.reply_text("Cancelled due to timeout.")

    query.data = f"deployment_{project_id}"
    await deployment_menu_callback(client, query)


@Client.on_callback_query(filters.regex(r"^back_to_main_"))
async def back_to_main_menu(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[-1]
    project = await get_project_by_id(project_id)
    if not project or project["user_id"] != query.from_user.id:
        return await query.answer("Access denied.", show_alert=True)

    keyboard = project_management_keyboard(project)
    await query.message.edit_text(
        f"Manage your project `{project['name']}` below.",
        reply_markup=keyboard,
    )
    await query.answer()
