import os
from datetime import datetime

import motor.motor_asyncio
from bson import ObjectId

from config import config


client = motor.motor_asyncio.AsyncIOMotorClient(config.Bot.MONGO_URI)
db = client[config.Bot.MONGO_DB_NAME]

users_collection = db["users"]
projects_collection = db["projects"]
settings_collection = db["bot_settings"]


async def add_user(user_id: int, username: str | None):
    """
    Create or refresh a user document.

    The legacy is_approved field is kept truthy so old data paths do not lock users out.
    Hosting approval now happens per project instead.
    """
    await users_collection.update_one(
        {"_id": user_id},
        {
            "$set": {"username": username, "is_approved": True},
            "$setOnInsert": {
                "joined_at": datetime.utcnow(),
                "project_quota": config.User.FREE_USER_PROJECT_QUOTA,
            },
        },
        upsert=True,
    )


async def update_user_approval(user_id: int, status: bool):
    await users_collection.update_one(
        {"_id": user_id},
        {"$set": {"is_approved": status}},
    )


async def find_user_by_id(user_id: int):
    return await users_collection.find_one({"_id": user_id})


async def increase_user_project_quota(user_id: int, amount: int = 1):
    result = await users_collection.find_one_and_update(
        {"_id": user_id},
        {"$inc": {"project_quota": amount}},
        return_document=True,
    )
    return result.get("project_quota", config.User.FREE_USER_PROJECT_QUOTA)


async def get_all_users(count_only: bool = False):
    if count_only:
        return await users_collection.count_documents({})
    return await users_collection.find({}).to_list(None)


async def add_project(
    user_id: int,
    project_name: str,
    path: str,
    fb_user: str,
    fb_pass: str,
    is_premium: bool,
    expiry_date: datetime | None,
    ram_limit_mb: int,
    approval_status: str = "approved",
    source_file_id: str | None = None,
    source_file_name: str | None = None,
):
    now = datetime.utcnow()
    approval_requested_at = now if approval_status == "pending" else None
    approval_decided_at = now if approval_status == "approved" else None

    project_doc = {
        "user_id": user_id,
        "name": project_name,
        "path": path,
        "created_at": now,
        "is_premium": is_premium,
        "expiry_date": expiry_date,
        "is_locked": False,
        "run_command": "python3 main.py",
        "resource_limits": {
            "cpu": 50,
            "ram": ram_limit_mb,
            "timeout": 3600,
        },
        "filebrowser_creds": {"user": fb_user, "pass": fb_pass},
        "execution_info": {
            "last_run_time": None,
            "exit_code": None,
            "status": "not_run",
            "log_file": os.path.join(path, "project.log"),
            "is_running": False,
            "pid": None,
        },
        "approval_status": approval_status,
        "approval_requested_at": approval_requested_at,
        "approval_decided_at": approval_decided_at,
        "approved_by": None,
        "approval_reason": None,
        "source_file_id": source_file_id,
        "source_file_name": source_file_name,
    }
    result = await projects_collection.insert_one(project_doc)
    return str(result.inserted_id)


async def get_user_projects(user_id: int):
    return await projects_collection.find({"user_id": user_id}).sort("created_at", 1).to_list(None)


async def get_project_by_id(project_id: str):
    try:
        return await projects_collection.find_one({"_id": ObjectId(project_id)})
    except Exception:
        return None


async def update_project_config(project_id: str, updates: dict):
    await projects_collection.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": updates},
    )


async def update_project_execution_info(project_id: str, exec_info: dict):
    await projects_collection.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {f"execution_info.{key}": value for key, value in exec_info.items()}},
    )


async def update_project_approval(
    project_id: str,
    status: str,
    reviewed_by: int | None = None,
    reason: str | None = None,
):
    update_fields = {
        "approval_status": status,
        "approval_requested_at": datetime.utcnow() if status == "pending" else None,
        "approval_decided_at": datetime.utcnow() if status in {"approved", "rejected"} else None,
        "approved_by": reviewed_by if status == "approved" else None,
        "approval_reason": reason,
    }
    await projects_collection.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": update_fields},
    )


async def delete_project(project_id: str):
    await projects_collection.delete_one({"_id": ObjectId(project_id)})


async def get_last_premium_project(user_id: int):
    return await projects_collection.find_one(
        {
            "user_id": user_id,
            "is_premium": True,
            "is_locked": False,
        },
        sort=[("created_at", -1)],
    )


async def get_first_locked_project(user_id: int):
    return await projects_collection.find_one(
        {
            "user_id": user_id,
            "is_premium": True,
            "is_locked": True,
        },
        sort=[("created_at", -1)],
    )


async def get_all_projects_count():
    return await projects_collection.count_documents({})


async def get_all_premium_projects_count():
    return await projects_collection.count_documents({"is_premium": True})


async def get_active_projects_count():
    return await projects_collection.count_documents({"execution_info.is_running": True})


async def get_premium_users_count():
    return await users_collection.count_documents(
        {"project_quota": {"$gt": config.User.FREE_USER_PROJECT_QUOTA}}
    )


async def get_global_settings():
    settings = await settings_collection.find_one({"_id": "global_config"})
    if settings:
        return settings

    default_settings = {
        "_id": "global_config",
        "free_user_ram_mb": config.User.FREE_USER_RAM_MB,
        # This now means hosting approval for projects before deployment.
        "require_approval": config.Bot.REQUIRE_APPROVAL,
        "force_public_channel": "",
        "force_public_link": "",
        "force_private_link": "",
    }
    await settings_collection.insert_one(default_settings)
    return default_settings


async def update_global_setting(key: str, value):
    await settings_collection.update_one(
        {"_id": "global_config"},
        {"$set": {key: value}},
        upsert=True,
    )
