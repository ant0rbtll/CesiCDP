"""GRASP (Greedy Randomized Adaptive Search Procedure) pour le VRP-CDR."""

from __future__ import annotations

import random

from ..solver_input import SolverInput
from .neighborhood import VRPSolution, local_search, total_cost


def greedy_randomized_construction(
    solver_input: SolverInput,
    rcl_alpha: float,
    rng: random.Random,
) -> list[list[int]]:
    """Construit une solution admissible par glouton randomise (RCL).

    A chaque etape, la liste restreinte des candidats (RCL) regroupe les
    ``rcl_alpha`` meilleurs clients joignables depuis la position courante
    sous contrainte de capacite residuelle. Le prochain client est tire
    uniformement dans cette liste.
    """

    depot = solver_input.depot
    demands = solver_input.demands
    capacity = solver_input.vehicle_capacity
    cost_matrix = solver_input.cost_matrix

    unvisited = {
        node for node, demand in demands.items() if node != depot and demand > 0
    }
    routes: list[list[int]] = []
    current_route = [depot]
    remaining_capacity = capacity

    while unvisited:
        current = current_route[-1]
        feasible = [node for node in unvisited if demands[node] <= remaining_capacity]

        if not feasible:
            if remaining_capacity == capacity:
                raise ValueError(
                    "Un client a une demande superieure a la capacite du vehicule."
                )
            current_route.append(depot)
            routes.append(current_route)
            current_route = [depot]
            remaining_capacity = capacity
            continue

        feasible.sort(key=lambda node: cost_matrix[current][node])
        cutoff = max(1, int(round(len(feasible) * rcl_alpha)))
        rcl = feasible[:cutoff]
        chosen = rng.choice(rcl)

        current_route.append(chosen)
        remaining_capacity -= demands[chosen]
        unvisited.remove(chosen)

    if len(current_route) > 1:
        current_route.append(depot)
        routes.append(current_route)

    return routes


def grasp(
    solver_input: SolverInput,
    *,
    max_iterations: int = 100,
    rcl_alpha: float = 0.3,
    use_local_search: bool = True,
    seed: int | None = None,
) -> VRPSolution:
    """Methode GRASP appliquee au VRP-CDR.

    Alterne une phase de construction gloutonne randomisee et une phase de
    recherche locale combinant ``relocate_inter``, ``swap_inter`` et ``2-opt``,
    puis retient la meilleure solution rencontree sur ``max_iterations`` essais.
    """

    if not 0.0 <= rcl_alpha <= 1.0:
        raise ValueError("rcl_alpha doit etre dans [0, 1]")
    if max_iterations <= 0:
        raise ValueError("max_iterations doit etre > 0")

    rng = random.Random(seed)
    cost_matrix = solver_input.cost_matrix
    demands = solver_input.demands
    capacity = solver_input.vehicle_capacity

    best_routes: list[list[int]] | None = None
    best_cost = float("inf")

    for _ in range(max_iterations):
        routes = greedy_randomized_construction(solver_input, rcl_alpha, rng)
        if use_local_search:
            routes = local_search(routes, cost_matrix, demands, capacity)
        cost = total_cost(routes, cost_matrix)
        if cost < best_cost:
            best_cost = cost
            best_routes = routes

    assert best_routes is not None
    return VRPSolution(routes=best_routes, total_cost=round(best_cost, 2))
