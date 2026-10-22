# -*- coding: utf-8 -*-
"""Construit la liste des portions roulables sans arret autour d'un point.

    python run_index.py angers
    python run_index.py beaufou --radius 25 --min-km 6

Sortie : un tableau lisible, et data/stretches_<lieu>.json pour l'appli.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))

import osmroads as R      # noqa: E402
import osmload as L       # noqa: E402
import physics as P       # noqa: E402

PBF = os.path.join(HERE, "data", "pays-de-la-loire.osm.pbf")

# points de depart : son domicile etudiant et ses racines vendeennes
PLACES = {
    "angers":  (47.4752, -0.5624),
    "beaufou": (46.8286, -1.4306),
    "nesmy":   (46.6069, -1.4028),
}

# seances de reference, pour dire ce que chaque portion permet
SESSIONS = [
    ("2x25 min seuil", 25 * 60, 0.95),
    ("3x20 min tempo", 20 * 60, 0.88),
    ("4x8 min",         8 * 60, 1.09),
    ("6x4 min VO2",     4 * 60, 1.13),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("place", choices=sorted(PLACES))
    ap.add_argument("--radius", type=float, default=30.0, help="km")
    ap.add_argument("--min-km", type=float, default=4.0)
    ap.add_argument("--ftp", type=float, default=260.0)
    ap.add_argument("--strict", action="store_true",
                    help="couper a tout carrefour de rang superieur ou egal")
    ap.add_argument("--max-rank", type=int, default=6,
                    help="6 = jusqu'aux departementales, 5 = routes plus petites")
    a = ap.parse_args()

    if not os.path.exists(PBF):
        print("extrait absent : lance d'abord  python fetch_osm.py")
        return 1

    lat, lon = PLACES[a.place]
    bbox = L.bbox_around(lat, lon, a.radius)
    print("%s  rayon %.0f km" % (a.place, a.radius))
    t0 = time.time()
    nodes, ways = L.load(PBF, bbox)
    print("  %d noeuds, %d ways routieres  (%.0f s)"
          % (len(nodes), len(ways), time.time() - t0))

    cfg = R.Config(strict_junctions=a.strict, max_rank=a.max_rank)
    G = R.RoadGraph(nodes, ways, cfg)
    print("  %d segments parcourables" % len(G.seg))
    t0 = time.time()
    st = R.find_stretches(G, min_length=a.min_km * 1000)
    st.sort(key=lambda s: -s.length)
    print("  %d portions >= %.1f km  (%.0f s)\n" % (len(st), a.min_km, time.time() - t0))

    r = P.Rider()
    print("  %-7s %-6s %-9s %-7s  %s" % ("km", "doutes", "classe", "a/r km", "permet"))
    print("  " + "-" * 62)
    rows = []
    for s in st[:40]:
        pw = a.ftp * 0.95
        t, d, lost = P.traverse(s.profile, pw, r)
        ok = [lab for lab, dur, frac in SESSIONS
              if P.traverse(s.profile, a.ftp * frac, r)[0] >= dur]
        ok2 = [lab for lab, dur, frac in SESSIONS
               if 2 * P.traverse(s.profile, a.ftp * frac, r)[0] >= dur]
        best = ok[0] if ok else ("(a/r) " + ok2[0] if ok2 else "trop courte")
        cls = {9: "autoroute", 8: "voie rapide", 7: "nationale",
               6: "departementale", 5: "dep. petite", 4: "sans nom",
               3: "lotissement"}.get(s.rank_min, "?")
        print("  %-7.2f %-6d %-9s %-7.1f  %s"
              % (s.km, len(s.doubts), cls[:9], 2 * s.km, best))
        rows.append({
            "km": round(s.km, 3), "doubts": len(s.doubts), "rank": s.rank_min,
            "mean_grade": round(s.mean_grade() * 100, 2),
            "min_s_at_threshold": round(t), "undoable_frac": round(lost, 3),
            "start": [G.N[s.nodes[0]].lat, G.N[s.nodes[0]].lon],
            "end": [G.N[s.nodes[-1]].lat, G.N[s.nodes[-1]].lon],
            "line": [[round(G.N[n].lat, 6), round(G.N[n].lon, 6)] for n in s.nodes],
        })

    out = os.path.join(HERE, "data", "stretches_%s.json" % a.place)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"place": a.place, "center": [lat, lon], "radius_km": a.radius,
                   "ftp": a.ftp, "config": {"strict": a.strict, "max_rank": a.max_rank},
                   "stretches": rows}, f, ensure_ascii=False)
    print("\n  ecrit : %s  (%.0f ko)" % (out, os.path.getsize(out) / 1024))

    print("\n  Rappel du besoin, a plat, FTP %.0f W :" % a.ftp)
    for lab, dur, frac in SESSIONS:
        need = P.holdable_distance(dur, a.ftp * frac, 0.0, r)
        print("    %-16s %5.2f km sans arret" % (lab, need / 1000))
    return 0


if __name__ == "__main__":
    sys.exit(main())
