# ===========================================================
# ©️ 2025-26 All Rights Reserved by Purvi Bots (Im-Notcoder) 🚀
# 
# This source code is under MIT License 📜
# ❌ Unauthorized forking, importing, or using this code
#    without giving proper credit will result in legal action ⚠️
# 
# 📩 DM for permission : @TheSigmaCoder
# ===========================================================

from pyrogram import Client, errors
from pyrogram.enums import ChatMemberStatus, ParseMode

import config

from ..logging import LOGGER


class Shivi(Client):
    def __init__(self):
        LOGGER(__name__).info(f"» sᴛᴀʀᴛɪɴɢ ʙᴏᴛ...")
        super().__init__(
            name="ShiviMusic",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            in_memory=True,
            max_concurrent_transmissions=7,
        )

    async def send_photo(self, chat_id, photo, *args, **kwargs):
        """Agar chat me /thumb disable hai to song thumbnail wale (stream) messages
        photo ki jagah sirf text me bhejo. Baaki photos (start/help) normal jaate hain."""
        try:
            if await self._thumb_disabled_for(chat_id, photo, kwargs.get("reply_markup")):
                text = kwargs.get("caption") or "\u200b"
                extra = {
                    k: v
                    for k, v in kwargs.items()
                    if k in ("parse_mode", "reply_markup", "reply_parameters",
                             "message_thread_id", "disable_notification",
                             "reply_to_message_id", "schedule_date", "protect_content",
                             "message_effect_id")
                }
                return await self.send_message(chat_id, text, **extra)
        except Exception:
            pass
        return await super().send_photo(chat_id, photo, *args, **kwargs)

    @staticmethod
    def _is_stream_photo(photo, markup) -> bool:
        if isinstance(photo, str) and photo.replace("\\", "/").startswith("cache/"):
            return True
        try:
            for row in markup.inline_keyboard:
                for b in row:
                    if str(getattr(b, "callback_data", "")).startswith("ADMIN "):
                        return True
        except Exception:
            pass
        return False

    async def _thumb_disabled_for(self, chat_id, photo, markup) -> bool:
        if not self._is_stream_photo(photo, markup):
            return False
        from ShiviMusic.utils.database import is_thumb_on

        try:
            return not await is_thumb_on(chat_id)
        except Exception:
            return False

    async def start(self):
        import asyncio

        last_err = None
        for attempt in range(1, 4):
            try:
                await super().start()
                last_err = None
                break
            except errors.AccessTokenInvalid:
                LOGGER(__name__).error("» BOT_TOKEN galat hai, BotFather se naya token lo.")
                raise SystemExit(1)
            except errors.ApiIdInvalid:
                LOGGER(__name__).error("» API_ID / API_HASH galat hain (my.telegram.org).")
                raise SystemExit(1)
            except (TimeoutError, ConnectionError, OSError) as e:
                last_err = e
                LOGGER(__name__).warning(
                    f"» Telegram login timeout (try {attempt}/3): {e}"
                )
                try:
                    await super().stop()
                except Exception:
                    pass
                await asyncio.sleep(5 * attempt)
        if last_err is not None:
            LOGGER(__name__).error(
                "» Telegram se connect nahi ho paya. Check karo: BOT_TOKEN, "
                "API_ID/API_HASH (apne khud ke), aur ki same BOT_TOKEN kisi aur "
                "jagah to run nahi ho raha."
            )
            raise SystemExit(1)
        self.id = self.me.id
        self.name = self.me.first_name + " " + (self.me.last_name or "")
        self.username = self.me.username
        self.mention = self.me.mention

        a = await self.get_chat_member(config.LOGGER_ID, self.id)
        if a.status != ChatMemberStatus.ADMINISTRATOR:
            LOGGER(__name__).error(
                "» ᴘʟᴇᴀsᴇ ᴘʀᴏᴍᴏᴛᴇ ʏᴏᴜʀ ʙᴏᴛ ᴀs ᴀɴ ᴀᴅᴍɪɴ ɪɴ ʏᴏᴜʀ ʟᴏɢ ɢʀᴏᴜᴘ/ᴄʜᴀɴɴᴇʟ."
            )
        LOGGER(__name__).info(f"✦ ᴍᴜsɪᴄ ʙᴏᴛ sᴛᴀʀᴛᴇᴅ ᴀs {self.name}")

    async def stop(self):
        await super().stop()

# ===========================================================
# ©️ 2025-26 All Rights Reserved by Purvi Bots (Im-Notcoder) 😎
# 
# 🧑‍💻 Developer : t.me/TheSigmaCoder
# 🔗 Source link : GitHub.com/Im-Notcoder/Shivi-V2
# 📢 Telegram channel : t.me/Purvi_Bots
# ===========================================================
