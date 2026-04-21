# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commandes

Le package n'est pas installable (pas de `pyproject.toml`). Importer depuis la racine nécessite :

```python
import sys; sys.path.insert(0, "src")
from cesipath import ...
```

- **Exécution de scripts** : `python3` (le binaire `python` n'est pas aliasé).
- **Visualisation interactive hors notebook** : `python3 main_visualization.py`.
- **Pas de suite de tests** formelle — la validation passe par des smoke tests ad-hoc et par les notebooks `notebooks/*.ipynb`, un par module métier.
- **Pas de linter configuré**.

## Architecture

Le projet implémente **VRP-CDR** (Vehicle Routing Problem with Capacity, edge Constraints, Dynamic routing), formalisé dans `livrable_modelisation_1.ipynb`. Deux couches :

### Domaine (`src/cesipath/`, hors `algorithms/`)

Le générateur produit des graphes réalistes, la fermeture métrique les rend exploitables par les solveurs, et le simulateur dynamique fait évoluer les coûts/statuts des arêtes pendant la résolution.

- **`graph_generator.py`** — Produit une `GraphInstance` filtrée par un profil de densité auto selon la taille. Les arêtes portent un `EdgeStatus` (`FREE` / `SURCHARGED` / `FORBIDDEN`).
- **`metric_closure.py`** — Complète le graphe résiduel par Dijkstra. Expose `completed_costs` (matrice Δ-TSP respectant l'inégalité triangulaire) et `completed_paths` (chemins).
- **`dynamic_network.py` + `dynamic_costs.py`** — Simule l'évolution des coûts avec gaussienne à retour vers la moyenne, plancher = coût statique, plafond = `dynamic_max_multiplier`. Des arêtes peuvent passer `FORBIDDEN` et redevenir `FREE` sous contraintes de connexité et densité.
- **`solver_input.py`** — Contrat unique `SolverInput` (cost_matrix, depot, demands, capacity, shortest_paths, source, dynamic_step). `build_static_solver_input` et `build_dynamic_solver_input` produisent la même structure depuis un état statique ou un `DynamicGraphSnapshot`. **Tous les algos consomment `SolverInput`, pas `GraphInstance`** — ne jamais lire la structure de graphe brute depuis un solveur.
- **`validators.py`** — `InstanceValidator` (validité structurelle de l'instance) et `DynamicStateValidator` (invariants sur snapshots). Ne valide **pas** les solutions VRP.

### Métaheuristiques (`src/cesipath/algorithms/`)

Quatre algorithmes partagent un même jeu de primitives de voisinage. **Toujours mutualiser dans `neighborhood.py` plutôt que dupliquer dans chaque algo.**

- **`neighborhood.py`** — Fondation : `VRPSolution` (dataclass), opérateurs déterministes best-improvement (`relocate_inter`, `swap_inter`, `two_opt`), `local_search` qui les compose jusqu'à stabilité, et versions aléatoires (`random_*`) utilisées par SA. `_prune_empty_routes` est `_private` mais réutilisé par `tabu_search`.
- **`grasp.py`** — GRASP = construction gloutonne randomisée (RCL paramétrée par `rcl_alpha`) + `local_search`, sur `max_iterations` restarts.
- **`simulated_annealing.py`** — Metropolis + refroidissement géométrique, mouvements via `random_neighbor`, passe finale `local_search` (flag `final_local_search`) pour équité vs GRASP.
- **`tabu_search.py`** — Balayage complet du voisinage relocate+swap, mémoire courte par attribut (client déplacé, paire échangée), aspiration, polissage final `local_search`.
- **`genetic.py`** — Représentation **giant-tour** (permutation) décodée par **Split de Prins** (DP O(n²)). OX crossover, mutation swap/reverse, sélection tournoi, élitisme, option mémétique qui applique `local_search` à chaque enfant.
- **`benchmark.py`** — Harnais : `run_benchmark(sizes, seeds, algos, algo_kwargs)` produit une liste de dicts. `plot_benchmark_quality`, `plot_benchmark_gap` (écart % au meilleur par instance), `plot_benchmark_runtime`. `save_benchmark_figures` sauvegarde les 3 PNG avec index auto-incrémenté partagé avec `save_solution_plot`.
- **`visualization.py`** — `plot_solution` (routes colorées + graphe résiduel en fond) et `save_solution_plot` (fichiers `png_result_N.png` dans `DEFAULT_IMAGE_DIR = algorithms/image/`).

### Contraintes transverses

- **Commentaires et docstrings en français sans accents** (style historique du repo).
- **Figures** : `algorithms/image/` est dans `.gitignore` (`*.png`). Ne pas commiter de PNG.
- **`.pyc`** : déjà ignorés et untracked — ne jamais re-commiter par inadvertance.
- **Reproductibilité** : tous les algos acceptent `seed`. Les tests manuels vérifient que deux runs même seed donnent le même coût.

## Git

- Branche principale : **`main`** (ne PAS utiliser `PROSIT1` même si `git status` le suggère).
- Style de messages : `feat : X`, `fix : X`, `refacto` (lowercase, espace autour du `:`).
- PR target : `main`.
