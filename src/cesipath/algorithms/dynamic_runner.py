"""Execution dynamique d'une tournee VRP-CDR.

Le simulateur fait evoluer les couts et la disponibilite des aretes entre
chaque transition. Un solveur statique (GRASP, SA, tabu, GA) n'est appele
qu'au step 0 pour produire le plan initial.

Strategies supportees :

- ``fixed`` : plan initial fige jusqu'au bout, aucune reaction ;
- ``reopt`` : re-resolution complete (solveur lourd) a chaque retour depot ;
- ``reactive`` : aucune re-resolution lourde apres l'init. A chaque
  transition, une passe de 2-opt reordonne le reste de la sous-tournee
  courante avec la matrice de couts courante ; au retour depot, une
  ``local_search`` (relocate + swap + two_opt) rebat le plan restant.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Literal

from ..dynamic_network import DynamicNetworkSimulator
from ..models import DynamicGraphSnapshot, GraphInstance
from ..solver_input import SolverInput, build_dynamic_solver_input
from .neighborhood import VRPSolution, local_search, two_opt


SolverFn = Callable[..., VRPSolution]
DynamicStrategy = Literal["fixed", "reopt", "reactive"]


@dataclass
class DynamicExecution:
    """Trace d'une execution dynamique complete."""

    traveled_route: list[int]
    realized_cost: float
    planned_cost: float
    step_costs: list[float]
    reoptimizations: int
    solver_time: float
    dijkstra_time: float
    total_steps: int
    depot_replans: int
    reactive_repairs: int


