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
from utils.theme import fmt_dt, neon_kv, neon_panel, neon_text
from utils.ui import edit_message_panel


PROJECTS_BASE_DIR = os.path.join(os.getcwd(), "projects")
MAX_FILE_SIZE = config.User.MAX_PROJECT_FILE_SIZE

os.makedirs(PROJECTS_BASE_DIR, exist_ok=True)


def generate_password(length: int = 14) -> str:
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(length))


def _infer_run_command(project_path: str) -> str:
    priority_files = ["main.py", "bot.py", "app.py", "run.py", "server.py"]
    for file_name in priority_files:
        if os.path.exists(os.path.join(project_path, file_name)):
            return f"python3 {file_name}"

    python_files = [
        file_name
        for file_name in os.listdir(project_path)
        if file_name.endswith(".py") and os.path.isfile(os.path.join(project_path, file_name))
    ]
    if python_files:
        python_files.sort()
        return f"python3 {python_files[0]}"
    return "python3 main.py"


def _available_ram_choices(max_ram_mb: int) -> list[int]:
    choices = [value for value in config.User.RAM_CHOICES_MB if value <= max_ram_mb]
    if not choices:
        choices = [max_ram_mb]
    if max_ram_mb not in choices:
        choices.append(max_ram_mb)
    return sorted(set(choices))


def _project_overview_text(project: dict, extra_notice: str | None = None) -> str:
    lines = [
        neon_kv("Name", project["name"]),
        neon_kv("Status", project.get("approval_status", "approved").upper()),
        neon_kv("Tier", "Premium" if project.get("is_premium") else "Free"),
        neon_kv("RAM", f"{project.get('resource_limits', {}).get('ram', 0)} MB"),
        neon_kv("Run Command", project.get("run_command", "python3 main.py")),
    ]
    if extra_notice:
        lines.append(neon_text("⚠️", extra_notice))
    return neon_panel("BOT CONTROL", lines)


def _approval_view(project: dict, filebrowser_url: str | None = None):
    approval_status = get_project_approval_status(project)

    if project.get("is_locked", False):
        text = neon_panel(
            "PROJECT LOCKED",
            [
                neon_kv("Project", project["name"]),
                neon_kv("Expired", fmt_dt(project.get("expiry_date"))),
                neon_text("💳", "Renew the subscription to unlock deployment tools."),
            ],
        )
        return text, project_locked_keyboard(str(project["_id"]))

    if approval_status == "pending":
        text = neon_panel(
            "HOSTING REVIEW PENDING",
            [
                neon_kv("Project", project["name"]),
                neon_kv("Requested", fmt_dt(project.get("approval_requested_at") or project.get("created_at"))),
                neon_text("📁", "You can manage files while the admin reviews this upload."),
                neon_text("🚫", "Deployment is blocked until approval."),
            ],
        )
        return text, project_hosting_review_keyboard(project, filebrowser_url=filebrowser_url)

    if approval_status == "rejected":
        text = neon_panel(
            "HOSTING REJECTED",
            [
                neon_kv("Project", project["name"]),
                neon_text("❌", project.get("approval_reason") or "Rejected by admin."),
                neon_text("📨", "Fix the files if needed, then submit it again."),
            ],
        )
        return text, project_hosting_review_keyboard(project, filebrowser_url=filebrowser_url)

    return _project_overview_text(project), project_management_keyboard(project, filebrowser_url=filebrowser_url)


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


async def _ask_for_ram_limit(client: Client, chat_id: int, is_premium: bool, user_doc: dict, settings: dict):
    if not is_premium:
        return settings.get("free_user_ram_mb", config.User.FREE_USER_RAM_MB)

    max_ram_mb = user_doc.get("premium_slot_ram_mb", config.Premium.PLANS["1"]["ram_mb"])
    ram_choices = _available_ram_choices(max_ram_mb)
    ask_text = neon_panel(
        "SELECT RAM",
        [
            neon_text("🧠", f"Your premium slot can use up to {max_ram_mb} MB."),
            neon_text("📦", f"Available choices: {', '.join(str(choice) for choice in ram_choices)}"),
            neon_text("✍️", "Send one RAM value from the list above."),
        ],
    )
    ram_msg = await client.ask(chat_id=chat_id, text=ask_text, timeout=120)
    ram_value = int(ram_msg.text.strip())
    if ram_value not in ram_choices:
        raise ValueError("Invalid RAM choice.")
    return ram_value


