from PIL import Image, ImageDraw
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "market_insight.ico"
SIZE = 512
SCALE = 4

def make_icon():
    n = SIZE * SCALE
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # Rounded charcoal tile, matching the supplied Market Insight artwork.
    d.rounded_rectangle((0, 0, n - 1, n - 1), radius=145 * SCALE, fill=(45, 46, 45, 255))
    # Custom angular M, preserving the proportions and broad strokes of the reference.
    points = [
        (334, 406), (439, 406), (624, 598), (810, 406),
        (914, 406), (914, 830), (800, 830), (800, 570),
        (624, 752), (448, 570), (448, 830), (334, 830)
    ]
    points = [(int(x * n / 1254), int(y * n / 1254)) for x, y in points]
    d.polygon(points, fill=(174, 175, 177, 255))
    im = im.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    im.save(OUT, format="ICO", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    return OUT

if __name__ == "__main__":
    print("Created:", make_icon())
