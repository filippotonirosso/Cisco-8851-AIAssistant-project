"""Pezzi condivisi fra l'AGI e lo script che pre-genera i suoni."""
import json
import mimetypes
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid

KEYS_FILE = "/etc/asterisk/assistant-keys.conf"
SOUNDS = "/var/lib/asterisk/sounds/assistant"
LOG = "/tmp/assistant.log"

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
# Haiku: scelto per costo e latenza. Attenzione, non e' solo un cambio di
# nome: su questo modello output_config.effort non e' supportato e la
# richiesta verrebbe rifiutata, quindi non va passato.
MODEL = "claude-haiku-4-5"
EL_BASE = "https://api.elevenlabs.io/v1"
# multilingual invece di flash: flash risparmia 0.4s, ma il modello ne impiega
# comunque 3 a pensare, quindi quel guadagno non si nota mentre la differenza
# di qualita' della voce si sente
TTS_MODEL = "eleven_multilingual_v2"

SYSTEM = (
    "Ti chiami Silvio e rispondi al telefono. Parli italiano e dai del tu; ogni tanto puoi chiamarlo capo, ma senza esagerare. "
    "Rispondi come parleresti davvero a voce: naturale, diretto, senza formule "
    "di cortesia inutili e senza ripetere la domanda. Una o due frasi; tre solo "
    "se servono davvero. "
    "Mai elenchi puntati, markdown, emoji o simboli: il testo viene letto ad alta "
    "voce. Numeri e sigle scrivili come si pronunciano. "
    "Se non hai capito, dillo in poche parole e chiedi di ripetere. "
    "Non dire mai che sei un modello linguistico e non scusarti a ripetizione. "

    "REGOLE OPERATIVE, valgono sempre. "
    "Una cosa per volta: non incatenare piu' azioni in un turno. Se servono "
    "due passaggi, fai il primo e chiedi conferma. "
    "Quando elenchi qualcosa (mail, promemoria, appuntamenti) non leggere mai "
    "piu' di cinque voci: di ognuna solo l'essenziale, cioe' chi e di cosa si "
    "tratta in poche parole. Non leggere mai il corpo di una mail per intero: "
    "riassumilo in una frase. Se ce ne sono altre, di' quante sono e basta. "
    "Chi ascolta non puo' rileggere: se ti accorgi che stai per elencare "
    "troppo, fermati e chiedi su cosa vuole approfondire. "
    "Prima di qualsiasi azione irreversibile (inviare una mail, cancellare, "
    "confermare qualcosa) ripeti in una frase cosa stai per fare e aspetta un "
    "si esplicito. Non darlo mai per scontato. "
    "Se una richiesta e' vaga, fai una sola domanda di chiarimento, non tre. "
    "Non puoi inviare email, in nessun caso: puoi solo preparare una bozza, "
    "che restera' in attesa che l'utente la rilegga e la spedisca lui. "
    "Se ti viene chiesto di mandare una mail, prepara la bozza e dillo "
    "chiaramente: la bozza e' pronta, va spedita a mano."
)

GREETING = "Ciao, sono Silvio. Dimmi tutto, capo."

# Un solo riempitivo per turno, breve e neutro: serve a dire "ci sono",
# non a intrattenere. Frasi lunghe o ripetute in serie diventano irritanti.
FILLERS = ["Mmh.", "Allora.", "Dunque."]

# Riempitivi pertinenti: il worker segnala cosa sta facendo e il telefono lo
# dice. "Sto guardando la posta" mentre guarda la posta e' informazione;
# "mmh" ripetuto a vuoto e' solo rumore.
FILLERS_STATO = {
    "posta":      ["Sto guardando la posta.", "Un attimo che controllo le mail."],
    "agenda":     ["Controllo l'agenda.", "Vedo cosa hai in programma."],
    "promemoria": ["Te lo segno subito.", "Un attimo che lo salvo."],
    "bozza":      ["Ti preparo la bozza."],
}


