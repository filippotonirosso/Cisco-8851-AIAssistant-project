#!/usr/bin/env python3
"""Schermata di riposo del CP-8851.

Il telefono chiede /idle a intervalli regolari e disegna cio' che riceve.
I dati vengono dalle API Google con le credenziali gia' presenti sul Pi.

Gira come utente asterisk: gli servono le chiavi in /etc/asterisk (600).
"""
import datetime as dt
import html
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, "/var/lib/asterisk/agi-bin")
import assistant_lib as L          # noqa: E402
import google_api as G             # noqa: E402

# Marchio mostrato in cima al pannello e nel piede. Cambialo col tuo.
BRAND = "ACME"

PORT = 8081
CACHE_TTL = 120        # il telefono ricarica spesso; non martelliamo Google
_cache = {"at": 0, "data": None}
_lock = threading.Lock()

GIORNI = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def esc(s):
    return html.escape(str(s), quote=True)


def fetch():
    """Eventi di oggi e numero di non lette. Un errore su uno non deve
    far sparire l'altro."""
    out = {"eventi": [], "non_lette": None, "errore": None}

    oggi = dt.date.today()
    tmin = dt.datetime(oggi.year, oggi.month, oggi.day)
    tmax = tmin + dt.timedelta(days=1)
    ev = G.call("GET", "calendar/v3/calendars/primary/events", {
        "timeMin": tmin.isoformat() + "Z", "timeMax": tmax.isoformat() + "Z",
        "singleEvents": "true", "orderBy": "startTime", "maxResults": 6,
        "fields": "items(summary,start,end)",
    })
    if "errore" in ev:
        out["errore"] = ev["errore"]
    else:
        for it in ev.get("items", []):
            s = it.get("start", {})
            quando = s.get("dateTime") or s.get("date") or ""
            out["eventi"].append({
                "titolo": (it.get("summary") or "(senza titolo)")[:26],
                "ora": quando[11:16] if "T" in quando else "",
            })

    ml = G.call("GET", "gmail/v1/users/me/labels/INBOX") if False else None
    mm = G.call("GET", "gmail/v1/users/me/messages",
                {"q": "is:unread in:inbox", "maxResults": 20,
                 "fields": "resultSizeEstimate"})
    if "errore" not in mm:
        out["non_lette"] = mm.get("resultSizeEstimate", 0)
    return out


def data():
    with _lock:
        if time.time() - _cache["at"] < CACHE_TTL and _cache["data"] is not None:
            return _cache["data"]
        try:
            _cache["data"] = fetch()
        except Exception as exc:
            L.log("cruscotto: %s" % exc)
            if _cache["data"] is None:
                _cache["data"] = {"eventi": [], "non_lette": None,
                                  "errore": str(exc)}
        _cache["at"] = time.time()
        return _cache["data"]


def page_idle():
    d = data()
    now = dt.datetime.now()
    righe = ["%s %d %s   %s" % (GIORNI[now.weekday()].capitalize(), now.day,
                                MESI[now.month - 1], now.strftime("%H:%M"))]

    ev = d.get("eventi") or []
    if ev:
        prossimi = [e for e in ev if not e["ora"] or e["ora"] >= now.strftime("%H:%M")]
        mostra = prossimi[:3] or ev[-1:]
        for e in mostra:
            righe.append("%s  %s" % (e["ora"] or "  -  ", e["titolo"]))
        if len(prossimi) > 3:
            righe.append("...e altri %d" % (len(prossimi) - 3))
    else:
        righe.append("Nessun impegno oggi")

    if d.get("non_lette") is not None:
        n = d["non_lette"]
        righe.append("Mail da leggere: %s" % ("nessuna" if n == 0 else n))

    return ("<CiscoIPPhoneText><Title>%s</Title><Text>%s</Text>"
            "</CiscoIPPhoneText>" % (esc(BRAND), esc("\n".join(righe))))


def page_services():
    d = data()
    ev = d.get("eventi") or []
    if d.get("errore"):
        return ("<CiscoIPPhoneText><Title>Agenda</Title><Text>%s</Text>"
                "</CiscoIPPhoneText>" % esc(d["errore"][:180]))
    if not ev:
        return ("<CiscoIPPhoneText><Title>Agenda di oggi</Title>"
                "<Text>Nessun impegno.</Text></CiscoIPPhoneText>")
    voci = "".join("<MenuItem><Name>%s %s</Name><URL>SoftKey:Exit</URL></MenuItem>"
                   % (esc(e["ora"] or "-"), esc(e["titolo"])) for e in ev)
    return ("<CiscoIPPhoneMenu><Title>Agenda di oggi</Title>"
            "<Prompt>%d impegni</Prompt>%s</CiscoIPPhoneMenu>" % (len(ev), voci))



# ---- schermata disegnata --------------------------------------------------
#
# Il riquadro di testo di Cisco e' grezzo. Disegnare un PNG da servire come
# CiscoIPPhoneImageFile da lo stesso controllo che si ha sullo sfondo:
# gerarchia tipografica, spaziature, colori di marca.

