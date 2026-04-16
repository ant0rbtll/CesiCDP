"""Contrats d'entree pour les futurs solveurs."""

from __future__ import annotations

from dataclasses import dataclass

from .metric_closure import CostMatrix, PathIndex
from .models import DynamicGraphSnapshot, GraphInstance


@dataclass(frozen=True)
class SolverInput:
    """Donnees minimales qu'un solveur de tournees doit recevoir."""

    cost_matrix: CostMatrix
    depot: int
    demands: dict[int, int]
    vehicle_capacity: int
    shortest_paths: PathIndex
    source: str
    dynamic_step: int | None = None


def build_static_solver_input(instance: GraphInstance) -> SolverInput:
    """Construit l'entree solveur pour l'instance statique."""

    return SolverInput(
        cost_matrix=instance.completed_costs,
        depot=instance.depot,
        demands=instance.demands,
        vehicle_capacity=instance.config.vehicle_capacity,
        shortest_paths=instance.completed_paths,
        source="static",
    )


def build_dynamic_solver_input(
    instance: GraphInstance,
    snapshot: DynamicGraphSnapshot,
) -> SolverInput:
    """Construit l'entree solveur pour un etat dynamique donne."""

    return SolverInput(
        cost_matrix=snapshot.completed_costs,
        depot=instance.depot,
        demands=instance.demands,
        vehicle_capacity=instance.config.vehicle_capacity,
        shortest_paths=snapshot.completed_paths,
        source="dynamic",
        dynamic_step=snapshot.step,
    )
