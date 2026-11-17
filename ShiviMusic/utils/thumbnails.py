import asyncio
import os
import re
import time
from functools import lru_cache

import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance
from py_yt import VideosSearch
from config import YOUTUBE_IMG_URL

# ----------------------------------------------------------------------------
#  PATHS  (absolute, so fonts load no matter where the bot is started from)
# ----------------------------------------------------------------------------
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../ShiviMusic
ASSETS_DIR = os.path.join(_BASE_DIR, "assets")

# Honey Salt (handwritten) -> song title
FONT_TITLE = os.path.join(ASSETS_DIR, "f.ttf")
# Poppins SemiBold -> everything else
FONT_BODY = os.path.join(ASSETS_DIR, "font.ttf")

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# ----------------------------------------------------------------------------
#  EDIT THESE TWO LINES
# ----------------------------------------------------------------------------
PLAYER_TAG = "@SonaliMusicBot"   # "Player : ...."  (left side)
CREDIT_TAG = "@PurviBots"        # "By : ...."      (bottom right)

# ----------------------------------------------------------------------------
#  DESIGN CONSTANTS (1280 x 720)
# ----------------------------------------------------------------------------
W, H = 1280, 720
ORANGE = (255, 140, 0, 255)
WHITE = (255, 255, 255, 255)
SOFT_WHITE = (235, 235, 243, 255)
SOFT_GREY = (218, 214, 224, 255)
YELLOW = (255, 252, 0, 255)
PILL_TEXT = (20, 20, 20, 255)
TRACK = (100, 101, 122, 255)

LEFT_X = 80
BAR_X0, BAR_X1 = 80, 511
BAR_Y = 490           # centre line of the progress bar
BAR_H = 8
KNOB_R = 12

# album-art card
RING_BOX = (641, 106, 1228, 593)
RING_RADIUS = 38
RING_WIDTH = 8
ART_BOX = (660, 125, 1210, 575)   # 550 x 450
ART_RADIUS = 18

MAX_TITLE_WIDTH = 500


def trim_text(text, font, max_width):
    try:
        if font.getlength(text) <= max_width:
            return text
        for i in range(len(text) - 1, 0, -1):
            cand = text[:i].rstrip() + "..."
            if font.getlength(cand) <= max_width:
                return cand
        return "..."
    except Exception:
        return text[:40]


@lru_cache(maxsize=32)
def _font(path, size):
    """Load a TTF safely. Falls back to a bundled / system font, never crashes."""
    for p in (path, FONT_BODY, "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _latin(text, default=""):
    """Handwritten title font only has Latin glyphs -> transliterate Hindi etc."""
    text = str(text or "")
    try:
        from unidecode import unidecode
        text = unidecode(text)
    except Exception:
        text = text.encode("ascii", "ignore").decode()
    text = re.sub(r"\s+", " ", text).strip()
    if not re.search(r"\w", text):  # nothing readable left (only symbols / empty)
        return default
    return text


def _wrap_title(title, font, max_width, max_lines=2):
    """Word-wrap into max_lines; last line gets '...' if text is cut."""
    words = title.split()
    lines, cur = [], ""
    for i, w in enumerate(words):
        test = (cur + " " + w).strip()
        if font.getlength(test) <= max_width:
            cur = test
            continue
        if cur:
            lines.append(cur)
        cur = w
        if len(lines) == max_lines - 1:
            cur = " ".join(words[i:])
            break
    if cur:
        lines.append(cur)
    lines = lines[:max_lines]
    if lines:
        lines[-1] = trim_text(lines[-1], font, max_width)
        # a single huge word on a non-last line
        lines = [trim_text(l, font, max_width) for l in lines]
    return lines


def _fmt_views(views):
    v = str(views or "").strip()
    v = re.sub(r"(?i)\s*views?\s*$", "", v).strip()
    return v or "Unknown"


def _to_seconds(duration):
    try:
        parts = [int(x) for x in str(duration).split(":")]
        return sum(n * 60 ** i for i, n in enumerate(reversed(parts)))
    except Exception:
        return 0


DIRECT_THUMB_FALLBACK = "https://i.ytimg.com/vi/{videoid}/hqdefault.jpg"


_META_CACHE = {}
_SESSION = None


def _get_session():
    global _SESSION
    if _SESSION is None or _SESSION.closed:
        _SESSION = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=50, ttl_dns_cache=300)
        )
    return _SESSION


def _prune_cache(max_age: int = 1800):
    """Purani generated images delete karo taaki disk na bhare."""
    try:
        now = time.time()
        for name in os.listdir(CACHE_DIR):
            fp = os.path.join(CACHE_DIR, name)
            try:
                if now - os.path.getmtime(fp) > max_age:
                    os.remove(fp)
            except Exception:
                pass
    except Exception:
        pass


