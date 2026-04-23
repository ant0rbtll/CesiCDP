# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Commandes rapides

Le package n est pas installable (pas de `pyproject.toml`).
Toujours importer depuis la racine avec:

```python
import sys
sys.path.insert(0, "src")
from cesipath import ...
```

- Executer avec `python3` (jamais `python`).
- Web UI Dash: `python3 dash_app/app.py`
- GUI tkinter legacy: `python3 main_gui.py`
- Visualisation hors notebook: `python3 main_visualization.py`

## Architecture du projet

### Domaine (source de verite)

Toute la logique metier est dans `src/cesipath/`:

- generation d instance VRP
- fermeture metrique et plus courts chemins
- dynamique de couts / statuts d aretes
- construction `SolverInput`
- solveurs (`grasp`, `tabu_search`, `simulated_annealing`, `genetic`)
- benchmark et visualisation

Ne pas casser les contrats de `SolverInput` et `VRPSolution`.

### Web UI Dash (`dash_app/`)

- `app.py`: point d entree Dash, insertion de `src` dans `sys.path`, initialisation app.
- `layout.py`: tabs Benchmark / Generation / Quartier + `dcc.Store`.
- `callbacks/benchmark.py`: lancement benchmark, polling statut, rendu 3 graphes Plotly.
- `callbacks/generation.py`: generation d instance et rendu du graphe.
- `callbacks/quartier.py`: chargement OSM, simulation VRP, animation camion.
- `components/log_console.py`: queue thread-safe par onglet + rendu logs.
- `components/map_view.py`: rendu carte OSM en graphe mathematique Plotly.
- `assets/style.css`: design system CSS.
- `assets/quartier_speed.js`: controle vitesse/start/pause en clientside JS.

## Etat, sessions et concurrence

- L app tourne avec `app.run(debug=True, port=8050, processes=1, threaded=True)`.
- Les objets non serialisables vont dans `SESSION_CACHE` (global serveur), indexes par `session_id`.
- Les `dcc.Store` ne contiennent que de l etat serialisable (status, session_id, params).
- Les operations longues tournent dans des `threading.Thread(..., daemon=True)`.
- Les logs temps reel passent par `LOG_STORE` (`queue.Queue`) et des callbacks `dcc.Interval`.

## Onglet Quartier (etat actuel)

- Chargement OSM via worker dedie, stockage en cache serveur (`osm_graph`, `osm_nodes`, `osm_edges`, etc.).
- Simulation sur graphe OSM avec couts dynamiques et chemins reels Dijkstra.
- Animation Plotly par frames avec sprite camion (`image/camionD.png`, `image/camionG.png`).
- Vitesse et commandes Start/Pause pilotes en JS (`assets/quartier_speed.js`).

## Conventions de developpement

- Commentaires et docstrings en francais sans accents.
- Reproductibilite: toujours passer `seed` aux algorithmes.
- Pour la migration UI, ne pas modifier la logique metier dans `src/cesipath/`.
- Conserver `main_gui.py` fonctionnel en parallele.
- Les PNG auto-generes ne doivent pas etre commits.

## Validation minimale

Avant livraison:

1. `python3 -m compileall dash_app`
2. smoke test manuel de `python3 dash_app/app.py`
3. verifier logs et callbacks sans erreur JS console sur le flux teste