async def _start_new_project_flow(client: Client, chat_id: int, user):
    user_id = user.id
    user_doc = await find_user_by_id(user_id)
    if not user_doc:
        await add_user(user_id, user.username)
        user_doc = await find_user_by_id(user_id)

    settings = await get_global_settings()
    projects = await get_user_projects(user_id)
    current_project_count = len(projects)
    user_quota = user_doc.get("project_quota", config.User.FREE_USER_PROJECT_QUOTA)

    if current_project_count >= user_quota:
        await client.send_message(
            chat_id,
            neon_panel(
                "SLOTS FULL",
                [
                    neon_text("📦", f"You are using all {user_quota} available slot(s)."),
                    neon_text("💎", "Buy or redeem more slots to deploy another bot."),
                ],
            ),
            reply_markup=buy_project_slot_keyboard(),
        )
        return

    is_premium = current_project_count >= config.User.FREE_USER_PROJECT_QUOTA
    project_id = None
    project_path = None

    try:
        project_name_message = await client.ask(
            chat_id=chat_id,
            text=neon_panel(
                "DEPLOY WIZARD",
                [
                    neon_text("✍️", "Send a unique bot name."),
                    neon_text("🧪", "Example: `my-awesome-bot`"),
                    neon_text("❌", "Send /cancel to abort."),
                ],
            ),
            timeout=180,
        )
        if project_name_message.text.strip().lower() == "/cancel":
            await client.send_message(chat_id, "Deployment cancelled.")
            return

        project_name = project_name_message.text.strip().replace(" ", "-").lower()
        user_project_dir = os.path.join(PROJECTS_BASE_DIR, str(user_id))
        project_path = os.path.join(user_project_dir, project_name)

        if os.path.exists(project_path):
            await client.send_message(chat_id, "A project with this name already exists.")
            return

        ram_limit = await _ask_for_ram_limit(client, chat_id, is_premium, user_doc, settings)

        upload_prompt = await client.ask(
            chat_id=chat_id,
            text=neon_panel(
                "UPLOAD PROJECT",
                [
                    neon_kv("Project", project_name),
                    neon_kv("Tier", "Premium" if is_premium else "Free"),
                    neon_kv("RAM", f"{ram_limit} MB"),
                    neon_text("📤", "Upload a `.py` file or `.zip` archive as a document."),
                    neon_text("📏", f"Maximum size: {MAX_FILE_SIZE // 1024 // 1024} MB"),
                ],
            ),
            timeout=300,
        )

        if not upload_prompt.document:
            await client.send_message(chat_id, "No document was uploaded. Deployment cancelled.")
            return

        if upload_prompt.document.file_size > MAX_FILE_SIZE:
            await client.send_message(
                chat_id,
                f"File too large. Limit is {MAX_FILE_SIZE // 1024 // 1024} MB.",
            )
            return

        status_msg = await client.send_message(
            chat_id,
            neon_panel(
                "PROCESSING UPLOAD",
                [neon_text("⚡", "Downloading and unpacking your bot files...")],
            ),
        )

        os.makedirs(project_path, exist_ok=True)
        uploaded_file_path = await client.download_media(
            upload_prompt.document,
            file_name=os.path.join(project_path, upload_prompt.document.file_name),
        )

        if uploaded_file_path.endswith(".zip"):
            await edit_message_panel(
                status_msg,
                neon_panel(
                    "EXTRACTING ARCHIVE",
                    [neon_text("📦", "Zip archive detected. Extracting now...")],
                ),
            )
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
                await edit_message_panel(
                    status_msg,
                    neon_panel(
                        "INVALID ZIP",
                        [neon_text("❌", "The uploaded archive could not be extracted.")],
                    ),
                )
                return

        hosting_approval_required = settings.get("require_approval", config.Bot.REQUIRE_APPROVAL)
        approval_status = (
            "approved"
            if (not hosting_approval_required or user_id in config.Bot.ADMIN_IDS)
            else "pending"
        )

        expiry_date = None
        if is_premium:
            expiry_date = datetime.utcnow() + timedelta(days=config.Premium.PLANS["1"]["duration_days"])

        fb_user = f"{user.username or user_id}_{project_name}"
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

        inferred_run_command = _infer_run_command(project_path)
        await update_project_config(project_id, {"run_command": inferred_run_command})
        project = await get_project_by_id(project_id)

        if approval_status == "pending":
            await send_project_for_hosting_review(
                client,
                project,
                user,
                note=f"Auto-submitted with RAM {ram_limit} MB.",
            )
            await edit_message_panel(
                status_msg,
                neon_panel(
                    "BOT SUBMITTED",
                    [
                        neon_kv("Project", project_name),
                        neon_text("📨", "Your upload has been sent for hosting approval."),
                        neon_text("📁", "You can still manage files while waiting."),
                    ],
                ),
            )
        else:
            await edit_message_panel(
                status_msg,
                neon_panel(
                    "BOT READY",
                    [
                        neon_kv("Project", project_name),
                        neon_kv("Run Command", inferred_run_command),
                        neon_text("✅", "Your bot is ready for deployment."),
                    ],
                ),
            )

        project = await get_project_by_id(project_id)
        text, keyboard = _approval_view(project)
        await client.send_message(chat_id, text, reply_markup=keyboard)

    except ValueError as error:
        if project_path and not project_id and os.path.exists(project_path):
            shutil.rmtree(project_path, ignore_errors=True)
        await client.send_message(chat_id, f"Invalid input: {error}")
    except Exception as error:
        if project_id:
            await client.send_message(
                chat_id,
                f"Project was created, but the final setup hit an error: {error}",
            )
            return
        if project_path and os.path.exists(project_path):
            shutil.rmtree(project_path, ignore_errors=True)
        await client.send_message(chat_id, f"An error occurred: {error}")


