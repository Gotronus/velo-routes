# -*- coding: utf-8 -*-
"""Interroge un fichier de portions deja calcule, sans relire le PBF.

  python src/ask.py data/stretches_angers80.json --name "D 952"
  python src/ask.py data/stretches_angers80.json --near 47.44 -0.52 8
  python src/ask.py data/stretches_angers80.json --clean --min-km 12
"""
from __future__ import annotations
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import physics as P  # noqa: E402

CLASSE = {6: "departementale", 5: "dep. petite", 4: "sans classe",
          3: "rue", 2: "zone 20", 1: "desserte"}


def hav(a, b, c, d):
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = p2 - p1, math.radians(d - b)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371000 * math.asin(min(1.0, math.sqrt(h)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--name", default=None, help="filtre sur le nom de la route")
    ap.add_argument("--near", nargs=3, type=float, metavar=("LAT", "LON", "KM"),
                    help="portions dont une extremite est a moins de KM du point")
    ap.add_argument("--clean", action="store_true", help="seulement zero doute")
    ap.add_argument("--min-km", type=float, default=0.0)
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--ftp", type=float, default=260.0)
    a = ap.parse_args()

    with open(a.path, encoding="utf-8") as f:
        d = json.load(f)
    st = d["stretches"]
    print("%s : %d portions, centre %.4f %.4f, rayon %g km, calcule %s"
          % (os.path.basename(a.path), len(st), d["center"][0], d["center"][1],
             d["radius_km"], d.get("generated", "?")))

    sel = [s for s in st if s["km"] >= a.min_km]
    if a.name:
        k = a.name.lower()
        sel = [s for s in sel if k in s["name"].lower()]
    if a.clean:
        sel = [s for s in sel if s["doubts"] == 0]
    if a.near:
        la, lo, km = a.near
        sel = [s for s in sel
               if min(hav(la, lo, p[0], p[1]) for p in s["line"]) <= km * 1000]
    sel.sort(key=lambda s: -s["km"])
    print("retenues : %d\n" % len(sel))

    r = P.Rider()
    print("  %8s %7s %6s %7s %-15s %9s  %s"
          % ("km", "pente", "D+", "doutes", "classe", "au seuil", "nom"))
    for s in sel[:a.top]:
        g = s.get("grade", 0.0) / 100.0
        t = P.traverse([(s["km"] * 1000, g)], 0.95 * a.ftp, r)[0]
        print("  %8.2f %+6.2f%% %5.0fm %7d %-15s %6.1f min  %s"
              % (s["km"], s.get("grade", 0), s.get("gain", 0), s["doubts"],
                 CLASSE.get(s["rank"], "?"), t / 60, s["name"]))
        print("           de %.5f, %.5f  a %.5f, %.5f"
              % (s["line"][0][0], s["line"][0][1], s["line"][-1][0], s["line"][-1][1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
