# 4. Promemoria

Glieli detti a voce; all'ora giusta **il telefono ti chiama** e te li legge.

> *"Ricordami fra tre minuti di chiamare il commercialista"* → conferma a voce
> → tre minuti dopo il telefono squilla e lo dice.

## Come funziona

Tre strumenti dichiarati al modello (`crea_promemoria`, `elenca_promemoria`,
`cancella_promemoria`) in `assistant_lib.py`. Archivio JSON in
`/var/lib/asterisk/reminders.json`, scritto in modo atomico.

La consegna è un cron ogni minuto:

```
* * * * * asterisk /usr/bin/python3 /var/lib/asterisk/agi-bin/deliver-reminders.py
```

Sintetizza il testo e apre una chiamata verso l'interno con `Playback`.

## Due trappole

**cron non ha `/usr/sbin` nel PATH.** Il binario `asterisk` va invocato con
percorso assoluto (`ASTERISK` in `reminders.py`), altrimenti la consegna
fallisce con `No such file or directory: 'asterisk'` — e siccome il cron scarta
l'output, fallisce **in silenzio**. Il promemoria semplicemente non arriva.

**`current_contact()`.** Su TCP il qualify falliva, Asterisk marcava il contatto
`Unavail` e componendo `PJSIP/<interno>` ripiegava sul nome dell'interno come
URI — che non è un indirizzo, e la chiamata falliva con *"Could not create
dialog to invalid URI"*. La funzione legge il contatto reale e compone quello.
**Passando a UDP il problema non si presenta più**, ma la funzione resta come
rete di sicurezza.

## Nessun timer di sicurezza

Non c'è chiusura automatica della chiamata dopo N turni di silenzio: se non
parli non parte alcuna trascrizione, quindi non consuma nulla, e un assistente
che riaggancia da solo è irritante.

## Verifica

```bash
sudo -u asterisk python3 -c "
import sys, time; sys.path.insert(0,'/var/lib/asterisk/agi-bin')
import reminders as R
print(R.add('prova', time.strftime('%Y-%m-%dT%H:%M', time.localtime(time.time()+120))))"
```

Il telefono deve squillare entro due minuti. Il registro è in
`/tmp/assistant.log`.
