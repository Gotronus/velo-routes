# -*- coding: utf-8 -*-
"""Relief depuis les tuiles SRTM ouvertes (jeu « skadi », 1 arc-seconde).

Source : https://s3.amazonaws.com/elevation-tiles-prod/skadi/
Pas d'authentification, 5 a 7 Mo par tuile de 1 degre, mise en cache locale.
Une tuile fait 3601 x 3601 entiers 16 bits gros-boutiens ; la ligne 0 est le
bord nord, la colonne 0 le bord ouest. -32768 signale un trou de donnee.

Resolution : environ 30 m. Suffisant pour la pente moyenne d'une cote,
insuffisant pour un ressaut de 50 m — les pentes sorties ici sont lissees
par construction, et c'est a garder en tete avant de croire un pourcentage
au dixieme pres.
"""
from __future__ import annotations
import gzip
import math
import os
import urllib.request

import numpy as np

BASE = "https://s3.amazonaws.com/elevation-tiles-prod/skadi"
SIZE = 3601
VOID = -32768


def tile_name(lat: int, lon: int) -> str:
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return "%s%02d%s%03d" % (ns, abs(lat), ew, abs(lon))


def tiles_for(bb):
    """bb = (lat_min, lat_max, lon_min, lon_max), comme extract.box."""
    y0, y1, x0, x1 = bb
    out = []
    for la in range(int(math.floor(y0)), int(math.floor(y1)) + 1):
        for lo in range(int(math.floor(x0)), int(math.floor(x1)) + 1):
            out.append((la, lo))
    return out


class Dem:
    """Cache de tuiles, interpolation bilineaire."""

    def __init__(self, cache_dir="data/dem", quiet=False):
        self.dir = cache_dir
        self.quiet = quiet
        self.t = {}
        self.missing = set()
        os.makedirs(cache_dir, exist_ok=True)

    def _path(self, la, lo):
        return os.path.join(self.dir, tile_name(la, lo) + ".hgt.gz")

    def ensure(self, la, lo) -> bool:
        key = (la, lo)
        if key in self.t:
            return True
        if key in self.missing:
            return False
        p = self._path(la, lo)
        if not os.path.exists(p) or os.path.getsize(p) < 100000:
            name = tile_name(la, lo)
            url = "%s/%s/%s.hgt.gz" % (BASE, name[:3], name)
            try:
                if not self.quiet:
                    print("  telechargement %s" % name, flush=True)
                urllib.request.urlretrieve(url, p + ".part")
                os.replace(p + ".part", p)
            except Exception as e:
                if not self.quiet:
                    print("  tuile %s indisponible (%s)" % (name, e), flush=True)
                self.missing.add(key)
                return False
        try:
            with gzip.open(p, "rb") as f:
                a = np.frombuffer(f.read(), dtype=">i2")
            if a.size != SIZE * SIZE:
                raise ValueError("taille inattendue %d" % a.size)
            self.t[key] = a.reshape(SIZE, SIZE).astype(np.float32)
        except Exception as e:
            if not self.quiet:
                print("  tuile %s illisible (%s)" % (tile_name(la, lo), e), flush=True)
            self.missing.add(key)
            return False
        return True

    def at(self, lat: float, lon: float):
        la, lo = int(math.floor(lat)), int(math.floor(lon))
        if not self.ensure(la, lo):
            return None
        g = self.t[(la, lo)]
        fr = (la + 1 - lat) * 3600.0
        fc = (lon - lo) * 3600.0
        r0 = min(SIZE - 2, max(0, int(fr)))
        c0 = min(SIZE - 2, max(0, int(fc)))
        dr, dc = fr - r0, fc - c0
        q = g[r0:r0 + 2, c0:c0 + 2]
        if np.any(q <= VOID + 1):
            v = q[q > VOID + 1]
            return float(v.mean()) if v.size else None
        return float((q[0, 0] * (1 - dr) + q[1, 0] * dr) * (1 - dc) +
                     (q[0, 1] * (1 - dr) + q[1, 1] * dr) * dc)

    def fill(self, nodes, quiet=False):
        """Affecte .ele a tous les noeuds, tuile par tuile et en vectoriel.

        Trois millions d'appels a at() en Python pur prennent plusieurs
        minutes ; regroupes par tuile et interpoles avec numpy, quelques
        secondes.
        """
        vals = list(nodes.values())
        if not vals:
            return 0, 0
        lat = np.fromiter((n.lat for n in vals), dtype=np.float64, count=len(vals))
        lon = np.fromiter((n.lon for n in vals), dtype=np.float64, count=len(vals))
        tla = np.floor(lat).astype(np.int32)
        tlo = np.floor(lon).astype(np.int32)
        key = tla.astype(np.int64) * 1000 + tlo
        ok = bad = 0
        for k in np.unique(key):
            sel = np.nonzero(key == k)[0]
            la, lo = int(k // 1000), int(k % 1000)
            if lo > 500:                      # remise en negatif apres le modulo
                lo -= 1000
                la += 1
            if not self.ensure(la, lo):
                bad += sel.size
                continue
            g = self.t[(la, lo)]
            fr = (la + 1 - lat[sel]) * 3600.0
            fc = (lon[sel] - lo) * 3600.0
            r0 = np.clip(fr.astype(np.int32), 0, SIZE - 2)
            c0 = np.clip(fc.astype(np.int32), 0, SIZE - 2)
            dr = fr - r0
            dc = fc - c0
            q00 = g[r0, c0]; q10 = g[r0 + 1, c0]
            q01 = g[r0, c0 + 1]; q11 = g[r0 + 1, c0 + 1]
            z = ((q00 * (1 - dr) + q10 * dr) * (1 - dc) +
                 (q01 * (1 - dr) + q11 * dr) * dc)
            void = (q00 <= VOID + 1) | (q10 <= VOID + 1) | \
                   (q01 <= VOID + 1) | (q11 <= VOID + 1)
            z[void] = np.nan
            for j, i in enumerate(sel):
                v = z[j]
                if v != v:                    # NaN
                    bad += 1
                else:
                    vals[i].ele = float(v)
                    ok += 1
        if not quiet:
            print("  relief : %d noeuds renseignes, %d sans donnee" % (ok, bad), flush=True)
        return ok, bad