def _restricted_solver_input(
    instance: GraphInstance,
    snapshot: DynamicGraphSnapshot,
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


def _reorder_route_suffix(
    route: list[int],
    route_position: int,
    cost_matrix: list[list[float]],
) -> tuple[list[int], bool]:
    """Applique 2-opt au suffixe [position courante -> depot] et reinjecte.

    Le premier element du suffixe (noeud physique courant) et le dernier
    (depot) sont traites comme bornes fixes par ``two_opt``.
    """

    anchor = route_position - 1
    suffix = route[anchor:]
    if len(suffix) < 4:
        return route, False
    reordered = two_opt(suffix, cost_matrix)
    if reordered == suffix:
        return route, False
    return route[:anchor] + reordered, True


def _adapt_solver_kwargs(
    solver_kwargs: dict[str, Any],
    *,
    remaining_clients_count: int,
    total_clients_count: int,
    adaptive_budget: bool,
) -> dict[str, Any]:
    """Reduit les budgets iterationnels quand il reste peu de clients.

    N'a d'effet que pour les appels au solveur lourd (strategie ``reopt``).
    """

    adapted = dict(solver_kwargs)
    if not adaptive_budget or total_clients_count <= 0:
        return adapted

    ratio = min(1.0, remaining_clients_count / total_clients_count)

    for key in ("max_iterations", "generations", "max_no_improve"):
        value = adapted.get(key)
        if isinstance(value, int) and value > 0:
            adapted[key] = max(1, int(round(value * ratio)))

    population_size = adapted.get("population_size")
    if isinstance(population_size, int) and population_size > 1:
        elitism = adapted.get("elitism", 2)
        if not isinstance(elitism, int):
            elitism = 2
        adapted["population_size"] = max(elitism + 1, int(round(population_size * ratio)), 2)

        tournament_k = adapted.get("tournament_k")
        if isinstance(tournament_k, int) and tournament_k > 0:
            adapted["tournament_k"] = min(tournament_k, adapted["population_size"])

    return adapted


def execute_dynamic(
    instance: GraphInstance,
    simulator: DynamicNetworkSimulator,
    solver_fn: SolverFn,
    *,
    solver_kwargs: dict[str, Any] | None = None,
    reoptimize_at_depot: bool = True,
    strategy: DynamicStrategy | None = None,
    adaptive_budget: bool = False,
) -> DynamicExecution:
    """Execute la tournee dynamique complete.

    - Plan initial calcule au step 0 via ``solver_fn``.
    - Chaque sous-tournee est parcourue etape par etape ; chaque transition
      paie le cout dans le snapshot courant puis ``advance`` le simulateur.
    - La reaction aux changements depend de ``strategy``.

    Le parametre historique ``reoptimize_at_depot`` est conserve pour la
    retrocompatibilite : si ``strategy`` est omis, il choisit entre
    ``fixed`` et ``reopt``.
    """

    solver_kwargs = solver_kwargs or {}
    if strategy is None:
        strategy = "reopt" if reoptimize_at_depot else "fixed"
    if strategy not in {"fixed", "reopt", "reactive"}:
        raise ValueError("strategy doit etre l'une de {'fixed', 'reopt', 'reactive'}")

    depot = instance.depot
    demands = instance.demands
    capacity = instance.config.vehicle_capacity
    total_clients_count = sum(
        1 for node, demand in demands.items() if node != depot and demand > 0
    )

    snapshot = simulator.initialize_snapshot()

    initial_si = build_dynamic_solver_input(instance, snapshot)
    initial_kwargs = _adapt_solver_kwargs(
        solver_kwargs,
        remaining_clients_count=total_clients_count,
        total_clients_count=total_clients_count,
        adaptive_budget=adaptive_budget,
    )
    t0 = time.perf_counter()
    initial_solution = solver_fn(initial_si, **initial_kwargs)
    solver_time = time.perf_counter() - t0
    dijkstra_time = snapshot.shortest_paths_time
    planned_cost = initial_solution.total_cost
    reoptimizations = 1

    remaining_routes: list[list[int]] = [route[:] for route in initial_solution.routes]
    remaining_clients = {c for route in remaining_routes for c in route[1:-1]}

    current = depot
    traveled = [depot]
    step_costs: list[float] = []
    realized = 0.0
    total_steps = 0
    depot_replans = 0
    reactive_repairs = 0

    while remaining_routes:
        current_route = remaining_routes.pop(0)
        route_position = 1

        while route_position < len(current_route):
            if strategy == "reactive":
                t0 = time.perf_counter()
                new_route, changed = _reorder_route_suffix(
                    current_route, route_position, snapshot.completed_costs
                )
                solver_time += time.perf_counter() - t0
                if changed:
                    current_route = new_route
                    reactive_repairs += 1

            next_node = current_route[route_position]
            step_cost = snapshot.completed_costs[current][next_node]
            realized += step_cost
            step_costs.append(step_cost)
            traveled.append(next_node)
            if next_node in remaining_clients:
                remaining_clients.remove(next_node)
            current = next_node
            total_steps += 1
            if remaining_clients or remaining_routes or route_position < len(current_route) - 1:
                snapshot = simulator.advance(snapshot)
                dijkstra_time += snapshot.shortest_paths_time
            route_position += 1

        if not remaining_clients:
            continue

        if strategy == "reopt":
            sub_si = _restricted_solver_input(instance, snapshot, remaining_clients)
            sub_kwargs = _adapt_solver_kwargs(
                solver_kwargs,
                remaining_clients_count=len(remaining_clients),
                total_clients_count=total_clients_count,
                adaptive_budget=adaptive_budget,
            )
            t0 = time.perf_counter()
            sub_solution = solver_fn(sub_si, **sub_kwargs)
            solver_time += time.perf_counter() - t0
            reoptimizations += 1
            remaining_routes = [route[:] for route in sub_solution.routes]
            depot_replans += 1
        elif strategy == "reactive":
            t0 = time.perf_counter()
            remaining_routes = local_search(
                remaining_routes, snapshot.completed_costs, demands, capacity
            )
            remaining_routes = [route[:] for route in remaining_routes]
            solver_time += time.perf_counter() - t0
            depot_replans += 1

    return DynamicExecution(
        traveled_route=traveled,
        realized_cost=round(realized, 2),
        planned_cost=planned_cost,
        step_costs=step_costs,
        reoptimizations=reoptimizations,
        solver_time=round(solver_time, 4),
        dijkstra_time=round(dijkstra_time, 4),
        total_steps=total_steps,
        depot_replans=depot_replans,
        reactive_repairs=reactive_repairs,
    )
