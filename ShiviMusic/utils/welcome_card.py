# Kirti Music - Golden welcome card renderer
# Template: ShiviMusic/assets/kirti_welcome_tpl.webp
#   - pfp wali gol jagah transparent hai (gulab/patte pfp ke upar hi rehte hain)
#   - User ID / User Name / Group Name ke values khaali hain, yahan code se likhe jaate hain

import os
import re

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
TEMPLATE = os.path.join(ASSETS, "kirti_welcome_tpl.webp")
FONT_VAL = os.path.join(ASSETS, "FreeSerifBold.ttf")  # Hindi + fancy letters dono support

# pfp ellipse (template ke hisaab se)
PFP_CENTER = (1289, 456)
PFP_RX, PFP_RY = 278, 262

# (start_x, max_width, center_y) - har pill me value kahan likhni hai
SLOT_ID = (514, 288, 633)
SLOT_NAME = (550, 306, 725)
SLOT_GROUP = (568, 336, 818)

GOLD_TOP = (255, 246, 200)
GOLD_BOTTOM = (236, 186, 92)
FONT_SIZE = 42
MIN_SIZE = 24


def _ensure_assets():
    """Assets folder me file na ho (sirf .py upload hui ho) to embedded data se bana do."""
    global TEMPLATE, FONT_VAL
    import base64

    for var, path in (("TEMPLATE", TEMPLATE), ("FONT_VAL", FONT_VAL)):
        if os.path.isfile(path):
            continue
        alt = os.path.join("downloads", "welcome_assets", os.path.basename(path))
        if os.path.isfile(alt):
            globals()[var] = alt
            continue
        try:
            from ShiviMusic.utils import welcome_assets_data as d
            data = getattr(d, "TPL_WEBP" if var == "TEMPLATE" else "FONT_VAL", None)
        except Exception:
            data = None
        if not data:
            # embedded data purana hai / nahi hai -> font ke liye fallback
            if var == "FONT_VAL":
                for f in (
                    os.path.join(ASSETS, "Poppins-Bold.ttf"),
                    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
                ):
                    if os.path.isfile(f):
                        globals()[var] = f
                        break
            continue
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(base64.b64decode(data))
        except Exception:
            alt = os.path.join("downloads", "welcome_assets", os.path.basename(path))
            os.makedirs(os.path.dirname(alt), exist_ok=True)
            if not os.path.isfile(alt):
                with open(alt, "wb") as f:
                    f.write(base64.b64decode(data))
            globals()[var] = alt


def _font(size):
    try:
        return ImageFont.truetype(FONT_VAL, size)
    except Exception:
        return ImageFont.load_default()


_EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"  # emoji
    "\U00002600-\U000027BF"  # symbols / dingbats
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0000200B-\U0000200D\U00002060"
    "\U000E0000-\U000E007F"
    "\x00-\x1f\x7f"
    "]+"
)


def _clean(text, fallback):
    text = _EMOJI.sub("", str(text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text or fallback


def _fit(draw, text, max_w):
    size = FONT_SIZE
    font = _font(size)
    while draw.textlength(text, font=font) > max_w and size > MIN_SIZE:
        size -= 2
        font = _font(size)
    if draw.textlength(text, font=font) > max_w:
        while len(text) > 1 and draw.textlength(text + "…", font=font) > max_w:
            text = text[:-1]
        text = text.rstrip() + "…"
    return text, font


def _gold_text(canvas, slot, text):
    """Golden gradient text + halki glow, pill ke andar left-middle anchor."""
    x, max_w, cy = slot
    draw = ImageDraw.Draw(canvas)
    text, font = _fit(draw, text, max_w)

    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).text((x, cy), text, font=font, fill=255, anchor="lm")
    bbox = mask.getbbox()
    if not bbox:
        return

    # glow
    glow = mask.filter(ImageFilter.GaussianBlur(6)).point(lambda v: int(v * 0.55))
    canvas.paste(Image.new("RGBA", canvas.size, (255, 170, 40, 255)), (0, 0), glow)
    # shadow
    shadow = Image.new("L", canvas.size, 0)
    shadow.paste(mask, (2, 3))
    canvas.paste(Image.new("RGBA", canvas.size, (40, 20, 0, 255)), (0, 0), shadow)

    # vertical gold gradient
    _, y0, _, y1 = bbox
    grad = Image.new("RGBA", canvas.size)
    gd = ImageDraw.Draw(grad)
    span = max(1, y1 - y0)
    for y in range(y0, y1 + 1):
        t = (y - y0) / span
        col = tuple(int(GOLD_TOP[i] + (GOLD_BOTTOM[i] - GOLD_TOP[i]) * t) for i in range(3))
        gd.line([(bbox[0], y), (bbox[2], y)], fill=col + (255,))
    canvas.paste(grad, (0, 0), mask)


def _ellipse_pfp(path):
    w, h = PFP_RX * 2, PFP_RY * 2
    img = Image.open(path).convert("RGBA")
    # center crop, ellipse ke ratio me
    ratio = w / h
    if img.width / img.height > ratio:
        nw = int(img.height * ratio)
        left = (img.width - nw) // 2
        img = img.crop((left, 0, left + nw, img.height))
    else:
        nh = int(img.width / ratio)
        top = (img.height - nh) // 2
        img = img.crop((0, top, img.width, top + nh))
    img = img.resize((w, h), Image.LANCZOS)
    ss = 4
    mask = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, w * ss - 1, h * ss - 1), fill=255)
    img.putalpha(mask.resize((w, h), Image.LANCZOS))
    return img


def create_welcome_card(
    pfp_path,
    user_id,
    username,
    chat_title,
    out_path,
    name=None,
    brand="Kirti Music",
    link=None,
    hue_shift=None,
):
    """Card banao aur out_path par save karo. out_path return hota hai.

    name     -> 'User Name' me dikhega (user ka naam). Na mile to @username.
    brand/link/hue_shift purane code ke saath compatibility ke liye hain.
    """
    try:
        _ensure_assets()
    except Exception:
        pass
    tpl = Image.open(TEMPLATE).convert("RGBA")
    W, H = tpl.size

    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    try:
        pfp = _ellipse_pfp(pfp_path)
        canvas.paste(pfp, (PFP_CENTER[0] - PFP_RX, PFP_CENTER[1] - PFP_RY), pfp)
    except Exception:
        pass
    canvas.alpha_composite(tpl)

    display = _clean(name, f"@{username}" if username else "User")
    _gold_text(canvas, SLOT_ID, str(user_id))
    _gold_text(canvas, SLOT_NAME, display)
    _gold_text(canvas, SLOT_GROUP, _clean(chat_title, brand))

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    canvas.convert("RGB").save(out_path, "PNG")
    return out_path
