"""Generation d'icones simples pour Tkinter via Pillow."""

from __future__ import annotations

import tkinter as tk

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
except Exception:  # pragma: no cover
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]
    ImageFont = None  # type: ignore[assignment]
    ImageTk = None  # type: ignore[assignment]


def create_tab_icon(symbol: str, color: str, size: int = 20) -> tk.PhotoImage | None:
    """Cree une icone de tab coloree.

    Retourne `None` si Pillow n'est pas disponible.
    """

    if Image is None or ImageDraw is None or ImageFont is None or ImageTk is None:
        return None

    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((1, 1, size - 2, size - 2), fill=color)
    draw.ellipse((1, 1, size - 2, size - 2), outline=(255, 255, 255, 90), width=1)

    try:
        font = ImageFont.truetype("Arial.ttf", int(size * 0.55))
    except Exception:
        font = ImageFont.load_default()

    text = (symbol or "?")[:1].upper()
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) / 2
    y = (size - text_h) / 2 - 1
    draw.text((x, y), text, fill="white", font=font)

    return ImageTk.PhotoImage(image)
