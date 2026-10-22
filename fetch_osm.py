# -*- coding: utf-8 -*-
"""Telechargement de l'extrait Geofabrik. A lancer une fois, ou quand OSM
bouge. Les Pays de la Loire couvrent Angers et la Vendee d'un seul coup.
"""
import os
import sys
import time
import urllib.request

URL = "https://download.geofabrik.de/europe/france/pays-de-la-loire-latest.osm.pbf"
DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data",
                    "pays-de-la-loire.osm.pbf")


def main():
    os.makedirs(os.path.dirname(DEST), exist_ok=True)
    if os.path.exists(DEST) and os.path.getsize(DEST) > 50_000_000:
        print("deja telecharge : %.0f Mo" % (os.path.getsize(DEST) / 1e6))
        return 0
    t0 = time.time()
    last = [0.0]

    def hook(blocks, bsize, total):
        done = blocks * bsize
        now = time.time()
        if now - last[0] < 2.0 and done < total:
            return
        last[0] = now
        pct = (100.0 * done / total) if total > 0 else 0
        mb = done / 1e6
        sp = mb / max(0.1, now - t0)
        print("  %5.1f %%  %6.0f Mo  %4.1f Mo/s" % (pct, mb, sp), flush=True)

    tmp = DEST + ".part"
    urllib.request.urlretrieve(URL, tmp, hook)
    os.replace(tmp, DEST)
    print("termine : %.0f Mo en %.0f s" % (os.path.getsize(DEST) / 1e6, time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
