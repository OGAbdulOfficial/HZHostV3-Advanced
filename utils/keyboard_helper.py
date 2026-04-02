# utils/keyboard_helper.py

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import config

# -------------------------------------------------------------------------------- #
# USER-FACING KEYBOARDS
# -------------------------------------------------------------------------------- #

def build_projects_keyboard(projects: list):
    """
    Builds a keyboard with a list of user's projects and a stats button.
    """
    buttons = []
    # First, add all the project buttons if they exist
    for project in projects:
        status_icon = "🟢" if project.get('execution_info', {}).get('is_running') else "🔴"
        premium_icon = "⭐" if project.get('is_premium') else "🆓"
        locked_icon = "🔒 " if project.get('is_locked') else ""
        
        button_text = f"{locked_icon}{premium_icon} {project['name']} {status_icon}"
        
        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"project_select_{str(project['_id'])}"
        )])
    
    # ALWAYS add the quota button at the end
    buttons.append([
        InlineKeyboardButton("📊 View My Quota", callback_data="user_stats")
    ])
        
    return InlineKeyboardMarkup(buttons)

def project_management_keyboard(project: dict, filebrowser_url: str = None):
    """Shows the main management keyboard for a selected project."""
    project_id = str(project['_id'])
    buttons = [
        [
            InlineKeyboardButton("🌐 Manage Files (Active)", url=filebrowser_url) 
            if filebrowser_url 
            else InlineKeyboardButton("🚀 Launch File Manager", callback_data=f"manage_files_{project_id}")
        ],
        [InlineKeyboardButton("⚙️ Deployment", callback_data=f"deployment_{project_id}")],
        [InlineKeyboardButton("🗑️ Delete Project", callback_data=f"delete_project_{project_id}")]
    ]
    return InlineKeyboardMarkup(buttons)

def project_deployment_keyboard(project: dict):
    """Shows the deployment actions for a project."""
    project_id = str(project['_id'])
    
    # Icons for actions
    start_text = "▶️ Start"
    stop_text = "⏹️ Stop"
    restart_text = "🔁 Restart"
    logs_text = "📝 Logs"
    status_text = "🔍 Status"
    usage_text = "💪 Usage"
    install_text = "📦 Install Dependencies"
    edit_cmd_text = "⚙️ Edit Run Command"
    back_text = "⬅️ Back to Project Menu"

    buttons = [
        [
            InlineKeyboardButton(start_text, callback_data=f"start_proj_{project_id}"),
            InlineKeyboardButton(stop_text, callback_data=f"stop_proj_{project_id}"),
            InlineKeyboardButton(restart_text, callback_data=f"restart_proj_{project_id}")
        ],
        [
            InlineKeyboardButton(logs_text, callback_data=f"logs_proj_{project_id}"),
            InlineKeyboardButton(status_text, callback_data=f"status_proj_{project_id}"),
            InlineKeyboardButton(usage_text, callback_data=f"usage_proj_{project_id}")
        ],
        [InlineKeyboardButton(install_text, callback_data=f"install_proj_{project_id}")],
        [InlineKeyboardButton(edit_cmd_text, callback_data=f"editcmd_proj_{project_id}")],
        [InlineKeyboardButton(back_text, callback_data=f"project_select_{project_id}")] # Changed back button logic
    ]
    return InlineKeyboardMarkup(buttons)

def project_locked_keyboard(project_id: str):
    """Keyboard shown for a locked/expired project."""
    buttons = [
        [InlineKeyboardButton("✅ Renew Subscription (30 Days)", callback_data=f"renew_project_{project_id}")],
        [InlineKeyboardButton("🗑️ Delete Project Permanently", callback_data=f"delete_project_{project_id}")],
        [InlineKeyboardButton("⬅️ Back to My Projects", callback_data="my_projects_list_refresh")]
    ]
    return InlineKeyboardMarkup(buttons)
    
def buy_project_slot_keyboard():
    """Simple keyboard to direct user to purchase a slot."""
    buttons = [[
        InlineKeyboardButton("🛒 Buy New Project Slot", callback_data="buy_project_slot")
    ]]
    return InlineKeyboardMarkup(buttons)
    
# -------------------------------------------------------------------------------- #
# ADMIN PANEL KEYBOARDS
# -------------------------------------------------------------------------------- #

