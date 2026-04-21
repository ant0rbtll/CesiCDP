"""Exécution dynamique d'une tournée VRP-CDR.

Le simulateur fait evoluer les couts et la disponibilite des aretes entre
chaque transition. Un solveur statique (GRASP, SA, tabu, GA) est appele
ponctuellement sur le reste des clients afin de reagir aux changements.

Strategie de base : un seul vehicule execute les sous-tournees en sequence.
A chaque retour au depot, on re-resout le probleme sur les clients restants
avec la matrice de couts courante. Entre deux depots, on suit la sous-tournee
courante mais on paie les couts dynamiques reels.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from ..dynamic_network import DynamicNetworkSimulator
from ..models import GraphInstance
from ..solver_input import SolverInput, build_dynamic_solver_input
from .neighborhood import VRPSolution


SolverFn = Callable[..., VRPSolution]


@dataclass
class DynamicExecution:
    """Trace d'une execution dynamique complete."""

    traveled_route: list[int]
    realized_cost: float
    planned_cost: float
    step_costs: list[float]
    reoptimizations: int
    solver_time: float
    total_steps: int


def _restricted_solver_input(
    instance: GraphInstance,
    snapshot,
    remaining_clients: set[int],
) -> SolverInput:
    """SolverInput avec demandes nulles pour les clients deja visites.

    Les solveurs filtrent les clients avec ``demand > 0``, donc mettre
    les clients visites a 0 les exclut sans modifier la matrice de couts.
    """

    demands = {
        node: (instance.demands[node] if node in remaining_clients or node == instance.depot else 0)
        for node in instance.demands
    }
    return SolverInput(
        cost_matrix=snapshot.completed_costs,
        depot=instance.depot,
        demands=demands,
        vehicle_capacity=instance.config.vehicle_capacity,
        shortest_paths=snapshot.completed_paths,
        source="dynamic",
        dynamic_step=snapshot.step,
    )


def execute_dynamic(
    instance: GraphInstance,
    simulator: DynamicNetworkSimulator,
    solver_fn: SolverFn,
    *,
    solver_kwargs: dict[str, Any] | None = None,
    reoptimize_at_depot: bool = True,
) -> DynamicExecution:
    """Execute la tournee dynamique complete.

    - Plan initial calcule au step 0 via ``solver_fn``.
    - Chaque sous-tournee est parcourue etape par etape ; chaque transition
      paie le cout dans le snapshot courant puis ``advance`` le simulateur.
    - Si ``reoptimize_at_depot`` est vrai, on re-resout le reste a chaque
      retour au depot avec la matrice de couts a jour. Sinon on suit le
      plan initial jusqu'au bout (strategie plan fige).
    """

    solver_kwargs = solver_kwargs or {}
    depot = instance.depot

    snapshot = simulator.initialize_snapshot()

    initial_si = build_dynamic_solver_input(instance, snapshot)
    t0 = time.perf_counter()
    initial_solution = solver_fn(initial_si, **solver_kwargs)
    solver_time = time.perf_counter() - t0
    planned_cost = initial_solution.total_cost
    reoptimizations = 1

    remaining_routes: list[list[int]] = [route[:] for route in initial_solution.routes]
    remaining_clients = {
        c for route in remaining_routes for c in route[1:-1]
    }

    current = depot
    traveled = [depot]
    step_costs: list[float] = []
    realized = 0.0
    total_steps = 0

    while remaining_routes:
        current_route = remaining_routes.pop(0)
        for i in range(1, len(current_route)):
            next_node = current_route[i]
            step_cost = snapshot.completed_costs[current][next_node]
            realized += step_cost
            step_costs.append(step_cost)
            traveled.append(next_node)
            if next_node in remaining_clients:
                remaining_clients.remove(next_node)
            current = next_node
            total_steps += 1
            if remaining_clients or remaining_routes or i < len(current_route) - 1:
                snapshot = simulator.advance(snapshot)

        if remaining_clients and reoptimize_at_depot:
            sub_si = _restricted_solver_input(instance, snapshot, remaining_clients)
            t0 = time.perf_counter()
            sub_solution = solver_fn(sub_si, **solver_kwargs)
            solver_time += time.perf_counter() - t0
            reoptimizations += 1
            remaining_routes = [route[:] for route in sub_solution.routes]

    return DynamicExecution(
        traveled_route=traveled,
        realized_cost=round(realized, 2),
        planned_cost=planned_cost,
        step_costs=step_costs,
        reoptimizations=reoptimizations,
        solver_time=round(solver_time, 4),
        total_steps=total_steps,
    )
