# ===========================================================
# 🖼 NOW PLAYING THUMBNAIL — "NOW PLAYING" orange card design
#
# Design: blur background, left me NOW PLAYING pill + title (2 line)
# + channel + views/duration + progress bar + Player name,
# right me orange glow frame ke andar song ki image, neeche
# right me "By : @..." (yellow).
#
# Use:
#   from ShiviMusic.utils.thumbnails import get_thumb
#   thumb = await get_thumb(videoid)
#
# 🔤 TITLE FONT: assets/f.ttf (Honey Salt) -> screenshot jaisa handwriting.
# Agar exact font chahiye to usko ShiviMusic/assets/title_font.ttf
# naam se rakh do, wahi sabse pehle use hoga.
# ===========================================================

import asyncio
import glob
import io
import os
import random
import traceback

import aiohttp
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1280, 720
BLUR_RADIUS = 30
ORANGE = (255, 140, 0, 255)
BY_TEXT = "By : @kirti_bots"  # neeche right me yellow text
BY_COLOR = (255, 238, 0, 255)

_ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")


def _a(name):
    return os.path.join(_ASSETS, name)


# Title font (pehli mili hui file use hoti hai)
_TITLE_FONTS = [
    _a("title_font.ttf"),
    _a("f.ttf"),  # Honey Salt
    _a("fonts.ttf"),  # Boogaloo
    _a("font.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_BOLD_FONTS = [
    _a("Poppins-Bold.ttf"),
    _a("font.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_MED_FONTS = [
    _a("Poppins-Medium.ttf"),
    _a("font.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


_SAFE_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    _a("Poppins-Bold.ttf"),
]


def _log(msg):
    try:
        from ShiviMusic.logging import LOGGER

        LOGGER(__name__).error(msg)
    except Exception:
        print(msg)


def _load(cands, size):
    for p in cands:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size)
    except Exception:
        return ImageFont.load_default()


def _cover_crop(img: Image.Image, w: int, h: int) -> Image.Image:
    iw, ih = img.size
    sc = max(w / iw, h / ih)
    img = img.resize((int(iw * sc) + 1, int(ih * sc) + 1), Image.LANCZOS)
    l, t = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((l, t, l + w, t + h))


def _blurred_background(cover: Image.Image) -> Image.Image:
    bg = _cover_crop(cover, W, H).filter(ImageFilter.GaussianBlur(BLUR_RADIUS))
    dark = Image.new("RGB", (W, H), (20, 20, 24))
    return Image.blend(bg, dark, 0.62)


def _rounded(img: Image.Image, radius: int) -> Image.Image:
    img = img.convert("RGBA")
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *img.size), radius, fill=255)
    img.putalpha(mask)
    return img


def _fit_text(draw, text: str, font, max_w: int) -> str:
    text = str(text or "")
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text.rstrip() + "…"


def _wrap_2_lines(draw, text: str, font, max_w: int):
    """Title ko max 2 line me todta hai; 2nd line lambi ho to '…' lagata hai."""
    words = str(text or "").split()
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
        if len(lines) == 2:
            break
    if len(lines) < 2:
        lines.append(cur)
        rest = ""
    else:
        used = " ".join(lines)
        rest = str(text)[len(used):].strip()
    lines = lines[:2]
    full = " ".join(lines)
    if rest or (len(str(text).split()) > len(full.split())):
        lines[-1] = lines[-1] + " …"
    lines = [_fit_text(draw, ln, font, max_w) for ln in lines]
    return lines


def _fmt_views(v):
    """Number/text ko 521M / 12K jaisa chhota karta hai."""
    if v is None:
        return None
    if isinstance(v, str):
        digits = "".join(ch for ch in v if ch.isdigit())
        if not digits:
            return None
        if any(ch in v for ch in "KMBkmb"):
            return v.split(" ")[0].upper()
        n = int(digits)
    else:
        n = int(v)
    for div, suf in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if n >= div:
            val = n / div
            return (f"{val:.0f}" if val >= 100 else f"{val:.1f}".rstrip("0").rstrip(".")) + suf
    return str(n)


def _dur_to_sec(dur):
    try:
        parts = [int(x) for x in str(dur).split(":")]
    except Exception:
        return 0
    sec = 0
    for p in parts:
        sec = sec * 60 + p
    return sec


def _sec_to_dur(sec):
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _bot_username():
    """Jo bhi music bot chal raha hai, uska username (har deploy me apne aap alag)."""
    try:
        from ShiviMusic import app

        u = getattr(app, "username", None)
        if not u and getattr(app, "me", None):
            u = app.me.username
        if u:
            return "@" + str(u).lstrip("@")
    except Exception:
        pass
    try:
        import config

        if getattr(config, "BOT_USERNAME", None):
            return "@" + str(config.BOT_USERNAME).lstrip("@")
    except Exception:
        pass
    return "@MusicBot"


