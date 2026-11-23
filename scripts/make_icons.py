"""Render placeholder PWA icons. Replace frontend/public/icon-*.png with the real logo when available."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public"
for size, name in ((192, "icon-192.png"), (512, "icon-512.png"), (180, "apple-touch-icon.png")):
    img = Image.new("RGB", (size, size), "#2E5E5A")
    d = ImageDraw.Draw(img)
    s = size / 64
    d.polygon([(18 * s, 40 * s), (26 * s, 28 * s), (40 * s, 24 * s), (48 * s, 32 * s), (38 * s, 30 * s), (30 * s, 38 * s), (24 * s, 44 * s)], fill="#F3E6D3")
    d.ellipse([18 * s, 18 * s, 26 * s, 26 * s], fill="#E0A16B")
    img.save(OUT / name)
print("icons written")
