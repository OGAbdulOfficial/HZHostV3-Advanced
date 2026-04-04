from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import config


def build_projects_keyboard(projects: list):
    buttons = []
    for project in projects:
        running = "RUN" if project.get("execution_info", {}).get("is_running") else "STOP"
        tier = "PREM" if project.get("is_premium") else "FREE"
        locked = "[LOCKED] " if project.get("is_locked") else ""

        approval_status = project.get("approval_status", "approved")
        if approval_status == "pending":
            approval_prefix = "[PENDING] "
        elif approval_status == "rejected":
            approval_prefix = "[REJECTED] "
        else:
            approval_prefix = ""

        button_text = f"{approval_prefix}{locked}{tier} {project['name']} ({running})"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"project_select_{str(project['_id'])}",
                )
            ]
        )

    buttons.append([InlineKeyboardButton("View My Quota", callback_data="user_stats")])
    return InlineKeyboardMarkup(buttons)


def project_management_keyboard(project: dict, filebrowser_url: str | None = None):
    project_id = str(project["_id"])
    buttons = [
        [
            InlineKeyboardButton("Manage Files (Active)", url=filebrowser_url)
            if filebrowser_url
            else InlineKeyboardButton("Launch File Manager", callback_data=f"manage_files_{project_id}")
        ],
        [InlineKeyboardButton("Deployment", callback_data=f"deployment_{project_id}")],
        [InlineKeyboardButton("Delete Project", callback_data=f"delete_project_{project_id}")],
    ]
    return InlineKeyboardMarkup(buttons)


def project_deployment_keyboard(project: dict):
    project_id = str(project["_id"])
    buttons = [
        [
            InlineKeyboardButton("Start", callback_data=f"start_proj_{project_id}"),
            InlineKeyboardButton("Stop", callback_data=f"stop_proj_{project_id}"),
            InlineKeyboardButton("Restart", callback_data=f"restart_proj_{project_id}"),
        ],
        [
            InlineKeyboardButton("Logs", callback_data=f"logs_proj_{project_id}"),
            InlineKeyboardButton("Status", callback_data=f"status_proj_{project_id}"),
            InlineKeyboardButton("Usage", callback_data=f"usage_proj_{project_id}"),
        ],
        [InlineKeyboardButton("Install Dependencies", callback_data=f"install_proj_{project_id}")],
        [InlineKeyboardButton("Edit Run Command", callback_data=f"editcmd_proj_{project_id}")],
        [InlineKeyboardButton("Back to Project Menu", callback_data=f"project_select_{project_id}")],
    ]
    return InlineKeyboardMarkup(buttons)


def project_locked_keyboard(project_id: str):
    buttons = [
        [InlineKeyboardButton("Renew Subscription (30 Days)", callback_data=f"renew_project_{project_id}")],
        [InlineKeyboardButton("Delete Project Permanently", callback_data=f"delete_project_{project_id}")],
        [InlineKeyboardButton("Back to My Projects", callback_data="my_projects_list_refresh")],
    ]
    return InlineKeyboardMarkup(buttons)


def project_hosting_review_keyboard(project: dict, filebrowser_url: str | None = None):
    project_id = str(project["_id"])
    approval_status = project.get("approval_status", "approved")

    if approval_status == "pending":
        review_button = InlineKeyboardButton("Hosting Review Pending", callback_data="noop")
    else:
        review_button = InlineKeyboardButton(
            "Send For Hosting Approval",
            callback_data=f"request_host_review_{project_id}",
        )

    buttons = [
        [
            InlineKeyboardButton("Manage Files (Active)", url=filebrowser_url)
            if filebrowser_url
            else InlineKeyboardButton("Launch File Manager", callback_data=f"manage_files_{project_id}")
        ],
        [review_button],
        [InlineKeyboardButton("Delete Project", callback_data=f"delete_project_{project_id}")],
        [InlineKeyboardButton("Back to My Projects", callback_data="my_projects_list_refresh")],
    ]
    return InlineKeyboardMarkup(buttons)


def buy_project_slot_keyboard():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Buy New Project Slot", callback_data="buy_project_slot")]]
    )


