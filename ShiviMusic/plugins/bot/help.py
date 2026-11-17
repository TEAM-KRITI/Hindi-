# ===========================================================
# ©️ 2025-26 All Rights Reserved by Purvi Bots (Im-Notcoder) 🚀
# 
# This source code is under MIT License 📜
# ❌ Unauthorized forking, importing, or using this code
#    without giving proper credit will result in legal action ⚠️
# 
# 📩 DM for permission : @TheSigmaCoder
# ===========================================================

from typing import Union
import random

from pyrogram import filters, types
from pyrogram.errors import MessageNotModified
from pyrogram.types import InlineKeyboardMarkup, Message, InputMediaPhoto

from ShiviMusic import app
from ShiviMusic.utils import help_pannel
from ShiviMusic.utils.database import get_lang
from ShiviMusic.utils.decorators.language import LanguageStart, languageCB
from ShiviMusic.utils.inline.help import help_back_markup, private_help_panel
from config import BANNED_USERS, START_IMG_URL, SUPPORT_CHAT
from strings import get_string, helpers
from ShiviMusic.utils.stuffs.buttons import BUTTONS
from ShiviMusic.utils.stuffs.helper import Helper


START_IMG = [
    "https://files.catbox.moe/4ojtc4.jpg",
    "https://files.catbox.moe/30wg78.jpg",
    "https://files.catbox.moe/4ojtc4.jpg",
    "https://files.catbox.moe/30wg78.jpg",
    "https://files.catbox.moe/4ojtc4.jpg",
    "https://files.catbox.moe/30wg78.jpg",
    "https://files.catbox.moe/4ojtc4.jpg",
    "https://files.catbox.moe/30wg78.jpg"
]

@app.on_message(filters.command(["help"]) & filters.private & ~BANNED_USERS)
@app.on_callback_query(filters.regex("settings_back_helper") & ~BANNED_USERS)
async def helper_private(
    client: app, update: Union[types.Message, types.CallbackQuery]
):
    is_callback = isinstance(update, types.CallbackQuery)
    if is_callback:
        try:
            await update.answer()
        except:
            pass
        chat_id = update.message.chat.id
        language = await get_lang(chat_id)
        _ = get_string(language)
        keyboard = help_pannel(_, True)
        await update.edit_message_text(
            _["help_1"].format(SUPPORT_CHAT), reply_markup=keyboard
        )
    else:
        try:
            await update.delete()
        except:
            pass
        language = await get_lang(update.chat.id)
        _ = get_string(language)
        keyboard = help_pannel(_)
        await update.reply_photo(
            photo=START_IMG_URL,
            has_spoiler=True,
            caption=_["help_1"].format(SUPPORT_CHAT),
            reply_markup=keyboard,
        )


@app.on_message(filters.command(["help"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def help_com_group(client, message: Message, _):
    keyboard = private_help_panel(_)
    await message.reply_text(_["help_2"], reply_markup=InlineKeyboardMarkup(keyboard))

@app.on_callback_query(filters.regex("wel_cb") & ~BANNED_USERS)
async def helper_cb(client, CallbackQuery):
    await CallbackQuery.edit_message_text(Helper.HELP_WEL, reply_markup=InlineKeyboardMarkup(BUTTONS.INFO_NEW))

@app.on_callback_query(filters.regex("lock_cb") & ~BANNED_USERS)
async def helper_cb(client, CallbackQuery):
    await CallbackQuery.edit_message_text(Helper.HELP_LOCK, reply_markup=InlineKeyboardMarkup(BUTTONS.INFO_NEW))

@app.on_callback_query(filters.regex("night_cb") & ~BANNED_USERS)
async def helper_cb(client, CallbackQuery):
    await CallbackQuery.edit_message_text(Helper.HELP_NIGHT, reply_markup=InlineKeyboardMarkup(BUTTONS.INFO_NEW))

@app.on_callback_query(filters.regex("aplay_cb") & ~BANNED_USERS)
async def helper_cb(client, CallbackQuery):
    await CallbackQuery.edit_message_text(Helper.HELP_AUTOPLAY, reply_markup=InlineKeyboardMarkup(BUTTONS.INFO_NEW))

@app.on_callback_query(filters.regex("abot_cb") & ~BANNED_USERS)
async def helper_cb(client, CallbackQuery):
    bot = await client.get_me()
    bot_mention = bot.mention

    await CallbackQuery.edit_message_text(
        Helper.HELP_ABOUT.format(bot_mention),
        reply_markup=InlineKeyboardMarkup(BUTTONS.INFO_BUTTON),
    )

@app.on_callback_query(filters.regex("sbot_cb") & ~BANNED_USERS)
async def helper_cb(client, CallbackQuery):
    bot = await client.get_me()
    bot_mention = bot.mention

    await CallbackQuery.edit_message_text(
        Helper.HELP_SUPPORT.format(bot_mention),
        reply_markup=InlineKeyboardMarkup(BUTTONS.ABUTTON),
    )

@app.on_callback_query(filters.regex("ibot_cb") & ~BANNED_USERS)
async def helper_cb(client, CallbackQuery):
    bot = await client.get_me()
    bot_mention = bot.mention

    await CallbackQuery.edit_message_text(
        Helper.HELP_INFO.format(bot_mention),
        reply_markup=InlineKeyboardMarkup(BUTTONS.INFO_BUTTON),
    )

@app.on_callback_query(filters.regex("back_cb") & ~BANNED_USERS)
async def back_cb(client, CallbackQuery):
    photo = random.choice(START_IMG)
    bot = await client.get_me()
    bot_mention = bot.mention

    await CallbackQuery.edit_message_media(
        media=InputMediaPhoto(
            media=photo,
            caption=Helper.HELP_ABOUT.format(bot_mention)
        ),
        reply_markup=InlineKeyboardMarkup(BUTTONS.INFO_BUTTON)
    )

@app.on_callback_query(filters.regex("help_callback") & ~BANNED_USERS)
@languageCB
async def helper_cb(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    cb = callback_data.split(None, 1)[1]
    keyboard = help_back_markup(_)
    try:
        num = int(cb.replace("hb", ""))
        text = getattr(helpers, f"HELP_{num}")
    except (ValueError, AttributeError):
        return await CallbackQuery.answer()
    try:
        await CallbackQuery.edit_message_text(text, reply_markup=keyboard)
    except MessageNotModified:
        await CallbackQuery.answer()
    except Exception:
        # Help panel photo caption hai (limit 1024 chars). Lamba text (jaise
        # play-info) caption me fit nahi hota -> photo hata ke text bhejo.
        try:
            await CallbackQuery.message.delete()
        except Exception:
            pass
        await client.send_message(
            CallbackQuery.message.chat.id,
            text,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )


# ===========================================================
# ©️ 2025-26 All Rights Reserved by Purvi Bots (Im-Notcoder) 😎
# 
# 🧑‍💻 Developer : t.me/TheSigmaCoder
# 🔗 Source link : GitHub.com/Im-Notcoder/Shivi-V2
# 📢 Telegram channel : t.me/Purvi_Bots
# ===========================================================
