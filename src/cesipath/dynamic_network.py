"""Simulation dynamique du reseau routier."""

from __future__ import annotations

import random

from .dynamic_costs import initialize_dynamic_edge_costs, sample_dynamic_edge_cost
from .metric_closure import EdgeKey, build_cost_matrix, complete_graph_with_shortest_paths
from .models import DynamicGraphSnapshot, GraphInstance
from .validators import DynamicStateValidator


class DynamicNetworkSimulator:
    """Fait evoluer les vraies aretes puis recalcule la fermeture metrique."""

    def __init__(self, instance: GraphInstance, seed: int | None = None) -> None:
        self.instance = instance
        self.random = random.Random(seed)
        self.validator = DynamicStateValidator(instance)

    def initialize_snapshot(self) -> DynamicGraphSnapshot:
        """Cree l'etat dynamique initial a partir du graphe residuel."""

        edge_costs = initialize_dynamic_edge_costs(self.instance.residual_edges)
        edge_availability = {key: True for key in edge_costs}
        return self._build_snapshot(step=0, edge_costs=edge_costs, edge_availability=edge_availability)

    def advance(self, snapshot: DynamicGraphSnapshot) -> DynamicGraphSnapshot:
        """Avance le reseau d'un tour dynamique."""

        edge_costs = dict(snapshot.edge_costs)
        edge_availability = dict(snapshot.edge_availability)

        for key, edge in self.instance.residual_edges.items():
            if edge.static_cost == float("inf"):
                continue

            if edge_availability.get(key, True):
                wants_to_forbid = self.random.random() < self.instance.config.dynamic_forbid_probability
                if wants_to_forbid and self.validator.can_disable_edge(edge_availability, key):
                    edge_availability[key] = False
            else:
                wants_to_restore = self.random.random() < self.instance.config.dynamic_restore_probability
                if wants_to_restore:
                    edge_availability[key] = True

            if edge_availability[key]:
                edge_costs[key] = sample_dynamic_edge_cost(
                    edge,
                    previous_cost=edge_costs.get(key),
                    rng=self.random,
                    sigma=self.instance.config.dynamic_sigma,
                    mean_reversion_strength=self.instance.config.dynamic_mean_reversion_strength,
                    max_multiplier=self.instance.config.dynamic_max_multiplier,
                )

        return self._build_snapshot(
            step=snapshot.step + 1,
            edge_costs=edge_costs,
            edge_availability=edge_availability,
        )

    def _build_snapshot(
        self,
        *,
        step: int,
        edge_costs: dict[EdgeKey, float],
        edge_availability: dict[EdgeKey, bool],
    ) -> DynamicGraphSnapshot:
        active_edge_costs = active_edge_costs_from_availability(edge_costs, edge_availability)
        residual_costs = build_cost_matrix(self.instance.node_count, active_edge_costs)
        completed_costs, completed_paths = complete_graph_with_shortest_paths(
            self.instance.node_count,
            active_edge_costs,
        )
        return DynamicGraphSnapshot(
            step=step,
            edge_costs=edge_costs,
            edge_availability=edge_availability,
            residual_costs=residual_costs,
            completed_costs=completed_costs,
            completed_paths=completed_paths,
        )


def active_edge_costs_from_availability(
    edge_costs: dict[EdgeKey, float],
    edge_availability: dict[EdgeKey, bool],
) -> dict[EdgeKey, float]:
    """Filtre les aretes actuellement disponibles."""

    return {
        key: cost
        for key, cost in edge_costs.items()
        if edge_availability.get(key, False)
    }
