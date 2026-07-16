import asyncio
import os
from pathlib import Path

import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from VampireMusic import config
from VampireMusic.helpers import Track

_HELP_DIR = Path(__file__).parent


def _font(name: str, size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(str(_HELP_DIR / name), size)
    except Exception:
        return ImageFont.load_default()


def draw_text_bbox(font, text: str):
    return ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), text, font=font)


def wrap_text(text: str, font, max_w: int, max_lines: int = 2) -> str:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if cur:
        lines.append(cur)
    return "\n".join(lines[:max_lines])


def _fmt(sec: int) -> str:
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
        from pathlib import Path
        try:
            help_dir = Path(__file__).parent
            self.title_font = ImageFont.truetype(str(help_dir / "Raleway-Bold.ttf"), 48)
            self.small_font = ImageFont.truetype(str(help_dir / "Inter-Light.ttf"), 28)
            self.time_font = ImageFont.truetype(str(help_dir / "Raleway-Bold.ttf"), 24)
        except Exception as e:
            print(f"Error loading fonts: {e}")
            self.title_font = ImageFont.load_default()
            self.small_font = ImageFont.load_default()
            self.time_font = ImageFont.load_default()

        self.session = None

    async def start(self):
        self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()

    async def download_thumb(self, url: str, path: str):
        async with self.session.get(url) as resp:
            resp.raise_for_status()
            with open(path, "wb") as f:
                f.write(await resp.read())

    def create_image(self, thumb_path, output, song):
        # Full-bleed blurred warm background
        bg = Image.open(thumb_path).convert("RGB").resize((self.WIDTH, self.HEIGHT))
        bg = bg.filter(ImageFilter.GaussianBlur(45))
        bg = ImageEnhance.Brightness(bg).enhance(0.92)
        bg = ImageEnhance.Contrast(bg).enhance(1.05)
        bg = ImageEnhance.Color(bg).enhance(1.10)

        # Right-side dark panel: gradient from left (transparent) to right (opaque)
        panel = Image.new("L", (self.WIDTH, self.HEIGHT), 0)
        pdraw = ImageDraw.Draw(panel)
        pw0, pw1 = int(self.WIDTH * 0.42), self.WIDTH
        for x in range(pw0, pw1):
            a = int(235 * (x - pw0) / (pw1 - pw0))
            pdraw.line([(x, 0), (x, self.HEIGHT)], fill=a)
        dark = Image.new("RGB", (self.WIDTH, self.HEIGHT), (8, 6, 8))
        bg = Image.composite(dark, bg, panel)
        # Subtle overall vignette
        vig = Image.new("L", (self.WIDTH, self.HEIGHT), 0)
        vdraw = ImageDraw.Draw(vig)
        vdraw.rectangle([0, 0, self.WIDTH, self.HEIGHT], fill=60)
        vdraw.ellipse([-200, -200, self.WIDTH + 200, self.HEIGHT + 200], fill=0)
        bg = Image.composite(bg, Image.new("RGB", (self.WIDTH, self.HEIGHT), (0, 0, 0)), vig)

        ACCENT = (197, 48, 48)  # reference red ~ rgb(163,52,49)

        # Big rounded album cover on the left
        cover = 440
        ax, ay = 90, (self.HEIGHT - cover) // 2 - 10
        art = Image.open(thumb_path).convert("RGB").resize((cover, cover))
        # soft shadow under the cover
        sh = Image.new("RGBA", (cover + 40, cover + 40), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(sh)
        sdraw.rounded_rectangle((20, 24, cover + 20, cover + 24), radius=40, fill=(0, 0, 0, 120))
        bg.paste(sh, (ax - 20, ay - 20), sh)
        mask = Image.new("L", (cover, cover), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, cover, cover), radius=40, fill=255)
        art.putalpha(mask)
        bg.paste(art, (ax, ay), art)

        # "NOW PLAYING" pill above the cover
        pill_font = _font("Raleway-Bold.ttf", 24)
        pill = "▶ NOW PLAYING"
        pb = draw_text_bbox(pill_font, pill)
        pw, ph = pb[2] - pb[0] + 44, pb[3] - pb[1] + 24
        px, py = ax, ay - 56
        pimg = Image.new("RGBA", (pw, ph), ACCENT + (235,))
        pdraw2 = ImageDraw.Draw(pimg)
        pdraw2.rounded_rectangle((0, 0, pw, ph), radius=ph // 2, outline=(255, 255, 255, 90), width=2)
        bg.paste(pimg, (px, py), pimg)
        ImageDraw.Draw(bg).text(
            (px + 22, py + (ph - (pb[3] - pb[1])) // 2 - 2), pill, fill="white", font=pill_font,
        )

        draw = ImageDraw.Draw(bg)
        # Text column on the right of the cover, over the dark panel
        tx = ax + cover + 70
        max_w = self.WIDTH - tx - 80
        ty = ay + 40

        title = wrap_text((song.title or "Unknown"), self.title_font, max_w, 3)
        draw.multiline_text((tx, ty), title, fill=(252, 248, 244), font=self.title_font, spacing=10)

        ay1 = ty + 3 * 58
        channel = (song.channel_name or "Unknown")
        if len(channel) > 38:
            channel = channel[:37] + "…"
        draw.text((tx, ay1), channel, fill=(222, 120, 124), font=self.small_font)

        meta = []
        if getattr(song, "view_count", None):
            meta.append(f"▶ {song.view_count}")
        if getattr(song, "duration", None):
            meta.append(f"⏱ {song.duration}")
        if meta:
            draw.text((tx, ay1 + 42), "   •   ".join(meta), fill=(205, 195, 195), font=self.small_font)

        # Brand badge (bottom-right)
        brand_font = _font("Raleway-Bold.ttf", 26)
        brand = "Vampire Music"
        bb = draw_text_bbox(brand_font, brand)
        bw, bh = (bb[2] - bb[0]) + 40, (bb[3] - bb[1]) + 30
        bx, by = self.WIDTH - bw - 70, self.HEIGHT - bh - 60
        badge = Image.new("RGBA", (bw, bh), (0, 0, 0, 170))
        bdraw = ImageDraw.Draw(badge)
        bdraw.rounded_rectangle((0, 0, bw, bh), radius=15, outline=(255, 255, 255, 50), width=2)
        bg.paste(badge, (bx, by), badge)
        draw.text((bx + 20, by + (bh - (bb[3] - bb[1])) // 2 - 5), brand, fill="white", font=brand_font)

        # Labeled progress bar (bottom, spans the dark panel)
        py2 = self.HEIGHT - 70
        sx, ex = tx - 30, self.WIDTH - 70
        draw.line([(sx, py2), (ex, py2)], fill=(120, 120, 120, 160), width=8)
        frac = min(max(getattr(song, "time", 0) / max(getattr(song, "duration_sec", 1) or 1, 1), 0), 1)
        knx = sx + int((ex - sx) * frac)
        draw.line([(sx, py2), (knx, py2)], fill=ACCENT, width=8)
        draw.ellipse((knx - 13, py2 - 13, knx + 13, py2 + 13), fill="white")
        draw.ellipse((knx - 7, py2 - 7, knx + 7, py2 + 7), fill=ACCENT)
        tfont = _font("Raleway-Bold.ttf", 22)
        cur = _fmt(getattr(song, "time", 0))
        tot = _fmt(getattr(song, "duration_sec", 0))
        draw.text((sx, py2 + 20), cur, fill=(225, 220, 220), font=tfont)
        tb = draw_text_bbox(tfont, tot)
        draw.text((ex - (tb[2] - tb[0]), py2 + 20), tot, fill=(225, 220, 220), font=tfont)

        bg.save(output, quality=95)
        return output

    async def generate(self, song: Track):
        try:
            if not self.session:
                await self.start()

            temp = f"cache/temp_{song.id}.jpg"
            output = f"cache/{song.id}.png"

            if os.path.exists(output):
                return output

            await self.download_thumb(song.thumbnail, temp)

            await asyncio.to_thread(
                self.create_image,
                temp,
                output,
                song,
            )

            if os.path.exists(temp):
                os.remove(temp)

            return output

        except Exception:
            return config.DEFAULT_THUMB
