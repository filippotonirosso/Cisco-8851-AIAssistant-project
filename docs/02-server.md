# 2. Il server

Raspberry Pi 400 (4 core, 4 GB) con FreePBX. Funziona su qualsiasi Linux sempre
acceso: un NAS, un mini PC, una VM.

> **Nota sull'originale**: girava su Raspbian Buster, che è end-of-life. Per
> giocare va bene; se ci passano telefonate aziendali, quella macchina va
> rifatta su una distribuzione supportata prima di appoggiarci il lavoro vero.

## Componenti

| Servizio | Porta | A cosa serve |
|---|---|---|
| Asterisk / FreePBX | 5060 | centralino SIP |
| `tftpd-hpa` | 69 | configurazione del telefono |
| HTTP statico | 6970 | idem, via HTTP: dal firmware 12.5 il telefono lo preferisce |
| `dashboard.py` | 8081 | schermata del telefono + autenticazione CGI |

## Installazione

```bash
sudo apt install asterisk tftpd-hpa espeak-ng sox tcpdump python3-pil
```

Nessuna dipendenza pip: il codice usa solo la libreria standard. Se il tuo
Python è ≥ 3.10 puoi usare l'SDK ufficiale `anthropic` al posto delle chiamate
HTTP diirette; qui non era possibile perché Buster ferma a Python 3.7.

### TFTP

`/etc/default/tftpd-hpa`:

```
TFTP_USERNAME="tftp"
TFTP_DIRECTORY="/srv/tftp"
TFTP_ADDRESS="0.0.0.0:69"
TFTP_OPTIONS="--secure --verbose"
```

Copia `server/systemd/tftpd-override.conf` in
`/etc/systemd/system/tftpd-hpa.service.d/override.conf`: senza, il servizio
parte prima che la rete sia pronta, fallisce con `status=66/NOINPUT` e **non
riprova mai più**. È un guasto silenzioso che può restare latente per mesi.

### HTTP di provisioning (porta 6970)

```bash
python3 -m http.server 6970 --directory /srv/tftp
```

Come unit systemd, sul modello di `server/systemd/meet-dashboard.service`.

### Asterisk

- `server/asterisk/extensions_custom.conf` → `/etc/asterisk/` (FreePBX include
  `from-internal-custom`, quindi non viene sovrascritto dalla GUI)
- `server/asterisk/pjsip.transports_custom.conf` → `/etc/asterisk/` se ti serve
  anche il transport TCP

Sull'interno del telefono, da GUI FreePBX:

| Impostazione | Valore | Perché |
|---|---|---|
| `direct_media` | **no** | il firmware Enterprise gestisce male i reinvite |
| `rewrite_contact` | yes | |
| `rtp_symmetric`, `force_rport` | yes | |
| codec | includere **g722** | banda larga: raddoppia la qualità audio |

### Codice

```bash
sudo cp server/agi/* /var/lib/asterisk/agi-bin/
sudo chown asterisk:asterisk /var/lib/asterisk/agi-bin/*
sudo chmod 755 /var/lib/asterisk/agi-bin/assistant.agi
```

`dashboard.py` gira **come utente asterisk**: deve leggere
`/etc/asterisk/assistant-keys.conf`, che è 600.

### Chiavi

```bash
sudo cp server/assistant-keys.conf.example /etc/asterisk/assistant-keys.conf
sudo chown asterisk:asterisk /etc/asterisk/assistant-keys.conf
sudo chmod 600 /etc/asterisk/assistant-keys.conf
sudo nano /etc/asterisk/assistant-keys.conf
```

## Rete

Dai al Raspberry un **IP fisso**, o una reservation DHCP sul router. Se cambia
indirizzo, il telefono non trova più il TFTP e smette di funzionare: nel
progetto originale è successo, e la diagnosi non è immediata perché il telefono
continua a mostrarsi connesso.
