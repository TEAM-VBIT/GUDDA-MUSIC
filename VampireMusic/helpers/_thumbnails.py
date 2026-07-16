import asyncio
import os
from pathlib import Path

import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from VampireMusic import config
from VampireMusic.helpers import Track

try:
    from unidecode import unidecode
except ImportError:
    def unidecode(text):
        return text

_HELP_DIR = Path(__file__).parent
FONT_TITLE_PATH = str(_HELP_DIR / "Raleway-Bold.ttf")
FONT_INFO_PATH = str(_HELP_DIR / "Inter-Light.ttf")


def safe_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _fmt(sec):
    try:
        sec = int(sec)
    except (TypeError, ValueError):
        return "0:00"
    m, s = divmod(sec, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class Thumbnail:
    WIDTH = 1280
    HEIGHT = 720

    def __init__(self):
        self.size = (self.WIDTH, self.HEIGHT)
        self.session = None

    async def start(self):
        self.session = aiohttp.ClientSession()
        return True

    async def close(self):
        if self.session:
            await self.session.close()

    async def save_thumb(self, output_path: str, url: str) -> str:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        for attempt in range(3):
            try:
                if url.startswith("http"):
                    async with aiohttp.ClientSession(headers=headers) as session:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                            if resp.status == 200:
                                content = await resp.read()
                                with open(output_path, "wb") as f:
                                    f.write(content)
                                return output_path
            except Exception as e:
                if attempt == 2:
                    print(f"Error saving thumb: {e}")
                await asyncio.sleep(1)
        return output_path

    async def download_thumb(self, url: str, path: str):
        await self.save_thumb(path, url)

    def create_image(self, thumb_path, output, song):
        # Dynamic font loading for proper sizes
        font_title = safe_font(FONT_TITLE_PATH, 135)
        font_info = safe_font(FONT_INFO_PATH, 24)
        font_time = safe_font(FONT_INFO_PATH, 20)
        font_brand = safe_font(FONT_TITLE_PATH, 26)

        W, H = self.size

        # --- 1. DARK BLURRED BACKGROUND ---
        try:
            src = Image.open(thumb_path).convert("RGBA")
        except Exception:
            try:
                src = Image.new("RGBA", (W, H), (30, 30, 30, 255))
            except Exception:
                return config.DEFAULT_THUMB

        bg_ratio = W / H
        src_ratio = src.width / src.height
        if src_ratio > bg_ratio:
            new_w = int(src.height * bg_ratio)
            offset = (src.width - new_w) // 2
            bg = src.crop((offset, 0, offset + new_w, src.height))
        else:
            new_h = int(src.width / bg_ratio)
            offset = (src.height - new_h) // 2
            bg = src.crop((0, offset, src.width, offset + new_h))

        bg = bg.resize((W, H), Image.Resampling.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(18))
        bg = bg.convert("RGBA")

        # Dark overlay
        bg_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 110))
        bg = Image.alpha_composite(bg, bg_overlay)

        canvas = bg.copy()
        draw = ImageDraw.Draw(canvas)

        # --- 2. CARD COMPONENT ---
        card_w, card_h = 960, 560
        card_x, card_y = 160, 100
        RADIUS = 28

        # Soft drop shadow behind the card
        shadow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        shadow_draw.rounded_rectangle(
            (card_x - 4, card_y + 8, card_x + card_w + 4, card_y + card_h + 12),
            radius=RADIUS + 4,
            fill=(0, 0, 0, 110),
        )
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(22))
        canvas = Image.alpha_composite(canvas, shadow_layer)
        draw = ImageDraw.Draw(canvas)

        card = Image.new("RGBA", (card_w, card_h), (220, 220, 220, 255))
        mask = Image.new("L", (card_w, card_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, card_w, card_h), RADIUS, fill=255)
        canvas.paste(card, (card_x, card_y), mask)
        draw = ImageDraw.Draw(canvas)

        # --- 3. INNER COVER IMAGE ---
        art = src.resize((840, 370))
        art_mask = Image.new("L", art.size, 0)
        ImageDraw.Draw(art_mask).rounded_rectangle(
            (0, 0, art.size[0], art.size[1]), 18, fill=255
        )
        canvas.paste(art, (card_x + 95, card_y + 22), art_mask)
        draw = ImageDraw.Draw(canvas)

        # --- 4. DETAILS SECTION ---
        title_text = unidecode(str(song.title or "Unknown"))

        def ellipsize(s, font, max_w):
            bbox = draw.textbbox((0, 0), s, font=font)
            if (bbox[2] - bbox[0]) <= max_w:
                return s
            lo, hi = 1, len(s)
            best = "…"
            while lo <= hi:
                mid = (lo + hi) // 2
                cand = s[:mid].rstrip() + "…"
                bbox = draw.textbbox((0, 0), cand, font=font)
                if (bbox[2] - bbox[0]) <= max_w:
                    best = cand
                    lo = mid + 1
                else:
                    hi = mid - 1
            return best

        # Large, bold title (>=100px tall) below the artwork
        title_str = ellipsize(title_text, font_title, card_w - 70)
        title_y = card_y + 415
        draw.text((card_x + 38, title_y + 3), title_str, fill=(0, 0, 0, 40), font=font_title)
        draw.text((card_x + 35, title_y), title_str, fill=(20, 20, 20, 255), font=font_title)

        # Subtitle (Channel name & views)
        sub_text = song.channel_name or "YouTube"
        if getattr(song, "view_count", None):
            sub_text += f"   ·   {song.view_count}"
        subtitle_str = ellipsize(sub_text, font_info, card_w - 70)
        draw.text((card_x + 35, card_y + 560 - 110), subtitle_str, fill=(90, 90, 90, 255), font=font_info)

        # --- 5. PROGRESS BAR ---
        bar_x = card_x + 35
        bar_y = card_y + 515
        bar_w = card_w - 70
        bar_h = 12
        # background track
        draw.rounded_rectangle(
            (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), 6, fill=(190, 190, 190)
        )
        # filled — driven by playback position when available
        total = getattr(song, "duration_sec", None) or 0
        cur = getattr(song, "time", None) or 0
        if total and cur:
            progress = min(max(cur / total, 0), 1)
        else:
            progress = 0.35  # static default for visual playback representation
        fill_w = int(bar_w * progress)
        draw.rounded_rectangle(
            (bar_x, bar_y, bar_x + fill_w, bar_y + bar_h), 6, fill=(220, 20, 20)
        )
        # knob
        knob_x = bar_x + fill_w
        draw.ellipse((knob_x - 10, bar_y - 5, knob_x + 10, bar_y + 15), fill=(220, 20, 20))

        # Timestamps
        draw.text((bar_x, bar_y + 28), _fmt(cur) if cur else "0:00", fill=(60, 60, 60), font=font_time)
        right_text = song.duration or _fmt(total) or "0:00"
        rb = draw.textbbox((0, 0), right_text, font=font_time)
        rw = rb[2] - rb[0]
        draw.text((bar_x + bar_w - rw, bar_y + 28), right_text, fill=(60, 60, 60), font=font_time)

        # --- 6. BOTTOM RED LINE ---
        draw.rounded_rectangle(
            (card_x + 35, card_y + card_h - 8, card_x + card_w - 35, card_y + card_h - 2),
            3, fill=(220, 20, 20)
        )

        # --- 7. TOP RIGHT WATERMARK ---
        watermark = "Vampire Music"
        wb = draw.textbbox((0, 0), watermark, font=font_brand)
        ww = wb[2] - wb[0]
        draw.text((W - ww - 30, 22), watermark, fill=(255, 255, 255, 220), font=font_brand)

        # Save final image
        out = canvas.convert("RGB")
        out.save(output, "JPEG", quality=95, optimize=True)
        return output

    async def generate(self, song: Track) -> str:
        try:
            if not self.session:
                await self.start()

            temp = f"cache/temp_{song.id}.jpg"
            output = f"cache/{song.id}.jpg"

            if os.path.exists(output):
                return output

            await self.download_thumb(song.thumbnail, temp)
            await asyncio.to_thread(self.create_image, temp, output, song)

            if os.path.exists(temp):
                os.remove(temp)

            return output

        except Exception as e:
            print(f"Error generating thumbnail: {e}")
            import traceback
            traceback.print_exc()
            return config.DEFAULT_THUMB
