"""Harnais de benchmark pour l'execution dynamique."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

import matplotlib.pyplot as plt

from ..dynamic_network import DynamicNetworkSimulator
from ..graph_generator import GraphGenerator
from ..models import GraphGenerationConfig
from .dynamic_runner import DynamicExecution, execute_dynamic
from .neighborhood import VRPSolution
from .visualization import DEFAULT_IMAGE_DIR


SolverFn = Callable[..., VRPSolution]
DynamicBenchmarkRow = dict[str, Any]


def run_dynamic_benchmark(
    sizes: list[int],
    instance_seeds: list[int],
    sim_seeds: list[int],
    algos: dict[str, SolverFn],
    *,
    algo_kwargs: dict[str, dict[str, Any]] | None = None,
    strategies: tuple[str, ...] = ("fixed", "reopt"),
    verbose: bool = True,
) -> list[DynamicBenchmarkRow]:
    """Lance ``algos`` en dynamique sur (sizes x instance_seeds x sim_seeds).

    Pour chaque combinaison on execute ``fixed`` (plan initial suivi jusqu'au
    bout) et/ou ``reopt`` (re-resolution a chaque retour au depot). Les
    strategies peuvent etre filtrees via le parametre ``strategies``.
    """

    algo_kwargs = algo_kwargs or {}
    results: list[DynamicBenchmarkRow] = []

    for size in sizes:
        for inst_seed in instance_seeds:
            cfg = GraphGenerationConfig(node_count=size, seed=inst_seed)
            instance = GraphGenerator(cfg).generate()

            for sim_seed in sim_seeds:
                if verbose:
                    print(f"[dyn-bench] size={size} inst_seed={inst_seed} sim_seed={sim_seed}")

                for algo_name, fn in algos.items():
                    kwargs = dict(algo_kwargs.get(algo_name, {}))
                    kwargs.setdefault("seed", inst_seed)

                    for strategy in strategies:
                        simulator = DynamicNetworkSimulator(instance, seed=sim_seed)
                        execution = execute_dynamic(
                            instance,
                            simulator,
                            fn,
                            solver_kwargs=kwargs,
                            reoptimize_at_depot=(strategy == "reopt"),
                        )
                        results.append(
                            {
                                "size": size,
                                "instance_seed": inst_seed,
                                "sim_seed": sim_seed,
                                "algo": algo_name,
                                "strategy": strategy,
                                "planned_cost": execution.planned_cost,
                                "realized_cost": execution.realized_cost,
                                "reoptimizations": execution.reoptimizations,
                                "solver_time": execution.solver_time,
                                "steps": execution.total_steps,
                            }
                        )

    return results


def _ordered_unique(values: list) -> list:
    seen = []
    for v in values:
        if v not in seen:
            seen.append(v)
    return seen


def _algo_palette(algos: list[str]) -> dict[str, str]:
    base = ["#3498db", "#e74c3c", "#2ecc71", "#9b59b6", "#f39c12", "#1abc9c"]
    return {algo: base[i % len(base)] for i, algo in enumerate(algos)}


def plot_dynamic_cost_comparison(
    results: list[DynamicBenchmarkRow],
    *,
    title: str = "Cout realise dynamique par strategie",
) -> plt.Figure:
    """Bar chart : cout realise moyen par algo x strategie, groupe par taille."""

    sizes = _ordered_unique([r["size"] for r in results])
    algos = _ordered_unique([r["algo"] for r in results])
    strategies = _ordered_unique([r["strategy"] for r in results])
    palette = _algo_palette(algos)

    fig, axes = plt.subplots(1, len(sizes), figsize=(5 * len(sizes), 5), sharey=False)
    if len(sizes) == 1:
        axes = [axes]

    for ax, size in zip(axes, sizes):
        width = 0.8 / max(len(algos), 1)
        for a_idx, algo in enumerate(algos):
            heights = []
            for strat in strategies:
                values = [
                    r["realized_cost"]
                    for r in results
                    if r["size"] == size and r["algo"] == algo and r["strategy"] == strat
                ]
                heights.append(sum(values) / len(values) if values else 0.0)
            positions = [i + (a_idx - (len(algos) - 1) / 2) * width for i in range(len(strategies))]
            ax.bar(
                positions,
                heights,
                width=width * 0.9,
                color=palette[algo],
                alpha=0.85,
                label=algo if ax is axes[0] else None,
            )
        ax.set_xticks(range(len(strategies)))
        ax.set_xticklabels(strategies)
        ax.set_xlabel("Strategie")
        ax.set_ylabel("Cout realise moyen")
        ax.set_title(f"n = {size}")
        ax.grid(True, axis="y", linestyle=":", alpha=0.4)

    fig.suptitle(title, fontsize=13)
    axes[0].legend(loc="best", frameon=True)
    fig.tight_layout()
    return fig


def plot_dynamic_gain(
    results: list[DynamicBenchmarkRow],
    *,
    title: str = "Gain de la re-optimisation vs plan fige (%)",
) -> plt.Figure:
    """Boxplot du gain relatif (fixed - reopt) / fixed par taille x algo.

    Un gain positif signifie que la re-optimisation reduit le cout realise.
    """

    sizes = _ordered_unique([r["size"] for r in results])
    algos = _ordered_unique([r["algo"] for r in results])
    palette = _algo_palette(algos)

    gain_lookup: dict[tuple[int, str, int, int], float] = {}
    fixed = {
        (r["size"], r["algo"], r["instance_seed"], r["sim_seed"]): r["realized_cost"]
        for r in results
        if r["strategy"] == "fixed"
    }
    reopt = {
        (r["size"], r["algo"], r["instance_seed"], r["sim_seed"]): r["realized_cost"]
        for r in results
        if r["strategy"] == "reopt"
    }
    for key in fixed:
        if key in reopt and fixed[key] > 0:
            gain_lookup[key] = 100.0 * (fixed[key] - reopt[key]) / fixed[key]

    fig, ax = plt.subplots(figsize=(10, 6))
    width = 0.8 / max(len(algos), 1)

    for a_idx, algo in enumerate(algos):
        data = [
            [gain_lookup[(size, algo, i, s)] for (sz, alg, i, s) in gain_lookup if sz == size and alg == algo]
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

    ax.axhline(0, color="black", linewidth=0.6, linestyle="--", alpha=0.5)
    ax.set_xticks(range(len(sizes)))
    ax.set_xticklabels([str(s) for s in sizes])
    ax.set_xlabel("Taille du graphe (n)")
    ax.set_ylabel("Gain relatif (%)")
    ax.set_title(title)
    ax.grid(True, axis="y", linestyle=":", alpha=0.4)
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=palette[a], alpha=0.7) for a in algos]
    ax.legend(handles, algos, loc="best", frameon=True)
    fig.tight_layout()
    return fig


def plot_dynamic_planned_vs_realized(
    results: list[DynamicBenchmarkRow],
    *,
    title: str = "Cout planifie vs cout realise",
) -> plt.Figure:
    """Scatter : chaque point = (planned, realized) pour une instance donnee.

    La diagonale ``y = x`` correspond a un plan parfait. Les points au-dessus
    indiquent que le cout reel depasse le cout planifie (cas usuel).
    """

    algos = _ordered_unique([r["algo"] for r in results])
    palette = _algo_palette(algos)

    fig, ax = plt.subplots(figsize=(9, 7))
    all_vals = []
    for algo in algos:
        pts = [(r["planned_cost"], r["realized_cost"]) for r in results if r["algo"] == algo]
        if not pts:
            continue
        xs, ys = zip(*pts)
        all_vals.extend(xs)
        all_vals.extend(ys)
        ax.scatter(xs, ys, color=palette[algo], alpha=0.65, label=algo, s=40, edgecolors="white")

    if all_vals:
        lo, hi = min(all_vals), max(all_vals)
        ax.plot([lo, hi], [lo, hi], color="black", linestyle="--", linewidth=1, alpha=0.5, label="y = x")

    ax.set_xlabel("Cout planifie (step 0)")
    ax.set_ylabel("Cout realise (coûts dynamiques)")
    ax.set_title(title)
    ax.grid(True, linestyle=":", alpha=0.4)
    ax.legend(loc="best", frameon=True)
    fig.tight_layout()
    return fig


def save_dynamic_benchmark_figures(
    results: list[DynamicBenchmarkRow],
    *,
    directory: Path | str | None = None,
    dpi: int = 120,
) -> dict[str, Path]:
    """Sauvegarde les 3 figures de benchmark dynamique avec index auto-incremente."""

    target = Path(directory) if directory is not None else DEFAULT_IMAGE_DIR
    target.mkdir(parents=True, exist_ok=True)

    index = 1
    prefix = "dynamic"
    while any(
        (target / f"{prefix}_{suffix}_{index}.png").exists()
        for suffix in ("cost", "gain", "scatter")
    ):
        index += 1

    paths: dict[str, Path] = {}
    for suffix, builder in (
        ("cost", plot_dynamic_cost_comparison),
        ("gain", plot_dynamic_gain),
        ("scatter", plot_dynamic_planned_vs_realized),
    ):
        fig = builder(results)
        path = target / f"{prefix}_{suffix}_{index}.png"
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        paths[suffix] = path

    return paths


def summarize_dynamic_benchmark(
    results: list[DynamicBenchmarkRow],
) -> list[dict[str, Any]]:
    """Agregat par (size, algo, strategy) : moyennes cout/temps, gain vs fixe."""

    grouped: dict[tuple, list[DynamicBenchmarkRow]] = defaultdict(list)
    for r in results:
        grouped[(r["size"], r["algo"], r["strategy"])].append(r)

    summary: list[dict[str, Any]] = []
    for (size, algo, strategy), rows in sorted(grouped.items()):
        realized = [r["realized_cost"] for r in rows]
        planned = [r["planned_cost"] for r in rows]
        times = [r["solver_time"] for r in rows]
        reopt = [r["reoptimizations"] for r in rows]
        summary.append(
            {
                "size": size,
                "algo": algo,
                "strategy": strategy,
                "n": len(rows),
                "planned_mean": sum(planned) / len(planned),
                "realized_mean": sum(realized) / len(realized),
                "realized_min": min(realized),
                "realized_max": max(realized),
                "solver_time_mean": sum(times) / len(times),
                "reoptimizations_mean": sum(reopt) / len(reopt),
            }
        )
    return summary
