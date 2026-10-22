# -*- coding: utf-8 -*-
"""Detection des portions de route ou l'on peut tenir un effort sans s'arreter.

C'est le coeur de l'outil. Une seance de 2x25 min au seuil ne demande pas
une belle route : elle demande une route qui ne s'interrompt pas pendant
25 minutes. Ce module repond a cette question a partir d'OpenStreetMap.

Le modele de donnees est volontairement independant du lecteur OSM :
on passe des Node et des Way, d'ou qu'ils viennent (pyosmium sur un
extrait Geofabrik, Overpass, ou une fixture de test).
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Iterable

R_EARTH = 6371000.0

# ---------------------------------------------------------------- classement

# Hierarchie des voies, utilisee pour la priorite et pour ecarter le trafic.
RANK = {
    "motorway": 9, "motorway_link": 9, "trunk": 8, "trunk_link": 8,
    "primary": 7, "primary_link": 7, "secondary": 6, "secondary_link": 6,
    "tertiary": 5, "tertiary_link": 5, "unclassified": 4, "road": 4,
    "residential": 3, "cycleway": 3, "living_street": 2,
    "service": 1, "track": 1,
}

# Revetements acceptables pour un effort sur velo de route.
GOOD_SURFACE = {
    None, "", "asphalt", "paved", "concrete", "concrete:plates",
    "concrete:lanes", "chipseal", "fine_gravel",
}
BAD_SMOOTHNESS = {"bad", "very_bad", "horrible", "very_horrible", "impassable"}

# Noeuds qui imposent un arret ou une forte deceleration.
HARD_STOP_NODE = {
    ("highway", "traffic_signals"),
    ("highway", "stop"),
    ("highway", "give_way"),
    ("highway", "mini_roundabout"),
    ("highway", "turning_circle"),
    ("railway", "level_crossing"),
    ("railway", "crossing"),
    ("barrier", "gate"),
    ("barrier", "lift_gate"),
    ("barrier", "swing_gate"),
    ("barrier", "bollard"),
    ("barrier", "cycle_barrier"),
    ("barrier", "block"),
    ("barrier", "stile"),
    ("barrier", "kissing_gate"),
}


class Node:
    """Classe a slots : un extrait de 20 km fait des centaines de milliers
    de noeuds, et un dataclass ordinaire coute environ trois fois plus de
    memoire par instance."""
    __slots__ = ("id", "lat", "lon", "ele", "tags")

    def __init__(self, id, lat, lon, ele=None, tags=None):
        self.id = id
        self.lat = lat
        self.lon = lon
        self.ele = ele
        self.tags = tags if tags else EMPTY

    def __repr__(self):
        return "Node(%d, %.5f, %.5f)" % (self.id, self.lat, self.lon)


class Way:
    __slots__ = ("id", "nodes", "tags")

    def __init__(self, id, nodes, tags=None):
        self.id = id
        self.nodes = nodes
        self.tags = tags if tags else EMPTY

    def __repr__(self):
        return "Way(%d, %d noeuds)" % (self.id, len(self.nodes))


EMPTY = {}


@dataclass
class Config:
    """Filtres et seuils. Tout est explicite pour pouvoir etre discute."""
    max_rank: int = 6          # on ecarte primary et au-dessus (trafic)
    min_rank: int = 3          # on ecarte service et track
    max_turn_deg: float = 75.0  # au-dela on freine
    allow_unknown_surface: bool = True
    # un carrefour avec une voie de rang >= au notre est compte comme un
    # doute, pas comme un arret : OSM ne tague pas la priorite directement
    strict_junctions: bool = False


# ---------------------------------------------------------------- geometrie

def haversine(a: Node, b: Node) -> float:
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp = p2 - p1
    dl = math.radians(b.lon - a.lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH * math.asin(min(1.0, math.sqrt(h)))


def bearing(a: Node, b: Node) -> float:
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dl = math.radians(b.lon - a.lon)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.degrees(math.atan2(y, x)) % 360.0


def turn_angle(prev_b: float, next_b: float) -> float:
    d = abs(next_b - prev_b) % 360.0
    return 360.0 - d if d > 180.0 else d


# ---------------------------------------------------------------- predicats

def road_rank(tags: dict) -> int:
    return RANK.get(tags.get("highway"), 0)


def is_rideable(tags: dict, cfg: Config) -> bool:
    r = road_rank(tags)
    if not (cfg.min_rank <= r <= cfg.max_rank):
        return False
    if tags.get("area") == "yes":
        return False
    if tags.get("bicycle") == "no" or tags.get("access") in ("no", "private"):
        return False
    surf = tags.get("surface")
    if surf not in GOOD_SURFACE:
        if not (surf is None and cfg.allow_unknown_surface):
            return False
    if tags.get("smoothness") in BAD_SMOOTHNESS:
        return False
    return True


def is_hard_stop(node: Node) -> bool:
    for k, v in HARD_STOP_NODE:
        if node.tags.get(k) == v:
            return True
    # passage pieton gere par feux
    if node.tags.get("highway") == "crossing":
        if node.tags.get("crossing") in ("traffic_signals", "signals"):
            return True
        if node.tags.get("crossing:signals") == "yes":
            return True
    if "traffic_calming" in node.tags:
        return True
    return False


# ---------------------------------------------------------------- graphe

class RoadGraph:
    """Segments elementaires entre noeuds consecutifs d'une way."""

    def __init__(self, nodes: dict, ways: Iterable[Way], cfg: Config):
        self.N = nodes
        self.cfg = cfg
        self.seg = []          # (way_id, n1, n2, length, grade)
        self.at = {}           # node id -> [indices de segments]
        self.ways_at = {}      # node id -> {way_id: rank}  (toutes les ways, filtrees ou non)
        self.roundabout = set()
        self.names = {}        # way id -> nom ou numero de route

        for w in ways:
            rank = road_rank(w.tags)
            nm = w.tags.get("ref") or w.tags.get("name")
            if nm:
                self.names[w.id] = nm
            for nid in w.nodes:
                self.ways_at.setdefault(nid, {})[w.id] = rank
            if not is_rideable(w.tags, cfg):
                continue
            ring = w.tags.get("junction") == "roundabout"
            for a, b in zip(w.nodes, w.nodes[1:]):
                if a not in nodes or b not in nodes:
                    continue
                na, nb = nodes[a], nodes[b]
                L = haversine(na, nb)
                if L <= 0:
                    continue
                dz = (nb.ele - na.ele) if (na.ele is not None and nb.ele is not None) else 0.0
                i = len(self.seg)
                self.seg.append((w.id, a, b, L, dz / L, rank))
                self.at.setdefault(a, []).append(i)
                self.at.setdefault(b, []).append(i)
                if ring:
                    self.roundabout.add(a)
                    self.roundabout.add(b)

    def other(self, i: int, nid: int) -> int:
        a, b = self.seg[i][1], self.seg[i][2]
        return b if a == nid else a

    def way_of(self, i: int) -> int:
        return self.seg[i][0]

    def rank_of(self, i: int) -> int:
        return self.seg[i][5]


