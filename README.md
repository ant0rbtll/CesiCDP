# CesiCDP

Base de projet pour CESIPATH, construite a partir du `livrable_modelisation_1.ipynb`.

## Ce qui est pose sur cette branche

- un generateur d'instances de graphe VRP-CDR dans `src/cesipath/graph_generator.py`
- une modelisation des aretes et des configurations dans `src/cesipath/models.py`
- une couche de calcul des surcouts statiques et dynamiques dans `src/cesipath/dynamic_costs.py`
- une fermeture metrique par Dijkstra dans `src/cesipath/metric_closure.py`
- un simulateur de reseau dynamique dans `src/cesipath/dynamic_network.py`
- des validateurs d'instance et d'etat dynamique dans `src/cesipath/validators.py`
- un contrat d'entree pour les futurs solveurs dans `src/cesipath/solver_input.py`
- une visualisation `matplotlib` dans `src/cesipath/visualization.py`
- un notebook d'explication et d'execution pour chaque module metier dans `notebooks/`

La dynamique actuelle suit une logique gaussienne avec retour vers la moyenne : a chaque changement de ville, les vraies aretes du graphe residuel sont mises a jour autour de leur cout precedent, mais une force de rappel les ramene progressivement vers leur cout statique. Le cout dynamique ne descend jamais sous le cout de base et ne depasse jamais un multiple configurable du cout statique. Une route reelle peut aussi devenir temporairement indisponible, puis redevenir disponible, a condition que le graphe dynamique reste connexe, suffisamment dense et sous un ratio maximal de routes `OFF`. Le graphe complet de resolution est ensuite recalcule avec Dijkstra pour conserver une fermeture metrique.

Le generateur filtre aussi les instances selon un profil automatique de densite par taille de graphe, avec bornes min/max sur le graphe de base et sur le graphe residuel, ainsi qu'un degre moyen residuel minimal pour eviter les cas trop pauvres ou presque complets.

## Demarrage rapide

Depuis la racine du depot :

```python
import sys
from pathlib import Path

sys.path.append(str(Path("src").resolve()))

from cesipath.dynamic_network import DynamicNetworkSimulator
from cesipath.graph_generator import GraphGenerator
from cesipath.models import GraphGenerationConfig
from cesipath.solver_input import build_dynamic_solver_input, build_static_solver_input
from cesipath.visualization import GraphVisualizer

generator = GraphGenerator(
    GraphGenerationConfig(
        node_count=7,
        seed=42,
        auto_density_profile=True,
    )
)
instance = generator.generate()
print(instance.summary())
static_solver_input = build_static_solver_input(instance)

simulator = DynamicNetworkSimulator(instance, seed=42)
snapshot = simulator.initialize_snapshot()
snapshot = simulator.advance(snapshot)
dynamic_solver_input = build_dynamic_solver_input(instance, snapshot)
print(snapshot.completed_costs[0])

visualizer = GraphVisualizer(instance, generator)
session = visualizer.show_dynamic_graph()
```

Les notebooks `notebooks/models.ipynb`, `notebooks/dynamic_costs.ipynb`, `notebooks/metric_closure.ipynb`, `notebooks/validators.ipynb`, `notebooks/graph_generator.ipynb`, `notebooks/dynamic_network.ipynb`, `notebooks/solver_input.ipynb`, `notebooks/visualization.ipynb`, `notebooks/main_visualization.ipynb` et `notebooks/package_exports.ipynb` servent de support d'explication et de validation interactive.

Pour tester la visualisation interactive avec le bouton `->` hors notebook :

```bash
python3 main_visualization.py
```

Par defaut, la dynamique utilise maintenant :

- `dynamic_mean_reversion_strength = 0.35`
- `dynamic_max_multiplier = 1.80`
- `dynamic_forbid_probability = 0.03`
- `dynamic_restore_probability = 0.20`
- `dynamic_max_disabled_ratio = 0.20`

Le notebook reste utile pour explorer le graphe, mais selon le frontend Jupyter le bouton `matplotlib` peut etre moins fiable qu'une fenetre Python classique.
