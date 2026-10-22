# velo-routes

Générateur de parcours d'entraînement à vélo, à partir d'OpenStreetMap.

Le principe tient en une phrase : **une séance de 2×25 min au seuil ne demande
pas une belle route, elle demande une route qui ne s'interrompt pas pendant
25 minutes.** Cet outil répond à cette question pour un terrain donné, puis
sert le résultat dans une application web installable.

Une PWA dans `docs/`, publiée par GitHub Pages. Les séances et la charge
d'entraînement vivent ailleurs, dans le Training Lab, qui reste connecté à
Strava en direct — un site statique ne peut rien écrire de partagé entre
appareils, donc les deux outils restent séparés et se renvoient l'un à l'autre.

## Installation

```
"%USERPROFILE%\anaconda3\python.exe" -m pip install -r requirements.txt
```

Sous Windows, `py.bat` règle le `PATH` d'Anaconda (sans quoi le module `ssl`
ne se charge pas) et lance Python depuis la racine du projet.

Il faut aussi un extrait OpenStreetMap, à télécharger une fois :

```
curl -L -o pays-de-la-loire.osm.pbf ^
  https://download.geofabrik.de/europe/france/pays-de-la-loire-latest.osm.pbf
```

## Utilisation

```
py.bat -u src\scan.py pays-de-la-loire.osm.pbf 47.4712 -0.5518 80 angers80
py.bat src\ask.py data\stretches_angers80.json --name "D 767"
py.bat src\ask.py data\stretches_angers80.json --clean --min-km 12
py.bat src\web_index.py docs\data\index.json data\stretches_*.json
py.bat tests\test_stretches.py
```

`scan.py` va du `.osm.pbf` aux portions sans intermédiaire JSON : trois passes
bornées par une boîte englobante, le relief, le graphe, puis la recherche. Le
pic de mémoire est celui du graphe seul. Compter environ 15 minutes et 3 Go
pour un rayon de 80 km.

`ask.py` interroge un résultat déjà calculé, en quelques secondes.

`web_index.py` fusionne et allège pour l'appli : Douglas-Peucker à 25 m,
coordonnées en entiers de 1e-5 degré encodées en delta, déduplication entre
zones. Environ 88 % des points sont retirés sans que les routes bougent.

## Ce qui coupe une portion

Arrêts durs : feux, stop, cédez-le-passage, mini-rond-point, passage à niveau,
barrière, ralentisseur, rond-point. Géométrie : virage de plus de 75°.
Revêtement : tout ce qui n'est pas asphalte ou béton, et `smoothness` à `bad`
ou pire. Classe : au-dessus de départementale (trafic) et en dessous de
lotissement.

Les carrefours où une voie de rang égal ou supérieur débouche sont comptés
comme des **doutes**, pas comme des arrêts : OpenStreetMap ne décrit pas la
priorité, donc l'outil la signale au lieu de la deviner. `--strict` les traite
comme des arrêts.

## Ce qu'il faut savoir avant de croire un chiffre

- **Le CdA est une moyenne de littérature** (Crouch et coll. 2017, tableau 4),
  pas une mesure : 0,32 m² aux cocottes, 0,29 mains en bas, 0,23 en chrono.
  L'étendue entre essais laisse ±15 % sur le terme aérodynamique.
- **Le modèle ignore l'abri du peloton**, qui retire 25 à 40 % de ce terme et
  pèse bien plus lourd que le choix du CdA. Il ignore aussi le vent.
- **Le relief est au pas de 30 m** (SRTM 1 arc-seconde) : bon pour la pente
  moyenne d'une côte, aveugle sur un ressaut court.
- **Dans l'appli, le temps d'une portion est calculé sur sa pente moyenne**,
  pas sur son profil détaillé : sur une route vallonnée il est légèrement
  sous-estimé.
- **Les fractions de puissance des séances** viennent des structures écrites du
  Training Lab, pas des IF de son catalogue, qui sont optimistes de 8 à 22 %.
- Les portions trouvées dépendent de l'extrait : à 80 km autour d'Angers on
  couvre presque toute la région Pays de la Loire, et ce qui dépasse (Centre-Val
  de Loire, Normandie, Bretagne, Nouvelle-Aquitaine) est simplement absent,
  sans erreur visible.

## Données

Routes © contributeurs OpenStreetMap, sous licence ODbL. Relief : jeu SRTM
« skadi » ouvert, 1 arc-seconde. Aucune donnée Strava n'est utilisée ni stockée
ici : la politique d'API de Strava interdit d'agréger ou de conserver des
données de localisation au-delà de sept jours.
