#!/usr/bin/env python3
"""Pre-genera saluto e riempitivi.

Girano una volta sola: al telefono devono partire istantaneamente, quindi
non possono dipendere da una chiamata di rete al momento della risposta.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assistant_lib as L

os.makedirs(L.SOUNDS, exist_ok=True)
keys = L.load_keys()

items = [("greeting", L.GREETING),
         ("goodbye", "Va bene capo, a presto!"),
         ("sorry", "Scusa, non ho capito. Puoi ripetere?")]
items += [("filler-%d" % i, t) for i, t in enumerate(L.FILLERS)]
for stato, frasi in L.FILLERS_STATO.items():
    items += [("filler-%s-%d" % (stato, i), t) for i, t in enumerate(frasi)]

for name, text in items:
    out = os.path.join(L.SOUNDS, name)
    if L.synth(text, out, keys):
        made = next((out + e for e in (".sln16", ".wav16") if os.path.exists(out + e)), None)
        size = os.path.getsize(made) if made else 0
        print("  %-12s %-34s %.1fs" % (name, repr(text), size / 32000.0))
    else:
        print("  %-12s FALLITO" % name)