def compose_thumb(cover: Image.Image, title: str, artist: str, duration: str, path: str, views=None, safe=False):
    TF = _SAFE_FONTS if safe else _TITLE_FONTS
    BF = _SAFE_FONTS if safe else _BOLD_FONTS
    cover = cover.convert("RGB")
    canvas = _blurred_background(cover).convert("RGBA")
    white = (255, 255, 255, 255)

    # ---- right: orange glow frame + song image ----
    fx0, fy0, fx1, fy1 = 643, 107, 1228, 593
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle((fx0, fy0, fx1, fy1), 34, outline=(255, 140, 0, 230), width=14)
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((fx0, fy0, fx1, fy1), 34, outline=ORANGE, width=12)
    ix0, iy0, ix1, iy1 = fx0 + 17, fy0 + 18, fx1 - 18, fy1 - 18
    canvas.alpha_composite(_rounded(_cover_crop(cover, ix1 - ix0, iy1 - iy0), 18), (ix0, iy0))
    d = ImageDraw.Draw(canvas)

    # ---- NOW PLAYING pill ----
    d.rounded_rectangle((80, 116, 326, 154), 19, fill=ORANGE)
    d.text((203, 136), "NOW PLAYING", font=_load(BF, 25), fill=(25, 15, 0, 255), anchor="mm")

    # ---- title (2 lines, handwriting font) ----
    f_title = _load(TF, 58)
    lines = _wrap_2_lines(d, title or "Unknown Title", f_title, 500)
    for i, ln in enumerate(lines):
        d.text((80, 215 + i * 56), ln, font=f_title, fill=white, anchor="lm", stroke_width=1, stroke_fill=white)

    # ---- orange small line ----
    d.rounded_rectangle((80, 337, 181, 342), 2, fill=ORANGE)

    # ---- channel + views | duration ----
    d.text((80, 392), _fit_text(d, artist or "Unknown", _load(BF, 37), 500),
           font=_load(BF, 37), fill=(238, 238, 245, 255), anchor="lm")
    vtxt = _fmt_views(views)
    info = (f"{vtxt} Views  |  " if vtxt else "") + f"{duration or '0:00'} Minutes"
    d.text((80, 432), info, font=_load(BF, 27), fill=(215, 215, 225, 255), anchor="lm")

    # ---- progress bar ----
    bx0, bx1, by = 80, 510, 490
    total = _dur_to_sec(duration)
    cur = int(total * random.uniform(0.15, 0.55)) if total else 0
    frac = (cur / total) if total else 0.34
    d.rounded_rectangle((bx0, by - 4, bx1, by + 4), 4, fill=(120, 120, 140, 255))
    kx = bx0 + int((bx1 - bx0) * frac)
    d.rounded_rectangle((bx0, by - 4, kx, by + 4), 4, fill=ORANGE)
    d.ellipse((kx - 13, by - 13, kx + 13, by + 13), fill=white)
    f_t = _load(BF, 20)
    d.text((bx0, 524), _sec_to_dur(cur), font=f_t, fill=(225, 225, 232, 255), anchor="lm")
    d.text((bx1, 524), duration or "0:00", font=f_t, fill=(225, 225, 232, 255), anchor="rm")

    # ---- Player name ----
    d.text((80, 574), f"Player :  {_bot_username()}", font=_load(BF, 29),
           fill=(205, 205, 215, 255), anchor="lm")

    # ---- By text (bottom right) ----
    d.text((1255, 687), BY_TEXT, font=_load(BF, 27), fill=BY_COLOR, anchor="rm")

    os.makedirs(os.path.dirname(path) or "", exist_ok=True) if os.path.dirname(path) else None
    canvas.convert("RGB").save(path, "JPEG", quality=92)
    return path


def _trim_bars(img: Image.Image) -> Image.Image:
    """YouTube hqdefault/sddefault me upar-neeche kali patti (letterbox) hoti hai -- use hata deta hai."""
    try:
        g = img.convert("L")
        w, h = g.size
        rows = list(g.resize((1, h), Image.BOX).getdata())
        top = 0
        while top < h // 3 and rows[top] < 14:
            top += 1
        bot = h
        while bot > h - h // 3 and rows[bot - 1] < 14:
            bot -= 1
        cols = list(g.resize((w, 1), Image.BOX).getdata())
        left = 0
        while left < w // 3 and cols[left] < 14:
            left += 1
        right = w
        while right > w - w // 3 and cols[right - 1] < 14:
            right -= 1
        # chhoti si dark border ko mat kaato (sirf asli patti)
        if top < h * 0.04:
            top = 0
        if h - bot < h * 0.04:
            bot = h
        if left < w * 0.04:
            left = 0
        if w - right < w * 0.04:
            right = w
        if (top, bot, left, right) != (0, h, 0, w):
            # 2px extra andar se, taaki patti ka kinara na bache
            return img.crop((left, top + (2 if top else 0), right, bot - (2 if bot < h else 0)))
    except Exception:
        pass
    return img