from PIL import Image, ImageDraw, ImageFont      # noqa: E402

W, H = 792, 380                # area utile dei servizi sull 8851
PNG = "/tmp/dashboard.png"
NAVY = (37, 38, 69)
F_DIR = "/usr/share/fonts/truetype/dejavu/"


def _font(nome, dim):
    try:
        return ImageFont.truetype(F_DIR + nome, dim)
    except Exception:
        return ImageFont.load_default()


def render_png():
    d = data()
    now = dt.datetime.now()
    img = Image.new("RGB", (W, H), NAVY)
    dr = ImageDraw.Draw(img)

    f_ora = _font("DejaVuSans-Bold.ttf", 62)
    f_data = _font("DejaVuSans.ttf", 24)
    f_voce = _font("DejaVuSans-Bold.ttf", 26)
    f_sub = _font("DejaVuSans.ttf", 22)
    f_pie = _font("DejaVuSans.ttf", 21)

    # fascia superiore: ora grande a sinistra, data sotto
    dr.text((36, 24), now.strftime("%H:%M"), font=f_ora, fill=(255, 255, 255))
    dr.text((40, 96), "%s %d %s" % (GIORNI[now.weekday()].capitalize(),
                                    now.day, MESI[now.month - 1]),
            font=f_data, fill=(150, 165, 215))
    dr.line([(36, 140), (W - 36, 140)], fill=(70, 75, 120), width=2)

    # corpo: i prossimi impegni
    y = 162
    ev = [e for e in (d.get("eventi") or [])
          if not e["ora"] or e["ora"] >= now.strftime("%H:%M")]
    if d.get("errore"):
        dr.text((36, y), "Agenda non raggiungibile", font=f_voce, fill=(230, 140, 140))
    elif not ev:
        dr.text((36, y), "Nessun impegno per oggi", font=f_voce, fill=(150, 165, 215))
    else:
        # lo spazio disponibile decide quante voci stanno: l'ultima riga non
        # deve mai finire addosso al piede
        limite = H - 96
        mostrati = 0
        for e in ev:
            if y + 46 > limite:
                break
            dr.rectangle([36, y + 4, 40, y + 30], fill=(90, 130, 235))
            dr.text((58, y), e["ora"] or "--:--", font=f_voce, fill=(120, 165, 255))
            dr.text((150, y + 2), e["titolo"][:30], font=f_sub, fill=(240, 242, 250))
            y += 46
            mostrati += 1
        se_altri = len(ev) - mostrati
        if se_altri > 0:
            dr.text((58, y), "e altri %d" % se_altri, font=f_sub,
                    fill=(130, 145, 190))

    # piede: posta
    n = d.get("non_lette")
    testo = ("Posta: %s da leggere" % n) if n else "Posta in ordine"
    if n is None:
        testo = "Posta non raggiungibile"
    dr.line([(36, H - 58), (W - 36, H - 58)], fill=(70, 75, 120), width=2)
    dr.text((36, H - 42), testo, font=f_pie, fill=(150, 165, 215))
    dr.text((W - 150, H - 42), BRAND, font=f_pie, fill=(95, 110, 165))

    img.save(PNG, "PNG")
    return PNG


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path, _, query = self.path.partition("?")
        args = dict(p.split("=", 1) for p in query.split("&") if "=" in p)

        if path == "/authenticate":
            from urllib.parse import unquote
            ok = check_auth(unquote(args.get("UserID", "")),
                            unquote(args.get("Password", "")))
            payload = b"AUTHORIZED" if ok else b"UNAUTHORIZED"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if path == "/dash.png":
            try:
                raw = open(render_png(), "rb").read()
            except Exception as exc:
                L.log("disegno fallito: %s" % exc)
                self.send_error(500)
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return

        if path == "/idle":
            body = page_idle()
        elif path in ("/services", "/"):
            # schermata disegnata; se il telefono non la reggesse resta /testo
            body = ("<CiscoIPPhoneImageFile><Title>" + esc(BRAND) + "</Title>"
                    "<Prompt></Prompt><LocationX>0</LocationX><LocationY>0</LocationY>"
                    "<URL>http://__PBX_IP__:8081/dash.png</URL>"
                    "</CiscoIPPhoneImageFile>")
        elif path == "/testo":
            body = page_services()
        elif path == "/health":
            body = ("<CiscoIPPhoneText><Title>Stato</Title><Text>%s</Text>"
                    "</CiscoIPPhoneText>" % esc(data()))
        else:
            self.send_error(404)
            return

        raw = ('<?xml version="1.0" encoding="UTF-8"?>' + body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Refresh", "120")
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt, *a):
        print("%s - %s" % (self.address_string(), fmt % a), flush=True)


def check_auth(user, password):
    """Il telefono ci delega la validazione per CGI/Execute."""
    import hmac
    try:
        want_u, _, want_p = open("/var/lib/asterisk/agi-bin/phone-auth.txt").read().strip().partition(":")
    except OSError:
        return False
    return bool(want_u) and hmac.compare_digest(user, want_u) and \
        hmac.compare_digest(password, want_p)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