@dataclass
class Stretch:
    """Une portion continue, parcourable sans arret."""
    nodes: list
    length: float                 # m
    profile: list                 # [(longueur_m, pente)]
    doubts: list = field(default_factory=list)   # carrefours de rang >= au notre
    rank_min: int = 0
    edges: list = field(default_factory=list)    # indices de segments, pour la deduplication

    @property
    def km(self) -> float:
        return self.length / 1000.0

    def gain(self) -> float:
        return sum(L * g for L, g in self.profile if g > 0)

    def mean_grade(self) -> float:
        return (sum(L * g for L, g in self.profile) / self.length) if self.length else 0.0


# ---------------------------------------------------------------- recherche
#
# Le suivi de corridor est deterministe : depuis une arete orientee, le pas
# suivant est unique (le candidat le plus droit). On construit donc une
# fonction successeur une seule fois, puis on ne part que des tetes de
# chaine. Cout lineaire en nombre d'aretes, au lieu d'une extension depuis
# chaque arete dans les deux sens avec deduplication quadratique.

def _build_succ(G: "RoadGraph"):
    """succ[d] = arete orientee suivante, ou -1. d = 2*i (a->b) ou 2*i+1 (b->a)."""
    cfg = G.cfg
    nseg = len(G.seg)
    out = {}
    for i, s in enumerate(G.seg):
        out.setdefault(s[1], []).append(2 * i)       # part de a
        out.setdefault(s[2], []).append(2 * i + 1)   # part de b

    def tail(d):
        s = G.seg[d >> 1]
        return s[1] if (d & 1) == 0 else s[2]

    def head(d):
        s = G.seg[d >> 1]
        return s[2] if (d & 1) == 0 else s[1]

    G._tail, G._head = tail, head
    succ = [-1] * (2 * nseg)
    for d in range(2 * nseg):
        n = head(d)
        nd = G.N.get(n)
        if nd is None or is_hard_stop(nd) or n in G.roundabout:
            continue
        p = G.N.get(tail(d))
        if p is None:
            continue
        b0 = bearing(p, nd)
        best = (1e9, 0, -1)
        for e in out.get(n, ()):
            if (e >> 1) == (d >> 1):
                continue
            h = G.N.get(head(e))
            if h is None:
                continue
            ang = turn_angle(b0, bearing(nd, h))
            if ang > cfg.max_turn_deg:
                continue
            k = (ang, -G.rank_of(e >> 1), e)
            if k < best:
                best = k
        succ[d] = best[2]
    return succ


