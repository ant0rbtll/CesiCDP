"""Recherche tabou pour le VRP-CDR."""

from __future__ import annotations

import random

from ..solver_input import SolverInput
from .grasp import greedy_randomized_construction
from .neighborhood import (
    VRPSolution,
    _prune_empty_routes,
    local_search,
    route_load,
    total_cost,
)


def tabu_search(
    solver_input: SolverInput,
    *,
    max_iterations: int = 300,
    tabu_tenure: int = 7,
    max_no_improve: int = 80,
    initial_rcl_alpha: float = 0.0,
    final_local_search: bool = True,
    seed: int | None = None,
) -> VRPSolution:
    """Recherche tabou sur un voisinage relocate + swap inter-tournees.

    Solution initiale : construction gloutonne (randomisee si
    ``initial_rcl_alpha > 0``).

    A chaque iteration, on balaie *tout* le voisinage et on choisit le
    meilleur mouvement admissible, tabou inclus si son acceptation ameliore
    le meilleur cout connu (aspiration).

    - Attribut tabou relocate : le client deplace est interdit de mouvement
      pendant ``tabu_tenure`` iterations.
    - Attribut tabou swap : la paire de clients echangee est interdite
      d'echange pendant ``tabu_tenure`` iterations.

    Arret : ``max_iterations`` iterations ou ``max_no_improve`` iterations
    consecutives sans amelioration. Une passe finale de ``local_search``
    polit la meilleure solution (desactivable via ``final_local_search``).
    """

    if max_iterations <= 0:
        raise ValueError("max_iterations doit etre > 0")
    if tabu_tenure < 0:
        raise ValueError("tabu_tenure doit etre >= 0")
    if max_no_improve <= 0:
        raise ValueError("max_no_improve doit etre > 0")

    rng = random.Random(seed)
    cost_matrix = solver_input.cost_matrix
    demands = solver_input.demands
    capacity = solver_input.vehicle_capacity

    current_routes = greedy_randomized_construction(solver_input, initial_rcl_alpha, rng)
    current_cost = total_cost(current_routes, cost_matrix)

    best_routes = [route[:] for route in current_routes]
    best_cost = current_cost

    tabu_relocate: dict[int, int] = {}
    tabu_swap: dict[frozenset[int], int] = {}

    no_improve = 0
    for iteration in range(max_iterations):
        best_move: tuple | None = None
        best_move_cost = float("inf")

        loads = [route_load(route, demands) for route in current_routes]

        for r1_idx, r1 in enumerate(current_routes):
            for i in range(1, len(r1) - 1):
                client = r1[i]
                removal = (
                    cost_matrix[r1[i - 1]][r1[i + 1]]
                    - cost_matrix[r1[i - 1]][client]
                    - cost_matrix[client][r1[i + 1]]
                )
                for r2_idx, r2 in enumerate(current_routes):
                    if r2_idx == r1_idx:
                        continue
                    if loads[r2_idx] + demands[client] > capacity:
                        continue
                    for j in range(1, len(r2)):
                        insertion = (
                            cost_matrix[r2[j - 1]][client]
                            + cost_matrix[client][r2[j]]
                            - cost_matrix[r2[j - 1]][r2[j]]
                        )
                        delta = removal + insertion
                        neighbor_cost = current_cost + delta

                        is_tabu = tabu_relocate.get(client, 0) > iteration
                        aspirated = neighbor_cost < best_cost - 1e-9
                        if is_tabu and not aspirated:
                            continue
                        if neighbor_cost < best_move_cost:
                            best_move_cost = neighbor_cost
                            best_move = ("relocate", client, r1_idx, i, r2_idx, j, delta)

        for r1_idx in range(len(current_routes)):
            for r2_idx in range(r1_idx + 1, len(current_routes)):
                r1 = current_routes[r1_idx]
                r2 = current_routes[r2_idx]
                for i in range(1, len(r1) - 1):
                    c1 = r1[i]
                    d1 = demands[c1]
                    for j in range(1, len(r2) - 1):
                        c2 = r2[j]
                        d2 = demands[c2]
                        if loads[r1_idx] - d1 + d2 > capacity:
                            continue
                        if loads[r2_idx] - d2 + d1 > capacity:
                            continue
                        delta = (
                            cost_matrix[r1[i - 1]][c2]
                            + cost_matrix[c2][r1[i + 1]]
                            + cost_matrix[r2[j - 1]][c1]
                            + cost_matrix[c1][r2[j + 1]]
                            - cost_matrix[r1[i - 1]][c1]
                            - cost_matrix[c1][r1[i + 1]]
                            - cost_matrix[r2[j - 1]][c2]
                            - cost_matrix[c2][r2[j + 1]]
                        )
                        neighbor_cost = current_cost + delta

                        key = frozenset({c1, c2})
                        is_tabu = tabu_swap.get(key, 0) > iteration
                        aspirated = neighbor_cost < best_cost - 1e-9
                        if is_tabu and not aspirated:
                            continue
                        if neighbor_cost < best_move_cost:
                            best_move_cost = neighbor_cost
                            best_move = ("swap", c1, c2, r1_idx, i, r2_idx, j, delta)

        if best_move is None:
            break

        if best_move[0] == "relocate":
            _, client, r1_idx, i, r2_idx, j, delta = best_move
            new_routes = [route[:] for route in current_routes]
            new_routes[r1_idx] = new_routes[r1_idx][:i] + new_routes[r1_idx][i + 1 :]
            new_routes[r2_idx] = new_routes[r2_idx][:j] + [client] + new_routes[r2_idx][j:]
            new_routes = _prune_empty_routes(new_routes)
            tabu_relocate[client] = iteration + tabu_tenure
        else:
            _, c1, c2, r1_idx, i, r2_idx, j, delta = best_move
            new_routes = [route[:] for route in current_routes]
            new_routes[r1_idx] = new_routes[r1_idx][:]
            new_routes[r2_idx] = new_routes[r2_idx][:]
            new_routes[r1_idx][i] = c2
            new_routes[r2_idx][j] = c1
            tabu_swap[frozenset({c1, c2})] = iteration + tabu_tenure

        current_routes = new_routes
        current_cost += delta

        if current_cost < best_cost - 1e-9:
            best_cost = current_cost
            best_routes = [route[:] for route in current_routes]
            no_improve = 0
        else:
            no_improve += 1

        if no_improve >= max_no_improve:
            break

    if final_local_search:
        best_routes = local_search(best_routes, cost_matrix, demands, capacity)
        best_cost = total_cost(best_routes, cost_matrix)

    return VRPSolution(routes=best_routes, total_cost=round(best_cost, 2))
