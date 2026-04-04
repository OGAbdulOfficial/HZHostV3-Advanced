import os
import random
import shutil
import string
import zipfile
from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import config
from utils.database import (
    add_project,
    add_user,
    delete_project,
    find_user_by_id,
    get_global_settings,
    get_project_by_id,
    get_user_projects,
    update_project_approval,
    update_project_config,
)
from utils.deployment_helper import stop_project
from utils.file_manager import start_filebrowser_session, stop_filebrowser_session
from utils.hosting_approval import get_project_approval_status, send_project_for_hosting_review
from utils.keyboard_helper import (
    build_projects_keyboard,
    buy_project_slot_keyboard,
    project_hosting_review_keyboard,
    project_locked_keyboard,
    project_management_keyboard,
    user_stats_keyboard,
)


PROJECTS_BASE_DIR = os.path.join(os.getcwd(), "projects")
MAX_FILE_SIZE = config.User.MAX_PROJECT_FILE_SIZE

os.makedirs(PROJECTS_BASE_DIR, exist_ok=True)


def generate_password(length: int = 14) -> str:
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(length))


def _approval_view(project: dict, filebrowser_url: str | None = None) -> tuple[str, InlineKeyboardMarkup]:
    approval_status = get_project_approval_status(project)

    if project.get("is_locked", False):
        expiry_date = project.get("expiry_date")
        expiry_str = expiry_date.strftime("%Y-%m-%d %H:%M UTC") if expiry_date else "N/A"
        text = (
            f"Project `{project['name']}` is locked.\n\n"
            f"The premium subscription expired on {expiry_str}.\n"
            "Renew it to continue using this project."
        )
        return text, project_locked_keyboard(str(project["_id"]))

    if approval_status == "pending":
        requested_at = project.get("approval_requested_at")
        requested_str = requested_at.strftime("%Y-%m-%d %H:%M UTC") if requested_at else "just now"
        text = (
            f"Project `{project['name']}` is waiting for hosting approval.\n\n"
            f"Requested: {requested_str}\n"
            "You can still manage files, but deployment stays blocked until an admin approves it."
        )
        return text, project_hosting_review_keyboard(project, filebrowser_url=filebrowser_url)

    if approval_status == "rejected":
        reason = project.get("approval_reason") or "No reason was provided."
        text = (
            f"Project `{project['name']}` was rejected for hosting.\n\n"
            f"Reason: {reason}\n\n"
            "Update the files if needed, then send it for hosting approval again."
        )
        return text, project_hosting_review_keyboard(project, filebrowser_url=filebrowser_url)

    text = f"Manage your project `{project['name']}` below."
    return text, project_management_keyboard(project, filebrowser_url=filebrowser_url)


async def check_and_lock_expired_projects(user_id: int):
    projects = await get_user_projects(user_id)
    now = datetime.utcnow()
    updated_projects = []

    for project in projects:
        if (
            project.get("is_premium")
            and not project.get("is_locked")
            and project.get("expiry_date")
            and project["expiry_date"] < now
        ):
            await stop_project(str(project["_id"]))
            await update_project_config(str(project["_id"]), {"is_locked": True})
            project["is_locked"] = True
        updated_projects.append(project)

    return updated_projects


