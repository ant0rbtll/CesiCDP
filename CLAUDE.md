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

### Metaheuristiques (`src/cesipath/algorithms/`)

Quatre algorithmes partagent un meme jeu de primitives de voisinage. Toujours mutualiser dans `neighborhood.py` plutot que dupliquer dans chaque algo.

- **`neighborhood.py`** — Fondation : `VRPSolution` (dataclass), operateurs deterministes best-improvement (`relocate_inter`, `swap_inter`, `two_opt`), `local_search` qui les compose jusqu a stabilite, et versions aleatoires (`random_*`) utilisees par SA. `_prune_empty_routes` est `_private` mais reutilise par `tabu_search`.
- **`grasp.py`** — GRASP = construction gloutonne randomisee (RCL parametree par `rcl_alpha`) + `local_search`, sur `max_iterations` restarts.
- **`simulated_annealing.py`** — Metropolis + refroidissement geometrique, mouvements via `random_neighbor`, passe finale `local_search` (flag `final_local_search`) pour equite vs GRASP.
- **`tabu_search.py`** — Balayage complet du voisinage relocate+swap, memoire courte par attribut (client deplace, paire echangee), aspiration, polissage final `local_search`.
- **`genetic.py`** — Representation giant-tour (permutation) decodee par Split de Prins (DP O(n^2)). OX crossover, mutation swap/reverse, selection tournoi, elitisme, option memetique qui applique `local_search` a chaque enfant.
- **`benchmark.py`** — Harnais : `run_benchmark(sizes, seeds, algos, algo_kwargs)` produit une liste de dicts. `plot_benchmark_quality`, `plot_benchmark_gap` (ecart % au meilleur par instance), `plot_benchmark_runtime`. `save_benchmark_figures` sauvegarde les 3 PNG avec index auto-incremente.
- **`visualization.py`** — `plot_solution` (routes colorees + graphe residuel en fond) et `save_solution_plot` (fichiers `png_result_N.png` dans `DEFAULT_IMAGE_DIR = algorithms/image/`).

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
- Branche principale : `main`. Style de messages : `feat : X`, `fix : X`, `refacto`.

## Validation minimale

Avant livraison:

1. `python3 -m compileall dash_app`
2. smoke test manuel de `python3 dash_app/app.py`
3. verifier logs et callbacks sans erreur JS console sur le flux teste