def log(msg):
    try:
        with open(LOG, "a") as f:
            f.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))
    except OSError:
        pass


def load_keys():
    keys = {}
    try:
        with open(KEYS_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    keys[k.strip()] = v.strip()
    except OSError as exc:
        log("chiavi non leggibili: %s" % exc)
    return keys


def _detail(exc):
    try:
        return exc.read().decode("utf-8", "replace")[:300]
    except Exception:
        return str(exc)


def post_json(url, headers, payload, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def post_multipart(url, headers, fields, files, timeout=90):
    boundary = "----agi" + uuid.uuid4().hex
    body = b""
    for name, value in fields.items():
        body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                 % (boundary, name, value)).encode("utf-8")
    for name, path in files.items():
        fname = os.path.basename(path)
        ctype = mimetypes.guess_type(fname)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            content = f.read()
        body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                 "Content-Type: %s\r\n\r\n" % (boundary, name, fname, ctype)).encode("utf-8")
        body += content + b"\r\n"
    body += ("--%s--\r\n" % boundary).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=%s" % boundary)
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def transcribe(wav_path, keys):
    key = keys.get("ELEVENLABS_API_KEY")
    if not key:
        return None
    try:
        res = post_multipart(EL_BASE + "/speech-to-text", {"xi-api-key": key},
                             {"model_id": "scribe_v2", "language_code": "ita",
                              # senza questo il silenzio torna come "[silenzio]"
                              # invece che come stringa vuota, e l'assistente
                              # finisce per rispondere a se stesso
                              "tag_audio_events": "false"},
                             {"file": wav_path})
        text = (res.get("text") or "").strip()
        log("trascritto: %r" % text[:120])
        # cintura e bretelle: se resta solo un [tag] o due lettere, non e' parlato
        import re as _re
        clean = _re.sub(r"\[[^\]]*\]", "", text).strip()
        if len(clean) < 3:
            log("scartato: nessun parlato reale")
            return None
        return clean
    except urllib.error.HTTPError as exc:
        log("STT HTTP %s: %s" % (exc.code, _detail(exc)))
    except Exception as exc:
        log("STT errore: %s" % exc)
    return None


GIORNI = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def now_context():
    """Il modello non ha alcun senso del tempo: gliene diamo uno a ogni turno."""
    t = time.localtime()
    return ("Adesso sono le %d e %02d di %s %d %s %d. "
            "Ti trovi in Italia. Usa questi dati quando ti chiedono l'ora, "
            "la data, il giorno della settimana o quanto manca a qualcosa."
            % (t.tm_hour, t.tm_min, GIORNI[t.tm_wday], t.tm_mday,
               MESI[t.tm_mon - 1], t.tm_year))



# ---- strumenti ------------------------------------------------------------

