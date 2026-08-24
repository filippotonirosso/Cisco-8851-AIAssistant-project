# 5. Schermata e personalizzazione

## Sfondo

`scripts/make-wallpaper.py` genera un 800×480 con gradiente e logo bianco al
centro. Il blu non è inventato: viene **campionato dal logo ufficiale**, così lo
sfondo resta agganciato all'identità reale.

Servono due file (i tuoi loghi, non versionati): la versione bianca su
trasparente e quella a colori da cui campionare il blu.

```bash
python3 scripts/make-wallpaper.py
sudo cp ema-blu.png ema-blu_80x53.png /srv/tftp/Desktops/800x480x24/
```

E in `Desktops/800x480x24/List.xml`:

```xml
<CiscoIPPhoneImageList>
  <ImageItem Image="TFTP:Desktops/800x480x24/ema-blu_80x53.png"
             URL="TFTP:Desktops/800x480x24/ema-blu.png"/>
</CiscoIPPhoneImageList>
```

La miniatura 80×53 serve all'anteprima nel menu.

Con `<defaultWallpaperFile>` nella configurazione lo sfondo viene **imposto**:
senza, resta solo disponibile nell'elenco e va scelto a mano dal menu — motivo
per cui "non compare" anche quando i file ci sono.

## Pannello informativo

`dashboard.py` serve una **immagine disegnata dal server** (`CiscoIPPhoneImageFile`)
con ora, data, impegni del giorno e posta non letta. Disegnare un PNG invece di
usare il riquadro di testo di Cisco dà lo stesso controllo che si ha sullo
sfondo: gerarchia tipografica, spaziature, colori.

Due modi di mostrarlo:

- `<servicesURL>` — compare quando **premi tu** il tasto Servizi
- `<idleURL>` + `<idleTimeout>` — compare **da solo** dopo N secondi di inattività

Il secondo è invadente: si ripresenta anche dopo che lo chiudi. Lasciare
`idleURL` vuoto e usare solo il tasto.

## Tasti di linea

Il CP-8851 ha cinque tasti, ognuno configurabile via `sipLines`:

| `featureID` | Funzione | Elementi |
|---|---|---|
| 9 | linea | `name`, `authName`, `authPassword`, `proxy` |
| 2 | chiamata rapida | `featureLabel`, `speedDialNumber` |
| 20 | URL a un servizio | `featureLabel`, `serviceURI` |
| 21 | chiamata rapida con stato | `featureOptionMask`, `speedDialNumber` |
| 130 | non disturbare | `featureLabel` |
| 195 | rubrica | `featureLabel` |

Elenco completo: [usecallmanager.nz/line-keys.html](https://usecallmanager.nz/line-keys.html).

Esempio, un tasto che chiama l'assistente:

```xml
<line button="2">
  <featureID>2</featureID>
  <featureLabel>Assistente</featureLabel>
  <speedDialNumber>500</speedDialNumber>
</line>
```

Le etichette lunghe vengono troncate: i tasti sono stretti.

## Altre personalizzazioni

- `<phoneLabel>` — intestazione in cima, max 12 caratteri
- `<featureLabel>` sulla linea — un nome al posto del numero
- `Ringlist.xml` e i file `.raw` — suonerie personalizzate
- `<directoryURL>` — una rubrica servita da te, per esempio da Google Workspace
