from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import config


def start_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🚀 Deploy Bot", callback_data="menu_newproject"),
                InlineKeyboardButton("📦 My Bots", callback_data="my_projects_list"),
            ],
            [
                InlineKeyboardButton("🎟 Redeem Key", callback_data="redeem_key"),
                InlineKeyboardButton("💎 Buy Slot", callback_data="buy_project_slot"),
            ],
            [
                InlineKeyboardButton("👤 My Profile", callback_data="menu_profile"),
                InlineKeyboardButton("🆘 Help", callback_data="menu_help"),
            ],
            [
                InlineKeyboardButton("👑 Owner", url=config.Bot.OWNER_URL),
                InlineKeyboardButton("📢 Channel", url=config.Bot.CHANNEL_URL),
            ],
        ]
    )


def back_home_keyboard():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🏠 Back Home", callback_data="menu_home")]]
    )


def support_links_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👑 Owner", url=config.Bot.OWNER_URL),
                InlineKeyboardButton("📢 Channel", url=config.Bot.CHANNEL_URL),
            ]
        ]
    )


def build_projects_keyboard(projects: list):
    buttons = []
    for project in projects:
        running = "🟢" if project.get("execution_info", {}).get("is_running") else "🔴"
        tier = "💎" if project.get("is_premium") else "🆓"
        locked = "🔒 " if project.get("is_locked") else ""

        approval_status = project.get("approval_status", "approved")
        if approval_status == "pending":
            approval_prefix = "🟡 "
        elif approval_status == "rejected":
            approval_prefix = "⛔ "
        else:
            approval_prefix = "⚡ "

        button_text = f"{approval_prefix}{locked}{tier} {project['name']} {running}"
        buttons.append(
            [InlineKeyboardButton(button_text, callback_data=f"project_select_{str(project['_id'])}")]
        )

    buttons.append(
        [
            InlineKeyboardButton("📊 My Slots", callback_data="user_stats"),
            InlineKeyboardButton("🏠 Home", callback_data="menu_home"),
        ]
    )
    return InlineKeyboardMarkup(buttons)


def project_management_keyboard(project: dict, filebrowser_url: str | None = None):
    project_id = str(project["_id"])
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📁 File Manager", url=filebrowser_url)
                if filebrowser_url
                else InlineKeyboardButton("📁 File Manager", callback_data=f"manage_files_{project_id}"),
                InlineKeyboardButton("⚙️ Deploy Panel", callback_data=f"deployment_{project_id}"),
            ],
            [
                InlineKeyboardButton("🧾 Hosting Status", callback_data=f"project_review_status_{project_id}"),
                InlineKeyboardButton("🗑 Delete", callback_data=f"delete_project_{project_id}"),
            ],
            [InlineKeyboardButton("⬅️ Back to Bots", callback_data="my_projects_list_refresh")],
        ]
    )


def project_deployment_keyboard(project: dict):
    project_id = str(project["_id"])
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("▶️ Start", callback_data=f"start_proj_{project_id}"),
                InlineKeyboardButton("⏹ Stop", callback_data=f"stop_proj_{project_id}"),
                InlineKeyboardButton("🔄 Restart", callback_data=f"restart_proj_{project_id}"),
            ],
            [
                InlineKeyboardButton("📜 Logs", callback_data=f"logs_proj_{project_id}"),
                InlineKeyboardButton("📡 Status", callback_data=f"status_proj_{project_id}"),
                InlineKeyboardButton("🧠 Usage", callback_data=f"usage_proj_{project_id}"),
            ],
            [
                InlineKeyboardButton("📦 Install Deps", callback_data=f"install_proj_{project_id}"),
                InlineKeyboardButton("📝 Run Cmd", callback_data=f"editcmd_proj_{project_id}"),
            ],
            [InlineKeyboardButton("⬅️ Back to Project", callback_data=f"project_select_{project_id}")],
        ]
    )


def project_locked_keyboard(project_id: str):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💳 Renew 30 Days", callback_data=f"renew_project_{project_id}")],
            [InlineKeyboardButton("🗑 Delete Permanently", callback_data=f"delete_project_{project_id}")],
            [InlineKeyboardButton("⬅️ Back to Bots", callback_data="my_projects_list_refresh")],
        ]
    )


def project_hosting_review_keyboard(project: dict, filebrowser_url: str | None = None):
    project_id = str(project["_id"])
    approval_status = project.get("approval_status", "approved")

    if approval_status == "pending":
        review_button = InlineKeyboardButton(
            "🟡 Review Pending",
            callback_data=f"project_review_status_{project_id}",
        )
    else:
        review_button = InlineKeyboardButton(
            "📨 Send for Approval",
            callback_data=f"request_host_review_{project_id}",
        )

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📁 File Manager", url=filebrowser_url)
                if filebrowser_url
                else InlineKeyboardButton("📁 File Manager", callback_data=f"manage_files_{project_id}"),
                review_button,
            ],
            [InlineKeyboardButton("🗑 Delete Project", callback_data=f"delete_project_{project_id}")],
            [InlineKeyboardButton("⬅️ Back to Bots", callback_data="my_projects_list_refresh")],
        ]
    )


def buy_project_slot_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💎 Buy New Slot", callback_data="buy_project_slot")],
            [InlineKeyboardButton("🏠 Back Home", callback_data="menu_home")],
        ]
    )