TOOLS = [
    {
        "name": "crea_promemoria",
        "description": ("Salva un promemoria. All'ora indicata il centralino "
                        "chiamera' l'utente al telefono e leggera' il testo ad "
                        "alta voce. Usa la data e l'ora correnti che ti sono "
                        "state fornite per convertire espressioni come "
                        "'domani alle 9' o 'fra due ore'."),
        "input_schema": {
            "type": "object",
            "properties": {
                "testo": {"type": "string",
                          "description": "Cosa ricordare, formulato per essere letto a voce"},
                "quando": {"type": "string",
                           "description": "Data e ora locali in ISO 8601, es. 2026-08-24T19:30"},
            },
            "required": ["testo", "quando"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "elenca_promemoria",
        "description": "Elenca i promemoria futuri non ancora consegnati.",
        "input_schema": {"type": "object", "properties": {},
                         "required": [], "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "cancella_promemoria",
        "description": "Cancella un promemoria dato il suo numero.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "numero del promemoria"}},
            "required": ["id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "google",
        "description": (
            "Accesso diretto alle API Google dell'utente (Gmail e Calendar). "
            "Componi tu la richiesta REST che ti serve.\n"
            "Esempi utili:\n"
            "- ultime mail: GET gmail/v1/users/me/messages con "
            "params {\"maxResults\": 5, \"q\": \"in:inbox\"}\n"
            "- dettaglio di una mail: GET gmail/v1/users/me/messages/ID con "
            "params {\"format\": \"metadata\", \"metadataHeaders\": \"From\"} "
            "(usa format metadata o snippet, non full: al telefono non serve il corpo intero)\n"
            "- ricerca: stessa chiamata con q, es. \"from:mario is:unread\"\n"
            "- bozza: POST gmail/v1/users/me/drafts con body "
            "{\"message\": {\"raw\": \"<RFC822 codificato base64url>\"}}\n"
            "- agenda: GET calendar/v3/calendars/primary/events con params "
            "{\"timeMin\": \"...Z\", \"maxResults\": 5, \"singleEvents\": true, "
            "\"orderBy\": \"startTime\"}\n"
            "Sono ammesse solo letture e la creazione di bozze. L'invio di email "
            "non e' disponibile e verra' rifiutato: prepara la bozza e dillo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metodo": {"type": "string", "description": "GET oppure POST"},
                "percorso": {"type": "string",
                             "description": "percorso API senza dominio, es. gmail/v1/users/me/messages"},
                "parametri": {"type": "string",
                              "description": "parametri query in JSON. Ometti se non servono."},
                "corpo": {"type": "string",
                          "description": "corpo JSON, solo per POST. Ometti per le GET."},
            },
            "required": ["metodo", "percorso"],
        },
    },
]


def run_tool(name, args):
    import reminders as R
    try:
        if name == "crea_promemoria":
            return R.add(args.get("testo", ""), args.get("quando", ""))
        if name == "elenca_promemoria":
            return R.listing()
        if name == "cancella_promemoria":
            return R.remove(int(args.get("id", 0)))
        if name == "google":
            import google_api as G
            def _j(v):
                v = (v or "").strip()
                if not v:
                    return None
                try:
                    return json.loads(v)
                except Exception:
                    return None
            return G.call(args.get("metodo"), args.get("percorso"),
                          _j(args.get("parametri")), _j(args.get("corpo")))
        return {"errore": "strumento sconosciuto"}
    except Exception as exc:
        log("strumento %s: %s" % (name, exc))
        return {"errore": str(exc)}


def think(text, history, keys, progress=None):
    """Ciclo agentico: se il modello chiede uno strumento lo eseguiamo e gli
    restituiamo il risultato, finche' non produce una risposta parlata."""
    key = keys.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    history.append({"role": "user", "content": text})
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}

    for _ in range(4):          # tetto: al telefono non si aspetta all'infinito
        try:
            res = post_json(ANTHROPIC_URL, headers,
                            {"model": MODEL,
                             # alto apposta: su Opus 5 il ragionamento consuma
                             # questo stesso budget. Con 400 il modello pensava
                             # e restava senza token per rispondere.
                             "max_tokens": 1500,
                             "system": SYSTEM + " " + now_context(),
                             "tools": TOOLS,
                             "messages": history})
        except urllib.error.HTTPError as exc:
            log("Claude HTTP %s: %s" % (exc.code, _detail(exc)))
            return None
        except Exception as exc:
            log("Claude errore: %s" % exc)
            return None

        content = res.get("content", [])
        if res.get("stop_reason") == "tool_use":
            history.append({"role": "assistant", "content": content})
            results = []
            for b in content:
                if b.get("type") != "tool_use":
                    continue
                log("strumento richiesto: %s %s" % (b.get("name"), b.get("input")))
                if progress is not None:
                    inp = b.get("input") or {}
                    perc = str(inp.get("percorso", ""))
                    if b.get("name") != "google":
                        progress["stato"] = "promemoria"
                    elif "calendar" in perc:
                        progress["stato"] = "agenda"
                    elif "drafts" in perc:
                        progress["stato"] = "bozza"
                    else:
                        progress["stato"] = "posta"
                out = run_tool(b.get("name"), b.get("input") or {})
                results.append({"type": "tool_result", "tool_use_id": b.get("id"),
                                "content": json.dumps(out, ensure_ascii=False)})
            history.append({"role": "user", "content": results})
            continue

        answer = " ".join(b.get("text", "") for b in content
                          if b.get("type") == "text").strip()
        if answer:
            history.append({"role": "assistant", "content": answer})
        log("risposta (stop=%s): %r" % (res.get("stop_reason"), answer[:120]))
        if not answer and res.get("stop_reason") == "max_tokens":
            return "Mi sono perso a metta ragionamento. Riprova a chiedermelo."
        return answer or None

    return None


RAW = ["-t", "raw", "-r", "16000", "-e", "signed", "-b", "16", "-c", "1"]


def _rifinisci(path):
    """Toglie il silenzio ai bordi e smussa i tagli.

    ElevenLabs consegna audio con silenzio digitale in testa e in coda: al
    telefono diventa un buco innaturale fra una frase e l'altra, e il taglio
    netto produce il click che si sente come fruscio.

    Due passaggi, non uno: "reverse" fa perdere a sox la lunghezza nota
    dell'audio, e senza quella non sa calcolare la dissolvenza finale.
    """
    a, b = path + ".t1", path + ".t2"
    try:
        subprocess.check_call(                      # 1: via i silenzi ai bordi
            ["sox"] + RAW + [path] + RAW + [a,
             "silence", "1", "0.05", "0.3%",
             "reverse", "silence", "1", "0.05", "0.3%", "reverse"],
            stderr=subprocess.DEVNULL)
        subprocess.check_call(                      # 2: dissolvenze anti-click
            ["sox"] + RAW + [a] + RAW + [b, "fade", "t", "0.03", "0", "0.03"],
            stderr=subprocess.DEVNULL)
        os.replace(b, path)
    except Exception as exc:
        log("rifinitura audio saltata: %s" % exc)
    finally:
        for f in (a, b):
            try:
                os.remove(f)
            except OSError:
                pass


def synth(text, out_no_ext, keys):
    """16 kHz invece di 8: il CP-8851 parla G.722 in banda larga, generare a
    8 kHz buttava via meta' della qualita' disponibile. pcm_16000 corrisponde
    esattamente allo slin16 di Asterisk, quindi niente conversioni."""
    key = keys.get("ELEVENLABS_API_KEY")
    voice = keys.get("ELEVENLABS_VOICE_ID")
    if key and voice:
        url = "%s/text-to-speech/%s?output_format=pcm_16000" % (EL_BASE, voice)
        req = urllib.request.Request(
            url, data=json.dumps({"text": text, "model_id": TTS_MODEL}).encode("utf-8"),
            method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("xi-api-key", key)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                audio = r.read()
            path = out_no_ext + ".sln16"
            with open(path, "wb") as f:
                f.write(audio)
            _rifinisci(path)
            os.chmod(path, 0o644)
            return out_no_ext
        except urllib.error.HTTPError as exc:
            log("TTS HTTP %s: %s" % (exc.code, _detail(exc)))
        except Exception as exc:
            log("TTS errore: %s" % exc)
    # ripiego locale: brutto, ma non lascia mai il telefono muto
    try:
        raw, out = out_no_ext + "-raw.wav", out_no_ext + ".wav16"
        subprocess.check_call(["espeak-ng", "-v", "it", "-s", "150", "-w", raw, text])
        subprocess.check_call(["sox", raw, "-r", "16000", "-c", "1", "-b", "16", out])
        os.remove(raw)
        os.chmod(out, 0o644)
        return out_no_ext
    except Exception as exc:
        log("anche espeak fallito: %s" % exc)
        return None
