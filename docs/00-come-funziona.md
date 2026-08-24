# 0. Come funziona il provisioning, e come si evita CUCM

Da leggere prima della procedura. Capito questo, il resto sono dettagli.

## Il modello mentale sbagliato

Un telefono SIP normale ha il concetto di **account**: server, utente, password,
tre campi in una pagina web. Il CP-8851 con firmware Enterprise **non ha questo
concetto**. Non ha una pagina dove scrivere le credenziali, e non è un limite
dell'interfaccia: è che il firmware non pensa in termini di account.

Pensa in termini di **cluster**. All'avvio la sua domanda non è "a quale server
mi registro" ma "chi è il mio CUCM, e cosa mi ordina di fare". Tutto — interno,
password, codec, tasti, suonerie, lingua, perfino se la pagina web è attiva —
arriva da un file che scarica all'accensione.

Ed è esattamente questa rigidità che lo rende scavalcabile: se controlli quel
file, controlli il telefono. Non serve un CUCM, serve **qualcosa che risponda al
posto suo**.

## La sequenza di avvio

Il telefono, acceso, fa in ordine:

1. **DHCP** — prende l'indirizzo, e cerca nell'offerta la **option 150**: l'IP
   del server di provisioning. Se non controlli il DHCP, glielo dici a mano
   (`Alternate TFTP`).
2. **Scarica la propria configurazione**, cercandola col proprio MAC nel nome:
   `SEPAABBCCDDEEFF.cnf.xml`. Prima prova **HTTP sulla porta 6970**, poi ripiega
   su **TFTP sulla 69** (dal firmware 12.5 in poi preferisce HTTP).
3. **Legge il file** e da lì apprende chi è il suo centralino, con che credenziali
   registrarsi e come comportarsi.
4. **Si registra in SIP** all'indirizzo che ha letto.

Ecco la sequenza reale osservata sul nostro TFTP, in ordine:

```
RRQ  ITLSEP<MAC>.tlv          ← lista di fiducia, sicurezza
RRQ  ITLFile.tlv              ← idem
RRQ  SEP<MAC>.cnf.xml         ← LA configurazione
RRQ  <lingua>/sl-be-sip.jar   ← pacchetto lingua
RRQ  /g3-tones.xml            ← toni di linea del paese
RRQ  AppDialRules.xml         ← regole di composizione
RRQ  CTLSEP<MAC>.tlv          ← certificati
RRQ  defaultheadsetconfig.json
```

Di questi **serve solo il terzo**. Tutti gli altri possono dare 404: il telefono
protesta in silenzio e prosegue. È una scoperta importante, perché all'inizio
sembra che manchi qualcosa di essenziale.

## Il trucco: `USECALLMANAGER`

Nel file di configurazione, la linea SIP ha questo campo:

```xml
<proxy>USECALLMANAGER</proxy>
```

Non è un indirizzo: è una **stringa magica** che significa *"il proxy è il call
manager che ti ho indicato più su"*. E il call manager è definito qui:

```xml
<callManagerGroup>
  <members>
    <member priority="0">
      <callManager>
        <ports><sipPort>5060</sipPort></ports>
        <processNodeName>IP_DEL_TUO_ASTERISK</processNodeName>
      </callManager>
    </member>
  </members>
</callManagerGroup>
```

Qui sta tutto. Il telefono crede di parlare con un CUCM; in realtà `processNodeName`
punta a un Asterisk. Il telefono manda un **REGISTER SIP perfettamente
standard**, con le credenziali prese da `authName` e `authPassword`, e Asterisk
lo accetta come qualsiasi altro interno.

Non c'è nessun exploit e nessuna licenza aggirata: il firmware parla SIP
standard, gli si dice solo dove mandarlo.

## Cosa abbiamo messo al posto di CUCM

CUCM è tante cose insieme. Ne servivano solo due:

| Ruolo di CUCM | Sostituto | Serve? |
|---|---|---|
| Server di provisioning (TFTP/HTTP) | `tftpd-hpa` + `python3 -m http.server` | **sì** |
| Registrar / proxy SIP | Asterisk (FreePBX) | **sì** |
| TVS (verifica certificati) | — | no, in modalità non sicura |
| CAPF (emissione certificati) | — | no |
| Directory aziendale | opzionale, un tuo URL | no |
| Pacchetti lingua e toni | — | no, il telefono resta in inglese |
| Distribuzione firmware | — | no, vedi sotto |

## La sicurezza, e perché si può disattivare

Il telefono verifica che la configurazione sia **firmata** dal CUCM che conosce.
Il meccanismo è l'**ITL** (Identity Trust List): un file che il telefono conserva
in memoria e che contiene le chiavi di cui si fida.

Qui sta la trappola più insidiosa: se il telefono è stato in passato su un CUCM,
ha ancora quell'ITL, e rifiuterà la nostra configurazione non firmata **senza
dire perché**. Sembra semplicemente rotto.

Cancellata l'ITL, e con:

```xml
<deviceSecurityMode>1</deviceSecurityMode>
```

il telefono accetta configurazioni non firmate. È ragionevole su una rete
domestica; su una rete aziendale è una scelta da fare consapevolmente, perché
chiunque possa rispondere al posto del TFTP può riconfigurare il telefono.

## Il firmware: non toccarlo

Nel file esiste un campo `<loadInformation>` con cui CUCM ordina al telefono
quale firmware installare. **Va lasciato fuori.** Se lo specifichi, il telefono
cerca quel firmware sul tuo server; non trovandolo può entrare in un ciclo di
riavvii. Omettendolo, si tiene quello che ha — che è esattamente ciò che
vogliamo.

## Perché il file non va scritto a mano

Il firmware valida l'intero documento e, al primo nodo che non gli torna,
**scarta tutto**. Non applica la parte buona, non segnala quale nodo, non scrive
niente di utile.

Il sintomo è caratteristico e all'inizio depistante: il telefono ri-scarica la
configurazione ogni ~15 secondi, l'interfaccia si reinizializza in continuazione,
i tasti sembrano bloccati. Sembra un problema di rete o di prestazioni; è un
errore di sintassi.

La soluzione non è indovinare meglio, è **partire da un file completo e valido** —
il template di [usecallmanagernz/tftpboot](https://github.com/usecallmanagernz/tftpboot)
— e cambiarne solo i valori.

## In sintesi

1. Il telefono chiede la sua configurazione a un server, all'accensione
2. Gli si dice dove chiederla (option 150, o `Alternate TFTP` a mano)
3. Nel file, `processNodeName` punta al tuo Asterisk invece che a un CUCM
4. `USECALLMANAGER` fa sì che la linea SIP usi quel server
5. Cancellata l'ITL e con `deviceSecurityMode` non sicuro, il file viene accettato
6. Il telefono manda un REGISTER SIP normale e si registra

Il resto — assistente vocale, promemoria, schermata — si costruisce sopra questo.
