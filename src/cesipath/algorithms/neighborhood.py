"""Primitives de voisinage partagees par les metaheuristiques VRP-CDR.

Une solution est representee comme une liste de sous-tournees
``list[list[int]]``, chaque sous-tournee commencant et se terminant au depot.
Les operateurs renvoient une nouvelle liste de routes sans modifier l'entree.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


Routes = list[list[int]]
CostMatrix = list[list[float]]


@dataclass
class VRPSolution:
    """Solution du VRP : liste de sous-tournees et cout total."""

    routes: Routes
    total_cost: float

    @property
    def route_count(self) -> int:
        return len(self.routes)


def route_cost(route: list[int], cost_matrix: CostMatrix) -> float:
    return sum(cost_matrix[route[i]][route[i + 1]] for i in range(len(route) - 1))


def total_cost(routes: Routes, cost_matrix: CostMatrix) -> float:
    return sum(route_cost(route, cost_matrix) for route in routes)


def route_load(route: list[int], demands: dict[int, int]) -> int:
    return sum(demands[c] for c in route[1:-1])


def is_feasible(routes: Routes, demands: dict[int, int], capacity: int) -> bool:
    for route in routes:
        if len(route) < 2 or route[0] != route[-1]:
            return False
        if route_load(route, demands) > capacity:
            return False
    return True


def _prune_empty_routes(routes: Routes) -> Routes:
    return [route for route in routes if len(route) > 2]


def two_opt(route: list[int], cost_matrix: CostMatrix) -> list[int]:
    """Recherche locale 2-opt intra-tournee."""

    best = route[:]
    improved = True
    while improved:
        improved = False
        for i in range(1, len(best) - 2):
            for j in range(i + 1, len(best) - 1):
                a, b = best[i - 1], best[i]
                c, d = best[j], best[j + 1]
                delta = (cost_matrix[a][c] + cost_matrix[b][d]) - (
                    cost_matrix[a][b] + cost_matrix[c][d]
                )
                if delta < -1e-9:
                    best[i : j + 1] = list(reversed(best[i : j + 1]))
                    improved = True
    return best


def two_opt_intra(routes: Routes, cost_matrix: CostMatrix) -> Routes:
    return [two_opt(route, cost_matrix) for route in routes]


def relocate_inter(
    routes: Routes,
    cost_matrix: CostMatrix,
    demands: dict[int, int],
    capacity: int,
) -> Routes:
    """Deplace un client d'une route vers une autre en best-improvement.

    A chaque passe, on choisit le deplacement (route source -> route cible) de
    plus grand gain admissible vis-a-vis de la capacite, puis on itere jusqu'a
    stabilite.
    """

    routes = [route[:] for route in routes]
    while True:
        best_delta = -1e-9
        best_move: tuple[int, int, int, int] | None = None

        loads = [route_load(route, demands) for route in routes]

        for r1_idx, r1 in enumerate(routes):
            for i in range(1, len(r1) - 1):
                client = r1[i]
                removal = (
                    cost_matrix[r1[i - 1]][r1[i + 1]]
                    - cost_matrix[r1[i - 1]][client]
                    - cost_matrix[client][r1[i + 1]]
                )
                for r2_idx, r2 in enumerate(routes):
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
                        if delta < best_delta:
                            best_delta = delta
                            best_move = (r1_idx, i, r2_idx, j)

        if best_move is None:
            break

        r1_idx, i, r2_idx, j = best_move
        client = routes[r1_idx][i]
        routes[r1_idx] = routes[r1_idx][:i] + routes[r1_idx][i + 1 :]
        r2 = routes[r2_idx]
        routes[r2_idx] = r2[:j] + [client] + r2[j:]

    return _prune_empty_routes(routes)


def swap_inter(
    routes: Routes,
    cost_matrix: CostMatrix,
    demands: dict[int, int],
    capacity: int,
) -> Routes:
    """Echange deux clients entre deux routes differentes (best-improvement)."""

    routes = [route[:] for route in routes]
    while True:
        best_delta = -1e-9
        best_move: tuple[int, int, int, int] | None = None

        loads = [route_load(route, demands) for route in routes]

        for r1_idx in range(len(routes)):
            for r2_idx in range(r1_idx + 1, len(routes)):
                r1 = routes[r1_idx]
                r2 = routes[r2_idx]
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
                        if delta < best_delta:
                            best_delta = delta
                            best_move = (r1_idx, i, r2_idx, j)

        if best_move is None:
            break

        r1_idx, i, r2_idx, j = best_move
        routes[r1_idx][i], routes[r2_idx][j] = routes[r2_idx][j], routes[r1_idx][i]

    return routes


def local_search(
    routes: Routes,
    cost_matrix: CostMatrix,
    demands: dict[int, int],
    capacity: int,
) -> Routes:
    """Compose relocate_inter, swap_inter et two_opt_intra jusqu'a stabilite."""

    previous_cost = float("inf")
    current = routes
    while True:
        current = relocate_inter(current, cost_matrix, demands, capacity)
        current = swap_inter(current, cost_matrix, demands, capacity)
        current = two_opt_intra(current, cost_matrix)
        new_cost = total_cost(current, cost_matrix)
        if new_cost >= previous_cost - 1e-9:
            return current
        previous_cost = new_cost


