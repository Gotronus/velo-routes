# -*- coding: utf-8 -*-
"""Reseau synthetique : on sait ce que l'algorithme doit trouver."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import osmroads as R          # noqa: E402
import physics as P           # noqa: E402

LAT = 47.0
STEP = 200.0  # m entre deux noeuds du corridor
DLON = STEP / (111320.0 * math.cos(math.radians(LAT)))


def build():
    nodes, ways = {}, []
    n = 61  # 60 segments de 200 m = 12 km
    for i in range(n):
        ele = 20.0
        if 50 <= i <= 56:            # bosse entre 10,0 et 11,2 km
            ele = 20.0 + (i - 50) * 12.0
        elif i > 56:
            ele = 20.0 + 6 * 12.0
        nodes[1000 + i] = R.Node(1000 + i, LAT, i * DLON, ele, {})

    # feu rouge a 5 km (noeud 25)
    nodes[1025].tags = {"highway": "traffic_signals"}

    ways.append(R.Way(1, [1000 + i for i in range(n)],
                      {"highway": "tertiary", "surface": "asphalt"}))

    # --- T residentielle a 2 km (noeud 10) : rang 3 < 5, aucun doute
    nodes[2000] = R.Node(2000, LAT - 0.004, 10 * DLON, 20.0, {})
    ways.append(R.Way(2, [1010, 2000], {"highway": "residential", "surface": "asphalt"}))

    # --- secondaire qui coupe a 3,5 km (noeud 17) : rang 6 >= 5, doute
    nodes[2100] = R.Node(2100, LAT - 0.004, 17 * DLON, 20.0, {})
    nodes[2101] = R.Node(2101, LAT + 0.004, 17 * DLON, 20.0, {})
    ways.append(R.Way(3, [2100, 1017, 2101], {"highway": "secondary", "surface": "asphalt"}))

    # --- branche en gravier a 6 km (noeud 30) : ecartee
    nodes[2200] = R.Node(2200, LAT - 0.004, 30 * DLON, 20.0, {})
    ways.append(R.Way(4, [1030, 2200], {"highway": "unclassified", "surface": "gravel"}))

    # --- rond-point a 9 km (noeud 45)
    nodes[2300] = R.Node(2300, LAT + 0.0003, 45 * DLON, 20.0, {})
    ways.append(R.Way(5, [1045, 2300, 1045],
                      {"highway": "tertiary", "junction": "roundabout", "surface": "asphalt"}))

    # --- route entierement en terre, ailleurs : jamais retenue
    for j in range(5):
        nodes[3000 + j] = R.Node(3000 + j, LAT + 0.05, j * DLON, 20.0, {})
    ways.append(R.Way(6, [3000 + j for j in range(5)],
                      {"highway": "unclassified", "surface": "dirt"}))

    return nodes, ways


def run():
    nodes, ways = build()
    cfg = R.Config()
    G = R.RoadGraph(nodes, ways, cfg)
    st = R.find_stretches(G, min_length=500.0)

    print("segments parcourables : %d" % len(G.seg))
    print("portions trouvees     : %d" % len(st))
    for s in st:
        print("  %5.2f km  de n%d a n%d  pente moy %+0.2f %%  D+ %3.0f m  doutes %d"
              % (s.km, s.nodes[0], s.nodes[-1], s.mean_grade() * 100, s.gain(), len(s.doubts)))

    ok = True

    def check(cond, msg):
        nonlocal ok
        print(("  OK   " if cond else "  ECHEC") + " " + msg)
        if not cond:
            ok = False

    main = sorted((round(s.km, 1) for s in st if 1000 <= s.nodes[0] < 2000), reverse=True)
    check(len(st) == 4, "quatre portions : le corridor coupe en trois, plus la secondaire")
    check(main == [5.0, 4.0, 3.0],
          "le corridor est coupe au feu de 5 km et au rond-point de 9 km -> %s" % main)

    check(any(len(s.doubts) == 1 for s in st),
          "un seul carrefour douteux signale (la secondaire a 3,5 km)")
    check(all(2200 not in s.nodes for s in st), "la branche en gravier est ecartee")
    check(all(3000 not in s.nodes for s in st), "la route en terre est ecartee")
    check(all(2000 not in s.nodes for s in st),
          "la T residentielle n'est pas suivie (angle droit)")

    hill = [s for s in st if s.gain() > 50]
    check(len(hill) == 1 and hill[0].gain() > 60,
          "la bosse de 72 m est dans la derniere portion")

    # ---------- dimensionnement : combien de km pour un intervalle ?
    print("\nCombien de route sans arret pour un intervalle :")
    print("  %-18s %5s  %-22s %-22s" % ("", "W", "a plat", "sur un faux plat a 2 %"))
    r = P.Rider()
    for lab, dur, pw in [("2x25 min au seuil", 25 * 60, 0.95 * 260),
                         ("3x20 min tempo", 20 * 60, 0.88 * 260),
                         ("6x4 min VO2", 4 * 60, 1.13 * 260),
                         ("8x1 min", 60, 1.35 * 260)]:
        row = "  %-18s %5.0f " % (lab, pw)
        for g in (0.0, 0.02):
            d = P.holdable_distance(dur, pw, g, r)
            v = P.speed_for(pw, g, r)
            row += " %5.1f km/h -> %5.2f km " % (v * 3.6, d / 1000)
        print(row)

    # coherence avec le modele du Lab : 260 W a plat
    v260 = P.speed_for(260, 0.0, r) * 3.6
    check(33.0 < v260 < 40.0, "260 W a plat donne %.1f km/h, plausible" % v260)

    t, d, lost = P.traverse(hill[0].profile, 0.95 * 260, r) if hill else (0, 0, 0)
    if hill:
        print("\nLa portion avec la bosse, parcourue a %d W : %.1f min, %.2f km, "
              "%.0f %% de descente non tenable" % (0.95 * 260, t / 60, d / 1000, lost * 100))

    print("\n=== %s ===" % ("tout passe" if ok else "DES VERIFICATIONS ECHOUENT"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(run())