def admin_main_keyboard():
    """The main keyboard for the /admin panel."""
    buttons = [
        [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("👤 User Management", callback_data="admin_users")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⚙️ Global Settings", callback_data="admin_settings")]
        ]

    return InlineKeyboardMarkup(buttons)

def admin_settings_keyboard(current_ram: int, require_approval: bool):
    """Keyboard for the global settings section."""
    approval_text = "✅ ON" if require_approval else "❌ OFF"
    buttons = [
        [InlineKeyboardButton(f"🔧 Free User RAM: {current_ram}MB", callback_data="admin_setfreeram")],
        [InlineKeyboardButton(f"🛡️ Approval System: {approval_text}", callback_data="admin_toggleapproval")],
        [InlineKeyboardButton("📢 Force Subscribe Settings", callback_data="admin_forcesub")],
        [InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_main")]
    ]
    return InlineKeyboardMarkup(buttons)


def admin_forcesub_keyboard(pub_ch: str, pub_link: str, priv_link: str):
    """Admin keyboard to manage Force Public & Force Private channel subscriptions."""
    pub_ch_text   = f"🌐 Public CH: {pub_ch}"   if pub_ch   else "🌐 Set Public Channel"
    pub_link_text = f"🔗 Public Link: Set"        if pub_link else "🔗 Set Public Invite Link"
    priv_text     = f"🔒 Private Link: Set"       if priv_link else "🔒 Set Private Invite Link"

    has_pub  = bool(pub_ch or pub_link)
    has_priv = bool(priv_link)

    buttons = [
        # ── Public Channel ──────────────────────────────────
        [InlineKeyboardButton("── 🌐 Force Public Channel ──", callback_data="noop")],
        [InlineKeyboardButton(pub_ch_text,   callback_data="admin_setfspubch"),
         InlineKeyboardButton(pub_link_text, callback_data="admin_setfspublink")],
        [InlineKeyboardButton("🗑️ Clear Public", callback_data="admin_clearfspub")] if has_pub else
         [InlineKeyboardButton("ℹ️ No public channel set", callback_data="noop")],
        # ── Private Channel ─────────────────────────────────
        [InlineKeyboardButton("── 🔒 Force Private Channel ──", callback_data="noop")],
        [InlineKeyboardButton(priv_text, callback_data="admin_setfsprivlink")],
        [InlineKeyboardButton("🗑️ Clear Private", callback_data="admin_clearfspriv")] if has_priv else
         [InlineKeyboardButton("ℹ️ No private channel set", callback_data="noop")],
        # ── Navigation ──────────────────────────────────────
        [InlineKeyboardButton("⬅️ Back to Settings", callback_data="admin_settings")]
    ]
    return InlineKeyboardMarkup(buttons)


def force_sub_required_keyboard(pub_link: str = None, priv_link: str = None):
    """Keyboard shown to users who have not joined the required channel(s)."""
    buttons = []
    if pub_link:
        buttons.append([InlineKeyboardButton("📢 Join Public Channel", url=pub_link)])
    if priv_link:
        buttons.append([InlineKeyboardButton("🔒 Join Private Channel", url=priv_link)])
    # Let user retry after joining
    buttons.append([InlineKeyboardButton("✅ I've Joined — Continue", callback_data="fsub_verify")])
    return InlineKeyboardMarkup(buttons)


def admin_back_to_main_keyboard(section: str = None):
    """A generic keyboard with a 'Back' button to the admin main menu."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_main")
    ]])
    
def admin_stats_keyboard():
    """Keyboard for the stats section."""
    return admin_back_to_main_keyboard("stats")

def admin_user_management_keyboard():
    """Keyboard for the user management section."""
    buttons = [
        [InlineKeyboardButton("🔎 Find User by ID", callback_data="admin_finduser")],
        [InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_main")]
    ]
    return InlineKeyboardMarkup(buttons)
    
def admin_user_detail_keyboard(user_id: int, current_quota: int, is_approved: bool = True):
    """Keyboard for managing a specific user."""
    # Dynamically generate user's plan info string
    free_quota = config.User.FREE_USER_PROJECT_QUOTA
    premium_slots = max(0, current_quota - free_quota)
    plan_info = f"Plan: {free_quota} Free + {premium_slots} Premium"

    buttons = []
    
    # Approval buttons if the user is not approved
    if not is_approved:
        buttons.append([
            InlineKeyboardButton("✅ Approve User", callback_data=f"admin_approve_{user_id}"),
            InlineKeyboardButton("❌ Reject User", callback_data=f"admin_reject_{user_id}")
        ])
    else:
        # If already approved, maybe show a way to revoke? 
        # (Optional, but let's keep it simple for now)
        pass

    buttons.extend([
        # First row is a label showing the plan info
        [InlineKeyboardButton(f"ℹ️ {plan_info}", callback_data="noop")], # noop = no operation
        [InlineKeyboardButton("➕ Add 1 Premium Slot", callback_data=f"admin_changequota_add_{user_id}")],
        [InlineKeyboardButton("➖ Remove 1 Premium Slot", callback_data=f"admin_changequota_remove_{user_id}")],
        [InlineKeyboardButton("⬅️ Back to User Search", callback_data="admin_users")]
    ])
    return InlineKeyboardMarkup(buttons)

def user_stats_keyboard():
    """Keyboard with a 'Back' button to the main project list."""
    buttons = [[
        InlineKeyboardButton("⬅️ Back to My Projects", callback_data="my_projects_list_refresh")
    ]]
    return InlineKeyboardMarkup(buttons)