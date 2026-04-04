from datetime import datetime

from pyrogram import Client
from pyrogram.types import User

from config import config
from utils.keyboard_helper import admin_project_approval_keyboard


def get_project_approval_status(project: dict) -> str:
    return project.get("approval_status", "approved")


def project_is_hosting_approved(project: dict) -> bool:
    return get_project_approval_status(project) == "approved"


def _format_dt(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S UTC")
    return "N/A"


def _approval_targets() -> list[int]:
    targets: list[int] = []
    if config.Bot.HOST_APPROVAL_CHAT_ID is not None:
        targets.append(config.Bot.HOST_APPROVAL_CHAT_ID)
    targets.extend(config.Bot.ADMIN_IDS)

    deduped: list[int] = []
    seen: set[int] = set()
    for target in targets:
        if target in seen:
            continue
        seen.add(target)
        deduped.append(target)
    return deduped


def build_project_review_text(project: dict, requester: User | None, note: str | None = None) -> str:
    username = getattr(requester, "username", None) or "N/A"
    first_name = getattr(requester, "first_name", None) or "Unknown"
    tier = "Premium" if project.get("is_premium") else "Free"
    file_name = project.get("source_file_name") or "Unknown upload"
    approval_status = get_project_approval_status(project).upper()

    lines = [
        "New hosting approval request",
        "",
        f"Project: {project['name']}",
        f"Project ID: {project['_id']}",
        f"Owner ID: {project['user_id']}",
        f"Owner Name: {first_name}",
        f"Username: @{username}" if username != "N/A" else "Username: N/A",
        f"Tier: {tier}",
        f"Upload: {file_name}",
        f"Requested At: {_format_dt(project.get('approval_requested_at') or project.get('created_at'))}",
        f"Current Status: {approval_status}",
    ]
    if note:
        lines.extend(["", f"Note: {note}"])
    return "\n".join(lines)


async def send_project_for_hosting_review(
    client: Client,
    project: dict,
    requester: User | None,
    note: str | None = None,
) -> int:
    text = build_project_review_text(project, requester, note=note)
    keyboard = admin_project_approval_keyboard(str(project["_id"]))
    source_file_id = project.get("source_file_id")
    sent_count = 0

    for target in _approval_targets():
        try:
            if source_file_id:
                await client.send_document(
                    chat_id=target,
                    document=source_file_id,
                    caption=text,
                    reply_markup=keyboard,
                )
            else:
                await client.send_message(
                    chat_id=target,
                    text=text,
                    reply_markup=keyboard,
                )
            sent_count += 1
        except Exception:
            try:
                await client.send_message(
                    chat_id=target,
                    text=text,
                    reply_markup=keyboard,
                )
                sent_count += 1
            except Exception as error:
                print(f"Failed to send hosting review request to {target}: {error}")

    return sent_count
