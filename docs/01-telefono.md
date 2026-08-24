# 1. Il telefono (client)

La parte difficile. Il firmware **Enterprise** del CP-8851 è pensato per
registrarsi a CUCM: non ha una pagina web dove scrivere le credenziali SIP, si
aspetta di **scaricare la configurazione via TFTP all'avvio**.

Si può fare senza CUCM e senza licenze: basta servirgli il file che si aspetta.

## Prerequisiti

- Firmware Enterprise (verificabile da `Applicazioni → Status → Product
  Information`: se il *Load ID* contiene `MPP` questa guida non serve, hai già
  il firmware multipiattaforma con la web UI)
- Telefono e Raspberry sulla stessa rete

## Passo 1 — Cancellare la trust list

**Da fare per primo.** Se il telefono è mai stato agganciato a un CUCM conserva
una *Identity Trust List* e rifiuterà qualsiasi configurazione non firmata da
quel CUCM, senza dire perché.

```
Impostazioni → Admin Settings → Reset Settings → Security
```

Oppure reset completo: scollega l'alimentazione, tieni premuto `#` mentre la
ricolleghi, rilascia quando il LED lampeggia, digita `123456789*0#`.

## Passo 2 — La configurazione

Copia `phone/SEP__MAC__.cnf.xml` in `/srv/tftp/`, rinominalo con il MAC reale
(`SEPAABBCCDDEEFF.cnf.xml`, **maiuscolo**) e sostituisci i segnaposto.

Il file deriva dal template del progetto
[usecallmanagernz/tftpboot](https://github.com/usecallmanagernz/tftpboot)
(CC BY 4.0), che copre tutti i nodi che il firmware si aspetta.

> **Non scrivere questo file a mano.** Il firmware **rifiuta l'intero file** se
> trova un errore, e non dice quale né dove. Il telefono entra in un ciclo di
> ri-provisioning ogni ~15 secondi: l'interfaccia si reinizializza di continuo e
> i tasti sembrano bloccati. Partire dal template e modificarlo.

I valori che contano:

| Nodo | Valore |
|---|---|
| `processNodeName` | IP del centralino |
| `sipLines/line/name`, `authName`, `authPassword`, `contact` | interno e password SIP |
| `transportLayerProtocol` | `2` = UDP, `1` = TCP, `3` = TLS |
| `deviceSecurityMode` | `1` (non sicuro: senza CUCM non c'è CA) |
| `defaultWallpaperFile` | impone lo sfondo senza doverlo scegliere dal menu |
| `phoneLabel` | intestazione in cima allo schermo, max 12 caratteri |

**Usa UDP.** La documentazione di riferimento sconsiglia UDP per possibili
errori di ritrasmissione SIP, ma su TCP il telefono risultava periodicamente
irraggiungibile: connessione morta, contatto `Unavail`, chiamate in entrata
fallite e — meno ovvio — **anche le chiamate in uscita bloccate**, perché il
telefono usa la stessa connessione. Passando a UDP il problema è sparito.

Serve anche `XMLDefault.cnf.xml` nella stessa cartella: il telefono lo chiede
prima del proprio.

## Passo 3 — Puntare il telefono al TFTP

Senza controllo del DHCP, a mano sul telefono:

```
Impostazioni → Admin Settings → Network Setup → IPv4 Setup
  Alternate TFTP  = Yes     ← per primo, altrimenti il campo sotto è ignorato
  TFTP Server 1   = IP del Raspberry
```

Se i campi sono in grigio: `**#` per sbloccarli. Con il DHCP sotto controllo,
l'alternativa pulita è la **option 150**.

Poi riavvia (togli e rimetti l'alimentazione).

## Passo 4 — L'onboarding

Al primo avvio il firmware recente mostra **"Enter activation code"** e non
scarica nulla finché resta lì. Premi **Cancel**: appare "Unprovisioned" e da
quel momento inizia a chiedere la configurazione via TFTP.

## Passo 5 — Verifica

```bash
ssh pi@PBX 'sudo journalctl -u tftpd-hpa -f'      # deve chiedere il file
ssh pi@PBX 'sudo asterisk -rx "pjsip show contacts"'
```

Atteso: contatto **`Avail`** con un tempo di risposta di pochi millisecondi.
Se resta `Unavail`, vedi [99-trappole.md](99-trappole.md).

Il telefono chiede anche `g3-tones.xml`, `sl-be-sip.jar` e i file `.tlv` di
sicurezza. **Quei 404 sono normali** e non impediscono il funzionamento.

## Tetto di tempo

Se dopo qualche ora non si registra, l'alternativa razionale è la licenza di
conversione a firmware MPP (`L-CP-E2M-88XX-CNV=`), che richiede Enterprise
12.5(1)SR3 o successivo. Con MPP il telefono ha una web UI e si registra a
qualsiasi PBX in dieci minuti.