def random_relocate_inter(
    routes: Routes,
    demands: dict[int, int],
    capacity: int,
    rng: random.Random,
) -> Routes | None:
    """Deplace un client au hasard vers une autre route (None si infaisable)."""

    non_empty = [idx for idx, route in enumerate(routes) if len(route) > 2]
    if not non_empty or len(routes) < 2:
        return None
    r1_idx = rng.choice(non_empty)
    r1 = routes[r1_idx]
    i = rng.randrange(1, len(r1) - 1)
    client = r1[i]

    other_indices = [idx for idx in range(len(routes)) if idx != r1_idx]
    r2_idx = rng.choice(other_indices)
    r2 = routes[r2_idx]

    if route_load(r2, demands) + demands[client] > capacity:
        return None

    j = rng.randrange(1, len(r2))
    new_routes = [route[:] for route in routes]
    new_routes[r1_idx] = new_routes[r1_idx][:i] + new_routes[r1_idx][i + 1 :]
    new_routes[r2_idx] = r2[:j] + [client] + r2[j:]
    return _prune_empty_routes(new_routes)


def random_swap_inter(
    routes: Routes,
    demands: dict[int, int],
    capacity: int,
    rng: random.Random,
) -> Routes | None:
    """Echange deux clients de deux routes differentes (None si infaisable)."""

    non_empty = [idx for idx, route in enumerate(routes) if len(route) > 2]
    if len(non_empty) < 2:
        return None
    r1_idx, r2_idx = rng.sample(non_empty, 2)
    r1 = routes[r1_idx]
    r2 = routes[r2_idx]
    i = rng.randrange(1, len(r1) - 1)
    j = rng.randrange(1, len(r2) - 1)
    c1, c2 = r1[i], r2[j]
    load1 = route_load(r1, demands)
    load2 = route_load(r2, demands)
    if load1 - demands[c1] + demands[c2] > capacity:
        return None
    if load2 - demands[c2] + demands[c1] > capacity:
        return None
    new_routes = [route[:] for route in routes]
    new_routes[r1_idx] = r1[:]
    new_routes[r2_idx] = r2[:]
    new_routes[r1_idx][i] = c2
    new_routes[r2_idx][j] = c1
    return new_routes


def random_two_opt(routes: Routes, rng: random.Random) -> Routes | None:
    """Inversion 2-opt sur un segment aleatoire d'une route (None si trop courte)."""

    eligible = [idx for idx, route in enumerate(routes) if len(route) >= 5]
    if not eligible:
        return None
    r_idx = rng.choice(eligible)
    route = routes[r_idx]
    i = rng.randint(1, len(route) - 3)
    j = rng.randint(i + 1, len(route) - 2)
    new_route = route[:i] + list(reversed(route[i : j + 1])) + route[j + 1 :]
    new_routes = [r[:] for r in routes]
    new_routes[r_idx] = new_route
    return new_routes


def random_neighbor(
    routes: Routes,
    demands: dict[int, int],
    capacity: int,
    rng: random.Random,
) -> Routes:
    """Genere un voisin aleatoire via relocate / swap / 2-opt.

    Si le mouvement tire au sort n'est pas realisable, on retombe sur une copie
    identique de la solution (pour garantir un retour toujours valide).
    """

    move = rng.choice(("relocate", "swap", "two_opt"))
    if move == "relocate":
        result = random_relocate_inter(routes, demands, capacity, rng)
    elif move == "swap":
        result = random_swap_inter(routes, demands, capacity, rng)
    else:
        result = random_two_opt(routes, rng)
    if result is None:
        return [route[:] for route in routes]
    return result