@Client.on_message(filters.command("newproject") & filters.private)
async def new_project_command(client: Client, message: Message):
    user_id = message.from_user.id
    user = await find_user_by_id(user_id)
    if not user:
        await add_user(user_id, message.from_user.username)
        user = await find_user_by_id(user_id)

    projects = await get_user_projects(user_id)
    current_project_count = len(projects)
    user_quota = user.get("project_quota", config.User.FREE_USER_PROJECT_QUOTA)

    if current_project_count >= user_quota:
        await message.reply_text(
            "Project limit reached.\n\n"
            f"You already use all {user_quota} slot(s).\n"
            f"Buy another slot for {config.Premium.PLANS['1']['stars']} Stars to deploy more projects.",
            reply_markup=buy_project_slot_keyboard(),
        )
        return

    is_premium = current_project_count >= config.User.FREE_USER_PROJECT_QUOTA

    project_id = None
    project_path = None
    try:
        project_name_message = await client.ask(
            chat_id=message.chat.id,
            text=(
                "Send a name for your new project.\n\n"
                "Example: `my-awesome-bot`\n"
                "Send /cancel to stop."
            ),
        )
        if project_name_message.text == "/cancel":
            return await message.reply_text("Project creation cancelled.")

        project_name = project_name_message.text.strip().replace(" ", "-").lower()
        user_project_dir = os.path.join(PROJECTS_BASE_DIR, str(user_id))
        project_path = os.path.join(user_project_dir, project_name)

        if os.path.exists(project_path):
            return await message.reply_text("A project with this name already exists.")

        upload_prompt = await client.ask(
            chat_id=message.chat.id,
            text=(
                f"Project `{project_name}` is ready.\n"
                f"{'This will use a premium slot.' if is_premium else 'This will use a free slot.'}\n\n"
                "Upload the main `.py` file or a `.zip` archive.\n"
                f"Max file size: {MAX_FILE_SIZE // 1024 // 1024} MB."
            ),
        )

        if not upload_prompt.document:
            return await message.reply_text("No file uploaded. Project creation aborted.")

        if upload_prompt.document.file_size > MAX_FILE_SIZE:
            return await message.reply_text(
                f"File too large. The limit is {MAX_FILE_SIZE // 1024 // 1024} MB."
            )

        status_msg = await message.reply_text("Downloading and preparing your project...")

        os.makedirs(project_path, exist_ok=True)
        uploaded_file_path = await client.download_media(
            upload_prompt.document,
            file_name=os.path.join(project_path, upload_prompt.document.file_name),
        )

        if uploaded_file_path.endswith(".zip"):
            await status_msg.edit("Extracting zip archive...")
            try:
                with zipfile.ZipFile(uploaded_file_path, "r") as zip_ref:
                    temp_extract_path = os.path.join(project_path, "temp_extract")
                    os.makedirs(temp_extract_path, exist_ok=True)
                    zip_ref.extractall(temp_extract_path)

                extracted_files = os.listdir(temp_extract_path)
                if len(extracted_files) == 1 and os.path.isdir(
                    os.path.join(temp_extract_path, extracted_files[0])
                ):
                    subfolder_path = os.path.join(temp_extract_path, extracted_files[0])
                    for item in os.listdir(subfolder_path):
                        shutil.move(os.path.join(subfolder_path, item), project_path)
                else:
                    for item in extracted_files:
                        shutil.move(os.path.join(temp_extract_path, item), project_path)

                shutil.rmtree(temp_extract_path)
                os.remove(uploaded_file_path)
            except zipfile.BadZipFile:
                shutil.rmtree(project_path, ignore_errors=True)
                return await status_msg.edit("The uploaded file is not a valid zip archive.")

        settings = await get_global_settings()
        hosting_approval_required = settings.get("require_approval", config.Bot.REQUIRE_APPROVAL)
        approval_status = (
            "approved"
            if (not hosting_approval_required or user_id in config.Bot.ADMIN_IDS)
            else "pending"
        )

        expiry_date = None
        ram_limit = config.User.FREE_USER_RAM_MB
        if is_premium:
            plan = config.Premium.PLANS["1"]
            expiry_date = datetime.utcnow() + timedelta(days=plan["duration_days"])
            ram_limit = plan["ram_mb"]

        fb_user = f"{message.from_user.username or user_id}_{project_name}"
        fb_pass = generate_password()

        project_id = await add_project(
            user_id=user_id,
            project_name=project_name,
            path=project_path,
            fb_user=fb_user,
            fb_pass=fb_pass,
            is_premium=is_premium,
            expiry_date=expiry_date,
            ram_limit_mb=ram_limit,
            approval_status=approval_status,
            source_file_id=upload_prompt.document.file_id,
            source_file_name=upload_prompt.document.file_name,
        )

        project = await get_project_by_id(project_id)

        if approval_status == "pending":
            await send_project_for_hosting_review(
                client,
                project,
                message.from_user,
                note="Auto-submitted after project upload.",
            )
            await status_msg.edit(
                f"Project `{project_name}` uploaded successfully.\n\n"
                "It has been sent for hosting approval. You can manage files now, "
                "but deployment will stay blocked until an admin approves it."
            )
        else:
            await status_msg.edit(f"Project `{project_name}` is ready.")

        text, keyboard = _approval_view(project)
        await message.reply_text(text, reply_markup=keyboard)

    except Exception as error:
        if project_id:
            await message.reply_text(
                f"Project was created, but the final setup hit an error: {error}"
            )
            return
        if project_path and os.path.exists(project_path):
            shutil.rmtree(project_path, ignore_errors=True)
        await message.reply_text(f"An error occurred: {error}")


@Client.on_message(filters.command("myproject") & filters.private)
async def my_projects_command(client: Client, message: Message):
    projects = await check_and_lock_expired_projects(message.from_user.id)
    keyboard = build_projects_keyboard(projects)
    text = (
        "You do not have any projects yet. Use /newproject to create one."
        if not projects
        else "Choose a project to manage:"
    )
    await message.reply_text(text, reply_markup=keyboard)


