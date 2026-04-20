"""Calculs de surcouts statiques et dynamiques."""

from __future__ import annotations

import random

from .models import EdgeAttributes

DEFAULT_DYNAMIC_SIGMA = 0.12


def sample_dynamic_edge_cost(
    edge: EdgeAttributes,
    previous_cost: float | None = None,
    rng: random.Random | None = None,
    sigma: float = DEFAULT_DYNAMIC_SIGMA,
    mean_reversion_strength: float = 0.35,
    max_multiplier: float = 1.80,
) -> float:
    """Echantillonne un nouveau cout dynamique pour une traversee.

    Le tirage suit une loi gaussienne centree sur une moyenne qui revient
    progressivement vers le cout statique. Plus le cout precedent s'eloigne du
    cout statique, plus la prochaine moyenne est attiree vers ce cout statique.
    Le cout final ne descend jamais sous le cout de base et ne depasse jamais
    un multiple configurable du cout statique.
    """

    if sigma < 0:
        raise ValueError("sigma doit etre >= 0")
    if not 0.0 <= mean_reversion_strength <= 1.0:
        raise ValueError("mean_reversion_strength doit etre entre 0 et 1")
    if max_multiplier < 1.0:
        raise ValueError("max_multiplier doit etre >= 1")
    if edge.status.value == "interdit":
        return float("inf")

    current_rng = rng or random.Random()
    static_cost = edge.static_cost
    baseline = static_cost if previous_cost is None else previous_cost

    # Retour vers la moyenne : plus on s'eloigne du cout statique, plus le
    # centre du prochain tirage se rapproche de ce cout statique.
    reverted_mean = baseline - mean_reversion_strength * (baseline - static_cost)

    # On reduit aussi legerement la volatilite quand le cout s'emballe.
    relative_gap = max(0.0, (baseline / static_cost) - 1.0) if static_cost > 0 else 0.0
    volatility_scale = max(0.35, 1.0 - 0.5 * min(relative_gap, 1.0))
    standard_deviation = max(static_cost * sigma * volatility_scale, 0.01)

    sampled_cost = current_rng.gauss(reverted_mean, standard_deviation)
    upper_bound = static_cost * max_multiplier
    bounded_cost = min(upper_bound, max(edge.base_cost, sampled_cost))

    return round(bounded_cost, 2)


def dynamic_multiplier(edge: EdgeAttributes, dynamic_cost: float) -> float:
    """Retourne le coefficient dynamique associe au cout genere."""

    static_cost = edge.static_cost
    if static_cost in (0, float("inf")):
        return float("inf")
    return round(dynamic_cost / static_cost, 4)


def initialize_dynamic_edge_costs(
    edges: dict[tuple[int, int], EdgeAttributes],
) -> dict[tuple[int, int], float]:
    """Initialise les couts dynamiques a partir des couts statiques."""

    return {
        key: edge.static_cost
        for key, edge in edges.items()
        if edge.static_cost != float("inf")
    }


def refresh_dynamic_edge_costs(
    edges: dict[tuple[int, int], EdgeAttributes],
    previous_costs: dict[tuple[int, int], float],
    rng: random.Random | None = None,
    sigma: float = DEFAULT_DYNAMIC_SIGMA,
    mean_reversion_strength: float = 0.35,
    max_multiplier: float = 1.80,
) -> dict[tuple[int, int], float]:
    """Met a jour toutes les vraies aretes du graphe residuel.

    Chaque arete non interdite evolue localement autour de son propre cout
    precedent. La completion metrque est ensuite a recalculer sur ces couts.
    """

    current_rng = rng or random.Random()
    updated_costs: dict[tuple[int, int], float] = {}

    for key, edge in edges.items():
        if edge.static_cost == float("inf"):
            continue
        updated_costs[key] = sample_dynamic_edge_cost(
            edge,
            previous_cost=previous_costs.get(key),
            rng=current_rng,
            sigma=sigma,
            mean_reversion_strength=mean_reversion_strength,
            max_multiplier=max_multiplier,
        )

    return updated_costs