@Client.on_message(filters.command("newproject") & filters.private)
async def new_project_command(client: Client, message: Message):
    await _start_new_project_flow(client, message.chat.id, message.from_user)


@Client.on_callback_query(filters.regex(r"^menu_newproject$"))
async def new_project_menu_callback(client: Client, query: CallbackQuery):
    await query.answer("🚀 Opening deploy wizard...")
    await _start_new_project_flow(client, query.from_user.id, query.from_user)


@Client.on_message(filters.command("myproject") & filters.private)
async def my_projects_command(client: Client, message: Message):
    projects = await check_and_lock_expired_projects(message.from_user.id)
    keyboard = build_projects_keyboard(projects)
    text = neon_panel(
        "MY HOSTED BOTS",
        [neon_text("📦", "Choose a bot below to manage it.")]
        if projects
        else [neon_text("📭", "You do not have any bots yet. Use Deploy Bot to create one.")],
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
    await edit_message_panel(query.message, text, reply_markup=keyboard)
    await query.answer("⚡ Bot panel updated.")


@Client.on_callback_query(filters.regex(r"^project_review_status_"))
async def project_review_status_callback(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[-1]
    project = await get_project_by_id(project_id)
    if not project or project["user_id"] != query.from_user.id:
        return await query.answer("Access denied.", show_alert=True)

    text, keyboard = _approval_view(project)
    await edit_message_panel(query.message, text, reply_markup=keyboard)
    approval_status = get_project_approval_status(project).upper()
    await query.answer(f"Hosting status: {approval_status}", show_alert=True)


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
        text = neon_panel(
            "FILE MANAGER READY",
            [
                neon_kv("URL", url),
                neon_kv("Username", fb_creds.get("user")),
                neon_kv("Password", fb_creds.get("pass")),
                neon_text("⏳", "The session stops automatically after inactivity."),
            ],
        )
        view_text, keyboard = _approval_view(project, filebrowser_url=url)
        await edit_message_panel(query.message, view_text, reply_markup=keyboard)
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
        note="Resubmitted by the bot owner.",
    )

    text, keyboard = _approval_view(project)
    await edit_message_panel(query.message, text, reply_markup=keyboard)
    await query.answer(f"Review sent to {sent_count} target(s).", show_alert=True)


@Client.on_callback_query(filters.regex(r"^delete_project_"))
async def delete_project_callback(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[2]
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_delete_{project_id}"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_delete_{project_id}"),
            ]
        ]
    )
    await edit_message_panel(
        query.message,
        neon_panel(
            "DELETE CONFIRMATION",
            [
                neon_text("🗑", "This will permanently delete all files and bot data."),
                neon_text("⚠️", "This action cannot be undone."),
            ],
        ),
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
    await edit_message_panel(
        query.message,
        neon_panel(
            "BOT DELETED",
            [neon_text("🗑", f"`{project['name']}` has been removed permanently.")],
        ),
        reply_markup=user_stats_keyboard(),
    )
    await query.answer("Project deleted.", show_alert=True)


@Client.on_callback_query(filters.regex(r"^cancel_delete_"))
async def cancel_delete_callback(client: Client, query: CallbackQuery):
    project_id = query.data.split("_")[2]

    try:
        await edit_message_panel(
            query.message,
            neon_panel(
                "DELETE CANCELLED",
                [neon_text("✅", "Returning to the bot panel...")],
            ),
        )
    except MessageNotModified:
        pass

    query.data = f"project_select_{project_id}"
    await select_project_callback(client, query)


@Client.on_callback_query(filters.regex(r"^(my_projects_list|my_projects_list_refresh)$"))
async def my_projects_list_callback(client: Client, query: CallbackQuery):
    projects = await check_and_lock_expired_projects(query.from_user.id)
    keyboard = build_projects_keyboard(projects)
    text = neon_panel(
        "MY HOSTED BOTS",
        [neon_text("📦", "Choose a bot below to manage it.")]
        if projects
        else [neon_text("📭", "You do not have any bots yet. Use Deploy Bot to create one.")],
    )

    await edit_message_panel(query.message, text, reply_markup=keyboard)
    await query.answer("📦 Bot list refreshed.")


@Client.on_callback_query(filters.regex(r"^user_stats$"))
async def show_user_stats_callback(client: Client, query: CallbackQuery):
    user = await find_user_by_id(query.from_user.id)
    projects = await get_user_projects(query.from_user.id)

    total_slots = user.get("project_quota", config.User.FREE_USER_PROJECT_QUOTA)
    used_slots = len(projects)
    slots_left = total_slots - used_slots
    free_slots = config.User.FREE_USER_PROJECT_QUOTA
    premium_slots = max(0, total_slots - free_slots)
    premium_ram = user.get("premium_slot_ram_mb", config.Premium.PLANS["1"]["ram_mb"])

    text = neon_panel(
        "YOUR SLOT STATS",
        [
            neon_kv("Total Slots", str(total_slots)),
            neon_kv("Used", str(used_slots)),
            neon_kv("Available", str(slots_left)),
            neon_kv("Free Slots", str(free_slots)),
            neon_kv("Premium Slots", str(premium_slots)),
            neon_kv("Premium RAM", f"{premium_ram} MB"),
        ],
        footer="Redeem a key or buy a slot to grow your hosting capacity.",
    )

    await edit_message_panel(query.message, text, reply_markup=user_stats_keyboard())
    await query.answer("📊 Slot stats loaded.")
