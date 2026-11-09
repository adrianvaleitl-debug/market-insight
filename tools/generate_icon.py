from PIL import Image, ImageDraw
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "market_insight.ico"
SIZE = 512
SUPERSAMPLE = 4
ICON_SIZES = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40),
              (48, 48), (64, 64), (128, 128), (256, 256)]


def make_icon():
    # Draw at high resolution so Windows receives clean artwork at every
    # common taskbar, title-bar, shortcut and high-DPI icon size.
    n = SIZE * SUPERSAMPLE
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    # Full 360-degree charcoal circle. The corners stay transparent so the
    # icon is genuinely circular in Windows shortcuts and the taskbar.
    d.ellipse(
        (0, 0, n - 1, n - 1),
        fill=(45, 46, 45, 255),
    )

    # Silver angular M. Enlarge it around its centre so its strokes remain
    # distinct at 16-32 px instead of appearing undersized in the taskbar.
    points = [
        (334, 406), (439, 406), (624, 598), (810, 406),
        (914, 406), (914, 830), (800, 830), (800, 570),
        (624, 752), (448, 570), (448, 830), (334, 830),
    ]
    centre_x, centre_y = 624, 618
    enlargement = 1.80
    points = [
        (
            int((centre_x + (x - centre_x) * enlargement) * n / 1254),
            int((centre_y + (y - centre_y) * 1.95) * n / 1254),
        )
        for x, y in points
    ]
    d.polygon(points, fill=(215, 216, 218, 255))

    # Downsample once with a high-quality filter, then let Pillow encode the
    # complete multi-resolution ICO image for Windows.
    im = im.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    im.save(OUT, format="ICO", sizes=ICON_SIZES)
    return OUT


if __name__ == "__main__":
    print("Created:", make_icon())
