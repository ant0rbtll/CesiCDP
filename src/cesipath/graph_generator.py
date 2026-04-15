"""Generation d'instances de graphe pour CESIPATH."""

from __future__ import annotations

import heapq
from collections import deque
from math import dist
import random

from .dynamic_costs import initialize_dynamic_edge_costs, sample_dynamic_edge_cost
from .models import (
    DynamicGraphSnapshot,
    EdgeAttributes,
    EdgeStatus,
    GraphGenerationConfig,
    GraphInstance,
)


class GraphGenerator:
    """Construit un graphe connexe, ses contraintes et sa completion."""

    def __init__(self, config: GraphGenerationConfig) -> None:
        self.config = config
        self.random = random.Random(config.seed)

    def generate(self) -> GraphInstance:
        for _ in range(self.config.generation_max_attempts):
            coordinates = self._generate_coordinates()
            adjacency = self._build_connected_adjacency(coordinates)
            base_edges = self._build_base_edges(adjacency)
            residual_edges = self._build_residual_edges(base_edges)
            base_costs = self._build_cost_matrix(base_edges, use_static_cost=False, skip_forbidden=False)
            residual_costs = self._build_cost_matrix(residual_edges, use_static_cost=True, skip_forbidden=True)
            completed_costs = self._complete_graph_with_dijkstra(residual_edges)
            demands = self._generate_demands()

            instance = GraphInstance(
                config=self.config,
                coordinates=coordinates,
                base_costs=base_costs,
                base_edges=base_edges,
                residual_costs=residual_costs,
                residual_edges=residual_edges,
                completed_costs=completed_costs,
                demands=demands,
            )
            if self._instance_is_interesting(instance):
                return instance

        raise ValueError(
            "Impossible de generer un graphe respectant les bornes de densite "
            f"apres {self.config.generation_max_attempts} tentatives."
        )

    def initialize_dynamic_snapshot(self, instance: GraphInstance) -> DynamicGraphSnapshot:
        """Cree l'etat dynamique initial a partir du graphe residuel statique."""

        edge_costs = initialize_dynamic_edge_costs(instance.residual_edges)
        edge_availability = {key: True for key in edge_costs}
        active_edge_costs = self._active_edge_costs(edge_costs, edge_availability)
        residual_costs = self._build_cost_matrix_from_weights(active_edge_costs)
        completed_costs = self._complete_graph_from_weights(active_edge_costs)
        return DynamicGraphSnapshot(
            step=0,
            edge_costs=edge_costs,
            edge_availability=edge_availability,
            residual_costs=residual_costs,
            completed_costs=completed_costs,
        )

    def advance_dynamic_snapshot(
        self,
        instance: GraphInstance,
        snapshot: DynamicGraphSnapshot,
    ) -> DynamicGraphSnapshot:
        """Fait evoluer toutes les vraies aretes puis recalcule Dijkstra."""

        edge_costs = dict(snapshot.edge_costs)
        edge_availability = dict(snapshot.edge_availability)

        for key, edge in instance.residual_edges.items():
            if edge.static_cost == float("inf"):
                continue

            currently_available = edge_availability.get(key, True)
            if currently_available:
                wants_to_forbid = self.random.random() < instance.config.dynamic_forbid_probability
                if wants_to_forbid and self._can_disable_edge(instance, edge_availability, key):
                    edge_availability[key] = False
            else:
                wants_to_restore = self.random.random() < instance.config.dynamic_restore_probability
                if wants_to_restore:
                    edge_availability[key] = True

            if edge_availability[key]:
                edge_costs[key] = sample_dynamic_edge_cost(
                    edge,
                    previous_cost=edge_costs.get(key),
                    rng=self.random,
                    sigma=instance.config.dynamic_sigma,
                    mean_reversion_strength=instance.config.dynamic_mean_reversion_strength,
                    max_multiplier=instance.config.dynamic_max_multiplier,
                )

        active_edge_costs = self._active_edge_costs(edge_costs, edge_availability)
        residual_costs = self._build_cost_matrix_from_weights(active_edge_costs)
        completed_costs = self._complete_graph_from_weights(active_edge_costs)
        return DynamicGraphSnapshot(
            step=snapshot.step + 1,
            edge_costs=edge_costs,
            edge_availability=edge_availability,
            residual_costs=residual_costs,
            completed_costs=completed_costs,
        )

    def _generate_coordinates(self) -> dict[int, tuple[float, float]]:
        return {
            node: (
                round(self.random.uniform(0, self.config.width), 2),
                round(self.random.uniform(0, self.config.height), 2),
            )
            for node in range(self.config.node_count)
        }

    def _build_connected_adjacency(
        self,
        coordinates: dict[int, tuple[float, float]],
    ) -> dict[tuple[int, int], float]:
        node_count = self.config.node_count
        target_density = self.config.resolved_edge_density
        target_edges = max(
            node_count - 1,
            int((node_count * (node_count - 1) / 2) * target_density),
        )
        adjacency: dict[tuple[int, int], float] = {}

        for node in range(1, node_count):
            parent = self.random.randrange(0, node)
            adjacency[(parent, node)] = self._distance(coordinates, parent, node)

        all_pairs = [
            (u, v)
            for u in range(node_count)
            for v in range(u + 1, node_count)
            if (u, v) not in adjacency
        ]
        self.random.shuffle(all_pairs)

        for u, v in all_pairs:
            if len(adjacency) >= target_edges:
                break
            adjacency[(u, v)] = self._distance(coordinates, u, v)

        return adjacency

    def _instance_is_interesting(self, instance: GraphInstance) -> bool:
        return (
            self._density_in_bounds(
                instance.base_density,
                self.config.resolved_min_base_density,
                self.config.resolved_max_base_density,
            )
            and self._density_in_bounds(
                instance.residual_density,
                self.config.resolved_min_residual_density,
                self.config.resolved_max_residual_density,
            )
            and instance.residual_average_degree >= self.config.resolved_min_average_residual_degree
            and self._is_residual_graph_connected(instance)
        )

    def _build_base_edges(self, adjacency: dict[tuple[int, int], float]) -> dict[tuple[int, int], EdgeAttributes]:
        return {key: EdgeAttributes(base_cost=cost) for key, cost in adjacency.items()}

    def _build_residual_edges(
        self,
        base_edges: dict[tuple[int, int], EdgeAttributes],
    ) -> dict[tuple[int, int], EdgeAttributes]:
        adjacency = {key: edge.base_cost for key, edge in base_edges.items()}
        protected_edges = self._spanning_tree_edges(adjacency)
        residual_edges: dict[tuple[int, int], EdgeAttributes] = {}

        for key, edge in base_edges.items():
            cost = edge.base_cost
            if key in protected_edges:
                residual_edges[key] = EdgeAttributes(base_cost=cost)
                continue

            draw = self.random.random()
            if draw < self.config.forbidden_rate:
                residual_edges[key] = EdgeAttributes(base_cost=cost, status=EdgeStatus.FORBIDDEN)
                continue

            surcharge_threshold = self.config.forbidden_rate + self.config.surcharge_rate
            if draw < surcharge_threshold:
                surcharge = round(
                    self.random.uniform(self.config.surcharge_min, self.config.surcharge_max),
                    2,
                )
                residual_edges[key] = EdgeAttributes(
                    base_cost=cost,
                    status=EdgeStatus.SURCHARGED,
                    static_surcharge=surcharge,
                )
                continue

            residual_edges[key] = EdgeAttributes(base_cost=cost)

        return residual_edges

    def _spanning_tree_edges(self, adjacency: dict[tuple[int, int], float]) -> set[tuple[int, int]]:
        parents: dict[int, int] = {}
        for u, v in adjacency:
            if v not in parents:
                parents[v] = u
        return {(parent, node) for node, parent in parents.items()}

    def _build_cost_matrix(
        self,
        edges: dict[tuple[int, int], EdgeAttributes],
        *,
        use_static_cost: bool,
        skip_forbidden: bool,
    ) -> list[list[float]]:
        size = self.config.node_count
        matrix = [[0.0 for _ in range(size)] for _ in range(size)]

        for (u, v), edge in edges.items():
            if skip_forbidden and edge.status == EdgeStatus.FORBIDDEN:
                continue
            cost = edge.static_cost if use_static_cost else edge.base_cost
            matrix[u][v] = cost
            matrix[v][u] = cost

        return matrix

    def _complete_graph_with_dijkstra(self, edges: dict[tuple[int, int], EdgeAttributes]) -> list[list[float]]:
        weights = {
            key: edge.static_cost
            for key, edge in edges.items()
            if edge.static_cost != float("inf")
        }
        return self._complete_graph_from_weights(weights)

    def _complete_graph_from_weights(
        self,
        edge_costs: dict[tuple[int, int], float],
    ) -> list[list[float]]:
        size = self.config.node_count
        matrix = [[0.0 for _ in range(size)] for _ in range(size)]
        neighbors = self._neighbor_map_from_weights(edge_costs)

        for source in range(size):
            distances = self._dijkstra(source, neighbors)
            for target, cost in enumerate(distances):
                matrix[source][target] = round(cost, 2)

        return matrix

    def _dijkstra(
        self,
        source: int,
        neighbors: dict[int, list[tuple[int, float]]],
    ) -> list[float]:
        size = self.config.node_count
        distances = [float("inf")] * size
        distances[source] = 0.0
        queue: list[tuple[float, int]] = [(0.0, source)]

        while queue:
            current_cost, node = heapq.heappop(queue)
            if current_cost > distances[node]:
                continue

            for neighbor, edge_cost in neighbors[node]:
                candidate = current_cost + edge_cost
                if candidate < distances[neighbor]:
                    distances[neighbor] = candidate
                    heapq.heappush(queue, (candidate, neighbor))

        return distances

    def _neighbor_map_from_weights(
        self,
        edge_costs: dict[tuple[int, int], float],
    ) -> dict[int, list[tuple[int, float]]]:
        neighbors = {node: [] for node in range(self.config.node_count)}

        for (u, v), cost in edge_costs.items():
            neighbors[u].append((v, cost))
            neighbors[v].append((u, cost))

        return neighbors

    def _build_cost_matrix_from_weights(
        self,
        edge_costs: dict[tuple[int, int], float],
    ) -> list[list[float]]:
        size = self.config.node_count
        matrix = [[0.0 for _ in range(size)] for _ in range(size)]

        for (u, v), cost in edge_costs.items():
            matrix[u][v] = round(cost, 2)
            matrix[v][u] = round(cost, 2)

        return matrix

    @staticmethod
    def _active_edge_costs(
        edge_costs: dict[tuple[int, int], float],
        edge_availability: dict[tuple[int, int], bool],
    ) -> dict[tuple[int, int], float]:
        return {
            key: cost
            for key, cost in edge_costs.items()
            if edge_availability.get(key, False)
        }

    def _can_disable_edge(
        self,
        instance: GraphInstance,
        edge_availability: dict[tuple[int, int], bool],
        candidate: tuple[int, int],
    ) -> bool:
        active_edges = {
            key
            for key, available in edge_availability.items()
            if available and key != candidate
        }
        return self._dynamic_state_is_valid(instance, active_edges, len(edge_availability))

    def _dynamic_state_is_valid(
        self,
        instance: GraphInstance,
        active_edges: set[tuple[int, int]],
        total_dynamic_edges: int,
    ) -> bool:
        if not self._is_connected(instance.node_count, active_edges):
            return False

        active_edge_count = len(active_edges)
        active_density = self._density_from_edge_count(instance.node_count, active_edge_count)
        if active_density < instance.config.resolved_dynamic_min_density:
            return False

        active_average_degree = self._average_degree_from_edge_count(instance.node_count, active_edge_count)
        if active_average_degree < instance.config.resolved_dynamic_min_average_degree:
            return False

        if total_dynamic_edges > 0:
            disabled_ratio = (total_dynamic_edges - active_edge_count) / total_dynamic_edges
            if disabled_ratio > instance.config.dynamic_max_disabled_ratio:
                return False

        return True

    def _is_residual_graph_connected(self, instance: GraphInstance) -> bool:
        active_edges = {
            key
            for key, edge in instance.residual_edges.items()
            if edge.status != EdgeStatus.FORBIDDEN
        }
        return self._is_connected(instance.node_count, active_edges)

    @staticmethod
    def _density_in_bounds(
        density: float,
        minimum: float | None,
        maximum: float | None,
    ) -> bool:
        if minimum is not None and density < minimum:
            return False
        if maximum is not None and density > maximum:
            return False
        return True

    @staticmethod
    def _is_connected(node_count: int, active_edges: set[tuple[int, int]]) -> bool:
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

    @staticmethod
    def _density_from_edge_count(node_count: int, edge_count: int) -> float:
        max_edges = node_count * (node_count - 1) / 2
        if max_edges == 0:
            return 0.0
        return edge_count / max_edges

    @staticmethod
    def _average_degree_from_edge_count(node_count: int, edge_count: int) -> float:
        if node_count == 0:
            return 0.0
        return (2 * edge_count) / node_count

    def _generate_demands(self) -> dict[int, int]:
        uniform_demand = self.random.randint(self.config.demand_min, self.config.demand_max)
        demands = {node: uniform_demand for node in range(self.config.node_count)}
        demands[self.config.depot] = 0
        return demands

    @staticmethod
    def _distance(
        coordinates: dict[int, tuple[float, float]],
        u: int,
        v: int,
    ) -> float:
        return round(dist(coordinates[u], coordinates[v]), 2)