async def _fetch_meta_via_search(videoid: str):
    hit = _META_CACHE.get(videoid)
    if hit and time.time() - hit[0] < 900:
        return hit[1]
    meta = await _fetch_meta_via_search_uncached(videoid)
    if meta:
        if len(_META_CACHE) > 300:
            _META_CACHE.clear()
        _META_CACHE[videoid] = (time.time(), meta)
    return meta


async def _fetch_meta_via_search_uncached(videoid: str):
    """Try to get title/thumb/duration/views/channel via py_yt search.
    Verifies the returned result's own id actually matches videoid,
    since VideosSearch is a text-search API, not an exact lookup —
    it can occasionally return an unrelated video."""
    for _attempt in range(2):
        try:
            results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
            results_data = await results.next()
            data = results_data.get("result", [{}])[0]

            fetched_id = data.get("id") or data.get("videoId")
            if fetched_id and fetched_id != videoid:
                # search drifted to a different video — don't trust it, retry once
                continue

            title = re.sub(r"\W+", " ", data.get("title", "Song")).title()
            thumbnail_url = data.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
            duration = data.get("duration")
            views = data.get("viewCount", {}).get("short", "Unknown")
            channel = data.get("channel", {}).get("name", "YouTube")
            if thumbnail_url:
                return title, thumbnail_url, duration, views, channel
        except Exception:
            pass
    return None


def _compose(src_path, out_path, title, channel, views, duration, progress_percent):
    """Draw the 'NOW PLAYING' card. Blocking -> run it in an executor."""
    S = 2  # supersampling for smooth edges

    progress = max(0, min(100, int(progress_percent or 0)))
    is_live = not duration or str(duration).strip().lower() in {"", "live"}
    total_seconds = 0 if is_live else _to_seconds(duration)
    cur = int(total_seconds * progress / 100)
    cur_txt = f"{cur // 60}:{cur % 60:02d}"
    total_txt = "LIVE" if is_live else str(duration)

    title = _latin(title, "Unknown Song")
    channel = _latin(channel, "YouTube")
    views = _fmt_views(views)

    # ------------------------------------------------------------ source image
    src = Image.open(src_path).convert("RGB")
    iw, ih = src.size
    if ih / iw > 0.6:  # hqdefault has black bars -> cut to real 16:9 picture
        ch = int(iw * 9 / 16)
        top = (ih - ch) // 2
        src = src.crop((0, top, iw, top + ch))

    # -------------------------------------------------------------- background
    bg = src.resize((160, 90), Image.BICUBIC).filter(ImageFilter.GaussianBlur(3))
    bg = bg.resize((W, H), Image.BICUBIC)
    bg = ImageEnhance.Color(bg).enhance(0.8)
    bg = ImageEnhance.Brightness(bg).enhance(0.48).convert("RGBA")
    # soft vignette (dark corners)
    vig = Image.radial_gradient("L").resize((W, H), Image.BICUBIC)
    vig = vig.point(lambda v: int(v * 0.55))
    bg = Image.composite(Image.new("RGBA", (W, H), (0, 0, 0, 255)), bg, vig)

    # ------------------------------------------------------- orange neon glow
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle(
        RING_BOX, radius=RING_RADIUS, outline=ORANGE, width=RING_WIDTH + 4
    )
    glow = glow.filter(ImageFilter.GaussianBlur(16))
    r_, g_, b_, a_ = glow.split()
    a_ = a_.point(lambda v: min(255, int(v * 2.2)))
    glow = Image.merge("RGBA", (r_, g_, b_, a_))
    bg = Image.alpha_composite(bg, glow)

    # --------------------------------------------------------------- album art
    ax0, ay0, ax1, ay1 = ART_BOX
    aw, ah = ax1 - ax0 + 1, ay1 - ay0 + 1
    art = src.resize((aw, ah), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (aw * S, ah * S), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, aw * S - 1, ah * S - 1), radius=ART_RADIUS * S, fill=255
    )
    mask = mask.resize((aw, ah), Image.LANCZOS)
    bg.paste(art, (ax0, ay0), mask)

    # ------------------------------------------------------------- UI layers
    ui = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    sh = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(ui)
    ds = ImageDraw.Draw(sh)

    def sc(v):
        return int(round(v * S))

    def rrect(x0, y0, x1, y1, r, fill):
        d.rounded_rectangle((sc(x0), sc(y0), sc(x1 + 1) - 1, sc(y1 + 1) - 1),
                            radius=sc(r), fill=fill)

    def txt(x, y, s, font, fill, anchor="ls", shadow=True):
        if shadow:
            ds.text((sc(x), sc(y + 3)), s, font=font, fill=(0, 0, 0, 175), anchor=anchor)
        d.text((sc(x), sc(y)), s, font=font, fill=fill, anchor=anchor)

    f_pill = _font(FONT_BODY, 27 * S)
    f_title = _font(FONT_TITLE, 63 * S)
    f_chan = _font(FONT_BODY, 39 * S)
    f_meta = _font(FONT_BODY, 29 * S)
    f_time = _font(FONT_BODY, 20 * S)
    f_by = _font(FONT_BODY, 24 * S)

    # card ring (crisp)
    d.rounded_rectangle(
        (sc(RING_BOX[0]), sc(RING_BOX[1]), sc(RING_BOX[2] + 1) - 1, sc(RING_BOX[3] + 1) - 1),
        radius=sc(RING_RADIUS), outline=ORANGE, width=sc(RING_WIDTH),
    )

    # NOW PLAYING pill
    rrect(80, 116, 325, 153, 19, ORANGE)
    txt(203, 144, "NOW PLAYING", f_pill, PILL_TEXT, anchor="ms", shadow=False)

    # title (max 2 lines)
    lines = _wrap_title(title, f_title, MAX_TITLE_WIDTH * S, 2)
    for i, line in enumerate(lines):
        txt(LEFT_X, 235 + i * 76, line, f_title, WHITE)

    # orange underline
    rrect(80, 336, 180, 341, 3, ORANGE)

    # channel + views | duration
    txt(LEFT_X, 405, trim_text(channel, f_chan, 430 * S), f_chan, SOFT_WHITE)
    meta = f"{views} Views  |  " + ("LIVE" if is_live else f"{duration} Minutes")
    txt(LEFT_X, 441, trim_text(meta, f_meta, 440 * S), f_meta, SOFT_WHITE)

    # progress bar + knob
    p = 1.0 if is_live else progress / 100.0
    kx = BAR_X0 + (BAR_X1 - BAR_X0) * p
    rrect(BAR_X0, BAR_Y - 4, BAR_X1, BAR_Y + 4, 4, TRACK)
    rrect(BAR_X0, BAR_Y - 4, max(BAR_X0 + 8, kx), BAR_Y + 4, 4, ORANGE)
    ds.ellipse((sc(kx - KNOB_R), sc(BAR_Y - KNOB_R + 3), sc(kx + KNOB_R), sc(BAR_Y + KNOB_R + 3)),
               fill=(0, 0, 0, 150))
    d.ellipse((sc(kx - KNOB_R), sc(BAR_Y - KNOB_R), sc(kx + KNOB_R), sc(BAR_Y + KNOB_R)),
              fill=WHITE)

    # times
    txt(LEFT_X, 531, cur_txt, f_time, SOFT_WHITE)
    txt(BAR_X1, 531, total_txt, f_time, SOFT_WHITE, anchor="rs")

    # player tag + credit
    txt(LEFT_X, 583, f"Player : {PLAYER_TAG}", f_meta, SOFT_GREY)
    txt(1255, 694, f"By : {CREDIT_TAG}", f_by, YELLOW, anchor="rs")

    # ------------------------------------------------------------- final merge
    sh = sh.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(4))
    ui = ui.resize((W, H), Image.LANCZOS)
    out = Image.alpha_composite(bg, sh)
    out = Image.alpha_composite(out, ui).convert("RGB")
    out.save(out_path, "PNG", compress_level=1)


