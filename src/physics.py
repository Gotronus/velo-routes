# -*- coding: utf-8 -*-
"""Modele de puissance en velo, identique a celui du Training Lab.

P = v*m*g*(sin th + Crr*cos th) + 0.5*rho*CdA*v^3

Les constantes par defaut sont celles d'Axel : CdA 0,29 m2 mains en bas
(Crouch et coll. 2017), Crr 0,005 route courante, masse totale 76 kg.
Ce sont des moyennes de litterature, pas des mesures.
"""
from __future__ import annotations
import math
from dataclasses import dataclass

G = 9.80665
R_AIR = 287.058

# Au-dela de cette vitesse on considere qu'on ne peut plus appliquer la
# puissance cible : la pente fait le travail et l'intervalle est casse.
V_MAX_HOLDABLE = 65 / 3.6


def air_density(temp_c: float = 10.0, alt_m: float = 50.0) -> float:
    """Pression barometrique standard puis loi des gaz parfaits (air sec)."""
    p = 101325.0 * (1.0 - 2.25577e-5 * max(0.0, alt_m)) ** 5.25588
    return p / (R_AIR * (temp_c + 273.15))


@dataclass(frozen=True)
class Rider:
    mass: float = 76.0        # toi + velo, kg
    cda: float = 0.29         # m2
    crr: float = 0.005
    rho: float = 1.2392       # 10 C, 50 m
    cp: float = 260.0         # W
    w_prime: float = 20000.0  # J

    @classmethod
    def at(cls, temp_c: float, alt_m: float, **kw) -> "Rider":
        return cls(rho=air_density(temp_c, alt_m), **kw)


def power_for(speed: float, grade: float, r: Rider) -> float:
    """Puissance necessaire pour tenir `speed` (m/s) sur une pente `grade` (fraction)."""
    th = math.atan(grade)
    roll = r.mass * G * (math.sin(th) + r.crr * math.cos(th))
    return speed * roll + 0.5 * r.rho * r.cda * speed ** 3


def speed_for(power: float, grade: float, r: Rider) -> float:
    """Vitesse d'equilibre (m/s) a `power` watts sur `grade`. Dichotomie."""
    lo, hi = 0.05, 35.0
    if power_for(hi, grade, r) < power:
        return hi
    if power_for(lo, grade, r) > power:
        # descente ou l'on depasse la cible meme en roue libre
        return hi
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if power_for(mid, grade, r) < power:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def traverse(profile, power: float, r: Rider):
    """Parcourt une liste de (longueur_m, pente) a puissance constante.

    Renvoie (duree_s, distance_m, fraction_non_tenable). La derniere valeur
    est la part de la distance ou la vitesse d'equilibre depasse
    V_MAX_HOLDABLE : sur ces portions la pente descend trop pour que
    l'intervalle ait un sens.
    """
    t = 0.0
    d = 0.0
    d_lost = 0.0
    for length, grade in profile:
        if length <= 0:
            continue
        v = speed_for(power, grade, r)
        t += length / v
        d += length
        if v > V_MAX_HOLDABLE:
            d_lost += length
    return t, d, (d_lost / d if d else 0.0)


def holdable_distance(duration_s: float, power: float, grade: float, r: Rider) -> float:
    """Distance couverte en `duration_s` a `power` sur une pente constante.

    Sert a dimensionner : un 2x25 min au seuil demande combien de kilometres
    de route sans arret ?
    """
    return speed_for(power, grade, r) * duration_s
