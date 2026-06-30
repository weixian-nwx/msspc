"""Generate per-participant QR code images.

Each image encodes the participant's ``unique qr id`` (the same string the
scanner decodes) and prints the participant's name underneath, so the printed
codes double as name cards. Files are named by seat number for easy sorting.
"""
from __future__ import annotations

import os
import re

import qrcode
from PIL import Image, ImageDraw, ImageFont

from app import config
from app.db import Database

# Vertical space reserved under the QR for the name caption.
_CAPTION_HEIGHT = 48
_MARGIN = 10


def _sanitize(text: str) -> str:
    """Make a string safe to use as a Windows filename component."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text).strip().strip(".")
    return cleaned


def _render(qr_id: str, name: str) -> Image.Image:
    """Render a QR for ``qr_id`` with ``name`` captioned beneath it."""
    qr_img = qrcode.make(qr_id).convert("RGB")
    qw, qh = qr_img.size

    canvas = Image.new("RGB", (qw, qh + _CAPTION_HEIGHT), "white")
    canvas.paste(qr_img, (0, 0))

    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    caption = name or qr_id
    # Center the caption horizontally within the QR width.
    bbox = draw.textbbox((0, 0), caption, font=font)
    tw = bbox[2] - bbox[0]
    tx = max(_MARGIN, (qw - tw) // 2)
    ty = qh + (_CAPTION_HEIGHT - (bbox[3] - bbox[1])) // 2
    draw.text((tx, ty), caption, fill="black", font=font)
    return canvas


def generate_qr_codes(db: Database) -> tuple[str, int]:
    """Write a QR image for every participant into ``config.QRCODE_DIR``.

    Returns ``(folder, count)``. Existing PNGs in the folder are removed first
    so stale codes from a previous roster do not linger.
    """
    os.makedirs(config.QRCODE_DIR, exist_ok=True)
    for fn in os.listdir(config.QRCODE_DIR):
        if fn.lower().endswith(".png"):
            try:
                os.remove(os.path.join(config.QRCODE_DIR, fn))
            except OSError:
                pass

    used: set[str] = set()
    count = 0
    for p in db.all_participants():
        stem = _sanitize(p.seat_no) or _sanitize(p.qr_id)
        if not stem:
            stem = f"participant_{p.row_index + 1}"
        # De-duplicate filenames (seat numbers are not guaranteed unique).
        candidate = stem
        if candidate in used:
            candidate = f"{stem}_{_sanitize(p.qr_id)}"
        suffix = 1
        while candidate in used:
            suffix += 1
            candidate = f"{stem}_{suffix}"
        used.add(candidate)

        img = _render(p.qr_id, p.name)
        img.save(os.path.join(config.QRCODE_DIR, f"{candidate}.png"))
        count += 1

    return config.QRCODE_DIR, count
