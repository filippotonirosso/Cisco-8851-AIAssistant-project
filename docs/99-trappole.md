# 99. Trappole

Tutte incontrate sul campo. Nessuna dava un messaggio d'errore utile.

## Telefono

**Il firmware rifiuta l'intera configurazione al primo errore, e non dice
quale.** Sintomo: il telefono ri-scarica il file ogni ~15 secondi, l'interfaccia
si reinizializza di continuo, i tasti sembrano bloccati. Non scrivere la
configurazione a mano: partire dal template di riferimento.

**La trust list residua fa rifiutare tutto.** Se il telefono è stato su un CUCM,
finché non cancelli l'ITL nessuna configurazione verrà accettata. È il singolo
punto in cui si arenano quasi tutti.

**`Alternate TFTP` va messo a `Yes` PRIMA dell'indirizzo.** Se no il campo
sottostante viene accettato e poi ignorato: sembra impostato e non fa nulla.

**L'onboarding blocca il provisioning.** Con "Enter activation code" a schermo il
telefono non scarica niente. Premere Cancel.

**Su TCP il telefono diventa periodicamente irraggiungibile.** Contatto
`Unavail`, chiamate in entrata fallite, e — meno ovvio — **anche le chiamate in
uscita bloccate**, perché usa la stessa connessione. Sintomo tipico: "il
telefono è connesso ma comporre l'interno non fa nulla", che ricompare
ciclicamente e sembra risolversi da solo dopo una ri-registrazione. **Usare UDP.**

**`defaultWallpaperFile` impone lo sfondo.** Senza, i file ci sono ma lo sfondo
non compare finché non lo scegli dal menu.

**404 normali**: `g3-tones.xml`, `sl-be-sip.jar`, `CTLSEP*.tlv`, `ITLFile.tlv`.
Sono file che normalmente genera CUCM. Non impediscono il funzionamento.

## Asterisk

**`Playback` vuole il percorso assoluto.** Con percorso relativo cerca dentro la
cartella della lingua, dove i file personalizzati non stanno.

**Il verbose impostato da `asterisk -rx "core set verbose 3"` non vale.** Si
applica solo a quella console effimera, che si chiude subito. Il log resta muto
e sembra che il dialplan non venga eseguito. Per tracciare, usare `System()` che
scrive su file: non dipende da nessuna impostazione.

```
same => n,System(/bin/echo "$(/bin/date +%T) passo 1" >> /tmp/dialplan.log)
```

**`channel request hangup all` chiude anche le chiamate dell'utente.** Se lo usi
per pulire canali zombie mentre qualcuno sta telefonando, sembrerà che le tue
modifiche abbiano rotto il sistema. Controlla `core show channels` prima.

**`BackgroundDetect` è l'unico modo di riprodurre restando in ascolto.** Serve
per l'interruzione vocale. Soglia minima di parlato ~400 ms, sotto scatta
sull'eco della propria voce.

## Sistema

**cron non ha `/usr/sbin` nel PATH.** Invocare i binari con percorso assoluto.
Combinato con `>/dev/null 2>&1` nella crontab, il fallimento è **invisibile**.

**`tftpd-hpa` parte prima della rete e non riprova.** Fallisce con
`status=66/NOINPUT` e resta morto finché qualcuno non se ne accorge, magari mesi
dopo. Serve l'override systemd con `After=network-online.target` e
`Restart=on-failure`.

**`grep` in una pipe bufferizza.** Un `tail -f | grep` sembra dire che non
succede nulla mentre il log si popola. Leggere il file, non seguirlo.

**`env -i` senza `HOME` rompe la CLI di Asterisk.** Utile saperlo quando si
simula l'ambiente di cron per riprodurre un problema.

## Audio

**ElevenLabs imbottisce di silenzio digitale.** 130-170 ms in testa e ~230 in
coda: fra una frase e l'altra si sente un buco innaturale, e il taglio netto
produce un click. Vanno tolti (`_rifinisci`).

**La pulizia audio richiede due passaggi di sox.** `reverse` fa perdere a sox la
lunghezza nota dell'audio, e senza quella `fade` non può calcolare la dissolvenza
finale: fallisce con *"cannot fade out: audio length is neither known nor
given"*.

**Generare a 8 kHz butta via metà della qualità.** Il telefono parla G.722.
Usare 16 kHz (`sln16`, `pcm_16000`) ovunque, anche per registrare.

## Modello e trascrizione

**ElevenLabs Scribe annota il silenzio.** Senza `tag_audio_events=false`, una
registrazione muta torna come `[silenzio]` e non come stringa vuota. Risultato:
l'assistente risponde a se stesso ogni pochi secondi, all'infinito. Filtrare
anche le trascrizioni fatte di soli `[tag]`.

**Con i modelli che ragionano, `max_tokens` basso produce risposte vuote.** Il
ragionamento attinge allo stesso budget: il modello pensa, esaurisce i token e
non ne resta per parlare. Sintomo: risposta vuota dopo una lunga attesa, che il
codice a valle interpreta come "non ho capito".

**Campi obbligatori inutili fanno inventare spazzatura.** Uno strumento che
richiede `corpo` anche sulle GET si vede riempire quel campo con testo casuale
pur di rispettare lo schema. Rendere obbligatorio solo ciò che serve davvero.

**`output_config.effort` non è supportato su tutti i modelli** e su alcuni fa
rifiutare la richiesta. Cambiare modello non è mai solo cambiare una stringa.
