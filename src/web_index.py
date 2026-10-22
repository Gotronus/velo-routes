# -*- coding: utf-8 -*-
"""Fusionne les fichiers de portions en un index leger pour l'appli web.

  python src/web_index.py web/data/index.json data/stretches_angers80dem.json data/stretches_beaufou80.json

Trois reductions :
  - Douglas-Peucker sur les polylignes, tolerance 25 m (une route reste une
    route a 25 m pres, et l'export GPX reste exploitable)
  - coordonnees en entiers de 1e-5 degre, soit environ 1,1 m, encodees en
    delta par rapport au point precedent
  - deduplication entre les deux zones, qui se recouvrent largement
"""
from __future__ import annotations
import json
import math
import os
import sys

R_EARTH = 6371000.0


def _perp(p, a, b):
    """Distance perpendiculaire approchee, en metres, en projection locale."""
    kx = 111320.0 * math.cos(math.radians(a[0]))
    ky = 110540.0
    ax, ay = a[1] * kx, a[0] * ky
    bx, by = b[1] * kx, b[0] * ky
    px, py = p[1] * kx, p[0] * ky
    dx, dy = bx - ax, by - ay
    d2 = dx * dx + dy * dy
    if d2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / d2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def simplify(line, tol=25.0):
    """Douglas-Peucker iteratif (pas de recursion : certaines portions
    comptent plus de mille points)."""
    n = len(line)
    if n <= 2:
        return list(line)
    keep = [False] * n
    keep[0] = keep[n - 1] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        worst, wi = -1.0, -1
        for k in range(i + 1, j):
            d = _perp(line[k], line[i], line[j])
            if d > worst:
                worst, wi = d, k
        if worst > tol:
            keep[wi] = True
            stack.append((i, wi))
            stack.append((wi, j))
    return [line[i] for i in range(n) if keep[i]]


def enc(line):
    """Entiers 1e-5 degre, delta par rapport au point precedent."""
    out = []
    pla = plo = 0
    for la, lo in line:
        ila, ilo = int(round(la * 1e5)), int(round(lo * 1e5))
        out.append(ila - pla)
        out.append(ilo - plo)
        pla, plo = ila, ilo
    return out


def key_of(s):
    """Signature geometrique grossiere, pour deduplication entre zones."""
    a, b = s["line"][0], s["line"][-1]
    f = lambda p: (round(p[0], 3), round(p[1], 3))
    e1, e2 = f(a), f(b)
    if e2 < e1:
        e1, e2 = e2, e1
    return (e1, e2, round(s["km"], 1))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    out_path, srcs = sys.argv[1], sys.argv[2:]
    seen = {}
    zones = []
    for p in srcs:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        zones.append({"name": d["place"], "center": d["center"],
                      "radius_km": d["radius_km"]})
        n_new = 0
        for s in d["stretches"]:
            k = key_of(s)
            if k in seen:
                continue
            seen[k] = s
            n_new += 1
        print("%-34s %5d portions, %5d nouvelles"
              % (os.path.basename(p), len(d["stretches"]), n_new))

    items = sorted(seen.values(), key=lambda s: -s["km"])
    rows = []
    pts_before = pts_after = 0
    for s in items:
        line = s["line"]
        pts_before += len(line)
        sl = simplify(line, 25.0)
        pts_after += len(sl)
        rows.append([
            int(round(s["km"] * 100)),            # 0 longueur en hectometres
            int(round(s.get("grade", 0) * 100)),  # 1 pente en centiemes de %
            int(s["doubts"]),                     # 2 carrefours douteux
            int(s["rank"]),                       # 3 classe de voie
            int(round(s.get("gain", 0))),         # 4 denivele positif
            s["name"],                            # 5 nom
            enc(sl),                              # 6 polyligne
        ])
    payload = {
        "v": 1,
        "zones": zones,
        "scale": 1e-5,
        "fields": ["hm", "grade_cpct", "doubts", "rank", "gain", "name", "dline"],
        "n": len(rows),
        "rows": rows,
    }
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    mb = os.path.getsize(out_path) / 1e6
    print("\n%d portions, polylignes %d -> %d points (%.0f %% retires)"
          % (len(rows), pts_before, pts_after,
             100 * (1 - pts_after / max(1, pts_before))))
    print("ecrit %s  (%.2f Mo brut)" % (out_path, mb))
    return 0


if __name__ == "__main__":
    sys.exit(main())
