# Synthetic sample -- NOT real data for any pilot district

Five made-up building points and two made-up street lines. Coordinates
were originally placed near Huambo (the pilot district before the
2026-09-22 switch to Luanda, see `discrepancies.md`) -- clicking
"Load demo data" in the viewer will jump the map away from Luanda to
this old location, which is expected and harmless: this fixture exists
solely to exercise the pipeline wiring (street assignment -> numbering
-> ID generation -> export) end to end without depending on real
Google Open Buildings / OSM data or network access, not to represent
either district geographically.

Replace with a real clipped Luanda extract before treating pipeline
output as meaningful.
