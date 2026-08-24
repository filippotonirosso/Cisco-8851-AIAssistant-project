"""Promemoria: archivio su file e consegna telefonica.

Nessuna credenziale: vive tutto sul Pi. Un promemoria scaduto fa squillare
il telefono e viene letto ad alta voce.
"""
import json
import os
import subprocess
import time

# percorso assoluto: cron non ha /usr/sbin nel PATH e il binario non si trova
ASTERISK = "/usr/sbin/asterisk"
STORE = "/var/lib/asterisk/reminders.json"
EXTENSION = "104"          # interno da chiamare
SOUNDS = "/var/lib/asterisk/sounds/assistant"


def _load():
    try:
        with open(STORE) as f:
            return json.load(f)
    except Exception:
        return []


def _save(items):
    tmp = STORE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STORE)          # scrittura atomica: niente file mezzi scritti
    try:
        os.chmod(STORE, 0o644)
    except OSError:
        pass


def add(testo, quando):
    """quando: ISO 8601 locale, es. 2026-08-24T19:30"""
    try:
        t = time.strptime(quando[:16], "%Y-%m-%dT%H:%M")
    except ValueError:
        return {"errore": "data non valida, serve il formato 2026-08-24T19:30"}
    epoch = time.mktime(t)
    if epoch < time.time() - 60:
        return {"errore": "quella data e' gia' passata"}
    items = _load()
    rid = max([i.get("id", 0) for i in items] + [0]) + 1
    items.append({"id": rid, "testo": testo, "quando": quando[:16],
                  "epoch": epoch, "fatto": False})
    _save(items)
    return {"ok": True, "id": rid,
            "conferma": "promemoria salvato per il %s alle %s"
                        % (quando[8:10] + "/" + quando[5:7], quando[11:16])}


def listing(solo_futuri=True):
    now = time.time()
    out = [{"id": i["id"], "testo": i["testo"], "quando": i["quando"]}
           for i in _load()
           if not i.get("fatto") and (not solo_futuri or i["epoch"] > now)]
    return {"promemoria": out} if out else {"promemoria": [], "nota": "nessuno"}


def remove(rid):
    items = _load()
    keep = [i for i in items if i.get("id") != rid]
    if len(keep) == len(items):
        return {"errore": "nessun promemoria con quel numero"}
    _save(keep)
    return {"ok": True}


def due():
    now = time.time()
    return [i for i in _load() if not i.get("fatto") and i["epoch"] <= now]


def mark_done(rid):
    items = _load()
    for i in items:
        if i.get("id") == rid:
            i["fatto"] = True
    _save(items)


def current_contact():
    """Indirizzo reale a cui e' registrato il telefono.

    Non si usa PJSIP/<interno> perche' il qualify su TCP fallisce e Asterisk,
    vedendo il contatto marcato Unavail, ripiega sul nome dell'interno come
    URI - che non e' un indirizzo e fa fallire la chiamata. Il contatto pero'
    e' perfettamente raggiungibile: basta comporlo esplicitamente.
    """
    try:
        out = subprocess.run([ASTERISK, "-rx", "pjsip show aor %s" % EXTENSION],
                             stdout=subprocess.PIPE, timeout=20).stdout.decode(
                                 "utf-8", "replace")
    except Exception:
        return None
    for line in out.splitlines():
        if line.strip().startswith("contact") and "sip:" in line:
            return line.split(":", 1)[1].strip()
    return None


def deliver(item, keys):
    """Sintetizza il promemoria e fa squillare il telefono."""
    import assistant_lib as L
    base = os.path.join("/tmp", "promemoria-%d" % item["id"])
    testo = "Promemoria, capo. %s" % item["testo"]
    if not L.synth(testo, base, keys):
        L.log("promemoria %d: sintesi fallita" % item["id"])
        return False
    uri = current_contact()
    target = "PJSIP/%s/%s" % (EXTENSION, uri) if uri else "PJSIP/%s" % EXTENSION
    cmd = [ASTERISK, "-rx",
           "channel originate %s application Playback %s" % (target, base)]
    try:
        out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             timeout=60).stdout.decode("utf-8", "replace").strip()
        L.log("promemoria %d consegnato: %s" % (item["id"], out[:120]))
        return True
    except Exception as exc:
        L.log("promemoria %d: chiamata fallita: %s" % (item["id"], exc))
        return False
