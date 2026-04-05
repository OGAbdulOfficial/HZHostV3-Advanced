from pyrogram.errors import MessageNotModified


async def edit_message_panel(message, text: str, reply_markup=None):
    try:
        if getattr(message, "photo", None) or getattr(message, "document", None):
            await message.edit_caption(caption=text, reply_markup=reply_markup)
        else:
            await message.edit_text(text=text, reply_markup=reply_markup, disable_web_page_preview=True)
    except MessageNotModified:
        pass
    except Exception:
        try:
            await message.edit_text(text=text, reply_markup=reply_markup, disable_web_page_preview=True)
        except Exception:
            try:
                await message.reply_text(text=text, reply_markup=reply_markup, disable_web_page_preview=True)
            except Exception:
                pass
