# 6. Gmail e Calendar

## Autorizzazione

Servono **tre** valori, non uno:

1. `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` da
   [console.cloud.google.com](https://console.cloud.google.com) →
   *APIs and Services* → *Credentials* → *OAuth client ID*, tipo **Desktop app**.
   Nello stesso progetto abilita **Gmail API** e **Calendar API**.
2. `GOOGLE_REFRESH_TOKEN`, che non si scarica da nessuna pagina: si ottiene
   autorizzando l'account una volta sola.

```bash
python3 scripts/google-auth.py
```

Stampa un link, lo apri nel browser, autorizzi, e lo script **scrive il refresh
token direttamente sul Pi** via ssh — non passa dal terminale.

Gira sulla macchina con il browser, non sul Raspberry: per i client Desktop
Google rimanda l'autorizzazione a `localhost`, e il `localhost` del tuo browser
è il tuo computer, non il Pi.

Se l'ID non finisce in `.apps.googleusercontent.com` e il secret non inizia con
`GOCSPX-`, li hai invertiti. Capita.

## Scope

```
gmail.readonly      lettura
gmail.compose       bozze
calendar.readonly   agenda
```

## Perché non l'iCal segreto del calendario

Più semplice, ma ha due difetti: Google mette in cache quel feed e
l'aggiornamento ritarda, e su molti tenant Workspace la voce **non compare
affatto** perché l'amministratore ha disattivato la condivisione esterna.

Riattivarla dalla console admin per far funzionare un telefono è un prezzo
sproporzionato: allenta la condivisione dei calendari per **tutta**
l'organizzazione. Meglio OAuth, o in alternativa un Apps Script deployato come
web app, che vive dentro l'account e non richiede di toccare impostazioni
d'organizzazione.

## Il confine

`google_api.py` non è un passacarte. Ha una **lista di endpoint ammessi**
(`ALLOW`) e un filtro (`DENY`) che rifiuta comunque qualsiasi percorso
contenente `send`, `trash` o `delete`.

L'agente compone da sé le richieste — decide query, filtri, quanto leggere — ma
non può raggiungere ciò che non è in lista. Verificabile:

```python
G.call("POST", "gmail/v1/users/me/messages/send", None, {})
# -> {'errore': 'endpoint non consentito: ...'}
```

**Chi aggiungesse un endpoint di invio violerebbe una decisione deliberata**,
non una svista. Google non offre uno scope "solo bozze": `gmail.compose` concede
bozze e invio insieme, quindi la garanzia deve venire dal codice.

C'è anche un tetto sulla dimensione della risposta (`MAX_BYTES`): al telefono
non si legge un romanzo, e una risposta enorme farebbe esplodere latenza e costi.