async def get_thumb(videoid: str, progress_percent: int = 0, use_cache: bool = True, user_name: str = "Badnam") -> str:
    # user_name is kept only so old calls keep working (new design has no "requested by")
    use_cache = False

    timestamp = int(time.time()) if not use_cache else 0
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_p{progress_percent}_t{timestamp}.png")

    if use_cache and os.path.exists(cache_path):
        return cache_path

    thumb_path = os.path.join(CACHE_DIR, f"thumb_{videoid}_{timestamp}.png")

    meta = await _fetch_meta_via_search(videoid)
    if meta:
        title, thumbnail_url, duration, views, channel = meta
    else:
        # search failed / drifted -> YouTube CDN thumbnail keyed by videoid
        title, thumbnail_url, duration, views, channel = (
            "Song", DIRECT_THUMB_FALLBACK.format(videoid=videoid), None, "Unknown", "YouTube"
        )

    downloaded = False
    for url in (thumbnail_url, DIRECT_THUMB_FALLBACK.format(videoid=videoid)):
        try:
            session = _get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    async with aiofiles.open(thumb_path, "wb") as f:
                        await f.write(await resp.read())
                    downloaded = True
                    break
        except Exception:
            continue

    if not downloaded:
        return YOUTUBE_IMG_URL

    def _render():
        try:
            _compose(thumb_path, cache_path, title, channel, views, duration, progress_percent)
            return cache_path
        except Exception as e:
            import traceback
            print(f"Thumbnail error: {e}")
            traceback.print_exc()
            return YOUTUBE_IMG_URL
        finally:
            try:
                if os.path.exists(thumb_path):
                    os.remove(thumb_path)
            except Exception:
                pass

    result = await asyncio.get_running_loop().run_in_executor(None, _render)
    _prune_cache()
    return result
