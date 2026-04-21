"""Fondations du projet CESIPATH."""

from .algorithms import (
    DynamicExecution,
    VRPSolution,
    execute_dynamic,
    genetic_algorithm,
    grasp,
    plot_benchmark_gap,
    plot_benchmark_quality,
    plot_benchmark_runtime,
    plot_dynamic_cost_comparison,
    plot_dynamic_gain,
    plot_dynamic_planned_vs_realized,
    plot_solution,
    run_benchmark,
    run_dynamic_benchmark,
    save_benchmark_figures,
    save_dynamic_benchmark_figures,
    save_solution_plot,
    simulated_annealing,
    summarize_benchmark,
    summarize_dynamic_benchmark,
    tabu_search,
)
from .dynamic_costs import (
    DEFAULT_DYNAMIC_SIGMA,
    dynamic_multiplier,
    initialize_dynamic_edge_costs,
    refresh_dynamic_edge_costs,
    sample_dynamic_edge_cost,
)
from .dynamic_network import DynamicNetworkSimulator
from .graph_generator import GraphGenerator
from .metric_closure import (
    build_cost_matrix,
    check_triangle_inequality,
    complete_graph_with_shortest_paths,
    dijkstra,
)
from .models import (
    DynamicGraphSnapshot,
    EdgeAttributes,
    EdgeStatus,
    GraphGenerationConfig,
    GraphInstance,
)
from .solver_input import SolverInput, build_dynamic_solver_input, build_static_solver_input
from .validators import DynamicStateValidator, InstanceValidator

try:
    from .quartier_graph import QuartierGraph, analyze_chemin
except ModuleNotFoundError:
    QuartierGraph = None  # type: ignore[assignment]
    analyze_chemin = None  # type: ignore[assignment]

__all__ = [
    "DEFAULT_DYNAMIC_SIGMA",
    "DynamicExecution",
    "DynamicNetworkSimulator",
    "DynamicGraphSnapshot",
    "DynamicStateValidator",
    "EdgeAttributes",
    "EdgeStatus",
    "GraphGenerationConfig",
    "GraphGenerator",
    "GraphInstance",
    "InstanceValidator",
    "SolverInput",
    "VRPSolution",
    "build_cost_matrix",
    "build_dynamic_solver_input",
    "build_static_solver_input",
    "check_triangle_inequality",
    "complete_graph_with_shortest_paths",
    "dijkstra",
    "dynamic_multiplier",
    "execute_dynamic",
    "genetic_algorithm",
    "grasp",
    "plot_benchmark_gap",
    "plot_benchmark_quality",
    "plot_benchmark_runtime",
    "plot_dynamic_cost_comparison",
    "plot_dynamic_gain",
    "plot_dynamic_planned_vs_realized",
    "plot_solution",
    "run_benchmark",
    "run_dynamic_benchmark",
    "save_benchmark_figures",
    "save_dynamic_benchmark_figures",
    "save_solution_plot",
    "simulated_annealing",
    "summarize_benchmark",
    "summarize_dynamic_benchmark",
    "tabu_search",
    "initialize_dynamic_edge_costs",
    "refresh_dynamic_edge_costs",
    "sample_dynamic_edge_cost",
]

if QuartierGraph is not None:
    __all__.extend(["QuartierGraph", "analyze_chemin"])
