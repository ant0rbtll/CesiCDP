"""Couche de services: logique metier decouplee de la GUI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cesipath.algorithms import (
    genetic_algorithm,
    grasp,
    run_benchmark,
    save_benchmark_figures,
    simulated_annealing,
    summarize_benchmark,
    tabu_search,
)
from cesipath.graph_generator import GraphGenerator
from cesipath.models import GraphGenerationConfig, GraphInstance
from cesipath.visualization import GraphVisualizationSession, GraphVisualizer

ALGO_FUNCTIONS = {
    "grasp": grasp,
    "tabu_search": tabu_search,
    "simulated_annealing": simulated_annealing,
    "genetic_algorithm": genetic_algorithm,
}

NETWORK_TYPES = {
    "Drive": "drive",
    "Walk": "walk",
    "Bike": "bike",
    "All": "all",
}


def parse_int_list(raw: str, *, field_name: str) -> list[int]:
    tokens = [tok for chunk in raw.split(",") for tok in chunk.split()]
    if not tokens:
        raise ValueError(f"{field_name}: aucune valeur fournie")

    values: list[int] = []
    for token in tokens:
        try:
            value = int(token)
        except ValueError as exc:
            raise ValueError(f"{field_name}: '{token}' n'est pas un entier") from exc
        if value <= 0:
            raise ValueError(f"{field_name}: les valeurs doivent etre > 0")
        values.append(value)
    return values


def parse_positive_int(raw: str, *, field_name: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{field_name}: valeur invalide") from exc
    if value <= 0:
        raise ValueError(f"{field_name}: la valeur doit etre > 0")
    return value


def parse_float(raw: str, *, field_name: str) -> float:
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{field_name}: valeur invalide") from exc


def parse_optional_int(raw: str, *, field_name: str) -> int | None:
    cleaned = raw.strip()
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError as exc:
        raise ValueError(f"{field_name}: valeur invalide") from exc


@dataclass
class BenchmarkServiceResult:
    results: list[dict[str, Any]]
    figure_paths: dict[str, Path]
    summary: list[dict[str, Any]]


def run_benchmark_service(
    *,
    sizes: list[int],
    seeds: list[int],
    selected_algorithms: list[str],
    output_dir: Path,
    verbose: bool,
    progress_callback=None,
) -> BenchmarkServiceResult:
    selected = {name: ALGO_FUNCTIONS[name] for name in selected_algorithms}
    if not selected:
        raise ValueError("Selectionner au moins un algorithme")

    output_dir.mkdir(parents=True, exist_ok=True)
    results = run_benchmark(
        sizes=sizes,
        seeds=seeds,
        algos=selected,
        progress_callback=progress_callback,
        verbose=verbose,
    )
    figure_paths = save_benchmark_figures(results, directory=output_dir)
    summary = summarize_benchmark(results)
    return BenchmarkServiceResult(results=results, figure_paths=figure_paths, summary=summary)


@dataclass
class GenerationServiceResult:
    summary: dict[str, Any]
    session: GraphVisualizationSession


def generate_and_build_visualizer(config: GraphGenerationConfig) -> GenerationServiceResult:
    generator = GraphGenerator(config)
    instance = generator.generate()
    visualizer = GraphVisualizer(
        instance,
        generator,
        show_edge_labels=False,
        show_node_labels=False,
        show_grid=False,
    )
    session = visualizer.show_dynamic_graph(
        size=(16.0, 10.8),
        external_controls=False,
        show_legend=True,
    )
    return GenerationServiceResult(summary=instance.summary(), session=session)


@dataclass
class QuartierServiceResult:
    quartier_graph: Any
    stats: dict[str, Any]
    export_path: str | None
    dynamic_instance_summary: dict[str, Any]
    dynamic_metadata: dict[str, Any]
    dynamic_instance: GraphInstance


def build_quartier_dynamic_session(
    result: QuartierServiceResult,
    *,
    title_callback=None,
    info_callback=None,
    legend_callback=None,
    state_callback=None,
) -> GraphVisualizationSession:
    generator = GraphGenerator(result.dynamic_instance.config)
    # Sur OSM: beaucoup d'aretes reelles -> les labels saturent la carte.
    show_edge_labels = False
    show_node_labels = False
    visualizer = GraphVisualizer(
        result.dynamic_instance,
        generator,
        background_renderer=result.quartier_graph.draw_basemap,
        show_edge_labels=show_edge_labels,
        show_node_labels=show_node_labels,
        show_grid=False,
    )
    # Popup natif matplotlib: taille initiale large pour maximiser la zone graphe.
    return visualizer.show_dynamic_graph(
        size=(16.0, 10.8),
        external_controls=False,
        show_legend=True,
        title_callback=title_callback,
        info_callback=info_callback,
        legend_callback=legend_callback,
        state_callback=state_callback,
    )


def run_quartier_service(
    *,
    quartier_graph_cls,
    place: str,
    network_type: str,
    distance: int,
    export_format: str,
    max_solver_clients: int = 35,
) -> QuartierServiceResult:
    qg = quartier_graph_cls(place, network_type=network_type)
    qg.charger_quartier(distance=distance)
    stats = qg.obtenir_stats()
    dynamic_instance, dynamic_metadata = qg.build_dynamic_instance(max_solver_clients=max_solver_clients)

    export_path = None
    if export_format != "none":
        export_path = qg.exporter_graphe(format=export_format)

    return QuartierServiceResult(
        quartier_graph=qg,
        stats=stats,
        export_path=export_path,
        dynamic_instance_summary=dynamic_instance.summary(),
        dynamic_metadata=dynamic_metadata,
        dynamic_instance=dynamic_instance,
    )
