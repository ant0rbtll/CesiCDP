"""Generation aleatoire d'instances de graphe pour CESIPATH."""

from __future__ import annotations

from math import dist
import random

from .dynamic_network import DynamicNetworkSimulator
from .metric_closure import build_cost_matrix, complete_graph_with_shortest_paths
from .models import (
    DynamicGraphSnapshot,
    EdgeAttributes,
    EdgeStatus,
    GraphGenerationConfig,
    GraphInstance,
)
from .validators import InstanceValidator


class GraphGenerator:
    """Construit le graphe de base, le residuel et la fermeture metrique."""

    def __init__(self, config: GraphGenerationConfig) -> None:
        self.config = config
        self.random = random.Random(config.seed)
        self.validator = InstanceValidator(config)

    def generate(self) -> GraphInstance:
        """Genere une instance valide selon les criteres de qualite."""

        for _ in range(self.config.generation_max_attempts):
            instance = self._build_candidate_instance()
            if self.validator.is_valid(instance):
                return instance

        raise ValueError(
            "Impossible de generer un graphe respectant les bornes de densite "
            f"apres {self.config.generation_max_attempts} tentatives."
        )

    def initialize_dynamic_snapshot(self, instance: GraphInstance) -> DynamicGraphSnapshot:
        """Compatibilite : cree un snapshot dynamique via le simulateur dedie."""

        return DynamicNetworkSimulator(instance, seed=self.config.seed).initialize_snapshot()

    def advance_dynamic_snapshot(
        self,
        instance: GraphInstance,
        snapshot: DynamicGraphSnapshot,
    ) -> DynamicGraphSnapshot:
        """Compatibilite : avance un snapshot dynamique via le simulateur dedie."""

        seed = self.config.seed + snapshot.step + 1 if self.config.seed is not None else None
        return DynamicNetworkSimulator(instance, seed=seed).advance(snapshot)

    def _build_candidate_instance(self) -> GraphInstance:
        coordinates = self._generate_coordinates()
        adjacency = self._build_connected_adjacency(coordinates)
        base_edges = self._build_base_edges(adjacency)
        residual_edges = self._build_residual_edges(base_edges)

        base_costs = self._build_matrix_from_edge_attributes(
            base_edges,
            use_static_cost=False,
            skip_forbidden=False,
        )
        residual_edge_costs = self._edge_costs_from_attributes(
            residual_edges,
            use_static_cost=True,
            skip_forbidden=True,
        )
        residual_costs = build_cost_matrix(self.config.node_count, residual_edge_costs)
        completed_costs, completed_paths = complete_graph_with_shortest_paths(
            self.config.node_count,
            residual_edge_costs,
        )

        return GraphInstance(
            config=self.config,
            coordinates=coordinates,
            base_costs=base_costs,
            base_edges=base_edges,
            residual_costs=residual_costs,
            residual_edges=residual_edges,
            completed_costs=completed_costs,
            completed_paths=completed_paths,
            demands=self._generate_demands(),
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
        target_edges = max(
            node_count - 1,
            int((node_count * (node_count - 1) / 2) * self.config.resolved_edge_density),
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

    @staticmethod
    def _build_base_edges(adjacency: dict[tuple[int, int], float]) -> dict[tuple[int, int], EdgeAttributes]:
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

    @staticmethod
    def _spanning_tree_edges(adjacency: dict[tuple[int, int], float]) -> set[tuple[int, int]]:
        parents: dict[int, int] = {}
        for u, v in adjacency:
            if v not in parents:
                parents[v] = u
        return {(parent, node) for node, parent in parents.items()}

    def _build_matrix_from_edge_attributes(
        self,
        edges: dict[tuple[int, int], EdgeAttributes],
        *,
        use_static_cost: bool,
        skip_forbidden: bool,
    ) -> list[list[float]]:
        edge_costs = self._edge_costs_from_attributes(
            edges,
            use_static_cost=use_static_cost,
            skip_forbidden=skip_forbidden,
        )
        return build_cost_matrix(self.config.node_count, edge_costs)

    @staticmethod
    def _edge_costs_from_attributes(
        edges: dict[tuple[int, int], EdgeAttributes],
        *,
        use_static_cost: bool,
        skip_forbidden: bool,
    ) -> dict[tuple[int, int], float]:
        edge_costs: dict[tuple[int, int], float] = {}
        for key, edge in edges.items():
            if skip_forbidden and edge.status == EdgeStatus.FORBIDDEN:
                continue
            edge_costs[key] = edge.static_cost if use_static_cost else edge.base_cost
        return edge_costs

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
