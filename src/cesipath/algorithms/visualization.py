"""Visualisation matplotlib des solutions VRP-CDR."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from ..models import EdgeStatus, GraphInstance
from .neighborhood import VRPSolution


DEFAULT_IMAGE_DIR = Path(__file__).resolve().parent / "image"


ROUTE_COLORS = [
    "#e74c3c",
    "#3498db",
    "#2ecc71",
    "#9b59b6",
    "#f39c12",
    "#1abc9c",
    "#e67e22",
    "#34495e",
    "#d35400",
    "#16a085",
    "#c0392b",
    "#2980b9",
]


def plot_solution(
    instance: GraphInstance,
    solution: VRPSolution,
    *,
    ax: plt.Axes | None = None,
    show_residual: bool = True,
    title: str | None = None,
) -> plt.Figure | None:
    """Trace une solution VRP sur matplotlib.

    - Sous-tournees coloriees differemment, avec fleches de sens de parcours.
    - Graphe residuel en fond (optionnel) pour situer les routes disponibles.
    """

    own_fig = ax is None
    fig: plt.Figure | None = None
    if own_fig:
        fig, ax = plt.subplots(figsize=(10, 8))

    coords = instance.coordinates

    if show_residual:
        for (u, v), edge in instance.residual_edges.items():
            if edge.status == EdgeStatus.FORBIDDEN:
                continue
            x1, y1 = coords[u]
            x2, y2 = coords[v]
            ax.plot(
                [x1, x2],
                [y1, y2],
                color="#cccccc",
                linewidth=0.8,
                alpha=0.45,
                zorder=1,
            )

    for idx, route in enumerate(solution.routes):
        color = ROUTE_COLORS[idx % len(ROUTE_COLORS)]
        xs = [coords[node][0] for node in route]
        ys = [coords[node][1] for node in route]
        ax.plot(
            xs,
            ys,
            color=color,
            linewidth=2.2,
            alpha=0.9,
            zorder=2,
            label=f"r{idx + 1} ({len(route) - 2} clients)",
        )
        for i in range(len(route) - 1):
            x1, y1 = coords[route[i]]
            x2, y2 = coords[route[i + 1]]
            ax.annotate(
                "",
                xy=(x2, y2),
                xytext=(x1, y1),
                arrowprops={"arrowstyle": "->", "color": color, "lw": 1.4, "alpha": 0.9},
                zorder=3,
            )

    xs, ys, node_colors, sizes = [], [], [], []
    for node, (x, y) in coords.items():
        xs.append(x)
        ys.append(y)
        if node == instance.depot:
            node_colors.append("#264653")
            sizes.append(280)
        else:
            node_colors.append("#8ecae6")
            sizes.append(180)
    ax.scatter(xs, ys, c=node_colors, s=sizes, edgecolors="black", linewidths=0.8, zorder=4)
    for node, (x, y) in coords.items():
        ax.text(
            x,
            y + 2.5,
            f"v{node}",
            ha="center",
            va="bottom",
            fontsize=10,
            weight="bold",
            zorder=5,
        )

    ax.set_title(
        title
        or (
            f"Solution VRP - {solution.route_count} sous-tournees - "
            f"cout={solution.total_cost:.2f}"
        ),
        fontsize=13,
    )
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.grid(True, linestyle=":", alpha=0.35)
    ax.set_aspect("equal", adjustable="datalim")
    ax.legend(loc="best", fontsize=9, frameon=True)

    if own_fig and fig is not None:
        fig.tight_layout()
        return fig
    return None


def save_solution_plot(
    fig: plt.Figure,
    *,
    directory: Path | str | None = None,
    prefix: str = "png_result",
    dpi: int = 120,
) -> Path:
    """Sauvegarde la figure dans ``directory`` avec un numero auto-incremente.

    Le numero choisi est le plus petit entier >= 1 tel que
    ``<prefix>_<n>.png`` n'existe pas encore dans le dossier cible.
    """

    target = Path(directory) if directory is not None else DEFAULT_IMAGE_DIR
    target.mkdir(parents=True, exist_ok=True)

    index = 1
    while (target / f"{prefix}_{index}.png").exists():
        index += 1

    path = target / f"{prefix}_{index}.png"
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    return path