def force_sub_required_keyboard(pub_link: str | None = None, priv_link: str | None = None):
    buttons = []
    if pub_link:
        buttons.append([InlineKeyboardButton("📢 Join Public Channel", url=pub_link)])
    if priv_link:
        buttons.append([InlineKeyboardButton("🔐 Join Private Channel", url=priv_link)])
    buttons.append([InlineKeyboardButton("✅ I've Joined", callback_data="fsub_verify")])
    return InlineKeyboardMarkup(buttons)


def admin_main_keyboard(maintenance_mode: bool = False):
    maintenance_label = "🟢 Maintenance Off" if not maintenance_mode else "🔴 Maintenance On"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
                InlineKeyboardButton("🧑‍🤝‍🧑 Users List", callback_data="admin_userslist_0"),
            ],
            [
                InlineKeyboardButton("🔎 User Tools", callback_data="admin_users"),
                InlineKeyboardButton("🎟 Keys", callback_data="admin_keys"),
            ],
            [
                InlineKeyboardButton("🚫 Ban User", callback_data="admin_banprompt"),
                InlineKeyboardButton("✅ Unban User", callback_data="admin_unbanprompt"),
            ],
            [
                InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
                InlineKeyboardButton(maintenance_label, callback_data="admin_togglemaintenance"),
            ],
            [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings")],
        ]
    )


def admin_stats_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_main")]])


def admin_user_management_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔎 Find by ID", callback_data="admin_finduser"),
                InlineKeyboardButton("🧑‍🤝‍🧑 Users List", callback_data="admin_userslist_0"),
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data="admin_main")],
        ]
    )


def admin_user_detail_keyboard(user_id: int, current_quota: int, is_banned: bool = False):
    ban_label = "✅ Unban User" if is_banned else "🚫 Ban User"
    ban_callback = f"admin_unban_{user_id}" if is_banned else f"admin_ban_{user_id}"

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➕ Slot", callback_data=f"admin_changequota_add_{user_id}"),
                InlineKeyboardButton("➖ Slot", callback_data=f"admin_changequota_remove_{user_id}"),
            ],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data=f"admin_viewuser_{user_id}"),
                InlineKeyboardButton(ban_label, callback_data=ban_callback),
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data="admin_users")],
        ]
    )


def admin_keys_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🎟 Generate Key", callback_data="admin_genkey"),
                InlineKeyboardButton("📜 View Keys", callback_data="admin_listkeys"),
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data="admin_main")],
        ]
    )


def admin_users_list_keyboard(page: int, total_users: int, page_size: int):
    max_page = max(0, (total_users - 1) // page_size)
    buttons = []
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_userslist_{page - 1}"))
    if page < max_page:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_userslist_{page + 1}"))
    if nav_row:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_main")])
    return InlineKeyboardMarkup(buttons)


def admin_settings_keyboard(current_ram: int, require_approval: bool, maintenance_mode: bool = False):
    approval_text = "🟢 ON" if require_approval else "🔴 OFF"
    maintenance_text = "🟢 OFF" if not maintenance_mode else "🔴 ON"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"🧠 Free RAM: {current_ram}MB", callback_data="admin_setfreeram")],
            [InlineKeyboardButton(f"🛡 Hosting Approval: {approval_text}", callback_data="admin_toggleapproval")],
            [InlineKeyboardButton(f"🧰 Maintenance: {maintenance_text}", callback_data="admin_togglemaintenance")],
            [InlineKeyboardButton("📢 Force Subscribe", callback_data="admin_forcesub")],
            [InlineKeyboardButton("⬅️ Back", callback_data="admin_main")],
        ]
    )


def admin_forcesub_keyboard(pub_ch: str, pub_link: str, priv_link: str):
    pub_summary = pub_ch if pub_ch else "Not Set"
    pub_link_summary = "Saved" if pub_link else "Missing"
    priv_summary = "Saved" if priv_link else "Missing"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"🌐 Public Channel: {pub_summary}", callback_data="admin_fsubinfo_public")],
            [
                InlineKeyboardButton("✏️ Set Public Channel", callback_data="admin_setfspubch"),
                InlineKeyboardButton(f"🔗 Public Link: {pub_link_summary}", callback_data="admin_setfspublink"),
            ],
            [
                InlineKeyboardButton(f"🔐 Private Link: {priv_summary}", callback_data="admin_setfsprivlink"),
                InlineKeyboardButton("🗑 Clear Public", callback_data="admin_clearfspub"),
            ],
            [
                InlineKeyboardButton("🗑 Clear Private", callback_data="admin_clearfspriv"),
                InlineKeyboardButton("⬅️ Back", callback_data="admin_settings"),
            ],
        ]
    )


def admin_project_approval_keyboard(project_id: str):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve Hosting", callback_data=f"admin_hostapprove_{project_id}"),
                InlineKeyboardButton("❌ Reject Hosting", callback_data=f"admin_hostreject_{project_id}"),
            ]
        ]
    )


def admin_back_to_main_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_main")]])


def user_stats_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📦 My Bots", callback_data="my_projects_list_refresh"),
                InlineKeyboardButton("🏠 Home", callback_data="menu_home"),
            ]
        ]
    )