def _walk(G, succ, start, claimed_dir):
    """Suit la chaine depuis `start` et renvoie une Stretch."""
    cfg = G.cfg
    tail, head = G._tail, G._head
    d = start
    nodes = [tail(d), head(d)]
    seen = {nodes[0], nodes[1]}
    prof = [(G.seg[d >> 1][3], G.seg[d >> 1][4])]
    edges = [d >> 1]
    doubts = []
    rmin = G.rank_of(d >> 1)
    while True:
        claimed_dir[d] = True
        e = succ[d]
        if e < 0:
            break
        nxt = head(e)
        if nxt in seen or claimed_dir[e]:
            break
        n = head(d)
        way_in, way_out = G.way_of(d >> 1), G.way_of(e >> 1)
        my_rank = max(G.rank_of(e >> 1), rmin)
        rivals = [r for wid, r in G.ways_at.get(n, {}).items()
                  if wid not in (way_in, way_out)]
        if rivals and max(rivals) >= my_rank:
            if cfg.strict_junctions:
                break
            doubts.append(n)
        d = e
        nodes.append(nxt)
        seen.add(nxt)
        prof.append((G.seg[d >> 1][3], G.seg[d >> 1][4]))
        edges.append(d >> 1)
        rmin = min(rmin, G.rank_of(d >> 1))
    s = Stretch(nodes=nodes, length=sum(L for L, _ in prof), profile=prof,
                doubts=doubts, rank_min=rmin)
    s.edges = edges
    return s


def find_stretches(G: "RoadGraph", min_length: float = 1000.0,
                   overlap_max: float = 0.7):
    """Portions maximales. `overlap_max` : on jette une portion dont cette
    fraction d'aretes est deja couverte par une portion plus longue."""
    nseg = len(G.seg)
    if nseg == 0:
        return []
    succ = _build_succ(G)

    indeg = [0] * (2 * nseg)
    for d in range(2 * nseg):
        e = succ[d]
        if e >= 0:
            indeg[e] += 1

    claimed_dir = bytearray(2 * nseg)
    chains = []
    for d in range(2 * nseg):          # tetes de chaine
        if indeg[d] == 0 and not claimed_dir[d]:
            chains.append(_walk(G, succ, d, claimed_dir))
    for d in range(2 * nseg):          # boucles fermees restantes
        if not claimed_dir[d]:
            chains.append(_walk(G, succ, d, claimed_dir))

    chains = [c for c in chains if c.length >= min_length]
    chains.sort(key=lambda s: -s.length)
    taken = bytearray(nseg)
    kept = []
    for c in chains:
        n = len(c.edges)
        dup = sum(1 for i in c.edges if taken[i])
        if n and dup / n > overlap_max:
            continue
        for i in c.edges:
            taken[i] = 1
        kept.append(c)
    return kept
