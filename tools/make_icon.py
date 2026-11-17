"""Generates build/icon.ico (same phone glyph as the tray icon)."""
import os
import sys

from PIL import Image, ImageDraw


def phone_icon(size=256):
    k = size / 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((18 * k, 4 * k, 46 * k, 60 * k), radius=6 * k,
                        fill=(40, 120, 220), outline=(255, 255, 255), width=max(1, round(3 * k)))
    d.rectangle((23 * k, 11 * k, 41 * k, 50 * k), fill=(220, 235, 255))
    return img


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join("build", "icon.ico")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    phone_icon(256).save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icon ->", out)
