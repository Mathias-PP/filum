from __future__ import annotations

import io
import textwrap

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1200
HEIGHT = 630
BG_COLOR = (15, 23, 42)
ACCENT_COLOR = (59, 130, 246)
TEXT_COLOR = (255, 255, 255)
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_PATH_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"


def generate_og_image(title: str, creator: str | None = None) -> bytes:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    title_font = ImageFont.truetype(FONT_PATH_SERIF, 48)
    subtitle_font = ImageFont.truetype(FONT_PATH, 24)
    small_font = ImageFont.truetype(FONT_PATH, 20)

    accent_bar = Image.new("RGB", (6, HEIGHT), ACCENT_COLOR)
    img.paste(accent_bar, (0, 0))

    draw.text((40, 40), "filum", font=subtitle_font, fill=ACCENT_COLOR)

    max_width = WIDTH - 120
    wrapped = textwrap.wrap(title, width=30)
    y = HEIGHT // 2 - (len(wrapped) * 60) // 2
    for line in wrapped:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        line_w = bbox[2] - bbox[0]
        draw.text(
            ((max_width - line_w) // 2 + 40, y),
            line,
            font=title_font,
            fill=TEXT_COLOR,
        )
        y += 70

    if creator:
        bbox = draw.textbbox((0, 0), creator, font=subtitle_font)
        creator_w = bbox[2] - bbox[0]
        draw.text(
            ((max_width - creator_w) // 2 + 40, HEIGHT - 80),
            creator,
            font=subtitle_font,
            fill=ACCENT_COLOR,
        )

    footer_text = "filum.app — bibliographie vérifiable"
    draw.text((40, HEIGHT - 40), footer_text, font=small_font, fill=(100, 116, 139))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
