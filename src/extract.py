# -*- coding: utf-8 -*-
"""Extrait d'un fichier .osm.pbf le graphe routier autour d'un point.

Trois passes, pour tenir en memoire sur un portable :
  0. les identifiants des noeuds dans la boite englobante
  1. les ways de type highway qui touchent la boite
  2. la position et les tags des noeuds de ces ways

Usage :
  python src/extract.py pays-de-la-loire.osm.pbf 47.4712 -0.5518 40 angers
"""
from __future__ import annotations
import json
import os
import sys
import time

import numpy as np
import osmium

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osmroads as R  # noqa: E402

# tags de noeud qui nous interessent (arrets, barrieres)
NODE_KEYS = ("highway", "barrier", "railway", "traffic_calming",
             "crossing", "crossing:signals")
WAY_KEYS = ("highway", "surface", "smoothness", "maxspeed", "junction",
            "bicycle", "access", "area", "name", "ref", "lanes",
            "bridge", "tunnel", "oneway")


def box(lat, lon, radius_km):
    dlat = radius_km / 111.32
    dlon = radius_km / (111.32 * np.cos(np.radians(lat)))
    return (lat - dlat, lat + dlat, lon - dlon, lon + dlon)


class NodeIds(osmium.SimpleHandler):
    """Passe 0 : identifiants des noeuds dans la boite."""

    def __init__(self, bb):
        super().__init__()
        self.bb = bb
        self.ids = []

    def node(self, n):
        if not n.location.valid():
            return
        la, lo = n.location.lat, n.location.lon
        y0, y1, x0, x1 = self.bb
        if y0 <= la <= y1 and x0 <= lo <= x1:
            self.ids.append(n.id)


class Ways(osmium.SimpleHandler):
    """Passe 1 : ways highway touchant la boite."""

    def __init__(self, inbox):
        super().__init__()
        self.inbox = inbox          # tableau trie d'identifiants
        self.ways = []
        self.wanted = set()

    def _hit(self, refs):
        a = np.asarray(refs, dtype=np.int64)
        i = np.searchsorted(self.inbox, a)
        i[i >= len(self.inbox)] = 0
        return bool(np.any(self.inbox[i] == a))

    def way(self, w):
        hw = w.tags.get("highway")
        if hw is None or hw not in R.RANK:
            return
        refs = [n.ref for n in w.nodes]
        if len(refs) < 2 or not self._hit(refs):
            return
        tags = {k: w.tags[k] for k in WAY_KEYS if k in w.tags}
        self.ways.append(R.Way(w.id, refs, tags))
        self.wanted.update(refs)


class Nodes(osmium.SimpleHandler):
    """Passe 2 : position et tags des noeuds retenus."""

    def __init__(self, wanted):
        super().__init__()
        self.wanted = wanted
        self.nodes = {}

    def node(self, n):
        if n.id not in self.wanted or not n.location.valid():
            return
        tags = {k: n.tags[k] for k in NODE_KEYS if k in n.tags}
        self.nodes[n.id] = R.Node(n.id, n.location.lat, n.location.lon, None, tags)


def run(pbf, lat, lon, radius_km, name, outdir="data"):
    bb = box(lat, lon, radius_km)
    t0 = time.time()

    h0 = NodeIds(bb)
    h0.apply_file(pbf)
    inbox = np.sort(np.asarray(h0.ids, dtype=np.int64))
    del h0
    print("passe 0 : %d noeuds dans la boite  (%.0f s)" % (len(inbox), time.time() - t0))

    h1 = Ways(inbox)
    h1.apply_file(pbf)
    print("passe 1 : %d ways highway retenues, %d noeuds a localiser  (%.0f s)"
          % (len(h1.ways), len(h1.wanted), time.time() - t0))

    h2 = Nodes(h1.wanted)
    h2.apply_file(pbf)
    print("passe 2 : %d noeuds localises  (%.0f s)" % (len(h2.nodes), time.time() - t0))

    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, name + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "center": [lat, lon], "radius_km": radius_km,
            "nodes": [[n.id, round(n.lat, 6), round(n.lon, 6), n.tags]
                      for n in h2.nodes.values()],
            "ways": [[w.id, w.nodes, w.tags] for w in h1.ways],
        }, f, separators=(",", ":"))
    print("ecrit %s  (%.1f Mo)" % (path, os.path.getsize(path) / 1e6))
    return path


def load(path, radius_km=None):
    """Relit un extrait. `radius_km` restreint au voisinage du centre :
    un extrait de 40 km fait plusieurs gigaoctets d'objets Python, 15 a
    20 km suffisent largement a trouver des routes d'entrainement."""
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    raw = d["nodes"]
    if radius_km:
        la0, lo0 = d["center"]
        dla = radius_km / 111.32
        dlo = radius_km / (111.32 * np.cos(np.radians(la0)))
        y0, y1 = la0 - dla, la0 + dla
        x0, x1 = lo0 - dlo, lo0 + dlo
        raw = [r for r in raw if y0 <= r[1] <= y1 and x0 <= r[2] <= x1]
    nodes = {}
    for i, la, lo, tg in raw:
        nodes[i] = R.Node(i, la, lo, None, tg)
    keep = nodes.keys()
    ways = []
    for i, ns, tg in d["ways"]:
        if any(n in keep for n in ns):
            ways.append(R.Way(i, ns, tg))
    d.pop("nodes", None)
    d.pop("ways", None)
    return nodes, ways, d


if __name__ == "__main__":
    if len(sys.argv) < 6:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]),
        float(sys.argv[4]), sys.argv[5])
