"""Algorithme genetique pour le VRP-CDR.

Representation par *giant-tour* : chaque individu est une permutation des
clients, convertie en solution VRP par une procedure de Split optimal
(Prins, 2004) qui partitionne le tour en sous-tournees admissibles par
programmation dynamique.
"""

from __future__ import annotations

import random

from ..solver_input import SolverInput
from .neighborhood import VRPSolution, local_search, total_cost


def _split(
    giant_tour: list[int],
    depot: int,
    cost_matrix: list[list[float]],
    demands: dict[int, int],
    capacity: int,
) -> tuple[list[list[int]], float]:
    """Split de Prins : partition optimale d'un giant-tour en sous-tournees."""

    n = len(giant_tour)
    inf = float("inf")
    v = [inf] * (n + 1)
    p = [0] * (n + 1)
    v[0] = 0.0

    for i in range(n):
        load = 0
        route_cost = 0.0
        for j in range(i, n):
            client = giant_tour[j]
            load += demands[client]
            if load > capacity:
                break
            if j == i:
                route_cost = cost_matrix[depot][client] + cost_matrix[client][depot]
            else:
                prev = giant_tour[j - 1]
                route_cost = (
                    route_cost
                    - cost_matrix[prev][depot]
                    + cost_matrix[prev][client]
                    + cost_matrix[client][depot]
                )
            candidate = v[i] + route_cost
            if candidate < v[j + 1]:
                v[j + 1] = candidate
                p[j + 1] = i

    routes: list[list[int]] = []
    j = n
    while j > 0:
        i = p[j]
        routes.append([depot, *giant_tour[i:j], depot])
        j = i
    routes.reverse()
    return routes, v[n]


def _ox_crossover(p1: list[int], p2: list[int], rng: random.Random) -> list[int]:
    """Order Crossover (OX) sur deux permutations."""

    n = len(p1)
    if n < 2:
        return p1[:]
    i, j = sorted(rng.sample(range(n), 2))
    child: list[int | None] = [None] * n
    child[i : j + 1] = p1[i : j + 1]
    used = set(p1[i : j + 1])
    pos = (j + 1) % n
    for k in range(n):
        gene = p2[(j + 1 + k) % n]
        if gene not in used:
            child[pos] = gene
            used.add(gene)
            pos = (pos + 1) % n
    return child  # type: ignore[return-value]


def _mutate(perm: list[int], rng: random.Random) -> list[int]:
    """Mutation : swap de deux genes ou inversion d'un segment."""

    n = len(perm)
    if n < 2:
        return perm[:]
    if rng.random() < 0.5:
        i, j = rng.sample(range(n), 2)
        mutated = perm[:]
        mutated[i], mutated[j] = mutated[j], mutated[i]
        return mutated
    i, j = sorted(rng.sample(range(n), 2))
    return perm[:i] + list(reversed(perm[i : j + 1])) + perm[j + 1 :]


def _tournament(
    population: list[tuple[list[int], list[list[int]], float]],
    k: int,
    rng: random.Random,
) -> tuple[list[int], list[list[int]], float]:
    contenders = rng.sample(population, min(k, len(population)))
    return min(contenders, key=lambda ind: ind[2])


def genetic_algorithm(
    solver_input: SolverInput,
    *,
    population_size: int = 30,
    generations: int = 100,
    tournament_k: int = 3,
    crossover_rate: float = 0.85,
    mutation_rate: float = 0.2,
    elitism: int = 2,
    memetic: bool = True,
    seed: int | None = None,
) -> VRPSolution:
    """Algorithme genetique a codage *giant-tour*.

    - Population initiale : permutations aleatoires, decodees par Split.
    - Selection : tournoi a ``tournament_k`` participants.
    - Croisement : OX applique au giant-tour avec probabilite ``crossover_rate``.
    - Mutation : swap ou inversion avec probabilite ``mutation_rate``.
    - Remplacement : generationnel avec elitisme (``elitism`` meilleurs conserves).
    - Option ``memetic`` : chaque enfant est educateur par ``local_search``
      apres Split (schema memetique, nettement plus intensif mais plus robuste).
    """

    if population_size <= 1:
        raise ValueError("population_size doit etre > 1")
    if generations <= 0:
        raise ValueError("generations doit etre > 0")
    if not 0.0 <= crossover_rate <= 1.0:
        raise ValueError("crossover_rate doit etre dans [0, 1]")
    if not 0.0 <= mutation_rate <= 1.0:
        raise ValueError("mutation_rate doit etre dans [0, 1]")
    if not 0 <= elitism < population_size:
        raise ValueError("elitism doit etre dans [0, population_size)")

    rng = random.Random(seed)
    depot = solver_input.depot
    cost_matrix = solver_input.cost_matrix
    demands = solver_input.demands
    capacity = solver_input.vehicle_capacity

    clients = [c for c, d in demands.items() if c != depot and d > 0]

    def evaluate(perm: list[int]) -> tuple[list[int], list[list[int]], float]:
        routes, cost_val = _split(perm, depot, cost_matrix, demands, capacity)
        if memetic:
            routes = local_search(routes, cost_matrix, demands, capacity)
            cost_val = total_cost(routes, cost_matrix)
        return perm, routes, cost_val

    population = []
    for _ in range(population_size):
        perm = clients[:]
        rng.shuffle(perm)
        population.append(evaluate(perm))
    population.sort(key=lambda ind: ind[2])

    best_perm, best_routes, best_cost = population[0]
    best_routes = [route[:] for route in best_routes]

    for _ in range(generations):
        next_pop = [population[i] for i in range(elitism)]

        while len(next_pop) < population_size:
            parent1 = _tournament(population, tournament_k, rng)
            parent2 = _tournament(population, tournament_k, rng)
            if rng.random() < crossover_rate:
                child_perm = _ox_crossover(parent1[0], parent2[0], rng)
            else:
                child_perm = parent1[0][:]
            if rng.random() < mutation_rate:
                child_perm = _mutate(child_perm, rng)
            next_pop.append(evaluate(child_perm))

        next_pop.sort(key=lambda ind: ind[2])
        population = next_pop

        if population[0][2] < best_cost - 1e-9:
            best_perm, routes, best_cost = population[0]
            best_routes = [route[:] for route in routes]

    return VRPSolution(routes=best_routes, total_cost=round(best_cost, 2))