@Client.on_callback_query(filters.regex(r"^project_select_"))
async def select_project_callback(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[2]

    await check_and_lock_expired_projects(query.from_user.id)
    project = await get_project_by_id(project_id)
    if not project or project["user_id"] != query.from_user.id:
        return await query.answer("Project not found or access denied.", show_alert=True)

    text, keyboard = _approval_view(project)
    await query.message.edit_text(text, reply_markup=keyboard)
    await query.answer()


@Client.on_callback_query(filters.regex(r"^manage_files_"))
async def manage_files_callback(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[2]
    project = await get_project_by_id(project_id)

    if not project or project["user_id"] != query.from_user.id:
        return await query.answer("Access denied.", show_alert=True)
    if project.get("is_locked", False):
        return await query.answer("This project is locked. Renew it first.", show_alert=True)

    try:
        url, port = await start_filebrowser_session(project_id, project)
        fb_creds = project.get("filebrowser_creds", {})
        text = (
            "File manager is ready.\n\n"
            f"URL: `{url}`\n"
            f"Username: `{fb_creds.get('user')}`\n"
            f"Password: `{fb_creds.get('pass')}`\n\n"
            "It stops automatically after 15 minutes of inactivity."
        )
        view_text, keyboard = _approval_view(project, filebrowser_url=url)
        await query.message.edit_text(view_text, reply_markup=keyboard)
        await client.send_message(query.from_user.id, text)
        await query.answer(f"File manager started on port {port}")
    except Exception as error:
        print(f"Error starting file manager for project {project_id}: {error}")
        await query.answer("Error starting file manager.", show_alert=True)


@Client.on_callback_query(filters.regex(r"^request_host_review_"))
async def request_host_review_callback(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[-1]
    project = await get_project_by_id(project_id)

    if not project or project["user_id"] != query.from_user.id:
        return await query.answer("Access denied.", show_alert=True)
    if project.get("is_locked", False):
        return await query.answer("Locked projects cannot be submitted right now.", show_alert=True)

    if get_project_approval_status(project) == "approved":
        return await query.answer("This project is already approved for hosting.", show_alert=True)

    await update_project_approval(project_id, "pending")
    project = await get_project_by_id(project_id)

    sent_count = await send_project_for_hosting_review(
        client,
        project,
        query.from_user,
        note="Resubmitted by the project owner.",
    )

    text, keyboard = _approval_view(project)
    await query.message.edit_text(text, reply_markup=keyboard)
    await query.answer(
        f"Hosting review request sent to {sent_count} target(s).",
        show_alert=True,
    )


@Client.on_callback_query(filters.regex(r"^delete_project_"))
async def delete_project_callback(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[2]
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Yes, Delete It", callback_data=f"confirm_delete_{project_id}")],
            [InlineKeyboardButton("No, Cancel", callback_data=f"cancel_delete_{project_id}")],
        ]
    )
    await query.message.edit_text(
        "Are you sure?\n\nThis permanently deletes all project files and data.",
        reply_markup=keyboard,
    )
    await query.answer()


@Client.on_callback_query(filters.regex(r"^confirm_delete_"))
async def confirm_delete_callback(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[2]
    project = await get_project_by_id(project_id)

    if not project or project["user_id"] != query.from_user.id:
        return await query.answer("Access denied.", show_alert=True)

    await stop_filebrowser_session(project_id, project)
    await stop_project(project_id)

    if os.path.exists(project["path"]):
        shutil.rmtree(project["path"])

    await delete_project(project_id)
    await query.message.edit_text(f"Project `{project['name']}` has been permanently deleted.")
    await query.answer("Project deleted.", show_alert=True)


@Client.on_callback_query(filters.regex(r"^cancel_delete_"))
async def cancel_delete_callback(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[2]

    try:
        await query.message.edit_text("Deletion cancelled. Returning to the project menu...")
    except MessageNotModified:
        pass

    query.data = f"project_select_{project_id}"
    await select_project_callback(client, query)
    await query.answer()


@Client.on_callback_query(filters.regex(r"^(my_projects_list|my_projects_list_refresh)$"))
async def my_projects_list_callback(client: Client, query: CallbackQuery):
    projects = await check_and_lock_expired_projects(query.from_user.id)
    keyboard = build_projects_keyboard(projects)
    text = (
        "You do not have any projects yet. Use /newproject to create one."
        if not projects
        else "Choose a project to manage:"
    )

    try:
        await query.message.edit_text(text, reply_markup=keyboard)
    except MessageNotModified:
        pass

    await query.answer()


@Client.on_callback_query(filters.regex(r"^user_stats$"))
async def show_user_stats_callback(client: Client, query: CallbackQuery):
    user = await find_user_by_id(query.from_user.id)
    projects = await get_user_projects(query.from_user.id)

    total_slots = user.get("project_quota", config.User.FREE_USER_PROJECT_QUOTA)
    used_slots = len(projects)
    slots_left = total_slots - used_slots
    free_slots = config.User.FREE_USER_PROJECT_QUOTA
    premium_slots = max(0, total_slots - free_slots)

    text = (
        "**Your Quota and Usage**\n\n"
        f"Total slots: `{total_slots}`\n"
        f"Free slots: `{free_slots}`\n"
        f"Premium slots: `{premium_slots}`\n\n"
        f"Used: `{used_slots}`\n"
        f"Available: `{slots_left}`\n\n"
        "You can buy more slots from the /start menu."
    )

    try:
        await query.message.edit_text(text=text, reply_markup=user_stats_keyboard())
    except MessageNotModified:
        pass

    await query.answer()
