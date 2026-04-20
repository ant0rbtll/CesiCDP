"""Harnais de benchmark pour comparer les metaheuristiques VRP-CDR."""

from __future__ import annotations

import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

import matplotlib.pyplot as plt

from ..graph_generator import GraphGenerator
from ..models import GraphGenerationConfig
from ..solver_input import build_static_solver_input
from .neighborhood import VRPSolution
from .visualization import DEFAULT_IMAGE_DIR


AlgoFn = Callable[..., VRPSolution]
BenchmarkRow = dict[str, Any]


def run_benchmark(
    sizes: list[int],
    seeds: list[int],
    algos: dict[str, AlgoFn],
    *,
    algo_kwargs: dict[str, dict[str, Any]] | None = None,
    verbose: bool = True,
) -> list[BenchmarkRow]:
    """Execute ``algos`` sur le produit cartesien ``sizes x seeds``.

    Chaque ligne retournee contient ``size``, ``seed``, ``algo``, ``cost``,
    ``runtime`` et ``routes``. Le parametre ``algo_kwargs`` permet de
    specifier des hyperparametres par algorithme.
    """

    algo_kwargs = algo_kwargs or {}
    results: list[BenchmarkRow] = []

    for size in sizes:
        for seed in seeds:
            cfg = GraphGenerationConfig(node_count=size, seed=seed)
            instance = GraphGenerator(cfg).generate()
            solver_input = build_static_solver_input(instance)

            if verbose:
                print(f"[bench] size={size} seed={seed}")

            for name, fn in algos.items():
                kwargs = dict(algo_kwargs.get(name, {}))
                kwargs.setdefault("seed", seed)
                start = time.perf_counter()
                solution = fn(solver_input, **kwargs)
                elapsed = time.perf_counter() - start
                results.append(
                    {
                        "size": size,
                        "seed": seed,
                        "algo": name,
                        "cost": solution.total_cost,
                        "runtime": elapsed,
                        "routes": solution.route_count,
                    }
                )

    return results


def _group_by(rows: list[BenchmarkRow], *keys: str) -> dict[tuple, list[BenchmarkRow]]:
    grouped: dict[tuple, list[BenchmarkRow]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row[k] for k in keys)].append(row)
    return grouped


def _ordered_unique(values: list) -> list:
    seen = []
    for v in values:
        if v not in seen:
            seen.append(v)
    return seen


def _algo_palette(algos: list[str]) -> dict[str, str]:
    base = ["#3498db", "#e74c3c", "#2ecc71", "#9b59b6", "#f39c12", "#1abc9c"]
    return {algo: base[i % len(base)] for i, algo in enumerate(algos)}


def plot_benchmark_quality(
    results: list[BenchmarkRow],
    *,
    title: str = "Qualite des solutions (cout)",
) -> plt.Figure:
    """Boxplot du cout par taille, une couleur par algorithme."""

    sizes = _ordered_unique([r["size"] for r in results])
    algos = _ordered_unique([r["algo"] for r in results])
    palette = _algo_palette(algos)

    fig, ax = plt.subplots(figsize=(10, 6))
    width = 0.8 / max(len(algos), 1)

    for a_idx, algo in enumerate(algos):
        data = [
            [r["cost"] for r in results if r["size"] == size and r["algo"] == algo]
            for size in sizes
        ]
        positions = [i + (a_idx - (len(algos) - 1) / 2) * width for i in range(len(sizes))]
        bp = ax.boxplot(
            data,
            positions=positions,
            widths=width * 0.85,
            patch_artist=True,
            medianprops={"color": "black", "linewidth": 1.2},
        )
        for patch in bp["boxes"]:
            patch.set_facecolor(palette[algo])
            patch.set_alpha(0.7)

    ax.set_xticks(range(len(sizes)))
    ax.set_xticklabels([str(s) for s in sizes])
    ax.set_xlabel("Taille du graphe (n)")
    ax.set_ylabel("Cout total")
    ax.set_title(title)
    ax.grid(True, axis="y", linestyle=":", alpha=0.4)

    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=palette[a], alpha=0.7) for a in algos]
    ax.legend(handles, algos, loc="best", frameon=True)
    fig.tight_layout()
    return fig


