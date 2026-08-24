"""Accesso alle API Google per l'assistente.

Filosofia: l'agente decide COSA chiedere; il codice decide COSA e' raggiungibile.
Lui compone endpoint e parametri come preferisce, ma passa da una lista di
permessi esplicita. Tutto cio' che non e' elencato viene rifiutato prima di
uscire dal Pi.

In particolare NON esiste alcun percorso che invii una mail: la decisione di
limitarsi alle bozze e' applicata qui, non nelle istruzioni al modello, perche'
un'istruzione si puo' disattendere e una lista di permessi no.
"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

TOKEN_CACHE = "/tmp/google-token.json"
BASE = "https://www.googleapis.com/"
MAX_BYTES = 24000        # tetto sulla risposta: al telefono non si legge un romanzo

# (metodo, espressione regolare sul percorso)
ALLOW = [
    ("GET",  r"^gmail/v1/users/me/messages$"),
    ("GET",  r"^gmail/v1/users/me/messages/[\w-]+$"),
    ("GET",  r"^gmail/v1/users/me/threads$"),
    ("GET",  r"^gmail/v1/users/me/threads/[\w-]+$"),
    ("GET",  r"^gmail/v1/users/me/labels$"),
    ("GET",  r"^gmail/v1/users/me/profile$"),
    ("GET",  r"^gmail/v1/users/me/drafts$"),
    ("POST", r"^gmail/v1/users/me/drafts$"),          # crea bozza: non spedisce
    ("GET",  r"^calendar/v3/calendars/[^/]+/events$"),
    ("GET",  r"^calendar/v3/users/me/calendarList$"),
]

# rete di sicurezza esplicita: anche se una regola sopra fosse scritta male,
# qualunque percorso che assomigli a un invio viene bloccato comunque
DENY = re.compile(r"(send|trash|delete|batchDelete|watch|stop)", re.I)


def _keys():
    import assistant_lib as L
    return L.load_keys()


def access_token():
    """Token valido, rinnovato col refresh token quando scade."""
    try:
        c = json.load(open(TOKEN_CACHE))
        if c.get("expires_at", 0) > time.time() + 60:
            return c["access_token"]
    except Exception:
        pass

    k = _keys()
    cid, csec, refresh = (k.get("GOOGLE_CLIENT_ID"), k.get("GOOGLE_CLIENT_SECRET"),
                          k.get("GOOGLE_REFRESH_TOKEN"))
    if not (cid and csec and refresh):
        return None
    data = urllib.parse.urlencode({
        "client_id": cid, "client_secret": csec,
        "refresh_token": refresh, "grant_type": "refresh_token"}).encode()
    try:
        with urllib.request.urlopen(
                urllib.request.Request("https://oauth2.googleapis.com/token", data=data),
                timeout=30) as r:
            tok = json.loads(r.read().decode())
    except Exception:
        return None
    at = tok.get("access_token")
    if at:
        try:
            json.dump({"access_token": at,
                       "expires_at": time.time() + int(tok.get("expires_in", 3600))},
                      open(TOKEN_CACHE, "w"))
            os.chmod(TOKEN_CACHE, 0o600)
        except OSError:
            pass
    return at


def permitted(method, path):
    if DENY.search(path):
        return False
    return any(m == method and re.match(rx, path) for m, rx in ALLOW)


def call(method, path, params=None, body=None):
    method = (method or "GET").upper()
    path = (path or "").lstrip("/")
    if not permitted(method, path):
        return {"errore": "endpoint non consentito: %s %s. Sono ammesse solo "
                          "letture di Gmail e Calendar e la creazione di bozze; "
                          "l'invio non e' disponibile." % (method, path)}
    token = access_token()
    if not token:
        return {"errore": "credenziali Google non disponibili"}

    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        try:
            det = json.loads(exc.read().decode()).get("error", {}).get("message", "")
        except Exception:
            det = ""
        return {"errore": "Google ha risposto %s %s" % (exc.code, det[:200])}
    except Exception as exc:
        return {"errore": str(exc)}

    if len(raw) > MAX_BYTES:
        return {"errore": "risposta troppo grande: restringi la richiesta, "
                          "per esempio con maxResults piu' basso o una query piu' "
                          "specifica"}
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        return {"errore": "risposta non interpretabile"}
