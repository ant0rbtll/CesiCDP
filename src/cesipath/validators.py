"""Validation des instances et des etats dynamiques."""

from __future__ import annotations

from collections import deque

from .metric_closure import EdgeKey
from .models import EdgeStatus, GraphGenerationConfig, GraphInstance


def density_from_edge_count(node_count: int, edge_count: int) -> float:
    """Calcule la densite d'un graphe non oriente."""

    max_edges = node_count * (node_count - 1) / 2
    if max_edges == 0:
        return 0.0
    return edge_count / max_edges


def average_degree_from_edge_count(node_count: int, edge_count: int) -> float:
    """Calcule le degre moyen d'un graphe non oriente."""

    if node_count == 0:
        return 0.0
    return (2 * edge_count) / node_count


def density_in_bounds(
    density: float,
    minimum: float | None,
    maximum: float | None,
) -> bool:
    """Verifie qu'une densite respecte des bornes optionnelles."""

    if minimum is not None and density < minimum:
        return False
    if maximum is not None and density > maximum:
        return False
    return True


def is_connected(node_count: int, active_edges: set[EdgeKey]) -> bool:
    """Verifie la connexite d'un graphe non oriente."""

    if node_count <= 1:
        return True

    adjacency = {node: set() for node in range(node_count)}
    for u, v in active_edges:
        adjacency[u].add(v)
        adjacency[v].add(u)

    visited = {0}
    queue = deque([0])

    while queue:
        node = queue.popleft()
        for neighbor in adjacency[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return len(visited) == node_count


class InstanceValidator:
    """Valide qu'une instance generee est exploitable et interessante."""

    def __init__(self, config: GraphGenerationConfig) -> None:
        self.config = config

    def is_valid(self, instance: GraphInstance) -> bool:
        """Retourne `True` si l'instance respecte les invariants principaux."""

        return (
            density_in_bounds(
                instance.base_density,
                self.config.resolved_min_base_density,
                self.config.resolved_max_base_density,
            )
            and density_in_bounds(
                instance.residual_density,
                self.config.resolved_min_residual_density,
                self.config.resolved_max_residual_density,
            )
            and instance.residual_average_degree >= self.config.resolved_min_average_residual_degree
            and self.is_residual_graph_connected(instance)
        )

    @staticmethod
    def is_residual_graph_connected(instance: GraphInstance) -> bool:
        """Verifie la connexite du graphe residuel statique."""

        active_edges = {
            key
            for key, edge in instance.residual_edges.items()
            if edge.status != EdgeStatus.FORBIDDEN
        }
        return is_connected(instance.node_count, active_edges)


class DynamicStateValidator:
    """Valide qu'un etat dynamique reste exploitable par les solveurs."""

    def __init__(self, instance: GraphInstance) -> None:
        self.instance = instance

    def can_disable_edge(
        self,
        edge_availability: dict[EdgeKey, bool],
        candidate: EdgeKey,
    ) -> bool:
        """Teste si une arete peut passer `OFF` sans casser les invariants."""

        active_edges = {
            key
            for key, available in edge_availability.items()
            if available and key != candidate
        }
        return self.is_valid_active_edges(active_edges, len(edge_availability))

    def is_valid_active_edges(
        self,
        active_edges: set[EdgeKey],
        total_dynamic_edges: int,
    ) -> bool:
        """Valide connexite, densite, degre moyen et ratio `OFF`."""

        if not is_connected(self.instance.node_count, active_edges):
            return False

        active_edge_count = len(active_edges)
        active_density = density_from_edge_count(self.instance.node_count, active_edge_count)
        if active_density < self.instance.config.resolved_dynamic_min_density:
            return False

        active_average_degree = average_degree_from_edge_count(
            self.instance.node_count,
            active_edge_count,
        )
        if active_average_degree < self.instance.config.resolved_dynamic_min_average_degree:
            return False

        if total_dynamic_edges > 0:
            disabled_ratio = (total_dynamic_edges - active_edge_count) / total_dynamic_edges
            if disabled_ratio > self.instance.config.dynamic_max_disabled_ratio:
                return False

        return True
