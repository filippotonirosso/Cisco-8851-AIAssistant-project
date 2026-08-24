# 7. Gestione quotidiana

Come si avvia, si controlla e si ripara. Tutti i comandi vanno dati sul
Raspberry, o da remoto con `ssh pi@__PBX_IP__ '<comando>'`.

## I cinque servizi

| Servizio | Porta | Cosa succede se manca |
|---|---|---|
| `asterisk` | 5060 | il telefono non registra, niente chiamate |
| `tftpd-hpa` | 69 | il telefono non trova la configurazione **all'avvio** |
| `phone-http` | 6970 | idem via HTTP (il telefono lo prova per primo) |
| `meet-dashboard` | 8081 | niente pannello, e CGI/Execute torna a rispondere 401 |
| `cron` | — | i promemoria non vengono consegnati |

Sono tutti abilitati all'avvio: **dopo un riavvio del Pi non c'è nulla da fare
a mano.**

## Stato

```bash
systemctl is-active asterisk tftpd-hpa phone-http meet-dashboard cron
```

Cinque `active` e siamo a posto. In un colpo solo, la salute del sistema:

```bash
sudo asterisk -rx "pjsip show contacts"      # atteso: Avail + pochi ms
sudo ss -tulnp | grep -E ":(69|5060|6970|8081) "
```

Il contatto **`Avail`** con un tempo di risposta basso è il singolo indicatore
più utile: se è `Unavail` o `nan`, il telefono non è raggiungibile e falliranno
sia le chiamate in entrata sia i promemoria.

## Avvio, arresto, riavvio

```bash
sudo systemctl restart meet-dashboard        # dopo aver toccato dashboard.py
sudo asterisk -rx "dialplan reload"          # dopo aver toccato il dialplan
sudo systemctl restart tftpd-hpa
```

Il codice dell'assistente (`assistant.agi`, `assistant_lib.py`, `reminders.py`,
`google_api.py`) **non richiede riavvii**: viene eseguito da capo a ogni turno di
conversazione. Basta copiare il file e la chiamata successiva lo usa.

> **Prima di ricaricare il dialplan, guarda se c'è qualcuno al telefono:**
> ```bash
> sudo asterisk -rx "core show channels"
> ```
> E non usare mai `channel request hangup all` su un sistema in uso: chiude
> anche le chiamate degli altri, e sembrera' che le tue modifiche abbiano rotto
> tutto.

## Dopo aver modificato la configurazione del telefono

Il file in `/srv/tftp/` viene letto **solo all'avvio del telefono**. Non serve
riavviare nulla sul Pi: si riavvia il telefono, togliendo e rimettendo
l'alimentazione.

Eccezione: `servicesURL` e gli altri URL puntano a servizi che rispondono in
tempo reale. Cambiare cosa *risponde* quel servizio ha effetto immediato;
cambiare l'URL stesso richiede il riavvio del telefono.

## Dopo aver cambiato i testi dell'assistente

Saluto, riempitivi e frasi fisse sono **pre-generati**: vanno risintetizzati.

```bash
sudo -u asterisk python3 /var/lib/asterisk/agi-bin/build-sounds.py
```

## Log

| Cosa | Dove |
|---|---|
| Assistente (trascrizioni, risposte, errori API) | `/tmp/assistant.log` |
| Passi del dialplan | `/tmp/dialplan.log` |
| Richieste di provisioning | `journalctl -u tftpd-hpa` |
| Pannello | `journalctl -u meet-dashboard` |
| Asterisk | `/var/log/asterisk/full` |
| Chiamate | `/var/log/asterisk/cdr-csv/Master.csv` |

Il più utile è il primo: mostra cosa ha capito, cosa ha risposto e quanto ci ha
messo.

```bash
tail -f /tmp/assistant.log
```

> **Leggi i file, non seguirli attraverso un `grep`.** `tail -f | grep`
> bufferizza e sembra dire che non succede niente mentre il log si popola.

## Diagnosi rapida

**Il telefono non chiama e non riceve**

```bash
sudo asterisk -rx "pjsip show contacts"
```

Se `Unavail`: controlla di essere su UDP (`transportLayerProtocol` a `2`) e
riavvia il telefono.

**Compongo 500 e non succede nulla**

```bash
tail -5 /tmp/dialplan.log
```

Se non compare `1 entrato`, la chiamata non è mai arrivata: è un problema di
registrazione, non di assistente. Per vedere se il telefono manda davvero
qualcosa:

```bash
sudo timeout 60 tcpdump -i any -n "host __PHONE_IP__ and port 5060" > /tmp/sip.txt
cat /tmp/sip.txt
```

**Risponde ma dice sempre "non ho capito"**

```bash
grep -a "trascritto\|risposta\|HTTP" /tmp/assistant.log | tail
```

Una `risposta: ''` vuota non significa che non ha capito: significa che il
modello non è riuscito a produrre testo. Vedi [99-trappole.md](99-trappole.md).

**I promemoria non arrivano**

```bash
grep -a promemoria /tmp/assistant.log | tail
cat /var/lib/asterisk/reminders.json
```

## Costi

Ogni scambio consuma crediti ElevenLabs (trascrizione **e** sintesi) e token del
modello. Il silenzio non consuma nulla: se non parli non parte alcuna
trascrizione.

Le frasi fisse sono sintetizzate **una volta sola** e riusate: è il motivo per
cui esiste `build-sounds.py` invece di generarle al volo.

## Accensione manuale con due pulsanti

Se preferisci che il sistema **non parta da solo** all'accensione del Pi — utile
quando l'apparecchio non serve tutti i giorni, o per non lasciare servizi in
ascolto senza motivo — si tolgono i servizi dall'avvio automatico e si mettono
due icone sul desktop.

```bash
sudo systemctl disable asterisk tftpd-hpa phone-http meet-dashboard
```

In `scripts/desktop/` ci sono i due script e i relativi lanciatori `.desktop`:
copiali in `~/bin/` e `~/Desktop/`, rendili eseguibili.

**Accendi** avvia i quattro servizi, riattiva i promemoria e **attende la
registrazione del telefono**, confermandola a schermo: è la differenza fra "ho
lanciato dei comandi" e "il sistema funziona".

**Spegni** ferma tutto. Prima sospende i promemoria, così nessuna consegna parte
durante l'arresto, e avvisa se ci sono chiamate in corso invece di troncarle.

I promemoria non si fermano fermando un servizio: il cron è installato in
permanenza. Sono governati da un file-interruttore,
`/var/lib/asterisk/assistente-attivo`: se manca, `deliver-reminders.py` esce
subito. Il cron continua a girare ogni minuto ma non fa nulla, in pochi
millisecondi.

> Il telefono non funziona finché non premi Accendi: senza Asterisk non si
> registra, e senza TFTP non trova la configurazione se lo riavvii.
