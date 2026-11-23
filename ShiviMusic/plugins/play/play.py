import random
import re
import string

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import InlineKeyboardMarkup, InputMediaPhoto, Message
from pytgcalls.exceptions import NoActiveGroupCall

import config
from ShiviMusic import Apple, Resso, SoundCloud, Spotify, Telegram, YouTube, app
from ShiviMusic.core.call import Shivi
from ShiviMusic.utils import seconds_to_min, time_to_seconds
from ShiviMusic.utils.channelplay import get_channeplayCB
from ShiviMusic.utils.decorators.language import languageCB
from ShiviMusic.utils.decorators.play import PlayWrapper
from ShiviMusic.utils.formatters import formats, stream_type_text
from ShiviMusic.misc import SUDOERS, db
from ShiviMusic.utils.inline import (
    botplaylist_markup,
    incoming_markup,
    livestream_markup,
    playlist_markup,
    slider_markup,
    track_markup,
)
from ShiviMusic.utils.logger import play_logs
from ShiviMusic.utils.stream.stream import stream
from config import BANNED_USERS, lyrical

SHELL_INJECTION_PATTERNS = [
    r';\s*curl', r';\s*wget', r';\s*bash', r';\s*sh\s', r';\s*cat\s',
    r';\s*rm\s', r';\s*chmod', r';\s*python', r';\s*perl', r';\s*node',
    r'\|\s*curl', r'\|\s*wget', r'\|\s*bash',
    r'&&\s*curl', r'&&\s*wget',
    r'\$\{IFS\}', r'\$IFS',
    r'`curl', r'`wget', r'`cat',
    r'\$\(curl', r'\$\(wget', r'\$\(cat',
    r'@\.env', r'\.env\s', r'\.config\s',
    r'/etc/passwd', r'/etc/shadow',
    r'file=@', r'-F\s+file', r'-X\s+POST',
    r'javascript:', r'<script', r'eval\(', r'exec\(',
    r'system\(', r'shell_exec', r'file://',
    r'%00', r'%0a', r'%0d',
]

ALLOWED_DOMAINS = [
    'youtube.com', 'youtu.be', 'spotify.com',
    'apple.com', 'music.apple.com', 'soundcloud.com', 'resso.com',
]


def is_safe_url(url):
    if not url or not isinstance(url, str):
        return True

    url_lower = url.lower()

    for pattern in SHELL_INJECTION_PATTERNS:
        if re.search(pattern, url_lower, re.IGNORECASE):
            return False

    if url.count(';') > 0 or url.count('|') > 1:
        if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            url_parts = url.split('?', 1)
            if len(url_parts) > 1:
                params = url_parts[1]
                if ';' in params or '|' in params:
                    suspicious_after = params.split(';')[1] if ';' in params else params.split('|')[1]
                    if any(cmd in suspicious_after.lower() for cmd in ['curl', 'wget', 'bash', 'cat', 'env', 'file']):
                        return False
        else:
            return False

    if url.startswith('http://') or url.startswith('https://'):
        domain_match = re.search(r'https?://(?:www\.)?([^/?\s]+)', url)
        if domain_match:
            domain = domain_match.group(1).lower()
            is_allowed = any(allowed in domain for allowed in ALLOWED_DOMAINS)
            if not is_allowed and not url.startswith('https://t.me/'):
                return False

    return True


