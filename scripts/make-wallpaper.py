#!/usr/bin/env python3
"""Genera lo sfondo 800x480 per il CP-8851: gradiente blu + wordmark bianco.

Il colore di marca non e' scritto a mano: viene campionato dal logo blu
ufficiale, cosi' lo sfondo resta agganciato all'identita' reale.
"""
import math
from PIL import Image

W, H = 800, 480
THUMB = (80, 53)
HERE = "/home/pi/wallpaper/"


def brand_navy():
    """Colore piu' scuro e saturo presente nel logo ufficiale."""
    im = Image.open(HERE + "EMA-blu.png").convert("RGBA")
    best, score = (37, 37, 64), 1e9
    for px in im.getdata():
        if px[3] < 200:
            continue
        lum = 0.299 * px[0] + 0.587 * px[1] + 0.114 * px[2]
        if lum < score:
            score, best = lum, px[:3]
    return best


def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def build():
    navy = brand_navy()
    # due poli del gradiente derivati dal navy: piu' cupo in basso a destra,
    # piu' luminoso e leggermente virato al blu elettrico in alto a sinistra
    dark = mix(navy, (0, 0, 0), 0.45)
    lift = mix(navy, (70, 110, 220), 0.55)

    bg = Image.new("RGB", (W, H))
    px = bg.load()
    cx, cy = W * 0.30, H * 0.28          # centro del bagliore
    maxd = math.hypot(W, H)
    for y in range(H):
        for x in range(W):
            # gradiente diagonale di base
            t = (x / W * 0.55 + y / H * 0.45)
            c = mix(lift, dark, t)
            # alone morbido dietro al logo, per dare profondita'
            d = math.hypot(x - cx, y - cy) / maxd
            glow = max(0.0, 1.0 - d * 1.9) ** 2 * 0.38
            c = mix(c, (120, 165, 255), glow)
            # vignettatura ai bordi
            dv = math.hypot(x - W / 2, y - H / 2) / (maxd / 2)
            c = mix(c, (0, 0, 0), max(0.0, dv - 0.45) * 0.55)
            px[x, y] = c

    # wordmark bianco, largo il 62% dello schermo, leggermente sopra il centro
    logo = Image.open(HERE + "EMA-W.png").convert("RGBA")
    tw = int(W * 0.62)
    th = max(1, int(logo.height * tw / logo.width))
    logo = logo.resize((tw, th), Image.LANCZOS)
    pos = ((W - tw) // 2, int(H * 0.40) - th // 2)

    # ombra diffusa sotto al testo: lo stacca dal fondo senza sporcarlo
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 110), (pos[0], pos[1] + 3), logo)
    try:
        from PIL import ImageFilter
        shadow = shadow.filter(ImageFilter.GaussianBlur(7))
    except Exception:
        pass

    out = bg.convert("RGBA")
    out = Image.alpha_composite(out, shadow)
    out.paste(logo, pos, logo)
    out = out.convert("RGB")

    out.save(HERE + "ema-blu.png", "PNG")
    out.resize(THUMB, Image.LANCZOS).save(HERE + "ema-blu_80x53.png", "PNG")
    print("navy campionato dal logo:", navy)
    print("scritti ema-blu.png (%dx%d) e miniatura %dx%d" % (W, H, *THUMB))


if __name__ == "__main__":
    build()
