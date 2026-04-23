"""Structures de donnees du projet CESIPATH."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import ceil


class EdgeStatus(str, Enum):
    """Statut statique d'une arete."""

    FREE = "libre"
    SURCHARGED = "surcout"
    FORBIDDEN = "interdit"


@dataclass(frozen=True)
class EdgeAttributes:
    """Description statique d'une arete non orientee."""

    base_cost: float
    status: EdgeStatus = EdgeStatus.FREE
    static_surcharge: float = 0.0

    @property
    def static_cost(self) -> float:
        if self.status == EdgeStatus.FORBIDDEN:
            return float("inf")
        return round(self.base_cost * (1.0 + self.static_surcharge), 2)


@dataclass(frozen=True)
class GraphGenerationConfig:
    """Parametres utilises pour construire une instance."""

    node_count: int
    depot: int = 0
    seed: int | None = 42
    width: int = 100
    height: int = 100
    edge_density: float | None = None
    auto_density_profile: bool = True
    min_base_density: float | None = None
    max_base_density: float | None = None
    min_residual_density: float | None = None
    max_residual_density: float | None = None
    min_average_residual_degree: float | None = None
    generation_max_attempts: int = 100
    forbidden_rate: float = 0.10
    surcharge_rate: float = 0.20
    surcharge_min: float = 0.10
    surcharge_max: float = 0.50
    demand_min: int = 1
    demand_max: int = 20
    vehicle_capacity: int = 40
    dynamic_sigma: float = 0.12
    dynamic_mean_reversion_strength: float = 0.35
    dynamic_max_multiplier: float = 1.80
    dynamic_forbid_probability: float = 0.03
    dynamic_restore_probability: float = 0.20
    dynamic_min_density: float | None = None
    dynamic_min_average_degree: float | None = None
    dynamic_max_disabled_ratio: float = 0.20

    def __post_init__(self) -> None:
        if self.node_count < 2:
            raise ValueError("node_count doit etre >= 2")
        if self.edge_density is not None and not 0.0 <= self.edge_density <= 1.0:
            raise ValueError("edge_density doit etre entre 0 et 1")
        self._validate_density_bound("min_base_density", self.min_base_density)
        self._validate_density_bound("max_base_density", self.max_base_density)
        self._validate_density_bound("min_residual_density", self.min_residual_density)
        self._validate_density_bound("max_residual_density", self.max_residual_density)
        self._validate_density_interval("base", self.min_base_density, self.max_base_density)
        self._validate_density_interval("residuelle", self.min_residual_density, self.max_residual_density)
        if not 0.0 <= self.forbidden_rate <= 1.0:
            raise ValueError("forbidden_rate doit etre entre 0 et 1")
        if not 0.0 <= self.surcharge_rate <= 1.0:
            raise ValueError("surcharge_rate doit etre entre 0 et 1")
        if self.surcharge_min > self.surcharge_max:
            raise ValueError("surcharge_min doit etre <= surcharge_max")
        if self.vehicle_capacity <= 0:
            raise ValueError("vehicle_capacity doit etre > 0")
        if self.dynamic_sigma < 0:
            raise ValueError("dynamic_sigma doit etre >= 0")
        if not 0.0 <= self.dynamic_mean_reversion_strength <= 1.0:
            raise ValueError("dynamic_mean_reversion_strength doit etre entre 0 et 1")
        if self.dynamic_max_multiplier < 1.0:
            raise ValueError("dynamic_max_multiplier doit etre >= 1")
        if not 0.0 <= self.dynamic_forbid_probability <= 1.0:
            raise ValueError("dynamic_forbid_probability doit etre entre 0 et 1")
        if not 0.0 <= self.dynamic_restore_probability <= 1.0:
            raise ValueError("dynamic_restore_probability doit etre entre 0 et 1")
        self._validate_density_bound("dynamic_min_density", self.dynamic_min_density)
        if self.dynamic_min_average_degree is not None and self.dynamic_min_average_degree < 0:
            raise ValueError("dynamic_min_average_degree doit etre >= 0")
        if not 0.0 <= self.dynamic_max_disabled_ratio <= 1.0:
            raise ValueError("dynamic_max_disabled_ratio doit etre entre 0 et 1")
        if self.generation_max_attempts <= 0:
            raise ValueError("generation_max_attempts doit etre > 0")
        if self.min_average_residual_degree is not None and self.min_average_residual_degree < 0:
            raise ValueError("min_average_residual_degree doit etre >= 0")
        if self.depot < 0 or self.depot >= self.node_count:
            raise ValueError("depot hors bornes")
        self._validate_density_interval(
            "base resolue",
            self.resolved_min_base_density,
            self.resolved_max_base_density,
        )
        self._validate_density_interval(
            "residuelle resolue",
            self.resolved_min_residual_density,
            self.resolved_max_residual_density,
        )

    @staticmethod
    def _validate_density_bound(name: str, value: float | None) -> None:
        if value is not None and not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} doit etre entre 0 et 1")

    @staticmethod
    def _validate_density_interval(
        label: str,
        minimum: float | None,
        maximum: float | None,
    ) -> None:
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError(f"borne min {label} > borne max {label}")

    @staticmethod
    def _recommended_density_profile(node_count: int) -> dict[str, float]:
        if node_count <= 10:
            return {
                "min_base_density": 0.45,
                "max_base_density": 0.75,
                "min_residual_density": 0.35,
                "max_residual_density": 0.65,
            }
        if node_count <= 25:
            return {
                "min_base_density": 0.30,
                "max_base_density": 0.60,
                "min_residual_density": 0.22,
                "max_residual_density": 0.50,
            }
        return {
            "min_base_density": 0.18,
            "max_base_density": 0.40,
            "min_residual_density": 0.12,
            "max_residual_density": 0.30,
        }

    @property
    def resolved_min_base_density(self) -> float | None:
        if self.min_base_density is not None:
            return self.min_base_density
        if self.auto_density_profile:
            return self._recommended_density_profile(self.node_count)["min_base_density"]
        return None

    @property
    def resolved_max_base_density(self) -> float | None:
        if self.max_base_density is not None:
            return self.max_base_density
        if self.auto_density_profile:
            return self._recommended_density_profile(self.node_count)["max_base_density"]
        return None

    @property
    def resolved_min_residual_density(self) -> float | None:
        if self.min_residual_density is not None:
            return self.min_residual_density
        if self.auto_density_profile:
            return self._recommended_density_profile(self.node_count)["min_residual_density"]
        return None

    @property
    def resolved_max_residual_density(self) -> float | None:
        if self.max_residual_density is not None:
            return self.max_residual_density
        if self.auto_density_profile:
            return self._recommended_density_profile(self.node_count)["max_residual_density"]
        return None

    @property
    def resolved_edge_density(self) -> float:
        if self.edge_density is not None:
            return self.edge_density
        minimum = self.resolved_min_base_density
        maximum = self.resolved_max_base_density
        if minimum is not None and maximum is not None:
            return round((minimum + maximum) / 2, 4)
        return 0.45

    @property
    def resolved_min_average_residual_degree(self) -> float:
        if self.min_average_residual_degree is not None:
            return self.min_average_residual_degree
        residual_min_density = self.resolved_min_residual_density
        if residual_min_density is None:
            return 2.0
        return round(max(2.0, residual_min_density * (self.node_count - 1) * 0.85), 2)

    @property
    def resolved_dynamic_min_density(self) -> float:
        if self.dynamic_min_density is not None:
            return self.dynamic_min_density
        residual_min_density = self.resolved_min_residual_density
        if residual_min_density is None:
            return 0.10
        return round(max(0.10, residual_min_density * 0.85), 4)

    @property
    def resolved_dynamic_min_average_degree(self) -> float:
        if self.dynamic_min_average_degree is not None:
            return self.dynamic_min_average_degree
        return round(max(2.0, self.resolved_min_average_residual_degree * 0.85), 2)


