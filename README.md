# velo-routes

Generateur de parcours d'entrainement a partir d'OpenStreetMap.

Le principe : une seance de 2x25 min au seuil ne demande pas une belle
route, elle demande une route qui ne s'interrompt pas pendant 25 minutes.
Cet outil repond a cette question, puis construit des boucles autour des
portions trouvees.

## Installation

    "%USERPROFILE%\anaconda3\python.exe" -m pip install -r requirements.txt

## Utilisation

    python fetch_osm.py              # extrait Pays de la Loire, une fois
    python run_index.py angers       # portions roulables autour d'Angers
    python run_index.py beaufou --radius 25 --min-km 6
    python tests/test_stretches.py   # verifications sur reseau synthetique

## Ce qui coupe une portion

Arrets durs : feux, stop, cedez-le-passage, mini-rond-point, passage a
niveau, barriere, ralentisseur, rond-point. Geometrie : virage de plus de
75 degres. Revetement : tout ce qui n'est pas asphalte ou beton, et
smoothness bad ou pire. Classe : au-dessus de departementale (trafic) et
en-dessous de lotissement.

Les carrefours ou une voie de rang egal ou superieur debouche sont
comptes comme des **doutes**, pas comme des arrets : OSM ne tague pas la
priorite, donc l'outil les signale au lieu de les deviner. `--strict` les
traite comme des arrets.

## Ce qui n'est pas encore la

Le relief : les pentes valent zero tant que les tuiles SRTM ne sont pas
branchees, donc les durees sont celles du plat. La heatmap personnelle,
a construire depuis l'export de donnees Strava (pas l'API, dont les
conditions interdisent un index permanent). Le generateur de boucles.
