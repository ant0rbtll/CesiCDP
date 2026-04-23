# CESIPATH - Guide de lecture du projet

Ce depot contient une implementation pedagogique de CESIPATH autour d'un probleme de tournees de vehicules sur reseau routier contraint et dynamique.

Le README est le point d'entree conseille pour la correction. Il indique quoi lire, dans quel ordre, et pourquoi chaque notebook existe.

## Livrables

| Livrable | Fichier |
|---|---|
| **Livrable 1** — modelisation et formalisation du probleme VRP-CDR | `livrable_modelisation_1.ipynb` (a la racine) |
| **Livrable 2** — implementation, algorithmes, benchmark et interface | Tous les notebooks du dossier `notebooks/` (voir parcours de lecture ci-dessous) + interface web (`main_gui.py`) |

## Idee generale

Le projet construit une instance VRP-CDR en plusieurs couches :

1. generation d'un graphe routier connexe ;
2. application de contraintes statiques sur les aretes (`FREE`, `SURCHARGED`, `FORBIDDEN`) ;
3. fermeture metrique par Dijkstra pour donner une matrice complete aux solveurs ;
4. simulation dynamique des couts et disponibilites d'aretes ;
5. resolution par metaheuristiques ;
6. benchmark et visualisation.

Les notebooks sont volontairement explicatifs : ils ne servent pas seulement a executer le code, mais a justifier les choix de modelisation, les invariants, les complexites et les compromis algorithmiques. Les notebooks principaux contiennent des references quand une notion externe est mobilisee.

## Parcours de lecture recommande

Pour une lecture complete, suivre cet ordre :

1. `notebooks/models.ipynb`
2. `notebooks/graph_generator.ipynb`
3. `notebooks/metric_closure.ipynb`
4. `notebooks/validators.ipynb`
5. `notebooks/dynamic_costs.ipynb`
6. `notebooks/dynamic_network.ipynb`
7. `notebooks/solver_input.ipynb`
8. `notebooks/algorithms/neighborhood.ipynb`
9. `notebooks/algorithms/grasp.ipynb`
10. `notebooks/algorithms/simulated_annealing.ipynb`
11. `notebooks/algorithms/tabu_search.ipynb`
12. `notebooks/algorithms/genetic.ipynb`
13. `notebooks/algorithms/benchmark.ipynb`
14. `notebooks/algorithms/dynamic_runner.ipynb`
15. `notebooks/algorithms/dynamic_benchmark.ipynb`
16. `notebooks/visualization.ipynb`
17. `notebooks/main_visualization.ipynb`
18. `notebooks/package_exports.ipynb`

Pour une correction rapide, lire en priorite :

- `notebooks/graph_generator.ipynb` : generation, connexite, contraintes, matrices.
- `notebooks/metric_closure.ipynb` : Dijkstra, fermeture metrique, chemins reels.
- `notebooks/algorithms/neighborhood.ipynb` : representation des solutions et recherche locale commune.
- `notebooks/algorithms/grasp.ipynb`, `simulated_annealing.ipynb`, `tabu_search.ipynb`, `genetic.ipynb` : metaheuristiques.
- `notebooks/algorithms/benchmark.ipynb` et `dynamic_benchmark.ipynb` : comparaison experimentale.

## Carte des notebooks

