#!/usr/bin/env python3
"""Eseguito ogni minuto: consegna i promemoria scaduti."""
import os
import sys
import time
sys.path.insert(0, "/var/lib/asterisk/agi-bin")
import assistant_lib as L
import reminders as R

keys = L.load_keys()
for item in R.due():
    if R.deliver(item, keys):
        R.mark_done(item["id"])
    else:
        # ritenta al minuto dopo, ma non all'infinito
        item.setdefault("tentativi", 0)
        if item["tentativi"] >= 3:
            R.mark_done(item["id"])
            L.log("promemoria %d abbandonato dopo 3 tentativi" % item["id"])
    # se il telefono e' occupato meglio non accavallare le chiamate
    time.sleep(2)