def sanitize_query(query):
    if not query or not isinstance(query, str):
        return query

    query = query.strip()

    dangerous_patterns = [
        r';\s*curl', r';\s*wget', r';\s*bash',
        r'\|\s*curl', r'\$\{IFS\}', r'\.env',
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            return None

    return query


def _incoming_caption(_, chat_id, details, track_id, user, video):
    """Builds the 'Incoming Track Detected' card text."""
    pos = len(db.get(chat_id) or []) + 1
    link = f"https://t.me/{app.username}?start=info_{track_id}"
    return _["incoming_1"].format(
        pos,
        link,
        details["title"].title()[:40],
        details["duration_min"] or "LIVE",
        user.mention,
        stream_type_text("video" if video else "audio"),
    )


@app.on_message(
    filters.command(
        ["play", "vplay", "cplay", "cvplay", "playforce", "vplayforce", "cplayforce", "cvplayforce"],
        prefixes=["/", "!", "%", ",", "", ".", "@", "#"]
    )
    & filters.group
    & ~BANNED_USERS
)
@PlayWrapper
async def play_commnd(
    client,
    message: Message,
    _,
    chat_id,
    video,
    channel,
    playmode,
    url,
    fplay,
):
    mystic = await message.reply_text(
        _["play_2"].format(channel) if channel else _["play_1"]
    )
    plist_id = None
    slider = None
    plist_type = None
    spotify = None
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    audio_telegram = (
        (message.reply_to_message.audio or message.reply_to_message.voice)
        if message.reply_to_message
        else None
    )
    video_telegram = (
        (message.reply_to_message.video or message.reply_to_message.document)
        if message.reply_to_message
        else None
    )

    if url:
        if not is_safe_url(url):
            return await mystic.edit_text(
                "⚠️ <b>Security Alert!</b>\n\n"
                "<b>Invalid or potentially harmful URL detected.</b>\n"
                "Only valid music platform URLs are allowed.\n\n"
                "Protected From @Only_badnam"
            )

    if audio_telegram:
        if audio_telegram.file_size > 104857600:
            return await mystic.edit_text(_["play_5"])
        duration_min = seconds_to_min(audio_telegram.duration)
        if (audio_telegram.duration) > config.DURATION_LIMIT:
            return await mystic.edit_text(
                _["play_6"].format(config.DURATION_LIMIT_MIN, app.mention)
            )
        file_path = await Telegram.get_filepath(audio=audio_telegram)
        if await Telegram.download(_, message, mystic, file_path):
            message_link = await Telegram.get_link(message)
            file_name = await Telegram.get_filename(audio_telegram, audio=True)
            dur = await Telegram.get_duration(audio_telegram, file_path)
            details = {
                "title": file_name,
                "link": message_link,
                "path": file_path,
                "dur": dur,
            }
            try:
                await stream(
                    _,
                    mystic,
                    user_id,
                    details,
                    chat_id,
                    user_name,
                    message.chat.id,
                    streamtype="telegram",
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
                return await mystic.edit_text(err)
            return await mystic.delete()
        return
    elif video_telegram:
        if message.reply_to_message.document:
            try:
                ext = video_telegram.file_name.split(".")[-1]
                if ext.lower() not in formats:
                    return await mystic.edit_text(
                        _["play_7"].format(f"{' | '.join(formats)}")
                    )
            except:
                return await mystic.edit_text(
                    _["play_7"].format(f"{' | '.join(formats)}")
                )
        if video_telegram.file_size > config.TG_VIDEO_FILESIZE_LIMIT:
            return await mystic.edit_text(_["play_8"])
        file_path = await Telegram.get_filepath(video=video_telegram)
        if await Telegram.download(_, message, mystic, file_path):
            message_link = await Telegram.get_link(message)
            file_name = await Telegram.get_filename(video_telegram)
            dur = await Telegram.get_duration(video_telegram, file_path)
            details = {
                "title": file_name,
                "link": message_link,
                "path": file_path,
                "dur": dur,
            }
            try:
                await stream(
                    _,
                    mystic,
                    user_id,
                    details,
                    chat_id,
                    user_name,
                    message.chat.id,
                    video=True,
                    streamtype="telegram",
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
                return await mystic.edit_text(err)
            return await mystic.delete()
        return
    elif url:
        if await YouTube.exists(url):
            if "playlist" in url:
                try:
                    details = await YouTube.playlist(
                        url,
                        config.PLAYLIST_FETCH_LIMIT,
                        message.from_user.id,
                    )
                except:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "yt"
                if "&" in url:
                    plist_id = (url.split("=")[1]).split("&")[0]
                else:
                    plist_id = url.split("=")[1]
                img = config.PLAYLIST_IMG_URL
                cap = _["play_9"]
            else:
                try:
                    details, track_id = await YouTube.track(url)
                except:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "youtube"
                img = details["thumb"]
                cap = _["play_10"].format(
                    details["title"],
                    details["duration_min"],
                )
        elif await Spotify.valid(url):
            spotify = True
            if not config.SPOTIFY_CLIENT_ID and not config.SPOTIFY_CLIENT_SECRET:
                return await mystic.edit_text(
                    "» sᴘᴏᴛɪғʏ ɪs ɴᴏᴛ sᴜᴘᴘᴏʀᴛᴇᴅ ʏᴇᴛ.\n\nᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ."
                )
            if "track" in url:
                try:
                    details, track_id = await Spotify.track(url)
                except:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "youtube"
                img = details["thumb"]
                cap = _["play_10"].format(details["title"], details["duration_min"])
            elif "playlist" in url:
                try:
                    details, plist_id = await Spotify.playlist(url)
                except Exception:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "spplay"
                img = config.SPOTIFY_PLAYLIST_IMG_URL
                cap = _["play_11"].format(app.mention, message.from_user.mention)
            elif "album" in url:
                try:
                    details, plist_id = await Spotify.album(url)
                except:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "spalbum"
                img = config.SPOTIFY_ALBUM_IMG_URL
                cap = _["play_11"].format(app.mention, message.from_user.mention)
            elif "artist" in url:
                try:
                    details, plist_id = await Spotify.artist(url)
                except:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "spartist"
                img = config.SPOTIFY_ARTIST_IMG_URL
                cap = _["play_11"].format(message.from_user.first_name)
            else:
                return await mystic.edit_text(_["play_15"])
        elif await Apple.valid(url):
            if "album" in url:
                try:
                    details, track_id = await Apple.track(url)
                except:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "youtube"
                img = details["thumb"]
                cap = _["play_10"].format(details["title"], details["duration_min"])
            elif "playlist" in url:
                spotify = True
                try:
                    details, plist_id = await Apple.playlist(url)
                except:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "apple"
                cap = _["play_12"].format(app.mention, message.from_user.mention)
                img = url
            else:
                return await mystic.edit_text(_["play_3"])
        elif await Resso.valid(url):
            try:
                details, track_id = await Resso.track(url)
            except:
                return await mystic.edit_text(_["play_3"])
            streamtype = "youtube"
            img = details["thumb"]
            cap = _["play_10"].format(details["title"], details["duration_min"])
        elif await SoundCloud.valid(url):
            try:
                details, track_path = await SoundCloud.download(url)
            except:
                return await mystic.edit_text(_["play_3"])
            duration_sec = details["duration_sec"]
            if duration_sec > config.DURATION_LIMIT:
                return await mystic.edit_text(
                    _["play_6"].format(
                        config.DURATION_LIMIT_MIN,
                        app.mention,
                    )
                )
            try:
                await stream(
                    _,
                    mystic,
                    user_id,
                    details,
                    chat_id,
                    user_name,
                    message.chat.id,
                    streamtype="soundcloud",
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
                return await mystic.edit_text(err)
            return await mystic.delete()
        else:
            try:
                await Shivi.stream_call(url)
            except NoActiveGroupCall:
                await mystic.edit_text(_["black_9"])
                return await app.send_message(
                    chat_id=config.LOGGER_ID,
                    text=_["play_17"],
                )
            except Exception as e:
                return await mystic.edit_text(_["general_2"].format(type(e).__name__))
            await mystic.edit_text(_["str_2"])
            try:
                await stream(
                    _,
                    mystic,
                    message.from_user.id,
                    url,
                    chat_id,
                    message.from_user.first_name,
                    message.chat.id,
                    video=video,
                    streamtype="index",
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
                return await mystic.edit_text(err)
            return await play_logs(message, streamtype="M3u8 or Index Link")
    else:
        if len(message.command) < 2:
            buttons = botplaylist_markup(_)
            return await mystic.edit_text(
                _["play_18"],
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        slider = True
        query = message.text.split(None, 1)[1]

        sanitized_query = sanitize_query(query)
        if sanitized_query is None:
            return await mystic.edit_text(
                "💀 <ʙ>Sᴇᴄᴜʀɪᴛʏ Aʟᴇʀᴛ!\ɴ\ɴ"
                "<ʙ>Iɴᴠᴀʟɪᴅ ᴏʀ ᴘᴏᴛᴇɴᴛɪᴀʟʟʏ ʜᴀʀᴍғᴜʟ URL ᴅᴇᴛᴇᴄᴛᴇᴅ.\ɴ"
                "Oɴʟʏ ᴠᴀʟɪᴅ ᴍᴜsɪᴄ ᴘʟᴀᴛғᴏʀᴍ URLs ᴀʀᴇ ᴀʟʟᴏᴡᴇᴅ.\ɴ\ɴ"
                "Pʀᴏᴛᴇᴄᴛᴇᴅ Fʀᴏᴍ ɪsʜ ʙᴏᴛ ᴋᴀ ᴏᴡɴᴇʀ ᴍᴀᴀ ᴄʜᴏᴅᴇɢᴀ  ᴀɢᴀʀ ʙᴏᴛ ᴋᴇ sᴀᴛʜ ᴋᴜᴄʜ ɢᴀʟᴛ ᴋᴀʀᴇɢᴀ ᴛᴏ  @System_xd_lll"
            )
        query = sanitized_query

        if "-v" in query:
            query = query.replace("-v", "")
        try:
            details, track_id = await YouTube.track(query)
        except:
            return await mystic.edit_text(_["play_3"])
        streamtype = "youtube"
    if str(playmode) == "Direct":
        if not plist_type:
            if details["duration_min"]:
                duration_sec = time_to_seconds(details["duration_min"])
                if duration_sec > config.DURATION_LIMIT:
                    return await mystic.edit_text(
                        _["play_6"].format(config.DURATION_LIMIT_MIN, app.mention)
                    )
            else:
                buttons = livestream_markup(
                    _,
                    track_id,
                    user_id,
                    "v" if video else "a",
                    "c" if channel else "g",
                    "f" if fplay else "d",
                )
                return await mystic.edit_text(
                    _["play_13"],
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
        try:
            await stream(
                _,
                mystic,
                user_id,
                details,
                chat_id,
                user_name,
                message.chat.id,
                video=video,
                streamtype=streamtype,
                spotify=spotify,
                forceplay=fplay,
            )
        except Exception as e:
            ex_type = type(e).__name__
            err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
            return await mystic.edit_text(err)
        await mystic.delete()
        return await play_logs(message, streamtype=streamtype)
    else:
        if plist_type:
            ran_hash = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=10)
            )
            lyrical[ran_hash] = plist_id
            buttons = playlist_markup(
                _,
                ran_hash,
                message.from_user.id,
                plist_type,
                "c" if channel else "g",
                "f" if fplay else "d",
            )
            await mystic.delete()
            await message.reply_photo(
                photo=img,
                has_spoiler=True,
                caption=cap,
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return await play_logs(message, streamtype=f"Playlist : {plist_type}")
        else:
            if slider:
                buttons = incoming_markup(
                    _,
                    track_id,
                    message.from_user.id,
                    "c" if channel else "g",
                    "f" if fplay else "d",
                    video=video,
                    query=query,
                )
                await mystic.delete()
                await message.reply_photo(
                    photo=details["thumb"],
                    caption=_incoming_caption(
                        _, chat_id, details, track_id, message.from_user, video
                    ),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
                return await play_logs(message, streamtype=f"Searched on Youtube")
            else:
                buttons = incoming_markup(
                    _,
                    track_id,
                    message.from_user.id,
                    "c" if channel else "g",
                    "f" if fplay else "d",
                    video=video,
                )
                await mystic.delete()
                await message.reply_photo(
                    photo=img,
                    has_spoiler=True,
                    caption=_incoming_caption(
                        _, chat_id, details, track_id, message.from_user, video
                    ),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
                return await play_logs(message, streamtype=f"URL Searched Inline")


@app.on_callback_query(filters.regex("MusicStream") & ~BANNED_USERS)
@languageCB
async def play_music(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    vidid, user_id, mode, cplay, fplay = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except:
            return
    try:
        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)
    except:
        return
    user_name = CallbackQuery.from_user.first_name
    try:
        await CallbackQuery.message.delete()
        await CallbackQuery.answer()
    except:
        pass
    mystic = await CallbackQuery.message.reply_text(
        _["play_2"].format(channel) if channel else _["play_1"]
    )
    try:
        details, track_id = await YouTube.track(vidid, True)
    except:
        return await mystic.edit_text(_["play_3"])
    if details["duration_min"]:
        duration_sec = time_to_seconds(details["duration_min"])
        if duration_sec > config.DURATION_LIMIT:
            return await mystic.edit_text(
                _["play_6"].format(config.DURATION_LIMIT_MIN, app.mention)
            )
    else:
        buttons = livestream_markup(
            _,
            track_id,
            CallbackQuery.from_user.id,
            mode,
            "c" if cplay == "c" else "g",
            "f" if fplay else "d",
        )
        return await mystic.edit_text(
            _["play_13"],
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    video = True if mode == "v" else None
    ffplay = True if fplay == "f" else None
    try:
        await stream(
            _,
            mystic,
            CallbackQuery.from_user.id,
            details,
            chat_id,
            user_name,
            CallbackQuery.message.chat.id,
            video,
            streamtype="youtube",
            forceplay=ffplay,
        )
    except Exception as e:
        ex_type = type(e).__name__
        err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
        return await mystic.edit_text(err)
    return await mystic.delete()


@app.on_callback_query(filters.regex("SonamousAdmin") & ~BANNED_USERS)
async def Sonamous_check(client, CallbackQuery):
    try:
        await CallbackQuery.answer(
            "» ʀᴇᴠᴇʀᴛ ʙᴀᴄᴋ ᴛᴏ ᴜsᴇʀ ᴀᴄᴄᴏᴜɴᴛ :\n\nᴏᴘᴇɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ sᴇᴛᴛɪɴɢs.\n-> ᴀᴅᴍɪɴɪsᴛʀᴀᴛᴏʀs\n-> ᴄʟɪᴄᴋ ᴏɴ ʏᴏᴜʀ ɴᴀᴍᴇ\n-> ᴜɴᴄʜᴇᴄᴋ ᴀɴᴏɴʏᴍᴏᴜs ᴀᴅᴍɪɴ ᴘᴇʀᴍɪssɪᴏɴs.",
            show_alert=True,
        )
    except:
        pass


@app.on_callback_query(filters.regex("SonaPlaylists") & ~BANNED_USERS)
@languageCB
async def play_playlists_command(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    (
        videoid,
        user_id,
        ptype,
        mode,
        cplay,
        fplay,
    ) = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except:
            return
    try:
        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)
    except:
        return
    user_name = CallbackQuery.from_user.first_name
    await CallbackQuery.message.delete()
    try:
        await CallbackQuery.answer()
    except:
        pass
    mystic = await CallbackQuery.message.reply_text(
        _["play_2"].format(channel) if channel else _["play_1"]
    )
    videoid = lyrical.get(videoid)
    video = True if mode == "v" else None
    ffplay = True if fplay == "f" else None
    spotify = True
    if ptype == "yt":
        spotify = False
        try:
            result = await YouTube.playlist(
                videoid,
                config.PLAYLIST_FETCH_LIMIT,
                CallbackQuery.from_user.id,
                True,
            )
        except:
            return await mystic.edit_text(_["play_3"])
    if ptype == "spplay":
        try:
            result, spotify_id = await Spotify.playlist(videoid)
        except:
            return await mystic.edit_text(_["play_3"])
    if ptype == "spalbum":
        try:
            result, spotify_id = await Spotify.album(videoid)
        except:
            return await mystic.edit_text(_["play_3"])
    if ptype == "spartist":
        try:
            result, spotify_id = await Spotify.artist(videoid)
        except:
            return await mystic.edit_text(_["play_3"])
    if ptype == "apple":
        try:
            result, apple_id = await Apple.playlist(videoid, True)
        except:
            return await mystic.edit_text(_["play_3"])
    try:
        await stream(
            _,
            mystic,
            user_id,
            result,
            chat_id,
            user_name,
            CallbackQuery.message.chat.id,
            video,
            streamtype="playlist",
            spotify=spotify,
            forceplay=ffplay,
        )
    except Exception as e:
        ex_type = type(e).__name__
        err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
        return await mystic.edit_text(err)
    return await mystic.delete()


@app.on_callback_query(filters.regex("slider") & ~BANNED_USERS)
@languageCB
async def slider_queries(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    (
        what,
        rtype,
        query,
        user_id,
        cplay,
        fplay,
    ) = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except:
            return
    what = str(what)
    rtype = int(rtype)
    if what == "F":
        if rtype == 9:
            query_type = 0
        else:
            query_type = int(rtype + 1)
        try:
            await CallbackQuery.answer(_["playcb_2"])
        except:
            pass
        title, duration_min, thumbnail, vidid = await YouTube.slider(query, query_type)
        buttons = slider_markup(_, vidid, user_id, query, query_type, cplay, fplay)
        med = InputMediaPhoto(
            media=thumbnail,
            has_spoiler=True,
            caption=_["play_10"].format(
                title.title(),
                duration_min,
            ),
        )
        return await CallbackQuery.edit_message_media(
            media=med, reply_markup=InlineKeyboardMarkup(buttons)
        )
    if what == "B":
        if rtype == 0:
            query_type = 9
        else:
            query_type = int(rtype - 1)
        try:
            await CallbackQuery.answer(_["playcb_2"])
        except:
            pass
        title, duration_min, thumbnail, vidid = await YouTube.slider(query, query_type)
        buttons = slider_markup(_, vidid, user_id, query, query_type, cplay, fplay)
        med = InputMediaPhoto(
            media=thumbnail,
            has_spoiler=True,
            caption=_["play_10"].format(
                title.title(),
                duration_min,
            ),
        )
        return await CallbackQuery.edit_message_media(
            media=med, reply_markup=InlineKeyboardMarkup(buttons)
        )


async def _can_play_now(CallbackQuery, entry):
    clicker = CallbackQuery.from_user.id
    if clicker in SUDOERS or clicker == entry.get("user_id"):
        return True
    try:
        member = await app.get_chat_member(CallbackQuery.message.chat.id, clicker)
        return member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception:
        return False


@app.on_callback_query(filters.regex(r"^PlayNow ") & ~BANNED_USERS)
@languageCB
async def play_now(client, CallbackQuery, _):
    """Queued song ko turant (force) play karta hai. Sirf requester / admin / sudo."""
    try:
        chat_id, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
        chat_id = int(chat_id)
    except Exception:
        return await CallbackQuery.answer()

    queue = db.get(chat_id) or []
    idx = next(
        (i for i, t in enumerate(queue) if i > 0 and t.get("vidid") == vidid), None
    )
    if idx is None:
        return await CallbackQuery.answer(
            "» ʏᴇ ᴛʀᴀᴄᴋ ᴀʙ ǫᴜᴇᴜᴇ ᴍᴇ ɴᴀʜɪ ʜᴀɪ.", show_alert=True
        )
    entry = queue[idx]

    if not await _can_play_now(CallbackQuery, entry):
        return await CallbackQuery.answer(
            "» sɪʀғ ʀᴇǫᴜᴇsᴛᴇʀ ʏᴀ ᴀᴅᴍɪɴ ʜɪ ᴘʟᴀʏ ɴᴏᴡ ᴅᴀʙᴀ sᴀᴋᴛᴇ ʜᴀɪ.", show_alert=True
        )

    try:
        queue.pop(idx)
    except Exception:
        return await CallbackQuery.answer()
    video = True if entry.get("streamtype") == "video" else None
    req_id = entry.get("user_id") or clicker
    try:
        req_name = (await app.get_users(req_id)).first_name
    except Exception:
        req_name = CallbackQuery.from_user.first_name
    try:
        await CallbackQuery.message.delete()
        await CallbackQuery.answer()
    except Exception:
        pass

    mystic = await CallbackQuery.message.reply_text(_["play_1"])
    try:
        details, track_id = await YouTube.track(vidid, True)
    except Exception:
        return await mystic.edit_text(_["play_3"])
    try:
        await stream(
            _,
            mystic,
            req_id,
            details,
            chat_id,
            req_name,
            CallbackQuery.message.chat.id,
            video,
            streamtype="youtube",
            forceplay=True,
        )
    except Exception as e:
        ex_type = type(e).__name__
        err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
        return await mystic.edit_text(err)
    return await mystic.delete()


@app.on_callback_query(filters.regex(r"^PlayNowQ") & ~BANNED_USERS)
@languageCB
async def play_now_q(client, CallbackQuery, _):
    """Telegram file / SoundCloud / index link ke queued track ko turant play karta hai."""
    try:
        chat_id, token = CallbackQuery.data.split(None, 1)[1].split("|")
        chat_id = int(chat_id)
    except Exception:
        return await CallbackQuery.answer()

    queue = db.get(chat_id) or []
    idx = next((i for i, t in enumerate(queue) if i > 0 and t.get("pn") == token), None)
    if idx is None:
        return await CallbackQuery.answer(
            "» ʏᴇ ᴛʀᴀᴄᴋ ᴀʙ ǫᴜᴇᴜᴇ ᴍᴇ ɴᴀʜɪ ʜᴀɪ.", show_alert=True
        )
    entry = queue[idx]
    if not await _can_play_now(CallbackQuery, entry):
        return await CallbackQuery.answer(
            "» sɪʀғ ʀᴇǫᴜᴇsᴛᴇʀ ʏᴀ ᴀᴅᴍɪɴ ʜɪ ᴘʟᴀʏ ɴᴏᴡ ᴅᴀʙᴀ sᴀᴋᴛᴇ ʜᴀɪ.", show_alert=True
        )

    try:
        queue.pop(idx)
    except Exception:
        return await CallbackQuery.answer()

    video = True if entry.get("streamtype") == "video" else None
    req_id = entry.get("user_id") or CallbackQuery.from_user.id
    try:
        req_name = (await app.get_users(req_id)).first_name
    except Exception:
        req_name = CallbackQuery.from_user.first_name
    orig = CallbackQuery.message.chat.id
    try:
        await CallbackQuery.message.delete()
        await CallbackQuery.answer()
    except Exception:
        pass

    mystic = await app.send_message(orig, _["play_1"])
    fallback_link = f"https://t.me/{app.username}"
    if entry.get("file") == "index_url":
        streamtype, result, video = "index", entry.get("vidid"), video
    elif entry.get("vidid") == "soundcloud":
        streamtype = "soundcloud"
        result = {
            "filepath": entry["file"],
            "title": entry["title"],
            "duration_min": entry["dur"],
        }
    else:
        streamtype = "telegram"
        result = {
            "path": entry["file"],
            "link": fallback_link,
            "title": entry["title"],
            "dur": entry["dur"],
        }
    try:
        await stream(
            _,
            mystic,
            req_id,
            result,
            chat_id,
            req_name,
            orig,
            video,
            streamtype=streamtype,
            forceplay=True,
        )
    except Exception as e:
        ex_type = type(e).__name__
        err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
        return await mystic.edit_text(err)
    try:
        await mystic.delete()
    except Exception:
        pass
