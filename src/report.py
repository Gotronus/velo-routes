# -*- coding: utf-8 -*-
"""Rapport : quelles portions sans arret existent vraiment autour d'un point.

Usage :
  python src/report.py data/angers.json
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osmroads as R      # noqa: E402
import physics as P       # noqa: E402
import extract as X       # noqa: E402

SESSIONS = [
    ("2x25 min seuil", 25 * 60, 0.95),
    ("3x20 min tempo", 20 * 60, 0.88),
    ("4x8 min VO2", 8 * 60, 1.09),
    ("6x4 min VO2", 4 * 60, 1.13),
    ("8x1 min", 60, 1.35),
]


def main(path, ftp=260.0, top=15, radius_km=20.0):
    print("lecture de %s (rayon %g km)..." % (path, radius_km), flush=True)
    nodes, ways, meta = X.load(path, radius_km)
    cfg = R.Config()
    G = R.RoadGraph(nodes, ways, cfg)
    print("centre %.4f, %.4f  rayon %g km" % (meta["center"][0], meta["center"][1],
                                              meta["radius_km"]))
    print("%d ways, %d noeuds, %d segments parcourables"
          % (len(ways), len(nodes), len(G.seg)))

    print("recherche des portions...", flush=True)
    st = R.find_stretches(G, min_length=2000.0)
    st.sort(key=lambda s: -s.length)
    print("\n%d portions de plus de 2 km sans arret dur.\n" % len(st))

    r = P.Rider()
    print("Les %d plus longues :" % min(top, len(st)))
    print("  %7s %7s %6s %7s %7s  %s" % ("km", "pente", "D+", "doutes", "classe", "nom"))
    for s in st[:top]:
        print("  %7.2f %+6.2f%% %5.0fm %6d %7d  %s"
              % (s.km, s.mean_grade() * 100, s.gain(), len(s.doubts),
                 s.rank_min, stretch_name(G, s)))

    print("\nCe que chaque seance demande, et ce que le terrain offre :")
    for lab, dur, iff in SESSIONS:
        pw = iff * ftp
        need_flat = P.holdable_distance(dur, pw, 0.0, r)
        # portions ou l'intervalle tient reellement, profil compris :
        # on ecarte celles dont plus de 15 % descend trop pour appliquer la puissance
        ok, ok0, ar = [], [], []
        for s in st:
            t, _, lost = P.traverse(s.profile, pw, r)
            if lost > 0.15:
                continue
            if t >= dur:
                ok.append(s)
                if not s.doubts:
                    ok0.append(s)
            if 2 * t >= dur:
                ar.append(s)
        print("  %-16s %4.0f W  %5.2f km a plat  ->  %3d portions, dont %d sans aucun doute"
              "  |  %3d en aller-retour"
              % (lab, pw, need_flat / 1000, len(ok), len(ok0), len(ar)))

    best = [s for s in st if not s.doubts]
    if best:
        b = max(best, key=lambda s: s.length)
        print("\nLa plus longue portion sans le moindre carrefour douteux : %.2f km"
              " (%s)" % (b.km, stretch_name(G, b)))
        for lab, dur, iff in SESSIONS:
            t, d, lost = P.traverse(b.profile, iff * ftp, r)
            print("    %-16s %5.1f min disponibles sur %5.1f demandees  %s"
                  % (lab, t / 60, dur / 60, "OK" if t >= dur else "trop court"))


def stretch_name(G, s):
    """Nom le plus frequent parmi les ways de la portion."""
    from collections import Counter
    c = Counter()
    for a, b in zip(s.nodes, s.nodes[1:]):
        for i in G.at.get(a, []):
            if G.other(i, a) == b:
                w = G.way_of(i)
                nm = G.names.get(w)
                if nm:
                    c[nm] += 1
    return c.most_common(1)[0][0] if c else "(sans nom)"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1],
         float(sys.argv[2]) if len(sys.argv) > 2 else 260.0,
         15,
         float(sys.argv[3]) if len(sys.argv) > 3 else 20.0)
