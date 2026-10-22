# -*- coding: utf-8 -*-
"""Lecture d'un extrait OpenStreetMap .osm.pbf vers les Node/Way de osmroads.

Deux passes, bornees par une boite englobante pour tenir dans la memoire
d'un portable :
  passe A  les noeuds dans la boite, avec leurs tags s'ils en ont d'utiles
  passe B  les ways routieres touchant la boite

Les segments dont un noeud manque sont ecartes plus loin par RoadGraph,
donc les effets de bord ne font pas planter le graphe.
"""
from __future__ import annotations
import osmium

from osmroads import Node, Way, RANK

# seuls ces tags de noeud nous interessent : tout le reste est jete
NODE_KEYS = ("highway", "railway", "barrier", "traffic_calming",
             "crossing", "crossing:signals")
# tags de way conserves
WAY_KEYS = ("highway", "surface", "smoothness", "maxspeed", "junction",
            "bicycle", "access", "area", "name", "ref", "lanes", "tracktype")


class _NodePass(osmium.SimpleHandler):
    def __init__(self, bbox):
        super().__init__()
        self.s, self.w, self.n, self.e = bbox  # lat_min, lon_min, lat_max, lon_max
        self.nodes = {}
        self.seen = 0

    def node(self, n):
        self.seen += 1
        loc = n.location
        if not loc.valid():
            return
        lat, lon = loc.lat, loc.lon
        if not (self.s <= lat <= self.n and self.w <= lon <= self.e):
            return
        tags = {}
        for k in NODE_KEYS:
            v = n.tags.get(k)
            if v is not None:
                tags[k] = v
        self.nodes[n.id] = Node(n.id, lat, lon, None, tags)


class _WayPass(osmium.SimpleHandler):
    def __init__(self, node_ids):
        super().__init__()
        self.ids = node_ids
        self.ways = []

    def way(self, w):
        hw = w.tags.get("highway")
        if hw is None or hw not in RANK:
            return
        refs = [n.ref for n in w.nodes]
        if not any(r in self.ids for r in refs):
            return
        tags = {}
        for k in WAY_KEYS:
            v = w.tags.get(k)
            if v is not None:
                tags[k] = v
        self.ways.append(Way(w.id, refs, tags))


def load(pbf_path: str, bbox):
    """bbox = (lat_min, lon_min, lat_max, lon_max). Renvoie (nodes, ways)."""
    a = _NodePass(bbox)
    a.apply_file(pbf_path, locations=False)
    b = _WayPass(set(a.nodes))
    b.apply_file(pbf_path, locations=False)
    return a.nodes, b.ways


def bbox_around(lat: float, lon: float, radius_km: float):
    import math
    dlat = radius_km / 111.32
    dlon = radius_km / (111.32 * math.cos(math.radians(lat)))
    return (lat - dlat, lon - dlon, lat + dlat, lon + dlon)
