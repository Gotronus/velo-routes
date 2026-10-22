# -*- coding: utf-8 -*-
"""PBF -> portions sans arret, en une seule passe memoire.

L'ancienne chaine ecrivait un JSON intermediaire de plusieurs centaines de
megaoctets, que json.load redeveloppait en plusieurs gigaoctets d'objets.
Ici on va directement du .osm.pbf au graphe : le pic de memoire est celui
du graphe seul, ce qui rend un rayon de 80 km tenable.

Usage :
  python src/scan.py data/pays-de-la-loire.osm.pbf 47.4712 -0.5518 80 angers
  python src/scan.py <pbf> <lat> <lon> <rayon_km> <nom> [--name "D 952"]
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osmroads as R      # noqa: E402
import physics as P       # noqa: E402
import elevation as E     # noqa: E402
from extract import NodeIds, Ways, Nodes, box  # noqa: E402

SESSIONS = [
    ("2x25 min seuil", 25 * 60, 0.95),
    ("3x20 min tempo", 20 * 60, 0.88),
    ("4x8 min VO2",     8 * 60, 1.09),
    ("6x4 min VO2",     4 * 60, 1.13),
    ("8x1 min",            60, 1.35),
]
CLASSE = {9: "autoroute", 8: "voie rapide", 7: "nationale", 6: "departementale",
          5: "dep. petite", 4: "sans classe", 3: "rue", 2: "zone 20", 1: "desserte"}


def stretch_name(G, s):
    from collections import Counter
    c = Counter()
    for i in s.edges:
        nm = G.names.get(G.way_of(i))
        if nm:
            c[nm] += 1
    return c.most_common(1)[0][0] if c else "(sans nom)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pbf")
    ap.add_argument("lat", type=float)
    ap.add_argument("lon", type=float)
    ap.add_argument("radius", type=float)
    ap.add_argument("name")
    ap.add_argument("--ftp", type=float, default=260.0)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--min-km", type=float, default=2.0)
    ap.add_argument("--filter-name", default=None,
                    help="n'affiche que les portions dont le nom contient ceci")
    ap.add_argument("--no-dem", action="store_true",
                    help="ignorer le relief (pentes a zero)")
    a = ap.parse_args()

    bb = box(a.lat, a.lon, a.radius)
    t0 = time.time()
    print("centre %.4f, %.4f  rayon %g km" % (a.lat, a.lon, a.radius), flush=True)

    h0 = NodeIds(bb)
    h0.apply_file(a.pbf)
    inbox = np.sort(np.asarray(h0.ids, dtype=np.int64))
    nin = len(inbox)
    del h0
    print("passe 0 : %d noeuds dans la boite  (%.0f s)" % (nin, time.time() - t0), flush=True)

    h1 = Ways(inbox)
    h1.apply_file(a.pbf)
    ways, wanted = h1.ways, h1.wanted
    del h1, inbox
    print("passe 1 : %d ways routieres, %d noeuds a localiser  (%.0f s)"
          % (len(ways), len(wanted), time.time() - t0), flush=True)

    h2 = Nodes(wanted)
    h2.apply_file(a.pbf)
    nodes = h2.nodes
    del h2, wanted
    print("passe 2 : %d noeuds localises  (%.0f s)" % (len(nodes), time.time() - t0), flush=True)

    if not a.no_dem:
        dem = E.Dem()
        print("relief : %d tuiles SRTM a couvrir" % len(E.tiles_for(bb)), flush=True)
        dem.fill(nodes)
        del dem

    G = R.RoadGraph(nodes, ways, R.Config())
    print("graphe  : %d segments parcourables  (%.0f s)"
          % (len(G.seg), time.time() - t0), flush=True)
    del ways

    st = R.find_stretches(G, min_length=a.min_km * 1000)
    st.sort(key=lambda s: -s.length)
    print("portions: %d de plus de %.1f km sans arret dur  (%.0f s)\n"
          % (len(st), a.min_km, time.time() - t0), flush=True)

    r = P.Rider()
    shown = st
    if a.filter_name:
        key = a.filter_name.lower()
        shown = [s for s in st if key in stretch_name(G, s).lower()]
        print("portions dont le nom contient %r : %d\n" % (a.filter_name, len(shown)))

    print("Les %d plus longues :" % min(a.top, len(shown)))
    print("  %8s %7s %7s %7s %-15s %9s  %s"
          % ("km", "pente", "D+", "doutes", "classe", "au seuil", "nom"))
    for s in shown[:a.top]:
        t25 = P.traverse(s.profile, 0.95 * a.ftp, r)
        print("  %8.2f %+6.2f%% %6.0fm %7d %-15s %5.1f min  %s"
              % (s.km, s.mean_grade() * 100, s.gain(), len(s.doubts),
                 CLASSE.get(s.rank_min, "?"), t25[0] / 60,
                 stretch_name(G, s)), flush=True)

    print("\nCe que chaque seance demande, et ce que le terrain offre :")
    for lab, dur, iff in SESSIONS:
        pw = iff * a.ftp
        need = P.holdable_distance(dur, pw, 0.0, r)
        ok, ok0, ar = 0, 0, 0
        for s in st:
            t, _, lost = P.traverse(s.profile, pw, r)
            if lost > 0.15:
                continue
            if t >= dur:
                ok += 1
                if not s.doubts:
                    ok0 += 1
            if 2 * t >= dur:
                ar += 1
        print("  %-16s %4.0f W  %5.2f km a plat  ->  %4d portions, dont %3d sans aucun doute"
              "  |  %4d en aller-retour" % (lab, pw, need / 1000, ok, ok0, ar), flush=True)

    out = os.path.join("data", "stretches_%s.json" % a.name)
    os.makedirs("data", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"place": a.name, "center": [a.lat, a.lon], "radius_km": a.radius,
                   "ftp": a.ftp, "generated": time.strftime("%Y-%m-%dT%H:%M"),
                   "stretches": [{
                       "km": round(s.km, 3), "name": stretch_name(G, s),
                       "doubts": len(s.doubts), "rank": s.rank_min,
                       "grade": round(s.mean_grade() * 100, 2), "gain": round(s.gain()),
                       "line": [[round(G.N[n].lat, 5), round(G.N[n].lon, 5)]
                                for n in s.nodes],
                   } for s in st]}, f, ensure_ascii=False, separators=(",", ":"))
    print("\necrit %s  (%.1f Mo)  total %.0f s"
          % (out, os.path.getsize(out) / 1e6, time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
