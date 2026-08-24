#!/bin/bash
# Accende il centralino e l assistente vocale.
SERVIZI="asterisk tftpd-hpa phone-http meet-dashboard"
FLAG=/var/lib/asterisk/assistente-attivo

echo "Avvio del centralino e dell assistente..."
echo

for s in $SERVIZI; do
    printf "  %-18s " "$s"
    sudo systemctl start "$s" 2>/dev/null && echo "avviato" || echo "ERRORE"
done

# riabilita la consegna dei promemoria
sudo touch "$FLAG"
echo "  promemoria         attivi"
echo
echo "Attendo la registrazione del telefono..."
for i in $(seq 1 20); do
    sleep 3
    C=$(sudo asterisk -rx "pjsip show contacts" 2>/dev/null | grep -c Avail || true)
    if [ "$C" != "0" ]; then
        echo
        echo "  TELEFONO REGISTRATO - tutto pronto."
        echo
        sudo asterisk -rx "pjsip show contacts" 2>/dev/null | grep Avail
        echo
        read -p "Premi Invio per chiudere. " _
        exit 0
    fi
done

echo
echo "  Il telefono non risulta ancora registrato."
echo "  Se e spento, accendilo: si registra da solo entro un minuto."
echo
read -p "Premi Invio per chiudere. " _
