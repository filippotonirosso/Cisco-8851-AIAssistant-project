"""Genera sfondo e pannello dimostrativi con un marchio testuale.

Variante di make-wallpaper.py che non richiede un file logo: disegna il
marchio come testo. Utile per provare il risultato prima di avere la
propria immagine, o per generare schermate neutre.

Cambia MARCHIO qui sotto.
"""
import sys, math
sys.path.insert(0, "/var/lib/asterisk/agi-bin")
from PIL import Image, ImageDraw, ImageFont, ImageFilter

MARCHIO = "ACME"
F = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W, H = 800, 480
NAVY = (37, 38, 69)

def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i]-a[i])*t)) for i in range(3))

dark = mix(NAVY, (0,0,0), 0.45)
lift = mix(NAVY, (70,110,220), 0.55)
bg = Image.new("RGB", (W,H)); px = bg.load()
cx, cy, maxd = W*0.30, H*0.28, math.hypot(W,H)
for y in range(H):
    for x in range(W):
        c = mix(lift, dark, x/W*0.55 + y/H*0.45)
        d = math.hypot(x-cx, y-cy)/maxd
        c = mix(c, (120,165,255), max(0.0, 1.0-d*1.9)**2 * 0.38)
        dv = math.hypot(x-W/2, y-H/2)/(maxd/2)
        px[x,y] = mix(c, (0,0,0), max(0.0, dv-0.45)*0.55)

font = ImageFont.truetype(F, 96)
dr = ImageDraw.Draw(bg)
bb = dr.textbbox((0,0), MARCHIO, font=font)
pos = ((W-(bb[2]-bb[0]))//2 - bb[0], int(H*0.40) - (bb[3]-bb[1])//2 - bb[1])

shadow = Image.new("RGBA", (W,H), (0,0,0,0))
ImageDraw.Draw(shadow).text((pos[0], pos[1]+3), MARCHIO, font=font, fill=(0,0,0,110))
shadow = shadow.filter(ImageFilter.GaussianBlur(7))
out = Image.alpha_composite(bg.convert("RGBA"), shadow)
ImageDraw.Draw(out).text(pos, MARCHIO, font=font, fill=(255,255,255,255))
out.convert("RGB").save("/tmp/demo-sfondo.png", "PNG")
print("sfondo generato")

# pannello con gli stessi dati di esempio, marchio neutro
import dashboard as D, datetime as dt
D.BRAND = MARCHIO
D.data = lambda: {"eventi":[
    {"ora":"09:30","titolo":"Riunione settimanale"},
    {"ora":"11:00","titolo":"Call con il fornitore"},
    {"ora":"15:00","titolo":"Revisione progetto"},
    {"ora":"17:30","titolo":"Uno a uno"}], "non_lette":7, "errore":None}
class FakeNow(dt.datetime):
    @classmethod
    def now(cls, tz=None): return cls(2026, 3, 12, 9, 14)
D.dt.datetime = FakeNow
D.render_png()
print("pannello generato")
