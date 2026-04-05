from datetime import datetime, timedelta

from pyrogram import Client, filters, types
from pyrogram.types import CallbackQuery, Message, PreCheckoutQuery

from config import config
from utils.database import (
    get_project_by_id,
    increase_user_project_quota,
    set_user_premium_ram,
    update_project_config,
)
from utils.theme import neon_kv, neon_panel, neon_text
from utils.ui import edit_message_panel


@Client.on_callback_query(filters.regex(r"^buy_project_slot$"))
async def send_slot_invoice(client: Client, callback_query: CallbackQuery):
    plan_key = "1"
    plan_details = config.Premium.PLANS.get(plan_key)
    if not plan_details:
        await callback_query.answer("Premium plan not configured.", show_alert=True)
        return

    invoice_payload = f"purchase-slot_{plan_key}_{callback_query.from_user.id}"
    await edit_message_panel(
        callback_query.message,
        neon_panel(
            "CHECKOUT",
            [
                neon_text("💎", "You are buying one additional hosting slot."),
                neon_kv("Price", f"{plan_details['stars']} Stars"),
                neon_kv("RAM", f"{plan_details['ram_mb']} MB"),
            ],
        ),
    )

    await client.send_invoice(
        chat_id=callback_query.from_user.id,
        title=plan_details["name"],
        description=plan_details["description"],
        payload=invoice_payload,
        currency=config.Premium.CURRENCY,
        prices=[
            types.LabeledPrice(
                label="1 Project Slot (30 Days)",
                amount=plan_details["stars"],
            )
        ],
    )
    await callback_query.answer()


@Client.on_callback_query(filters.regex(r"^renew_project_(\w+)$"))
async def send_renewal_invoice(client: Client, callback_query: CallbackQuery):
    project_id = callback_query.matches[0].group(1)
    project = await get_project_by_id(project_id)

    if not project or project["user_id"] != callback_query.from_user.id:
        await callback_query.answer("Project not found or access denied.", show_alert=True)
        return
    if not project.get("is_locked", False):
        await callback_query.answer("This project is already active.", show_alert=True)
        return

    plan_key = "1"
    plan_details = config.Premium.PLANS.get(plan_key)
    if not plan_details:
        await callback_query.answer("Premium plan not configured.", show_alert=True)
        return

    invoice_payload = f"renew-project_{plan_key}_{callback_query.from_user.id}_{project_id}"
    await edit_message_panel(
        callback_query.message,
        neon_panel(
            "RENEW PROJECT",
            [
                neon_kv("Project", project["name"]),
                neon_kv("Duration", f"{plan_details['duration_days']} days"),
                neon_kv("Price", f"{plan_details['stars']} Stars"),
            ],
        ),
    )

    await client.send_invoice(
        chat_id=callback_query.from_user.id,
        title=f"Renew Project: {project['name']}",
        description=f"Unlocks `{project['name']}` for {plan_details['duration_days']} more days.",
        payload=invoice_payload,
        currency=config.Premium.CURRENCY,
        prices=[
            types.LabeledPrice(
                label=f"Renewal ({plan_details['duration_days']} Days)",
                amount=plan_details["stars"],
            )
        ],
    )
    await callback_query.answer()


@Client.on_pre_checkout_query()
async def pre_checkout_handler(client: Client, query: PreCheckoutQuery):
    await query.answer(True)


@Client.on_message(filters.successful_payment)
async def successful_payment_handler(client: Client, message: Message):
    invoice_payload = message.successful_payment.payload
    try:
        payload_parts = invoice_payload.split("_")
        purpose = payload_parts[0]
        plan_key = payload_parts[1]
        user_id = int(payload_parts[2])

        plan_details = config.Premium.PLANS.get(plan_key)
        if not plan_details:
            raise ValueError(f"Invalid plan key '{plan_key}' in payload.")

        if purpose == "purchase-slot":
            new_quota = await increase_user_project_quota(user_id, 1)
            await set_user_premium_ram(user_id, max(plan_details["ram_mb"], config.User.DEFAULT_PREMIUM_RAM_MB))
            await client.send_message(
                chat_id=user_id,
                text=neon_panel(
                    "PAYMENT SUCCESSFUL",
                    [
                        neon_text("✅", "Your hosting slot has been added."),
                        neon_kv("New Total Slots", str(new_quota)),
                        neon_kv("Premium RAM", f"{plan_details['ram_mb']} MB"),
                    ],
                    footer="Use Deploy Bot to launch another project.",
                ),
            )

        elif purpose == "renew-project":
            if len(payload_parts) < 4:
                raise ValueError("Project ID missing from renewal payload.")

            project_id = payload_parts[3]
            new_expiry_date = datetime.utcnow() + timedelta(days=plan_details["duration_days"])
            await update_project_config(
                project_id,
                {"expiry_date": new_expiry_date, "is_locked": False},
            )

            project = await get_project_by_id(project_id)
            await client.send_message(
                chat_id=user_id,
                text=neon_panel(
                    "RENEWAL SUCCESSFUL",
                    [
                        neon_kv("Project", project["name"]),
                        neon_kv("Valid Until", new_expiry_date.strftime("%Y-%m-%d %H:%M UTC")),
                        neon_text("✅", "Your project is unlocked again."),
                    ],
                ),
            )

        else:
            raise ValueError(f"Unknown payment purpose: '{purpose}'")

    except Exception as error:
        print(f"CRITICAL ERROR in successful_payment_handler: {error}\nPayload: {invoice_payload}")
        await client.send_message(
            message.chat.id,
            neon_panel(
                "PAYMENT RECORDED",
                [
                    neon_text("⚠️", "Your payment succeeded, but activation failed automatically."),
                    neon_text("👑", "Please contact the admin with your payment details."),
                ],
            ),
        )
