from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from utils.database import find_user_by_id, redeem_key
from utils.keyboard_helper import back_home_keyboard
from utils.theme import neon_kv, neon_panel, neon_text
from utils.ui import edit_message_panel


async def _redeem_key_flow(
    client: Client,
    chat_id: int,
    user,
    prompt_message=None,
    preset_code: str | None = None,
):
    try:
        key_code = preset_code
        if not key_code:
            ask_msg = await client.ask(
                chat_id=chat_id,
                text=(
                    "🎟 **Redeem Your Key**\n\n"
                    "Send the key code now.\n"
                    "Send /cancel to abort."
                ),
                timeout=120,
            )
            if ask_msg.text.strip().lower() == "/cancel":
                await client.send_message(chat_id, "Key redemption cancelled.")
                return
            key_code = ask_msg.text.strip()

        success, result_text, key_doc = await redeem_key(key_code, user.id, username=user.username)
        user_doc = await find_user_by_id(user.id)

        if success:
            panel = neon_panel(
                "KEY REDEEMED",
                [
                    neon_text("✅", "Your key has been activated successfully."),
                    neon_kv("Added Slots", str(key_doc.get("slots", 0))),
                    neon_kv("Premium RAM", f"{key_doc.get('ram_mb', 0)} MB"),
                    neon_kv("Total Slots", str(user_doc.get("project_quota", 0))),
                ],
                footer="You can now deploy more projects from the home panel.",
            )
        else:
            panel = neon_panel(
                "REDEEM FAILED",
                [
                    neon_text("❌", result_text),
                    neon_text("🧠", "Make sure the code is valid and not already used."),
                ],
            )

        if prompt_message is not None:
            await edit_message_panel(prompt_message, panel, reply_markup=back_home_keyboard())
        else:
            await client.send_message(chat_id, panel, reply_markup=back_home_keyboard())
    except TimeoutError:
        await client.send_message(chat_id, "Key redemption timed out.")


@Client.on_message(filters.command("redeem") & filters.private)
async def redeem_command(client: Client, message: Message):
    preset_code = message.command[1] if len(message.command) > 1 else None
    await _redeem_key_flow(
        client,
        chat_id=message.chat.id,
        user=message.from_user,
        preset_code=preset_code,
    )


@Client.on_callback_query(filters.regex(r"^redeem_key$"))
async def redeem_key_callback(client: Client, query: CallbackQuery):
    await query.answer("🎟 Opening redeem wizard...")
    await _redeem_key_flow(
        client,
        chat_id=query.from_user.id,
        user=query.from_user,
        prompt_message=query.message,
    )
