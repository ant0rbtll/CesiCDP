"""Visualisation matplotlib des graphes CESIPATH."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.widgets import Button

from .algorithms.grasp import grasp
from .algorithms.neighborhood import VRPSolution
from .dynamic_network import DynamicNetworkSimulator
from .graph_generator import GraphGenerator
from .models import DynamicGraphSnapshot, EdgeStatus, GraphInstance
from .solver_input import build_dynamic_solver_input


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
    solution: VRPSolution | None = None
    animation: FuncAnimation | None = None
    truck_artist: AnnotationBbox | None = None


class GraphVisualizer:
    """Affichage statique et dynamique du reseau routier."""

    BASE_EDGE_COLOR = "#7a7a7a"
    ACTIVE_EDGE_COLOR = "#2a9d8f"
    SURCHARGED_EDGE_COLOR = "#7b2cbf"
    FORBIDDEN_EDGE_COLOR = "#c1121f"
    TEMP_DISABLED_EDGE_COLOR = "#f4a261"
    DEPOT_COLOR = "#264653"
    CLIENT_COLOR = "#8ecae6"
    ROUTE_COLOR = "#ff7b00"
    ROUTE_ALT_COLOR = "#2a9d8f"
    TRUCK_ZOOM = 0.12
    ANIMATION_INTERVAL_MS = 90
    FRAMES_PER_EDGE = 16

    def __init__(self, instance: GraphInstance, generator: GraphGenerator) -> None:
        self.instance = instance
        self.generator = generator
        self._truck_left, self._truck_right = self._load_truck_sprites()

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
        self._stop_animation(session)
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

        session.solution = self._compute_dynamic_solution(session)
        if session.solution is not None:
            self._draw_solution_overlay(ax, session.solution)

        title = (
            f"Graphe dynamique - tour {session.snapshot.step}\n"
            f"aretes actives={active_edge_count} | densite active={active_density:.3f} | ratio OFF={disabled_ratio:.3f}"
        )
        if session.solution is not None:
            title += f"\nGRASP: cout={session.solution.total_cost:.2f} | routes={session.solution.route_count}"
        self._apply_axes_style(ax, title)
        legend_items = [
            ("Route active", self.ACTIVE_EDGE_COLOR, "-"),
            ("Route active surchargee", self.SURCHARGED_EDGE_COLOR, "-"),
            ("Route interdite statique", self.FORBIDDEN_EDGE_COLOR, "--"),
            ("Route indisponible dynamique", self.TEMP_DISABLED_EDGE_COLOR, "--"),
        ]
        if session.solution is not None:
            legend_items.append(("Trajet GRASP", self.ROUTE_COLOR, "-"))
        self._draw_legend(ax, legend_items)

        if session.solution is not None:
            self._start_truck_animation(session)

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

    def _compute_dynamic_solution(self, session: GraphVisualizationSession) -> VRPSolution | None:
        """Calcule une solution dynamique via GRASP pour animer le camion."""

        solver_input = build_dynamic_solver_input(self.instance, session.snapshot)
        seed_base = self.generator.config.seed or 0
        try:
            return grasp(
                solver_input,
                max_iterations=40,
                rcl_alpha=0.3,
                use_local_search=False,
                seed=seed_base + session.snapshot.step,
            )
        except Exception:
            return None

    def _draw_solution_overlay(self, ax: plt.Axes, solution: VRPSolution) -> None:
        """Dessine les routes de solution pour contextualiser l'animation."""

        for idx, route in enumerate(solution.routes):
            if len(route) < 2:
                continue
            xs = [self.instance.coordinates[node][0] for node in route]
            ys = [self.instance.coordinates[node][1] for node in route]
            if idx == 0:
                ax.plot(xs, ys, color=self.ROUTE_COLOR, linewidth=3.0, alpha=0.95, zorder=6)
            else:
                ax.plot(xs, ys, color=self.ROUTE_ALT_COLOR, linewidth=1.6, alpha=0.55, zorder=5)

    def _primary_route_coords(self, solution: VRPSolution) -> list[tuple[float, float]]:
        for route in solution.routes:
            if len(route) >= 2:
                return [self.instance.coordinates[node] for node in route]
        return []

    def _start_truck_animation(self, session: GraphVisualizationSession) -> None:
        route_coords = self._primary_route_coords(session.solution) if session.solution else []
        if len(route_coords) < 2:
            return

        frames: list[tuple[float, float, float]] = []
        for (x1, y1), (x2, y2) in zip(route_coords, route_coords[1:]):
            for step in range(self.FRAMES_PER_EDGE):
                t = step / self.FRAMES_PER_EDGE
                x = x1 + (x2 - x1) * t
                y = y1 + (y2 - y1) * t
                dx = x2 - x1
                frames.append((x, y, dx))
        last_x, last_y = route_coords[-1]
        frames.append((last_x, last_y, 0.0))

        initial_sprite = self._truck_right if self._truck_right is not None else self._truck_left
        if initial_sprite is None:
            return

        image_box = OffsetImage(initial_sprite, zoom=self.TRUCK_ZOOM)
        artist = AnnotationBbox(
            image_box,
            (frames[0][0], frames[0][1]),
            frameon=False,
            box_alignment=(0.5, 0.5),
            zorder=9,
        )
        session.ax.add_artist(artist)
        session.truck_artist = artist

        def _update(frame_idx: int):
            x, y, dx = frames[frame_idx]
            artist.xy = (x, y)
            if dx < 0 and self._truck_left is not None:
                image_box.set_data(self._truck_left)
            elif dx >= 0 and self._truck_right is not None:
                image_box.set_data(self._truck_right)
            return (artist,)

        session.animation = FuncAnimation(
            session.fig,
            _update,
            frames=len(frames),
            interval=self.ANIMATION_INTERVAL_MS,
            blit=False,
            repeat=True,
        )

    @staticmethod
    def _stop_animation(session: GraphVisualizationSession) -> None:
        if session.animation is not None:
            session.animation.event_source.stop()
            session.animation = None
        session.truck_artist = None

    @staticmethod
    def _load_sprite(path: Path):
        if not path.exists():
            return None
        try:
            return mpimg.imread(path)
        except Exception:
            return None

    def _load_truck_sprites(self):
        project_root = Path(__file__).resolve().parents[2]
        left = self._load_sprite(project_root / "image" / "camionG.png")
        right = self._load_sprite(project_root / "image" / "camionD.png")
        return left, right
