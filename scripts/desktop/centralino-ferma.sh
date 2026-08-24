#!/bin/bash
# Spegne il centralino e l assistente vocale.
SERVIZI="meet-dashboard phone-http tftpd-hpa asterisk"
FLAG=/var/lib/asterisk/assistente-attivo

echo "Arresto del centralino e dell assistente..."
echo

# prima i promemoria, cosi nessuna consegna parte durante lo spegnimento
sudo rm -f "$FLAG"
echo "  promemoria         sospesi"

CH=$(sudo asterisk -rx "core show channels" 2>/dev/null | grep -oE "^[0-9]+ active channel" | grep -oE "^[0-9]+" || echo 0)
if [ "${CH:-0}" != "0" ]; then
    echo
    echo "  ATTENZIONE: ci sono $CH chiamate in corso."
    read -p "  Le interrompo? [s/N] " R
    [ "$R" = "s" ] || { echo "  Annullato."; read -p "Premi Invio. " _; exit 0; }
fi

for s in $SERVIZI; do
    printf "  %-18s " "$s"
    sudo systemctl stop "$s" 2>/dev/null && echo "fermato" || echo "gia fermo"
done

echo
echo "  Tutto spento. Il telefono non funzionera finche non riavvii."
echo
read -p "Premi Invio per chiudere. " _
