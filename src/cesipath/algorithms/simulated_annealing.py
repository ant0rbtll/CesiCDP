"""Recuit simule pour le VRP-CDR."""

from __future__ import annotations

import math
import random

from ..solver_input import SolverInput
from .grasp import greedy_randomized_construction
from .neighborhood import VRPSolution, local_search, random_neighbor, total_cost


def simulated_annealing(
    solver_input: SolverInput,
    *,
    initial_temperature: float = 100.0,
    final_temperature: float = 0.01,
    cooling_rate: float = 0.995,
    max_iterations: int = 10_000,
    initial_rcl_alpha: float = 0.0,
    final_local_search: bool = True,
    seed: int | None = None,
) -> VRPSolution:
    """Recuit simule avec refroidissement geometrique.

    La solution initiale est construite par glouton (plus proche voisin si
    ``initial_rcl_alpha = 0``, randomise sinon).

    A chaque iteration : un voisin aleatoire est genere via relocate / swap /
    2-opt, puis le critere de Metropolis decide de l'acceptation :

    - amelioration : toujours acceptee ;
    - degradation  : acceptee avec probabilite ``exp(-delta / T)``.

    La temperature decroit geometriquement ``T <- cooling_rate * T``. La
    meilleure solution visitee est retournee. Si ``final_local_search`` est
    vrai, une descente ``local_search`` est appliquee sur la meilleure
    solution pour polir l'optimum (intensification finale).
    """

    if final_temperature <= 0 or initial_temperature <= final_temperature:
        raise ValueError("initial_temperature doit etre > final_temperature > 0")
    if not 0.0 < cooling_rate < 1.0:
        raise ValueError("cooling_rate doit etre dans (0, 1)")
    if max_iterations <= 0:
        raise ValueError("max_iterations doit etre > 0")

    rng = random.Random(seed)
    cost_matrix = solver_input.cost_matrix
    demands = solver_input.demands
    capacity = solver_input.vehicle_capacity

    current_routes = greedy_randomized_construction(solver_input, initial_rcl_alpha, rng)
    current_cost = total_cost(current_routes, cost_matrix)

    best_routes = [route[:] for route in current_routes]
    best_cost = current_cost

    temperature = initial_temperature
    iteration = 0
    while temperature > final_temperature and iteration < max_iterations:
        neighbor_routes = random_neighbor(current_routes, demands, capacity, rng)
        neighbor_cost = total_cost(neighbor_routes, cost_matrix)
        delta = neighbor_cost - current_cost

        if delta < 0 or rng.random() < math.exp(-delta / temperature):
            current_routes = neighbor_routes
            current_cost = neighbor_cost
            if current_cost < best_cost:
                best_routes = [route[:] for route in current_routes]
                best_cost = current_cost

        temperature *= cooling_rate
        iteration += 1

    if final_local_search:
        best_routes = local_search(best_routes, cost_matrix, demands, capacity)
        best_cost = total_cost(best_routes, cost_matrix)

    return VRPSolution(routes=best_routes, total_cost=round(best_cost, 2))
