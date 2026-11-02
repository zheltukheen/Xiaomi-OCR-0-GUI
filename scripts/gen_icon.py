"""Generate application icons: icons/icon.png, icons/icon.ico and the macOS
iconset (icons/icon.iconset) for conversion to .icns via `iconutil`."""

import os

from PIL import Image, ImageDraw

BLUE = (40, 96, 216, 255)
GREY = (168, 178, 200, 255)
WHITE = (255, 255, 255, 255)


def page_icon(size: int) -> Image.Image:
    """A white page with text lines on a blue rounded background."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = round(size * 0.06)
    d.rounded_rectangle([m, m, size - m, size - m], radius=size * 0.18, fill=BLUE)
    px = round(size * 0.26)
    py = round(size * 0.20)
    pw = round(size * 0.48)
    ph = round(size * 0.60)
    d.rounded_rectangle([px, py, px + pw, py + ph], radius=size * 0.03, fill=WHITE)
    line_h = max(2, size // 64)
    x0 = px + round(pw * 0.16)
    y = py + round(ph * 0.16)
    bottom = py + round(ph * 0.85)
    while y + line_h < bottom:
        w = pw * 0.55
        if y <= py + round(ph * 0.28):
            w = pw * 0.68
        d.rounded_rectangle([x0, y, x0 + round(w), y + line_h],
                            radius=line_h / 2, fill=GREY)
        y += round(line_h * 2.2)
    return img


def main():
    os.makedirs("icons/icon.iconset", exist_ok=True)
    for s in (16, 32, 128, 256, 512):
        page_icon(s).save(f"icons/icon.iconset/icon_{s}x{s}.png")
        page_icon(s * 2).save(f"icons/icon.iconset/icon_{s}x{s}@2x.png")
    page_icon(1024).save("icons/icon.png")
    page_icon(256).save(
        "icons/icon.ico",
        sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256)],
    )
    print("icons generated under icons/", flush=True)


if __name__ == "__main__":
    main()
