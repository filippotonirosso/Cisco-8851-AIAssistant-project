# 3. L'assistente vocale

Interno **500**. Alzi, parli, ti risponde.

## Come funziona

`extensions_custom.conf` risponde, riproduce il saluto e chiama l'AGI a ogni
turno. L'AGI registra, trascrive, interroga il modello, sintetizza e **consegna
il file al dialplan**, che lo riproduce con `BackgroundDetect`.

Perché non lo riproduce l'AGI: `BackgroundDetect` è l'unico modo in Asterisk di
suonare un file **restando in ascolto**. Quando rileva che l'utente ha ripreso a
parlare salta all'estensione `talk`, che rientra nel ciclo — cioè lo interrompe
a metà frase. Soglia a 400 ms di parlato continuo: sotto quella scatta sull'eco
della propria voce, soprattutto in vivavoce.

## File

| File | Ruolo |
|---|---|
| `assistant.agi` | un turno: registra, coordina, consegna |
| `assistant_lib.py` | trascrizione, modello, sintesi, strumenti |
| `google_api.py` | accesso recintato a Gmail e Calendar |
| `reminders.py` | archivio e consegna promemoria |
| `build-sounds.py` | pre-genera saluto e riempitivi |

```bash
sudo -u asterisk python3 /var/lib/asterisk/agi-bin/build-sounds.py
```

Da rilanciare ogni volta che cambi i testi in `assistant_lib.py`.

## Audio

Tutto a **16 kHz** (`sln16`): il telefono parla G.722, generare a 8 kHz
buttava via metà della qualità. ElevenLabs consegna `pcm_16000`, che è già il
formato nativo di Asterisk — nessuna conversione.

Ogni file sintetizzato passa da `_rifinisci()`: toglie il silenzio ai bordi e
applica 30 ms di dissolvenza. Senza, fra una frase e l'altra si sente un buco
innaturale e un click ai tagli.

## Riempitivi

Mentre il modello lavora, un thread separato elabora e il principale parla. I
riempitivi sono **pertinenti**: se sta guardando la posta dice "Sto guardando la
posta". `FILLERS_STATO` in `assistant_lib.py`.

Prima si aspetta 1,2 secondi: se la risposta arriva subito non si dice nulla.

## Modello

`MODEL` in `assistant_lib.py`. Attenzione: **non è solo un cambio di nome**.
`output_config.effort` non è supportato su tutti i modelli e su alcuni fa
rifiutare la richiesta; con i modelli che ragionano, `max_tokens` deve essere
generoso perché il ragionamento attinge allo stesso budget — con un valore
basso il modello pensa e resta senza token per rispondere, restituendo una
risposta **vuota**.

## Chiusura

Frasi come "chiudi", "basta", "arrivederci", "grazie" chiudono la chiamata.
È riconoscimento diretto delle parole (`wants_close`), non una decisione del
modello: così è istantaneo e funziona anche se le API sono irraggiungibili.

L'estensione `h` cancella memoria della conversazione e file audio a fine
chiamata.

## Regole di condotta

In `SYSTEM`: una azione per turno, massimo cinque voci per elenco, mai leggere
una mail per intero, conferma esplicita prima di azioni irreversibili.

**I limiti che contano davvero sono nel codice**, non nel prompt: `google_api.py`
tronca le risposte troppo grandi e rifiuta gli endpoint non ammessi. Le
istruzioni sono indicazioni, il codice è un vincolo.
