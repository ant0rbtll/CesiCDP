# CesiCDP

Base de projet pour CESIPATH, construite a partir du `livrable_modelisation_1.ipynb`.

## Ce qui est pose sur cette branche

- un generateur d'instances de graphe VRP-CDR dans `src/cesipath/graph_generator.py`
- une modelisation des aretes et des configurations dans `src/cesipath/models.py`
- une couche de calcul des surcouts statiques et dynamiques dans `src/cesipath/dynamic_costs.py`
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

from cesipath.graph_generator import GraphGenerator
from cesipath.models import GraphGenerationConfig
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
snapshot = generator.initialize_dynamic_snapshot(instance)
snapshot = generator.advance_dynamic_snapshot(instance, snapshot)
print(snapshot.completed_costs[0])

visualizer = GraphVisualizer(instance, generator)
session = visualizer.show_dynamic_graph()
```

Les notebooks `notebooks/models.ipynb`, `notebooks/dynamic_costs.ipynb`, `notebooks/graph_generator.ipynb` et `notebooks/visualization.ipynb` servent de support d'explication et de validation interactive.

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
