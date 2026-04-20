"""Fermeture metrique d'un graphe par plus courts chemins."""

from __future__ import annotations

import heapq


EdgeKey = tuple[int, int]
CostMatrix = list[list[float]]
PathIndex = dict[EdgeKey, list[int]]


def normalize_edge(u: int, v: int) -> EdgeKey:
    """Retourne une cle stable pour une arete non orientee."""

    return (min(u, v), max(u, v))


def build_neighbor_map(
    node_count: int,
    edge_costs: dict[EdgeKey, float],
) -> dict[int, list[tuple[int, float]]]:
    """Transforme un dictionnaire d'aretes en listes de voisins."""

    neighbors = {node: [] for node in range(node_count)}
    for (u, v), cost in edge_costs.items():
        if cost == float("inf"):
            continue
        neighbors[u].append((v, cost))
        neighbors[v].append((u, cost))
    return neighbors


def build_cost_matrix(
    node_count: int,
    edge_costs: dict[EdgeKey, float],
) -> CostMatrix:
    """Construit une matrice d'adjacence ponderee."""

    matrix = [[0.0 for _ in range(node_count)] for _ in range(node_count)]
    for (u, v), cost in edge_costs.items():
        if cost == float("inf"):
            continue
        matrix[u][v] = round(cost, 2)
        matrix[v][u] = round(cost, 2)
    return matrix


def dijkstra(
    source: int,
    node_count: int,
    neighbors: dict[int, list[tuple[int, float]]],
) -> tuple[list[float], list[int | None]]:
    """Calcule les plus courts chemins depuis une source."""

    distances = [float("inf")] * node_count
    predecessors: list[int | None] = [None] * node_count
    distances[source] = 0.0
    queue: list[tuple[float, int]] = [(0.0, source)]

    while queue:
        current_cost, node = heapq.heappop(queue)
        if current_cost > distances[node]:
            continue

        for neighbor, edge_cost in neighbors[node]:
            candidate = current_cost + edge_cost
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                predecessors[neighbor] = node
                heapq.heappush(queue, (candidate, neighbor))

    return distances, predecessors


def reconstruct_path(
    source: int,
    target: int,
    predecessors: list[int | None],
) -> list[int]:
    """Reconstruit le chemin source -> cible a partir des predecesseurs."""

    if source == target:
        return [source]

    path = [target]
    current = target
    while current != source:
        previous = predecessors[current]
        if previous is None:
            return []
        path.append(previous)
        current = previous

    path.reverse()
    return path


def complete_graph_with_shortest_paths(
    node_count: int,
    edge_costs: dict[EdgeKey, float],
) -> tuple[CostMatrix, PathIndex]:
    """Construit la matrice complete et les vrais chemins associes."""

    matrix = [[0.0 for _ in range(node_count)] for _ in range(node_count)]
    paths: PathIndex = {}
    neighbors = build_neighbor_map(node_count, edge_costs)

    for source in range(node_count):
        distances, predecessors = dijkstra(source, node_count, neighbors)
        for target, cost in enumerate(distances):
            matrix[source][target] = round(cost, 2)
            if source < target:
                paths[(source, target)] = reconstruct_path(source, target, predecessors)

    return matrix, paths


def check_triangle_inequality(matrix: CostMatrix) -> tuple[bool, tuple[int, int, int] | None]:
    """Verifie l'inegalite triangulaire sur une matrice de couts."""

    node_count = len(matrix)
    for i in range(node_count):
        for j in range(node_count):
            for k in range(node_count):
                if matrix[i][j] > matrix[i][k] + matrix[k][j] + 1e-9:
                    return False, (i, j, k)
    return True, None
