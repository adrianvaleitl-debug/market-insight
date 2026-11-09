from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "market_insight.ico"
SIZE = 256

def make_icon():
    # Minimal charcoal tile with a single matte-silver M.
    im = Image.new("RGB", (SIZE, SIZE), (42, 42, 42))
    d = ImageDraw.Draw(im)
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    font = None
    for path in font_paths:
        try:
            font = ImageFont.truetype(path, 174)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()
    box = d.textbbox((0, 0), "M", font=font, stroke_width=0)
    x = (SIZE - (box[2] - box[0])) / 2 - box[0]
    y = (SIZE - (box[3] - box[1])) / 2 - box[1] - 5
    d.text((x, y), "M", font=font, fill=(190, 190, 190))
    im.save(OUT, format="ICO", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    return OUT

if __name__ == "__main__":
    print("Created:", make_icon())