def admin_main_keyboard():
    buttons = [
        [InlineKeyboardButton("Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("User Management", callback_data="admin_users")],
        [InlineKeyboardButton("Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("Global Settings", callback_data="admin_settings")],
    ]
    return InlineKeyboardMarkup(buttons)


def admin_settings_keyboard(current_ram: int, require_approval: bool):
    approval_text = "ON" if require_approval else "OFF"
    buttons = [
        [InlineKeyboardButton(f"Free User RAM: {current_ram}MB", callback_data="admin_setfreeram")],
        [InlineKeyboardButton(f"Hosting Approval: {approval_text}", callback_data="admin_toggleapproval")],
        [InlineKeyboardButton("Force Subscribe Settings", callback_data="admin_forcesub")],
        [InlineKeyboardButton("Back to Admin Panel", callback_data="admin_main")],
    ]
    return InlineKeyboardMarkup(buttons)


def admin_forcesub_keyboard(pub_ch: str, pub_link: str, priv_link: str):
    pub_ch_text = f"Public CH: {pub_ch}" if pub_ch else "Set Public Channel"
    pub_link_text = "Public Link: Set" if pub_link else "Set Public Invite Link"
    priv_text = "Private Link: Set" if priv_link else "Set Private Invite Link"

    has_pub = bool(pub_ch or pub_link)
    has_priv = bool(priv_link)

    buttons = [
        [InlineKeyboardButton("-- Force Public Channel --", callback_data="noop")],
        [
            InlineKeyboardButton(pub_ch_text, callback_data="admin_setfspubch"),
            InlineKeyboardButton(pub_link_text, callback_data="admin_setfspublink"),
        ],
        [InlineKeyboardButton("Clear Public", callback_data="admin_clearfspub")]
        if has_pub
        else [InlineKeyboardButton("No public channel set", callback_data="noop")],
        [InlineKeyboardButton("-- Force Private Channel --", callback_data="noop")],
        [InlineKeyboardButton(priv_text, callback_data="admin_setfsprivlink")],
        [InlineKeyboardButton("Clear Private", callback_data="admin_clearfspriv")]
        if has_priv
        else [InlineKeyboardButton("No private channel set", callback_data="noop")],
        [InlineKeyboardButton("Back to Settings", callback_data="admin_settings")],
    ]
    return InlineKeyboardMarkup(buttons)


def force_sub_required_keyboard(pub_link: str | None = None, priv_link: str | None = None):
    buttons = []
    if pub_link:
        buttons.append([InlineKeyboardButton("Join Public Channel", url=pub_link)])
    if priv_link:
        buttons.append([InlineKeyboardButton("Join Private Channel", url=priv_link)])
    buttons.append([InlineKeyboardButton("I've Joined - Continue", callback_data="fsub_verify")])
    return InlineKeyboardMarkup(buttons)


def admin_back_to_main_keyboard(section: str | None = None):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Back to Admin Panel", callback_data="admin_main")]]
    )


def admin_stats_keyboard():
    return admin_back_to_main_keyboard("stats")


def admin_user_management_keyboard():
    buttons = [
        [InlineKeyboardButton("Find User by ID", callback_data="admin_finduser")],
        [InlineKeyboardButton("Back to Admin Panel", callback_data="admin_main")],
    ]
    return InlineKeyboardMarkup(buttons)


def admin_user_detail_keyboard(user_id: int, current_quota: int, is_approved: bool = True):
    free_quota = config.User.FREE_USER_PROJECT_QUOTA
    premium_slots = max(0, current_quota - free_quota)
    plan_info = f"Plan: {free_quota} Free + {premium_slots} Premium"

    buttons = [
        [InlineKeyboardButton(plan_info, callback_data="noop")],
        [InlineKeyboardButton("Add 1 Premium Slot", callback_data=f"admin_changequota_add_{user_id}")],
        [InlineKeyboardButton("Remove 1 Premium Slot", callback_data=f"admin_changequota_remove_{user_id}")],
        [InlineKeyboardButton("Back to User Search", callback_data="admin_users")],
    ]
    return InlineKeyboardMarkup(buttons)


def admin_project_approval_keyboard(project_id: str):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Approve Hosting", callback_data=f"admin_hostapprove_{project_id}"),
                InlineKeyboardButton("Reject Hosting", callback_data=f"admin_hostreject_{project_id}"),
            ]
        ]
    )


def user_stats_keyboard():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Back to My Projects", callback_data="my_projects_list_refresh")]]
    )
