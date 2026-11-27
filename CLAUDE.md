# velo-routes · Générateur de parcours d'entraînement vélo

Projet perso de Gotronus. Claude Code lit ce fichier au début de chaque session, et toutes les sessions parallèles partent de lui. À garder sous 200 lignes.

## Le but

Trouver, à partir d'OpenStreetMap, les portions de route où l'on peut tenir un effort sans s'arrêter (une séance de 2×25 min au seuil demande une route qui ne s'interrompt pas pendant 25 minutes), puis les servir dans une PWA installable sur PC et sur téléphone.

Les séances et la charge d'entraînement vivent dans le Training Lab, connecté à Strava : les deux outils restent séparés et se renvoient l'un à l'autre.

## Organisation

- `src/osmroads.py` : le cœur, la détection des portions sans arrêt. Son modèle de données (Node, Way) est indépendant du lecteur OSM.
- `src/scan.py` : du `.osm.pbf` aux portions en une passe mémoire (compter ~15 min et ~3 Go pour un rayon de 80 km).
- `src/extract.py` : extraction du graphe routier en trois passes bornées par une boîte englobante.
- `src/elevation.py` : relief SRTM « skadi » (~30 m), tuiles mises en cache localement.
- `src/physics.py` : modèle de puissance, identique à celui du Training Lab.
- `src/ask.py`, `src/report.py` : interroger un résultat déjà calculé.
- `src/web_index.py` : fusion et allègement pour l'appli (Douglas-Peucker à 25 m, coordonnées entières encodées en delta, dédoublonnage entre zones).
- `docs/` : la PWA (`index.html`, `sw.js`, `manifest.webmanifest`), publiée par GitHub Pages. `docs/data/index.json` est généré par `web_index.py`.
- `tests/test_stretches.py` : réseau synthétique dont on connaît la bonne réponse.
- `data/` et `*.osm.pbf` : données lourdes régénérées par le pipeline, jamais versionnées.

## Commandes (Windows, Anaconda)

Toujours passer par `py.bat` : il règle le PATH d'Anaconda (sinon le module `ssl` ne se charge pas) et lance Python depuis la racine du projet.

- Installer : `"%USERPROFILE%\anaconda3\python.exe" -m pip install -r requirements.txt`
- Tests : `py.bat tests\test_stretches.py`
- Scanner une zone (long, ne pas le lancer sans raison) : `py.bat -u src\scan.py pays-de-la-loire.osm.pbf 47.4712 -0.5518 80 angers80`
- Interroger un résultat : `py.bat src\ask.py data\stretches_angers80.json --clean --min-km 12`
- Régénérer l'index de l'appli : `py.bat src\web_index.py docs\data\index.json data\stretches_*.json`

## Règles métier (à ne pas changer sans le dire dans la PR)

- Ce qui coupe une portion : feux, stop, cédez-le-passage, mini-rond-point, passage à niveau, barrière, ralentisseur, rond-point ; virage de plus de 75° ; revêtement autre qu'asphalte ou béton, ou `smoothness` à `bad` ou pire ; classe de route hors de la plage retenue.
- Un carrefour où débouche une voie de rang égal ou supérieur est un **doute**, pas un arrêt : OpenStreetMap ne décrit pas la priorité. `--strict` les traite comme des arrêts.
- CdA, Crr et masse sont des moyennes de littérature, pas des mesures : ne jamais présenter un temps ou une puissance comme précis.
- Toute modification d'un critère ou du modèle physique ajoute ou adapte un cas dans `tests/test_stretches.py`.

## Règles de travail

1. Une tâche = une branche = une PR, même en solo.
2. Jamais de commit direct sur `main` : c'est ce que GitHub Pages publie.
3. Sessions parallèles : une par worktree (`claude -w moteur`, `claude -w appli`). Zone « moteur » : `src/` et `tests/`. Zone « appli » : `docs/` sauf `docs/data/`. Le format de `docs/data/index.json` est le contrat entre les deux : le changer demande une PR dédiée qui modifie les deux côtés.
4. Ne jamais versionner de `.osm.pbf`, de JSON de `data/`, de tuiles de relief, ni aucune donnée Strava (la politique d'API de Strava interdit de conserver des localisations plus de sept jours).
5. Aucun nom civil ni chemin personnel (`C:\Users\…`) dans les fichiers : le dépôt est publié sous le pseudo Gotronus.
6. L'appli affiche « © contributeurs OpenStreetMap » (licence ODbL) et cite la source du relief.
7. Messages de commit en français, à l'impératif, comme dans l'historique.
8. Avant une PR : agent `testeur`, puis agent `relecteur`.
