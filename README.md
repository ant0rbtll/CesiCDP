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
- une feature de reconnaissance de quartier OSM dans `src/cesipath/quartier_graph.py`
- un notebook d'explication et d'execution pour chaque module metier dans `notebooks/`

La dynamique actuelle suit une logique gaussienne avec retour vers la moyenne : a chaque changement de ville, les vraies aretes du graphe residuel sont mises a jour autour de leur cout precedent, mais une force de rappel les ramene progressivement vers leur cout statique. Le cout dynamique ne descend jamais sous le cout de base et ne depasse jamais un multiple configurable du cout statique. Une route reelle peut aussi devenir temporairement indisponible, puis redevenir disponible, a condition que le graphe dynamique reste connexe, suffisamment dense et sous un ratio maximal de routes `OFF`. Le graphe complet de resolution est ensuite recalcule avec Dijkstra pour conserver une fermeture metrique.

Le generateur filtre aussi les instances selon un profil automatique de densite par taille de graphe, avec bornes min/max sur le graphe de base et sur le graphe residuel, ainsi qu'un degre moyen residuel minimal pour eviter les cas trop pauvres ou presque complets.

## Demarrage rapide

Depuis la racine du depot :

```bash
python3 -m pip install -r requirements.txt
```

Si `pip` retourne `externally-managed-environment` (Python Homebrew),
utiliser soit un venv, soit :

```bash
python3 -m pip install --user --break-system-packages -r requirements.txt
```

Puis :

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

Pour lancer l'interface graphique principale (modes `Benchmark CESIPATH`,
`Generation + Visualizer` et `Reconnaissance quartier`) :

```bash
python3 main_gui.py
```

Le mode `Generation + Visualizer` remplace l'ancien lancement separé
`main_visualization.py` et ouvre automatiquement la fenetre interactive
du graphe apres generation.

Le visualizer de generation affiche maintenant une animation de camion sur
le trajet dynamique calcule par GRASP (camion `image/camionG.png` vers la gauche,
`image/camionD.png` vers la droite).

Le mode `Reconnaissance quartier` utilise directement le module interne
`src/cesipath/quartier_graph.py` (plus de dependance a un dossier externe),
affiche le visualizer directement dans l'onglet GUI (pas de popup, pas de PNG),
convertit le graphe OSM en non oriente puis le projette dans le moteur dynamique
CESIPATH (`GraphInstance`): simulation des couts dynamiques, aretes OFF/ON,
recalcul de fermeture metrique et resolution GRASP animee sur fond de carte OSM.

Le graphe OSM complet est conserve pour la topologie (sommets + aretes), tandis que
les clients VRP sont echantillonnes via le parametre GUI `Clients dynamiques`
afin de garder une preuve de concept fluide et representative en quartier reel.

Optimisation de fluidite appliquee sur cet onglet :

- rendu du graphe calcule en thread de fond (UI non bloquee)
- fond de carte toujours actif, avec telechargement des tuiles optimise (parallelisation + cache)
- cache local du basemap entre snapshots pour eviter un re-telechargement a chaque step
- creation du visualizer dynamique dans le thread principal (evite les warnings matplotlib thread)

L'interface est maintenant structuree avec :

- `src/gui/theme.py` : palette, styles et theming global
- `src/gui/components.py` : composants reutilisables (champs labels, boutons, logs, tooltips)
- `src/gui/icons.py` : generation d'icones d'onglets via Pillow (fallback texte si indisponible)
- `src/gui/services.py` : logique metier decouplee de la couche Tkinter
- `src/gui/STYLE_CONVENTIONS.md` : conventions UI/UX et regles de maintenance GUI

Ameliorations UX appliquees :

- systeme de couleur coherent (primaire/accent/succes/erreur)
- disposition aeree avec sections visuelles
- validation live des champs
- logs colores avec indicateurs (`✓`, `✗`, `ℹ`, `⏳`)
- barre de progression et etat running/idle sur chaque onglet
- visualizer quartier imbrique dans la fenetre principale

Par defaut, la dynamique utilise maintenant :

- `dynamic_mean_reversion_strength = 0.35`
- `dynamic_max_multiplier = 1.80`
- `dynamic_forbid_probability = 0.03`
- `dynamic_restore_probability = 0.20`
- `dynamic_max_disabled_ratio = 0.20`

Le notebook reste utile pour explorer le graphe, mais selon le frontend Jupyter le bouton `matplotlib` peut etre moins fiable qu'une fenetre Python classique.
