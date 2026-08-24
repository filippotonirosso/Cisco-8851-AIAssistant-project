#!/usr/bin/env python3
"""Autorizzazione Google, una volta sola.

Gira sul Mac (che ha browser e localhost), legge client id e secret dal Pi via
ssh, apre il consenso, e riscrive il refresh token direttamente nel file sul Pi.
Nessun valore sensibile passa dal terminale o dalla chat.
"""
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

PI = "pi@__PBX_IP__"   # utente@host del Raspberry
KEYS = "/etc/asterisk/assistant-keys.conf"
PORT = 8801
REDIRECT = "http://localhost:%d/" % PORT

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",     # bozze; l'invio non e' esposto dal codice
    "https://www.googleapis.com/auth/calendar.readonly",
]

code_box = {}


def pi_get(key):
    out = subprocess.run(
        ["ssh", PI, "sudo grep '^%s=' %s | cut -d= -f2-" % (key, KEYS)],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30)
    return out.stdout.decode().strip()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        code_box["code"] = (q.get("code") or [None])[0]
        code_box["error"] = (q.get("error") or [None])[0]
        msg = ("Autorizzazione ricevuta. Puoi chiudere questa scheda."
               if code_box["code"] else
               "Autorizzazione non riuscita: %s" % code_box.get("error"))
        body = ("<html><body style='font-family:sans-serif;padding:3rem'>"
                "<h2>%s</h2></body></html>" % msg).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def main():
    cid = pi_get("GOOGLE_CLIENT_ID")
    csec = pi_get("GOOGLE_CLIENT_SECRET")
    if not cid or not csec:
        print("ERRORE: client id o secret mancanti sul Pi")
        return 1

    auth = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cid,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",     # senza questo non arriva il refresh token
        "prompt": "consent",          # forza il consenso: se no al secondo giro non lo ridà
    })
    print("APRI QUESTO INDIRIZZO NEL BROWSER:\n")
    print(auth)
    print("\nin attesa dell'autorizzazione...", flush=True)

    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    srv.timeout = 300
    while "code" not in code_box and "error" not in code_box:
        srv.handle_request()

    if not code_box.get("code"):
        print("nessun codice ricevuto: %s" % code_box.get("error"))
        return 1

    data = urllib.parse.urlencode({
        "code": code_box["code"], "client_id": cid, "client_secret": csec,
        "redirect_uri": REDIRECT, "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            tok = json.loads(r.read().decode())
    except Exception as exc:
        detail = ""
        try:
            detail = exc.read().decode()[:300]
        except Exception:
            pass
        print("scambio del codice fallito: %s %s" % (exc, detail))
        return 1

    refresh = tok.get("refresh_token")
    if not refresh:
        print("Google non ha restituito un refresh token.")
        return 1

    # scrittura sul Pi via stdin: il token non compare mai in una riga di comando
    p = subprocess.run(
        ["ssh", PI,
         "sudo python3 -c \"import sys,re;p='%s';t=sys.stdin.read().strip();"
         "s=open(p).read();s=re.sub(r'^GOOGLE_REFRESH_TOKEN=.*$','GOOGLE_REFRESH_TOKEN='+t,s,flags=re.M);"
         "open(p,'w').write(s);print('scritto')\"" % KEYS],
        input=refresh.encode(), stdout=subprocess.PIPE, timeout=30)
    print("refresh token salvato sul Pi:", p.stdout.decode().strip())
    print("scope concessi:", tok.get("scope", "?"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
