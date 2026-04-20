"""Visualisation matplotlib des graphes CESIPATH."""

from __future__ import annotations

from dataclasses import dataclass

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.widgets import Button

from .dynamic_network import DynamicNetworkSimulator
from .graph_generator import GraphGenerator
from .models import DynamicGraphSnapshot, EdgeStatus, GraphInstance


@dataclass
class GraphVisualizationSession:
    """Session interactive pour faire avancer la dynamique du graphe."""

    instance: GraphInstance
    generator: GraphGenerator
    simulator: DynamicNetworkSimulator
    snapshot: DynamicGraphSnapshot
    fig: plt.Figure
    ax: plt.Axes
    button: Button


class GraphVisualizer:
    """Affichage statique et dynamique du reseau routier."""

    BASE_EDGE_COLOR = "#7a7a7a"
    ACTIVE_EDGE_COLOR = "#2a9d8f"
    SURCHARGED_EDGE_COLOR = "#7b2cbf"
    FORBIDDEN_EDGE_COLOR = "#c1121f"
    TEMP_DISABLED_EDGE_COLOR = "#f4a261"
    DEPOT_COLOR = "#264653"
    CLIENT_COLOR = "#8ecae6"

    def __init__(self, instance: GraphInstance, generator: GraphGenerator) -> None:
        self.instance = instance
        self.generator = generator

    def show_base_graph(self) -> plt.Figure:
        """Affiche le graphe de base avec ses couts."""

        fig, ax = plt.subplots(figsize=(10, 8))
        self._draw_base_graph(ax)
        fig.tight_layout()
        return fig

    def show_residual_graph(self) -> plt.Figure:
        """Affiche le graphe residuel apres contraintes statiques."""

        fig, ax = plt.subplots(figsize=(10, 8))
        self._draw_residual_graph(ax)
        fig.tight_layout()
        return fig

    def show_dynamic_graph(self) -> GraphVisualizationSession:
        """Affiche le graphe dynamique avec un bouton pour avancer d'un tour."""

        simulator = DynamicNetworkSimulator(self.instance, seed=self.generator.config.seed)
        snapshot = simulator.initialize_snapshot()
        fig, ax = plt.subplots(figsize=(11, 8))
        plt.subplots_adjust(bottom=0.16)
        button_ax = fig.add_axes([0.82, 0.03, 0.12, 0.07])
        button = Button(button_ax, "->")

        session = GraphVisualizationSession(
            instance=self.instance,
            generator=self.generator,
            simulator=simulator,
            snapshot=snapshot,
            fig=fig,
            ax=ax,
            button=button,
        )
        self._draw_dynamic_graph(session)

        def advance(_: object) -> None:
            self.advance_session(session)

        button.on_clicked(advance)
        return session

    def advance_session(self, session: GraphVisualizationSession) -> None:
        """Fait avancer une session dynamique d'un tour."""

        session.snapshot = session.simulator.advance(session.snapshot)
        self._draw_dynamic_graph(session)
        session.fig.canvas.draw_idle()

    def _draw_base_graph(self, ax: plt.Axes) -> None:
        ax.clear()
        for (u, v), edge in self.instance.base_edges.items():
            self._draw_edge(
                ax,
                u,
                v,
                label=f"{edge.base_cost:.2f}",
                color=self.BASE_EDGE_COLOR,
                linestyle="-",
            )
        self._draw_nodes(ax)
        self._apply_axes_style(ax, "Graphe de base")
        self._draw_legend(
            ax,
            [
                ("Route de base", self.BASE_EDGE_COLOR, "-"),
            ],
        )

    def _draw_residual_graph(self, ax: plt.Axes) -> None:
        ax.clear()
        for (u, v), edge in self.instance.residual_edges.items():
            if edge.status == EdgeStatus.FORBIDDEN:
                self._draw_edge(
                    ax,
                    u,
                    v,
                    label="interdit",
                    color=self.FORBIDDEN_EDGE_COLOR,
                    linestyle="--",
                )
            elif edge.status == EdgeStatus.SURCHARGED:
                self._draw_edge(
                    ax,
                    u,
                    v,
                    label=f"{edge.static_cost:.2f}",
                    color=self.SURCHARGED_EDGE_COLOR,
                    linestyle="-",
                )
            else:
                self._draw_edge(
                    ax,
                    u,
                    v,
                    label=f"{edge.static_cost:.2f}",
                    color=self.ACTIVE_EDGE_COLOR,
                    linestyle="-",
                )
        self._draw_nodes(ax)
        self._apply_axes_style(ax, "Graphe residuel")
        self._draw_legend(
            ax,
            [
                ("Route libre", self.ACTIVE_EDGE_COLOR, "-"),
                ("Route surchargee", self.SURCHARGED_EDGE_COLOR, "-"),
                ("Route interdite", self.FORBIDDEN_EDGE_COLOR, "--"),
            ],
        )

    def _draw_dynamic_graph(self, session: GraphVisualizationSession) -> None:
        ax = session.ax
        ax.clear()

        for (u, v), edge in self.instance.residual_edges.items():
            if edge.status == EdgeStatus.FORBIDDEN:
                self._draw_edge(
                    ax,
                    u,
                    v,
                    label="interdit",
                    color=self.FORBIDDEN_EDGE_COLOR,
                    linestyle="--",
                )
                continue

            available = session.snapshot.edge_availability.get((u, v), False)
            if not available:
                self._draw_edge(
                    ax,
                    u,
                    v,
                    label="OFF",
                    color=self.TEMP_DISABLED_EDGE_COLOR,
                    linestyle="--",
                )
                continue

            color = self.ACTIVE_EDGE_COLOR
            if edge.status == EdgeStatus.SURCHARGED:
                color = self.SURCHARGED_EDGE_COLOR

            dynamic_cost = session.snapshot.edge_costs[(u, v)]
            self._draw_edge(
                ax,
                u,
                v,
                label=f"{dynamic_cost:.2f}",
                color=color,
                linestyle="-",
            )

        self._draw_nodes(ax)
        active_edge_count = session.snapshot.active_edge_count
        total_dynamic_edges = len(session.snapshot.edge_availability)
        max_edges = self.instance.node_count * (self.instance.node_count - 1) / 2
        active_density = active_edge_count / max_edges if max_edges else 0.0
        disabled_ratio = (
            (total_dynamic_edges - active_edge_count) / total_dynamic_edges
            if total_dynamic_edges
            else 0.0
        )
        title = (
            f"Graphe dynamique - tour {session.snapshot.step}\n"
            f"aretes actives={active_edge_count} | densite active={active_density:.3f} | ratio OFF={disabled_ratio:.3f}"
        )
        self._apply_axes_style(ax, title)
        self._draw_legend(
            ax,
            [
                ("Route active", self.ACTIVE_EDGE_COLOR, "-"),
                ("Route active surchargee", self.SURCHARGED_EDGE_COLOR, "-"),
                ("Route interdite statique", self.FORBIDDEN_EDGE_COLOR, "--"),
                ("Route indisponible dynamique", self.TEMP_DISABLED_EDGE_COLOR, "--"),
            ],
        )

    def _draw_edge(
        self,
        ax: plt.Axes,
        u: int,
        v: int,
        *,
        label: str,
        color: str,
        linestyle: str,
    ) -> None:
        x1, y1 = self.instance.coordinates[u]
        x2, y2 = self.instance.coordinates[v]
        ax.plot([x1, x2], [y1, y2], color=color, linestyle=linestyle, linewidth=2, alpha=0.9, zorder=1)

        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        ax.text(
            mid_x,
            mid_y,
            label,
            fontsize=8,
            color="#222222",
            ha="center",
            va="center",
            bbox={"facecolor": "white", "edgecolor": color, "boxstyle": "round,pad=0.2", "alpha": 0.85},
            zorder=3,
        )

    def _draw_nodes(self, ax: plt.Axes) -> None:
        xs = []
        ys = []
        colors = []
        sizes = []

        for node, (x, y) in self.instance.coordinates.items():
            xs.append(x)
            ys.append(y)
            if node == self.instance.depot:
                colors.append(self.DEPOT_COLOR)
                sizes.append(260)
            else:
                colors.append(self.CLIENT_COLOR)
                sizes.append(180)

        ax.scatter(xs, ys, c=colors, s=sizes, edgecolors="black", linewidths=0.8, zorder=4)

        for node, (x, y) in self.instance.coordinates.items():
            ax.text(x, y + 2.5, f"v{node}", ha="center", va="bottom", fontsize=10, weight="bold", zorder=5)

    def _apply_axes_style(self, ax: plt.Axes, title: str) -> None:
        ax.set_title(title, fontsize=13)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.grid(True, linestyle=":", alpha=0.35)
        ax.set_aspect("equal", adjustable="datalim")

    @staticmethod
    def _draw_legend(ax: plt.Axes, items: list[tuple[str, str, str]]) -> None:
        handles = [
            Line2D([0], [0], color=color, lw=2, linestyle=linestyle, label=label)
            for label, color, linestyle in items
        ]
        ax.legend(handles=handles, loc="upper left", frameon=True)
