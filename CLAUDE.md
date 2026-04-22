# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commandes

Le package n'est pas installable (pas de `pyproject.toml`). Importer depuis la racine nécessite :

```python
import sys; sys.path.insert(0, "src")
from cesipath import ...
```

- **Exécution de scripts** : `python3` (le binaire `python` n'est pas aliasé).
- **GUI modernisé** : `python3 main_gui.py` — Interface 3 onglets (Benchmark, Génération, Quartier) avec design system cohérent
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

## Interface Graphique (`src/gui/`)

Refonte complète moderne avec design system cohérent. Trois couches :

### Design System (`theme.py`)

Palette professionnelle avec variable systématiques :
- **Couleurs** : `primary` (gris foncé), `accent` (bleu ciel), états (`success` vert, `error` rouge, `warning` ambre)
- **Typographie** : `FONT_FAMILY="Segoe UI"`, `MONO_FONT_FAMILY="Menlo"`, constantes `FONT_SIZE_*` (XS à 3XL)
- **Espacements** : constantes `SPACING_*` (XS à 2XL) pour alignement systématique
- **Styles ttk** : H1/H2/H3, Body/BodyBold/BodySecondary, Hint/Caption, Chip, Card, Section, App.TNotebook

Toujours utiliser `PALETTE` et constantes plutôt que hardcoder les valeurs.

### Composants (`components.py`)

Widgets réutilisables avec animations et états visuels :
- **`ColoredButton`** — Bouton avec `role` (primary/secondary/success/danger/warning), `size` (sm/md/lg), animations hover fluides, état running
- **`RunningIndicator`** — Progression indéterminée + message d'état avec couleurs contextuelles
- **`LogConsole`** — Console monospace dark avec tags colorés (info/success/error/warning/running), supporteCtrl+A pour sélectionner tout
- **`LabeledEntry`** — Champ texte avec label, hint, tooltip, validation live en temps réel, désélection auto au focus
- **`LabeledCombobox`** — Dropdown avec label et tooltip intégrés
- **`ToolTip`** — Tooltips rectangles avec bordure solide, apparition au hover
- **Utilitaires** : `blend()`, `lighten()`, `darken()` pour interpolation lisse de couleurs

### Interface Principale (`main_gui.py`)

Trois onglets tab avec icônes colorées :
- **`BenchmarkTab`** — Benchmark multi-algo avec sélection de tailles/seeds, dossier de sortie, console de logs
- **`GenerationTab`** — Génération d'instances VRP avec paramètres dynamiques (sigma, reversion, forbid_prob, etc.)
- **`QuartierTab`** — **Reconnaissance OSM intégrée et interactive** : charge des vrais quartiers de villes réelles (Paris, Lyon, Marseille, etc.) via OpenStreetMap, affiche le réseau urbain (routes, chemins piétons) directement dans l'appli avec visualisation imbriquée. Permet de **tester les algorithmes sur des topologies réalistes** : vous pouvez optimiser des tournées de livraison sur un vrai quartier avec contraintes géographiques authentiques.

En-tête avec titre + sous-titre + chips informatifs (Desktop UI, Embedded Visualizer, OSM Ready).

**Visualisation interactive et user-friendly** :
- Graphe résiduel coloré en arrière-plan pendant les benchmarks
- Routes colorées par véhicule avec trajectoires claires
- Zoom et pan fluides dans les onglets Generation et Quartier
- Rendu des réseaux OSM avec fond de carte intégré
- Logs en temps réel avec icônes colorées (✓ succès, ✗ erreur, ⏳ en cours)
- États visuels clairs : boutons hover, champs validés/erreur, progression indéterminée

### Conventions GUI

- Tous les espacements via `SPACING_*` (jamais de nombres hardcodés comme 8, 12, 16)
- Labels avec `style="BodyBold.TLabel"` (jamais `"Body.TLabel"`)
- Entrées utilisateur : `LabeledEntry` ou `LabeledCombobox` plutôt que widgets bruts
- Actions principales : `ColoredButton(role="primary")` ou `role="success"` selon contexte
- Logs : toujours via `LogConsole.log(level, message)` avec niveaux prédéfinis
- Validateurs : utiliser les fonctions de `services.py` (parse_int_list, parse_positive_int, parse_float, etc.)
- Opérations longues : toujours en thread worker avec `RunningIndicator` en UI principal

### Intégration OSM et Topologies Réalistes

La **reconnaissance quartier** (`QuartierTab`) charge des réseaux urbains réels via OpenStreetMap :
- Autorise le géocodage libre (Paris, Lyon, Marseille, Bordeaux, etc.)
- Supporte plusieurs types de réseaux : `drive` (routes), `walk` (piétons), `bike` (cyclistes), `all` (tous)
- Charge dynamiquement la topologie réelle avec distances authentiques
- **Permet d'appliquer directement les métaheuristiques sur le quartier chargé** — tournées de livraison optimisées sur géographie réelle, contraintes VRP respectées (capacité véhicule, distances, clients)
- Export optionnel en GraphML/GeoJSON pour intégration externe
- Visualisation imbriquée directement dans l'appli (sans popup externe)

## Git

- Branche principale : **`main`** (ne PAS utiliser `PROSIT1` même si `git status` le suggère).
- Style de messages : `feat : X`, `fix : X`, `refacto` (lowercase, espace autour du `:`).
- PR target : `main`.

## Changements Récents (Branche GUI Moderne)

### Refonte Complète de l'Interface
- **Design System moderne** : palette couleurs professionnelles, espacements systématisés, typographie cohérente
- **Composants sophistiqués** : animations fluides, états visuels clairs, validation en temps réel
- **Layout amélioré** : meilleure hiérarchie visuelle, espacements élégants, tooltips rectangulaires
- **Fixes UX** : désélection auto des champs au focus, console non focusable, interactions cohérentes

### Fichiers Modifiés
- `src/gui/theme.py` — Palette PALETTE étendue, constantes SPACING_*, FONT_SIZE_*, styles ttk complets
- `src/gui/components.py` — Composants refactorisés avec animations, utilitaires color (blend/lighten/darken)
- `main_gui.py` — Layout amélioré avec en-tête moderne, imports des constantes de theme, meilleur responsive
