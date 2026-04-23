"""Algorithmes de resolution du VRP-CDR."""

from .benchmark import (
    plot_benchmark_gap,
    plot_benchmark_quality,
    plot_benchmark_runtime,
    run_benchmark,
    save_benchmark_figures,
    summarize_benchmark,
)
from .dynamic_benchmark import (
    plot_dynamic_cost_comparison,
    plot_dynamic_gain,
    plot_dynamic_planned_vs_realized,
    plot_dynamic_reactive_gain,
    run_dynamic_benchmark,
    save_dynamic_benchmark_figures,
    summarize_dynamic_benchmark,
)
from .dynamic_runner import DynamicExecution, execute_dynamic
from .genetic import genetic_algorithm
from .grasp import grasp, greedy_randomized_construction
from .neighborhood import (
    VRPSolution,
    is_feasible,
    local_search,
    random_neighbor,
    random_relocate_inter,
    random_swap_inter,
    random_two_opt,
    relocate_inter,
    route_cost,
    route_load,
    swap_inter,
    total_cost,
    two_opt,
    two_opt_intra,
)
from .simulated_annealing import simulated_annealing
from .tabu_search import tabu_search
from .visualization import DEFAULT_IMAGE_DIR, plot_solution, save_solution_plot

__all__ = [
    "DEFAULT_IMAGE_DIR",
    "DynamicExecution",
    "VRPSolution",
    "execute_dynamic",
    "genetic_algorithm",
    "grasp",
    "greedy_randomized_construction",
    "is_feasible",
    "local_search",
    "plot_benchmark_gap",
    "plot_benchmark_quality",
    "plot_benchmark_runtime",
    "plot_dynamic_cost_comparison",
    "plot_dynamic_gain",
    "plot_dynamic_planned_vs_realized",
    "plot_dynamic_reactive_gain",
    "plot_solution",
    "random_neighbor",
    "random_relocate_inter",
    "random_swap_inter",
    "random_two_opt",
    "relocate_inter",
    "route_cost",
    "route_load",
    "run_benchmark",
    "run_dynamic_benchmark",
    "save_benchmark_figures",
    "save_dynamic_benchmark_figures",
    "save_solution_plot",
    "simulated_annealing",
    "summarize_benchmark",
    "summarize_dynamic_benchmark",
    "swap_inter",
    "tabu_search",
    "total_cost",
    "two_opt",
    "two_opt_intra",
]