@dataclass
class GraphInstance:
    """Instance exploitable du probleme VRP-CDR."""

    config: GraphGenerationConfig
    coordinates: dict[int, tuple[float, float]]
    base_costs: list[list[float]]
    base_edges: dict[tuple[int, int], EdgeAttributes]
    residual_costs: list[list[float]]
    residual_edges: dict[tuple[int, int], EdgeAttributes]
    completed_costs: list[list[float]]
    completed_paths: dict[tuple[int, int], list[int]]
    demands: dict[int, int]

    @property
    def node_count(self) -> int:
        return self.config.node_count

    @property
    def depot(self) -> int:
        return self.config.depot

    @property
    def uniform_demand(self) -> int:
        return next(value for node, value in self.demands.items() if node != self.depot)

    @property
    def minimum_route_count(self) -> int:
        total_demand = sum(self.demands.values())
        return ceil(total_demand / self.config.vehicle_capacity)

    @property
    def base_density(self) -> float:
        return self._density_from_edge_count(len(self.base_edges))

    @property
    def residual_density(self) -> float:
        active_residual_edges = sum(
            1
            for edge in self.residual_edges.values()
            if edge.status != EdgeStatus.FORBIDDEN
        )
        return self._density_from_edge_count(active_residual_edges)

    @property
    def residual_average_degree(self) -> float:
        active_residual_edges = sum(
            1
            for edge in self.residual_edges.values()
            if edge.status != EdgeStatus.FORBIDDEN
        )
        return self._average_degree_from_edge_count(active_residual_edges)

    def edge(self, u: int, v: int) -> EdgeAttributes:
        key = (min(u, v), max(u, v))
        return self.residual_edges[key]

    def summary(self) -> dict[str, int | float]:
        base_direct = sum(1 for edge in self.base_edges.values() if edge.base_cost > 0)
        residual_direct = sum(1 for edge in self.residual_edges.values() if edge.base_cost > 0)
        forbidden = sum(1 for edge in self.residual_edges.values() if edge.status == EdgeStatus.FORBIDDEN)
        surcharged = sum(1 for edge in self.residual_edges.values() if edge.status == EdgeStatus.SURCHARGED)
        return {
            "node_count": self.node_count,
            "base_edge_count": base_direct,
            "residual_edge_count": residual_direct - forbidden,
            "base_density": round(self.base_density, 4),
            "residual_density": round(self.residual_density, 4),
            "residual_average_degree": round(self.residual_average_degree, 4),
            "forbidden_edge_count": forbidden,
            "surcharged_edge_count": surcharged,
            "uniform_demand": self.uniform_demand,
            "vehicle_capacity": self.config.vehicle_capacity,
            "edge_density_target": self.config.resolved_edge_density,
            "min_base_density": self.config.resolved_min_base_density,
            "max_base_density": self.config.resolved_max_base_density,
            "min_residual_density": self.config.resolved_min_residual_density,
            "max_residual_density": self.config.resolved_max_residual_density,
            "min_average_residual_degree": self.config.resolved_min_average_residual_degree,
            "dynamic_sigma": self.config.dynamic_sigma,
            "dynamic_mean_reversion_strength": self.config.dynamic_mean_reversion_strength,
            "dynamic_max_multiplier": self.config.dynamic_max_multiplier,
            "dynamic_forbid_probability": self.config.dynamic_forbid_probability,
            "dynamic_restore_probability": self.config.dynamic_restore_probability,
            "dynamic_min_density": self.config.resolved_dynamic_min_density,
            "dynamic_min_average_degree": self.config.resolved_dynamic_min_average_degree,
            "dynamic_max_disabled_ratio": self.config.dynamic_max_disabled_ratio,
            "minimum_route_count": self.minimum_route_count,
        }

    def _density_from_edge_count(self, edge_count: int) -> float:
        max_edges = self.node_count * (self.node_count - 1) / 2
        if max_edges == 0:
            return 0.0
        return edge_count / max_edges

    def _average_degree_from_edge_count(self, edge_count: int) -> float:
        if self.node_count == 0:
            return 0.0
        return (2 * edge_count) / self.node_count


@dataclass
class DynamicGraphSnapshot:
    """Etat dynamique courant du reseau routier."""

    step: int
    edge_costs: dict[tuple[int, int], float]
    edge_availability: dict[tuple[int, int], bool]
    residual_costs: list[list[float]]
    completed_costs: list[list[float]]
    completed_paths: dict[tuple[int, int], list[int]]
    shortest_paths_time: float = 0.0

    def edge_cost(self, u: int, v: int) -> float:
        key = (min(u, v), max(u, v))
        return self.edge_costs[key]

    def is_available(self, u: int, v: int) -> bool:
        key = (min(u, v), max(u, v))
        return self.edge_availability.get(key, False)

    @property
    def active_edge_count(self) -> int:
        return sum(1 for available in self.edge_availability.values() if available)
