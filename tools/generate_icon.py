from PIL import Image, ImageDraw
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "market_insight.ico"
SIZE = 512
ICON_SIZES = [(16,16),(20,20),(24,24),(32,32),(40,40),(48,48),(64,64),(128,128),(256,256)]

def make_icon():
    # Match the clean, rounded, layered visual language of the SoloDesk identity.
    n = SIZE * 3
    im = Image.new("RGBA", (n,n), (0,0,0,0))
    d = ImageDraw.Draw(im)
    k = n / 256
    def box(v): return tuple(round(x*k) for x in v)
    d.rounded_rectangle(box((8,8,248,248)), radius=round(58*k), fill="#1A2D43")
    d.rounded_rectangle(box((48,48,208,208)), radius=round(25*k), fill="#EAF2FF")
    # Three market columns with a rising connecting line.
    d.rounded_rectangle(box((72,139,101,181)), radius=round(7*k), fill="#9AB6D8")
    d.rounded_rectangle(box((113,111,142,181)), radius=round(7*k), fill="#5F8FCB")
    d.rounded_rectangle(box((154,79,183,181)), radius=round(7*k), fill="#5F8FCB")
    d.line([box((75,118)),box((121,91)),box((166,61))], fill="#69D3C8", width=round(9*k), joint="curve")
    d.ellipse(box((153,48,179,74)), fill="#69D3C8")
    im = im.resize((SIZE,SIZE), Image.Resampling.LANCZOS)
    im.save(OUT, format="ICO", sizes=ICON_SIZES)
    return OUT

if __name__ == "__main__":
    print("Created:", make_icon())
