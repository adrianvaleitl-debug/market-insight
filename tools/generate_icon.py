from PIL import Image, ImageDraw
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "market_insight.ico"
SIZE = 256

def make_icon():
    im = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # Dark rounded tile with a subtle green frame.
    d.rounded_rectangle((8, 8, 248, 248), radius=54, fill=(8, 20, 16, 255), outline=(40, 190, 118, 255), width=5)
    # Rising bars.
    for x, top in [(54, 157), (91, 128), (128, 96), (165, 65)]:
        d.rounded_rectangle((x, top, x+24, 198), radius=5, fill=(40, 205, 130, 255))
    # Rising trend line and arrow.
    line = [(42, 151), (91, 118), (126, 135), (198, 59)]
    d.line(line, fill=(151, 255, 194, 255), width=13, joint="curve")
    d.polygon([(198, 34), (221, 70), (181, 65)], fill=(151, 255, 194, 255))
    im.save(OUT, format="ICO", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    return OUT

if __name__ == "__main__":
    print("Created:", make_icon())