async def _download(session, vidid: str):
    for q in ("maxresdefault", "sddefault", "hqdefault", "mqdefault"):
        try:
            async with session.get(
                f"https://i.ytimg.com/vi/{vidid}/{q}.jpg",
                timeout=aiohttp.ClientTimeout(total=8),
            ) as r:
                if r.status == 200:
                    img = Image.open(io.BytesIO(await r.read())).convert("RGB")
                    if img.width > 200:
                        return _trim_bars(img)
        except Exception:
            continue
    return None


def _views_of(r):
    vc = r.get("viewCount") or {}
    if isinstance(vc, dict):
        return vc.get("short") or vc.get("text")
    return vc


async def _meta(session, videoid: str):
    """(title, artist, duration, views) -- jo library mile usse; sab fail ho to oEmbed."""
    url = f"https://www.youtube.com/watch?v={videoid}"
    # 1) py_yt
    try:
        from py_yt import VideosSearch

        r = (await VideosSearch(url, limit=1).next())["result"][0]
        return r.get("title"), (r.get("channel") or {}).get("name"), r.get("duration"), _views_of(r)
    except Exception:
        pass
    # 2) youtubesearchpython (async)
    try:
        from youtubesearchpython.__future__ import VideosSearch

        r = (await VideosSearch(url, limit=1).next())["result"][0]
        return r.get("title"), (r.get("channel") or {}).get("name"), r.get("duration"), _views_of(r)
    except Exception:
        pass
    # 3) youtubesearchpython (sync)
    try:
        from youtubesearchpython import VideosSearch

        res = await asyncio.get_running_loop().run_in_executor(
            None, lambda: VideosSearch(url, limit=1).result()
        )
        r = res["result"][0]
        return r.get("title"), (r.get("channel") or {}).get("name"), r.get("duration"), _views_of(r)
    except Exception:
        pass
    # 4) YouTube oEmbed (kisi library ki zarurat nahi)
    try:
        async with session.get(
            "https://www.youtube.com/oembed",
            params={"url": url, "format": "json"},
            timeout=aiohttp.ClientTimeout(total=8),
        ) as r:
            if r.status == 200:
                j = await r.json()
                return j.get("title"), j.get("author_name"), None, None
    except Exception:
        pass
    return None, None, None, None


async def get_thumb(videoid, *args, title=None, artist=None, duration=None, views=None, **kwargs):
    """NOW PLAYING orange-card thumbnail banata hai.

    Purane code ke saare call styles chalte hain: get_thumb(vidid),
    get_thumb(vidid, user_id), get_thumb(vidid, a, b, c ...) -- extra args ignore.
    Kuch bhi fail ho to bhi card hi banta hai (sirf aakhri option me plain photo).
    """
    videoid = str(videoid)
    title = title if isinstance(title, str) else None
    artist = artist if isinstance(artist, str) else None
    duration = duration if isinstance(duration, str) else None
    fallback = f"https://i.ytimg.com/vi/{videoid}/hqdefault.jpg"

    os.makedirs("cache", exist_ok=True)
    for old in glob.glob(f"cache/{videoid}_np_*.jpg"):
        try:
            os.remove(old)
        except Exception:
            pass
    path = f"cache/{videoid}_np_{random.randint(1000, 9999)}.jpg"

    cover = None
    try:
        async with aiohttp.ClientSession() as session:
            if not (title and artist and duration and views):
                try:
                    t, a, dur, v = await _meta(session, videoid)
                    title, artist, duration, views = title or t, artist or a, duration or dur, views or v
                except Exception as e:
                    _log(f"[THUMB] meta fail {videoid}: {e!r}")
            cover = await _download(session, videoid)
    except Exception as e:
        _log(f"[THUMB] network fail {videoid}: {e!r}")

    # cover na mile to bot ki apni image (assets) se card bana do
    if cover is None:
        _log(f"[THUMB] cover download fail for {videoid} -> local image use ho rahi hai")
        for name in ("thum.png", "upic.png"):
            try:
                cover = Image.open(_a(name)).convert("RGB")
                break
            except Exception:
                continue
    if cover is None:
        return fallback

    args_ = (
        cover,
        title or "Unknown Title",
        artist or "YouTube",
        duration or "0:00",
        path,
        views,
    )
    loop = asyncio.get_running_loop()
    for safe in (False, True):
        try:
            await loop.run_in_executor(None, lambda: compose_thumb(*args_, safe=safe))
            return path
        except Exception:
            _log(f"[THUMB] compose fail (safe={safe}) for {videoid}:\n{traceback.format_exc()}")
    return fallback


gen_thumb = get_thumb  # purane naam se bhi chale