| Notebook | Pourquoi le lire | Points importants |
|---|---|---|
| `notebooks/models.ipynb` | Pose le vocabulaire commun du projet. | `EdgeStatus`, `EdgeAttributes`, `GraphGenerationConfig`, `GraphInstance`, `DynamicGraphSnapshot`, seuils derives. |
| `notebooks/graph_generator.ipynb` | Explique comment une instance exploitable est construite. | Coordonnees, arbre couvrant, densification, protection de la connexite, trois matrices de couts, demandes, rejection sampling. |
| `notebooks/metric_closure.ipynb` | Justifie le passage d'un graphe routier incomplet a une matrice complete pour les solveurs. | Dijkstra, listes d'adjacence, reconstruction des chemins, complexites, Floyd-Warshall, inegalite triangulaire. |
| `notebooks/validators.ipynb` | Montre les garde-fous qui empechent les instances invalides. | Densite, degre moyen, connexite BFS, validation statique, validation dynamique avant coupure. |
| `notebooks/dynamic_costs.ipynb` | Detaille le modele de variation des couts dynamiques. | Trois niveaux de cout, mean reversion, bornes, multiplicateur dynamique, reproductibilite. |
| `notebooks/dynamic_network.ipynb` | Explique comment le reseau evolue tour par tour. | Aretes ON/OFF, refus des coupures dangereuses, recalcul Dijkstra, invariants dynamiques. |
| `notebooks/solver_input.ipynb` | Explique le contrat d'entree commun aux solveurs. | `SolverInput`, entree statique, entree dynamique, decouplage entre reseau et optimisation. |
| `notebooks/visualization.ipynb` | Montre comment inspecter les graphes et les solutions. | Graphe de base, residuel, dynamique, session interactive, fallback si le bouton Jupyter ne marche pas. |
| `notebooks/main_visualization.ipynb` | Documente le lanceur interactif hors notebook. | Pourquoi une fenetre matplotlib native est utile, options CLI, lien avec `GraphVisualizer`. |
| `notebooks/package_exports.ipynb` | Sert de carte d'API du package `cesipath`. | Imports publics, facade, exports de generation, dynamique, solveurs, benchmarks et visualisation. |

## Notebooks d'algorithmes

| Notebook | Pourquoi le lire | Points importants |
|---|---|---|
| `notebooks/algorithms/neighborhood.ipynb` | Base commune des metaheuristiques. | `VRPSolution`, couts, capacite, admissibilite, 2-opt, relocate, swap, recherche locale, voisins aleatoires. |
| `notebooks/algorithms/grasp.ipynb` | Premiere metaheuristique complete, simple a suivre. | Construction gloutonne randomisee, RCL, `rcl_alpha`, recherche locale, reproductibilite, cas d'usage. |
| `notebooks/algorithms/simulated_annealing.ipynb` | Explique l'acceptation de mauvaises solutions controlee par temperature. | Refroidissement, probabilite d'acceptation, exploration/exploitation, recherche locale finale, variance par seed. |
| `notebooks/algorithms/tabu_search.ipynb` | Montre une recherche locale avec memoire. | Liste tabou, tenure, aspiration, arret sans amelioration, comparaison avec GRASP et SA. |
| `notebooks/algorithms/genetic.ipynb` | Algorithme le plus detaille sur la partie population. | Codage giant-tour, Split de Prins, OX crossover, mutation, schema memetique, pression selective. |
| `notebooks/algorithms/benchmark.ipynb` | Compare les algorithmes statiques. | Lignes de benchmark, resumes agreges, boxplot du cout, gap relatif, runtime, sauvegarde des figures. |
| `notebooks/algorithms/dynamic_runner.ipynb` | Explique l'execution d'une solution dans un reseau dynamique. | Plan fige vs re-optimisation, demandes restantes, cout planifie vs cout realise, interchangeabilite des solveurs. |
| `notebooks/algorithms/dynamic_benchmark.ipynb` | Compare les strategies en dynamique. | Cout realise, gain de re-optimisation, cout planifie vs realise, conseils de benchmark dynamique. |
| `notebooks/algorithms/visualization.ipynb` | Complete la visualisation par le trace des solutions. | Trace de solution, options, sauvegarde auto-incrementee, palette. |

## Relation entre notebooks et code source

Chaque notebook documente un fichier source correspondant :

| Code source | Notebook |
|---|---|
| `src/cesipath/models.py` | `notebooks/models.ipynb` |
| `src/cesipath/graph_generator.py` | `notebooks/graph_generator.ipynb` |
| `src/cesipath/metric_closure.py` | `notebooks/metric_closure.ipynb` |
| `src/cesipath/validators.py` | `notebooks/validators.ipynb` |
| `src/cesipath/dynamic_costs.py` | `notebooks/dynamic_costs.ipynb` |
| `src/cesipath/dynamic_network.py` | `notebooks/dynamic_network.ipynb` |
| `src/cesipath/solver_input.py` | `notebooks/solver_input.ipynb` |
| `src/cesipath/visualization.py` | `notebooks/visualization.ipynb` |
| `src/cesipath/__init__.py` | `notebooks/package_exports.ipynb` |
| `src/cesipath/algorithms/*.py` | `notebooks/algorithms/*.ipynb` |