def plot_benchmark_gap(
    results: list[BenchmarkRow],
    *,
    title: str = "Ecart relatif au meilleur (%)",
) -> plt.Figure:
    """Bar chart du gap moyen (%) par taille et algo, vs meilleur de l'instance."""

    sizes = _ordered_unique([r["size"] for r in results])
    algos = _ordered_unique([r["algo"] for r in results])
    palette = _algo_palette(algos)

    best_per_instance: dict[tuple[int, int], float] = {}
    for r in results:
        key = (r["size"], r["seed"])
        best_per_instance[key] = min(best_per_instance.get(key, float("inf")), r["cost"])

    mean_gap: dict[tuple[int, str], float] = {}
    for size in sizes:
        for algo in algos:
            gaps = [
                100.0 * (r["cost"] - best_per_instance[(r["size"], r["seed"])])
                / best_per_instance[(r["size"], r["seed"])]
                for r in results
                if r["size"] == size and r["algo"] == algo
            ]
            mean_gap[(size, algo)] = sum(gaps) / len(gaps) if gaps else 0.0

    fig, ax = plt.subplots(figsize=(10, 6))
    width = 0.8 / max(len(algos), 1)

    for a_idx, algo in enumerate(algos):
        values = [mean_gap[(size, algo)] for size in sizes]
        positions = [i + (a_idx - (len(algos) - 1) / 2) * width for i in range(len(sizes))]
        ax.bar(positions, values, width=width * 0.9, color=palette[algo], alpha=0.85, label=algo)

    ax.set_xticks(range(len(sizes)))
    ax.set_xticklabels([str(s) for s in sizes])
    ax.set_xlabel("Taille du graphe (n)")
    ax.set_ylabel("Gap moyen vs meilleur (%)")
    ax.set_title(title)
    ax.grid(True, axis="y", linestyle=":", alpha=0.4)
    ax.legend(loc="best", frameon=True)
    fig.tight_layout()
    return fig


def plot_benchmark_runtime(
    results: list[BenchmarkRow],
    *,
    title: str = "Temps d'execution moyen",
    log_scale: bool = True,
) -> plt.Figure:
    """Courbes du temps moyen (s) par taille, une ligne par algorithme."""

    sizes = _ordered_unique([r["size"] for r in results])
    algos = _ordered_unique([r["algo"] for r in results])
    palette = _algo_palette(algos)

    fig, ax = plt.subplots(figsize=(10, 6))
    for algo in algos:
        means = []
        for size in sizes:
            times = [r["runtime"] for r in results if r["size"] == size and r["algo"] == algo]
            means.append(sum(times) / len(times) if times else 0.0)
        ax.plot(sizes, means, marker="o", linewidth=2, color=palette[algo], label=algo)

    ax.set_xlabel("Taille du graphe (n)")
    ax.set_ylabel("Temps moyen (s)" + (" [log]" if log_scale else ""))
    if log_scale:
        ax.set_yscale("log")
    ax.set_title(title)
    ax.grid(True, which="both", linestyle=":", alpha=0.4)
    ax.legend(loc="best", frameon=True)
    fig.tight_layout()
    return fig


def save_benchmark_figures(
    results: list[BenchmarkRow],
    *,
    directory: Path | str | None = None,
    dpi: int = 120,
) -> dict[str, Path]:
    """Trace et sauvegarde les trois figures de benchmark avec un numero
    auto-incremente (partage avec ``save_solution_plot``).
    """

    target = Path(directory) if directory is not None else DEFAULT_IMAGE_DIR
    target.mkdir(parents=True, exist_ok=True)

    index = 1
    prefix = "benchmark"
    while any(
        (target / f"{prefix}_{suffix}_{index}.png").exists()
        for suffix in ("quality", "gap", "runtime")
    ):
        index += 1

    paths: dict[str, Path] = {}
    for suffix, builder in (
        ("quality", plot_benchmark_quality),
        ("gap", plot_benchmark_gap),
        ("runtime", plot_benchmark_runtime),
    ):
        fig = builder(results)
        path = target / f"{prefix}_{suffix}_{index}.png"
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        paths[suffix] = path

    return paths


def summarize_benchmark(results: list[BenchmarkRow]) -> list[dict[str, Any]]:
    """Aggrege les resultats par (size, algo) : moyenne / min / max du cout,
    moyenne du temps, nombre d'instances.
    """

    grouped = _group_by(results, "size", "algo")
    summary: list[dict[str, Any]] = []
    for (size, algo), rows in sorted(grouped.items()):
        costs = [r["cost"] for r in rows]
        times = [r["runtime"] for r in rows]
        summary.append(
            {
                "size": size,
                "algo": algo,
                "n_instances": len(rows),
                "cost_mean": sum(costs) / len(costs),
                "cost_min": min(costs),
                "cost_max": max(costs),
                "runtime_mean": sum(times) / len(times),
            }
        )
    return summary
