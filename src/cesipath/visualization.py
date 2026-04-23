"""Visualisation matplotlib des graphes CESIPATH."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Callable

from matplotlib import colors as mcolors
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.text import Text
from matplotlib.widgets import Button, Slider

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
    button: Button | None = None
    speed_slider: Slider | None = None
    solution: VRPSolution | None = None
    animation: FuncAnimation | None = None
    truck_artist: AnnotationBbox | None = None
    dynamic_edge_artists: dict[tuple[int, int], tuple[Line2D, Text | None]] | None = None
    animation_paused: bool = True
    initial_pause_hook_id: int | None = None
    speed_multiplier: float = 1.0
    external_controls: bool = False
    title_callback: Callable[[str], None] | None = None
    info_callback: Callable[[str], None] | None = None
    legend_callback: Callable[[list[tuple[str, str, str]]], None] | None = None
    state_callback: Callable[[str], None] | None = None
    visualizer: "GraphVisualizer | None" = None
    show_legend: bool = True

    def set_speed(self, multiplier: float) -> None:
        """Ajuste la vitesse de lecture du camion (1.0 = cadence par defaut)."""

        if multiplier <= 0:
            return
        self.speed_multiplier = multiplier
        if self.animation is None:
            return
        new_interval = max(1, int(round(GraphVisualizer.ANIMATION_INTERVAL_MS / multiplier)))
        # TimedAnimation._step re-applique animation._interval a chaque frame;
        # il faut donc mettre a jour _interval en plus du timer backend.
        if hasattr(self.animation, "_interval"):
            self.animation._interval = new_interval
        event_source = self.animation.event_source
        if event_source is None:
            return
        was_running = not self.animation_paused
        if was_running:
            event_source.stop()
        event_source.interval = new_interval
        if was_running:
            event_source.start(interval=new_interval)

    def toggle(self) -> None:
        """Bascule lecture/pause de l'animation (API externe)."""

        if self.visualizer is not None:
            self.visualizer.toggle_animation(self)

    def play(self) -> None:
        """Force la lecture de l'animation."""

        if self.animation is None or self.animation.event_source is None:
            return
        if self.animation_paused:
            self.toggle()

    def pause(self) -> None:
        """Force la pause de l'animation."""

        if self.animation is None or self.animation.event_source is None:
            return
        if not self.animation_paused:
            self.toggle()


class GraphVisualizer:
    """Affichage statique et dynamique du reseau routier."""

    BASE_EDGE_COLOR = "#7a7a7a"
    ACTIVE_EDGE_COLOR = "#2a9d8f"
    SURCHARGED_EDGE_COLOR = "#7b2cbf"
    FORBIDDEN_EDGE_COLOR = "#c1121f"
    TEMP_DISABLED_EDGE_COLOR = "#f4a261"
    DEPOT_COLOR = "#264653"
    CLIENT_COLOR = "#8ecae6"
    TRANSIT_COLOR = "#6c757d"
    ROUTE_COLOR = "#1f4f8b"
    ROUTE_ALT_COLOR = "#2a9d8f"
    COST_LOW_COLOR = "#2ecc71"
    COST_MID_COLOR = "#f1c40f"
    COST_HIGH_COLOR = "#f39c12"
    COST_MAX_COLOR = "#e74c3c"
    TRUCK_ZOOM = 0.1728
    ANIMATION_INTERVAL_MS = 50
    FRAMES_PER_EDGE = 10
    MIN_FRAMES_PER_SUBEDGE = 1
    MAX_FRAMES_PER_SUBEDGE = 30
    DEPOT_PAUSE_FRAMES = 0

    def __init__(
        self,
        instance: GraphInstance,
        generator: GraphGenerator,
        *,
        background_renderer: Callable[[plt.Axes], None] | None = None,
        show_edge_labels: bool = True,
        show_node_labels: bool = True,
        show_grid: bool = True,
    ) -> None:
        self.instance = instance
        self.generator = generator
        self._background_renderer = background_renderer
        self._show_edge_labels = show_edge_labels
        self._show_node_labels = show_node_labels
        self._show_grid = show_grid
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

    def show_dynamic_graph(
        self,
        *,
        size: tuple[float, float] = (11, 8),
        external_controls: bool = False,
        show_legend: bool = True,
        title_callback: Callable[[str], None] | None = None,
        info_callback: Callable[[str], None] | None = None,
        legend_callback: Callable[[list[tuple[str, str, str]]], None] | None = None,
        state_callback: Callable[[str], None] | None = None,
    ) -> GraphVisualizationSession:
        """Affiche le graphe dynamique.

        Si external_controls=True, aucun bouton Start/Pause n'est cree dans la
        figure (titre, info et legende sont aussi routes via callbacks pour que
        l'hote tk dispose de tout l'espace du canvas pour la carte).
        """

        simulator = DynamicNetworkSimulator(self.instance, seed=self.generator.config.seed)
        snapshot = simulator.initialize_snapshot()
        fig, ax = plt.subplots(figsize=size)

        button: Button | None = None
        speed_slider: Slider | None = None
        if external_controls:
            fig.subplots_adjust(left=0.02, right=0.995, top=0.995, bottom=0.02)
        else:
            fig.subplots_adjust(left=0.015, right=0.995, top=0.99, bottom=0.12)
            speed_ax = fig.add_axes([0.10, 0.042, 0.58, 0.036])
            speed_slider = Slider(
                speed_ax,
                "Vitesse camion",
                0.5,
                25.0,
                valinit=3.0,
                valstep=0.5,
            )
            button_ax = fig.add_axes([0.74, 0.028, 0.20, 0.072])
            button = Button(button_ax, "Start")

        session = GraphVisualizationSession(
            instance=self.instance,
            generator=self.generator,
            simulator=simulator,
            snapshot=snapshot,
            fig=fig,
            ax=ax,
            button=button,
            speed_slider=speed_slider,
            external_controls=external_controls,
            visualizer=self,
            title_callback=title_callback,
            info_callback=info_callback,
            legend_callback=legend_callback,
            state_callback=state_callback,
            show_legend=show_legend,
        )
        self._draw_dynamic_graph(session)

        if button is not None:
            def toggle(_: object) -> None:
                self.toggle_animation(session)

            button.on_clicked(toggle)
        if speed_slider is not None:
            def _on_slider_speed(value: float) -> None:
                session.set_speed(float(value))

            speed_slider.on_changed(_on_slider_speed)
            session.set_speed(float(speed_slider.val))
        self._maximize_figure_window(fig)
        return session

    @staticmethod
    def _maximize_figure_window(fig: plt.Figure) -> None:
        """Essaie de maximiser la fenetre du popup matplotlib selon le backend."""

        manager = getattr(fig.canvas, "manager", None)
        if manager is None:
            return
        window = getattr(manager, "window", None)
        if window is None:
            return

        for maximize_call in ("wm_state", "state", "showMaximized"):
            try:
                fn = getattr(window, maximize_call, None)
                if fn is None:
                    continue
                if maximize_call in {"wm_state", "state"}:
                    fn("zoomed")
                else:
                    fn()
                return
            except Exception:
                continue

        # Fallback cross-platform: occuper quasi tout l'ecran sans plein ecran strict.
        try:
            screen_w = int(window.winfo_screenwidth())
            screen_h = int(window.winfo_screenheight())
            width = max(900, int(screen_w))
            height = max(700, int(screen_h))
            window.geometry(f"{width}x{height}+0+0")
        except Exception:
            return

    @staticmethod
    def _set_button_label(button: Button | None, label: str) -> None:
        if button is None:
            return
        button.label.set_text(label)
        button.ax.figure.canvas.draw_idle()

    @staticmethod
    def _emit_state(session: GraphVisualizationSession, state: str) -> None:
        """Pousse l'etat play/pause vers l'exterieur si un callback est cable."""

        if session.state_callback is not None:
            try:
                session.state_callback(state)
            except Exception:
                pass

    def toggle_animation(self, session: GraphVisualizationSession) -> None:
        """Bascule l'animation dynamique entre lecture et pause."""

        if session.animation is None:
            return
        event_source = session.animation.event_source
        if event_source is None:
            # Animation terminee: reinitialiser la scene pour un nouveau cycle.
            self._draw_dynamic_graph(session)
            session.fig.canvas.draw_idle()
            return
        if session.animation_paused:
            event_source.start()
            session.animation_paused = False
            self._set_button_label(session.button, "Pause")
            self._emit_state(session, "playing")
        else:
            event_source.stop()
            session.animation_paused = True
            self._set_button_label(session.button, "Start")
            self._emit_state(session, "paused")

    def advance_session(self, session: GraphVisualizationSession) -> None:
        """Fait avancer une session dynamique d'un tour."""

        session.snapshot = session.simulator.advance(session.snapshot)
        self._draw_dynamic_graph(session)
        session.fig.canvas.draw_idle()

    def _draw_base_graph(self, ax: plt.Axes) -> None:
        ax.clear()
        self._draw_background(ax)
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
        self._draw_background(ax)
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
        self._draw_background(ax)
        edge_artists: dict[tuple[int, int], tuple[Line2D, Text | None]] = {}
        for (u, v), edge in self.instance.residual_edges.items():
            color, linestyle, label = self._dynamic_edge_style(session.snapshot, (u, v), edge)
            edge_artists[(u, v)] = self._draw_edge(
                ax,
                u,
                v,
                label=label,
                color=color,
                linestyle=linestyle,
            )
        session.dynamic_edge_artists = edge_artists

        self._draw_nodes(ax)
        session.solution = self._compute_dynamic_solution(session)
        if session.solution is not None:
            self._draw_solution_overlay(ax, session.solution)

        title = self._dynamic_title(session.snapshot, session.solution)
        self._apply_axes_style(ax, title, session=session)
        legend_items = [
            ("Route interdite", self.FORBIDDEN_EDGE_COLOR, "--"),
            ("Route indisponible", self.TEMP_DISABLED_EDGE_COLOR, "--"),
        ]
        if session.solution is not None:
            legend_items.insert(0, ("Trajet en cours", self.ROUTE_COLOR, "-"))
        if session.show_legend:
            if session.legend_callback is not None:
                try:
                    session.legend_callback(legend_items)
                except Exception:
                    pass
            else:
                self._draw_dynamic_legend(ax, include_route=session.solution is not None)

        if session.solution is not None:
            self._start_truck_animation(session)

    def _dynamic_edge_style(
        self,
        snapshot: DynamicGraphSnapshot,
        edge_key: tuple[int, int],
        edge,
    ) -> tuple[str, str, str]:
        """Retourne style + label pour l'etat dynamique courant d'une arete."""

        if edge.status == EdgeStatus.FORBIDDEN:
            return self.FORBIDDEN_EDGE_COLOR, "--", "interdit"

        available = snapshot.edge_availability.get(edge_key, False)
        if not available:
            return self.TEMP_DISABLED_EDGE_COLOR, "--", ""

        dynamic_cost = snapshot.edge_costs[edge_key]
        return self._dynamic_cost_color(edge, dynamic_cost), "-", ""

    def _dynamic_cost_color(self, edge, dynamic_cost: float) -> str:
        """Convertit un cout dynamique en couleur (vert -> jaune -> orange -> rouge)."""

        static_cost = edge.static_cost
        if static_cost in (0, float("inf")):
            return self.COST_MAX_COLOR

        base_cost = float(edge.base_cost)
        max_cost = static_cost * self.instance.config.dynamic_max_multiplier
        if max_cost <= base_cost:
            ratio = 1.0 if dynamic_cost > base_cost else 0.0
        else:
            ratio = (dynamic_cost - base_cost) / (max_cost - base_cost)
        ratio = max(0.0, min(1.0, ratio))
        return self._interpolate_cost_color(ratio)

    def _interpolate_cost_color(self, ratio: float) -> str:
        if ratio <= 0.5:
            local_t = ratio / 0.5
            return self._mix_hex_color(self.COST_LOW_COLOR, self.COST_MID_COLOR, local_t)
        if ratio <= 0.8:
            local_t = (ratio - 0.5) / 0.3
            return self._mix_hex_color(self.COST_MID_COLOR, self.COST_HIGH_COLOR, local_t)
        local_t = (ratio - 0.8) / 0.2
        return self._mix_hex_color(self.COST_HIGH_COLOR, self.COST_MAX_COLOR, local_t)

    @staticmethod
    def _mix_hex_color(color_a: str, color_b: str, factor: float) -> str:
        factor = max(0.0, min(1.0, factor))

        def _hex_to_rgb(value: str) -> tuple[int, int, int]:
            value = value.lstrip("#")
            return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

        ar, ag, ab = _hex_to_rgb(color_a)
        br, bg, bb = _hex_to_rgb(color_b)
        rr = int(round(ar + (br - ar) * factor))
        rg = int(round(ag + (bg - ag) * factor))
        rb = int(round(ab + (bb - ab) * factor))
        return f"#{rr:02x}{rg:02x}{rb:02x}"

    def _dynamic_title(self, snapshot: DynamicGraphSnapshot, solution: VRPSolution | None) -> str:
        static_blocked = sum(
            1
            for edge in self.instance.residual_edges.values()
            if edge.status == EdgeStatus.FORBIDDEN
        )
        dynamic_blocked = len(snapshot.edge_availability) - snapshot.active_edge_count
        total_blocked = static_blocked + dynamic_blocked

        lines = [f"Simulation livraison   •   Tour n°{snapshot.step}"]
        if solution is not None:
            total_clients = sum(
                max(0, len(route) - 2)
                for route in solution.routes
                if len(route) >= 2
            )
            lines.append(
                f"{solution.route_count} tournee(s) planifiee(s)   |   "
                f"{total_clients} livraison(s) a effectuer   |   "
                f"Distance planifiee : {solution.total_cost:.0f}"
            )
        lines.append(
            f"Routes indisponibles : {total_blocked}   "
            f"(structurelles : {static_blocked}   •   trafic : {dynamic_blocked})"
        )
        return "\n".join(lines)

    def _draw_background(self, ax: plt.Axes) -> None:
        if self._background_renderer is None:
            return
        try:
            self._background_renderer(ax)
        except Exception:
            return

    def _refresh_dynamic_edge_artists(
        self,
        session: GraphVisualizationSession,
        snapshot: DynamicGraphSnapshot,
    ) -> None:
        if not session.dynamic_edge_artists:
            return
        for edge_key, artists in session.dynamic_edge_artists.items():
            edge = self.instance.residual_edges[edge_key]
            color, linestyle, label = self._dynamic_edge_style(snapshot, edge_key, edge)
            line_artist, label_artist = artists
            line_artist.set_color(color)
            line_artist.set_linestyle(linestyle)
            if label_artist is not None:
                label_artist.set_text(label)
                bbox_patch = label_artist.get_bbox_patch()
                if bbox_patch is not None:
                    bbox_patch.set_edgecolor(color)
        title = self._dynamic_title(snapshot, session.solution)
        if session.title_callback is not None:
            try:
                session.title_callback(title)
            except Exception:
                pass
        else:
            session.ax.set_title(title, fontsize=13)

    def _draw_edge(
        self,
        ax: plt.Axes,
        u: int,
        v: int,
        *,
        label: str,
        color: str,
        linestyle: str,
    ) -> tuple[Line2D, Text | None]:
        x1, y1 = self.instance.coordinates[u]
        x2, y2 = self.instance.coordinates[v]
        line_artist, = ax.plot(
            [x1, x2],
            [y1, y2],
            color=color,
            linestyle=linestyle,
            linewidth=2,
            alpha=0.9,
            zorder=1,
        )

        if not self._show_edge_labels:
            return line_artist, None
        if not label:
            return line_artist, None

        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        text_artist = ax.text(
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
        return line_artist, text_artist

    def _draw_nodes(self, ax: plt.Axes) -> None:
        depot_x: list[float] = []
        depot_y: list[float] = []
        client_x: list[float] = []
        client_y: list[float] = []
        transit_x: list[float] = []
        transit_y: list[float] = []

        for node, (x, y) in self.instance.coordinates.items():
            if node == self.instance.depot:
                depot_x.append(x)
                depot_y.append(y)
                continue

            if self.instance.demands.get(node, 0) > 0:
                client_x.append(x)
                client_y.append(y)
            else:
                transit_x.append(x)
                transit_y.append(y)

        if transit_x:
            ax.scatter(
                transit_x,
                transit_y,
                c=self.TRANSIT_COLOR,
                s=24,
                alpha=0.45,
                edgecolors="none",
                zorder=3,
            )
        if client_x:
            ax.scatter(
                client_x,
                client_y,
                c=self.CLIENT_COLOR,
                s=170,
                edgecolors="black",
                linewidths=0.8,
                zorder=4,
            )
        if depot_x:
            ax.scatter(
                depot_x,
                depot_y,
                c=self.DEPOT_COLOR,
                s=280,
                edgecolors="black",
                linewidths=1.0,
                zorder=5,
            )

        if not self._show_node_labels:
            return
        y_values = [coord[1] for coord in self.instance.coordinates.values()]
        if y_values:
            y_span = max(y_values) - min(y_values)
            label_offset = (y_span * 0.02) if y_span > 0 else 0.02
        else:
            label_offset = 0.02
        for node, (x, y) in self.instance.coordinates.items():
            if node != self.instance.depot and self.instance.demands.get(node, 0) <= 0:
                continue
            ax.text(
                x,
                y + label_offset,
                f"v{node}",
                ha="center",
                va="bottom",
                fontsize=9,
                weight="bold",
                zorder=6,
            )

    def _apply_axes_style(
        self,
        ax: plt.Axes,
        title: str,
        *,
        session: GraphVisualizationSession | None = None,
    ) -> None:
        if session is not None and session.title_callback is not None:
            try:
                session.title_callback(title)
            except Exception:
                pass
            ax.set_title("")
        else:
            ax.set_title(title, fontsize=13)
        if session is not None:
            ax.set_xlabel("")
            ax.set_ylabel("")
            ax.tick_params(axis="both", which="both", length=0, labelsize=0)
            for spine in ax.spines.values():
                spine.set_visible(False)
        else:
            if self._background_renderer is None:
                ax.set_xlabel("X")
                ax.set_ylabel("Y")
            else:
                ax.set_xlabel("Longitude")
                ax.set_ylabel("Latitude")
        if self._show_grid:
            ax.grid(True, linestyle=":", alpha=0.35)
        else:
            ax.grid(False)
        # "box" evite les warnings "Ignoring fixed x limits..." avec les fonds OSM.
        ax.set_aspect("equal", adjustable="box")

    @staticmethod
    def _draw_legend(ax: plt.Axes, items: list[tuple[str, str, str]]) -> None:
        handles = [
            Line2D([0], [0], color=color, lw=2, linestyle=linestyle, label=label)
            for label, color, linestyle in items
        ]
        ax.legend(handles=handles, loc="upper left", frameon=True)

    def _draw_dynamic_legend(self, ax: plt.Axes, *, include_route: bool) -> None:
        """Legende simplifiee pour une lecture metier (non technique)."""

        handles: list[Line2D] = []
        if include_route:
            handles.append(Line2D([0], [0], color=self.ROUTE_COLOR, lw=2.6, linestyle="-", label="Tournee en cours"))
        handles.append(
            Line2D([0], [0], color=self.FORBIDDEN_EDGE_COLOR, lw=2.2, linestyle="--", label="Route interdite")
        )
        handles.append(
            Line2D([0], [0], color=self.TEMP_DISABLED_EDGE_COLOR, lw=2.2, linestyle="--", label="Route indisponible")
        )
        ax.legend(handles=handles, loc="upper left", frameon=True, title="Lecture rapide")

        # Barre en degrade continue pour le niveau de trafic.
        grad_ax = ax.inset_axes([0.02, 0.86, 0.28, 0.03])
        cmap = mcolors.LinearSegmentedColormap.from_list(
            "traffic_scale",
            [self.COST_LOW_COLOR, self.COST_MID_COLOR, self.COST_HIGH_COLOR, self.COST_MAX_COLOR],
        )
        grad_ax.imshow([[0.0, 1.0]], cmap=cmap, aspect="auto", extent=(0, 1, 0, 1), interpolation="bilinear")
        grad_ax.set_yticks([])
        grad_ax.set_xticks([0.0, 1.0])
        grad_ax.set_xticklabels(["Fluide", "Charge"], fontsize=8)
        grad_ax.tick_params(axis="x", length=0, pad=1)
        for spine in grad_ax.spines.values():
            spine.set_visible(False)
        grad_ax.set_title("Niveau de trafic", fontsize=8, pad=1)

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

        for route in solution.routes:
            if len(route) < 2:
                continue
            real_route: list[int] = [route[0]]
            for u_log, v_log in zip(route, route[1:]):
                real_path = self._real_path_between(u_log, v_log)
                real_route.extend(real_path[1:])
            xs = [self.instance.coordinates[node][0] for node in real_route]
            ys = [self.instance.coordinates[node][1] for node in real_route]
            # Le parcours orange est reserve au passage reel du camion (trail anime).
            ax.plot(xs, ys, color=self.ROUTE_ALT_COLOR, linewidth=1.6, alpha=0.45, zorder=5)

    def _real_path_between(self, u: int, v: int) -> list[int]:
        """Renvoie la suite de vrais sommets entre deux sommets logiques.

        Utilise completed_paths (sortie de Dijkstra) pour developper une arete du
        graphe metrique en une sequence d'aretes residuelles reelles.
        """

        if u == v:
            return [u]
        key = (min(u, v), max(u, v))
        path = self.instance.completed_paths.get(key)
        if not path:
            return [u, v]
        if path[0] == u:
            return list(path)
        return list(reversed(path))

    def _solution_routes(self, solution: VRPSolution) -> list[list[int]]:
        """Retourne les routes animables (au moins une arete)."""

        return [route for route in solution.routes if len(route) >= 2]

    @staticmethod
    def _clone_simulator(instance: GraphInstance, simulator: DynamicNetworkSimulator) -> DynamicNetworkSimulator:
        """Clone un simulateur pour previsualisation sans consommer l'etat RNG live."""

        clone = DynamicNetworkSimulator(instance)
        clone.random.setstate(simulator.random.getstate())
        return clone

    def _frames_for_subedge(self, segment_len: float, ref_len: float) -> int:
        """Calcule le nombre de frames d'un sous-segment selon sa longueur reelle."""

        if segment_len <= 0:
            return self.MIN_FRAMES_PER_SUBEDGE
        if ref_len <= 0:
            return self.FRAMES_PER_EDGE
        scaled = int(round(self.FRAMES_PER_EDGE * (segment_len / ref_len)))
        return max(self.MIN_FRAMES_PER_SUBEDGE, min(self.MAX_FRAMES_PER_SUBEDGE, scaled))

    def _build_truck_frames(
        self,
        session: GraphVisualizationSession,
    ) -> tuple[
        list[tuple[float, float, float, int, int, int, int, int, int, int, float, int, int, int, int, bool, bool]],
        dict[int, DynamicGraphSnapshot],
    ]:
        """Construit une animation complete sur toutes les routes.

        Une arete logique (u,v) du graphe metrique est developpee via
        completed_paths en une suite de vraies aretes residuelles. Le simulateur
        dynamique n'avance qu'une fois par arete logique (a la fin), pour rester
        coherent avec l'instant ou GRASP a calcule la solution.

        Chaque frame contient:
        (x, y, dx, route_idx, total_routes, segment_idx, total_segments_route,
         snapshot_step, edge_idx, total_edges, step_cost,
         real_from, real_to, logical_from, logical_to,
         is_real_end, is_logical_end)
        """

        if session.solution is None:
            return [], {}
        routes = self._solution_routes(session.solution)
        if not routes:
            return [], {}

        total_edges = sum(len(route) - 1 for route in routes)
        if total_edges <= 0:
            return [], {}

        xs = [coord[0] for coord in self.instance.coordinates.values()]
        ys = [coord[1] for coord in self.instance.coordinates.values()]
        diag = math.hypot(max(xs) - min(xs), max(ys) - min(ys)) if xs and ys else 0.0
        # Longueur de reference pour adapter la fluidite aux segments courts/longs.
        ref_len = diag / 12.0 if diag > 0 else 1.0

        preview_simulator = self._clone_simulator(self.instance, session.simulator)
        rolling_snapshot = session.snapshot
        edge_snapshots: dict[int, DynamicGraphSnapshot] = {}
        frames: list[
            tuple[float, float, float, int, int, int, int, int, int, int, float, int, int, int, int, bool, bool]
        ] = []
        total_routes = len(routes)
        edge_idx = 0

        for route_idx, route in enumerate(routes, start=1):
            total_segments_route = len(route) - 1
            if total_segments_route <= 0:
                continue

            first_x, first_y = self.instance.coordinates[route[0]]
            first_real_path = self._real_path_between(route[0], route[1])
            if len(first_real_path) > 1:
                next_x, _ = self.instance.coordinates[first_real_path[1]]
            else:
                next_x = first_x
            first_dx = next_x - first_x
            first_snapshot_step = rolling_snapshot.step
            if not frames:
                frames.append(
                    (
                        first_x,
                        first_y,
                        first_dx,
                        route_idx,
                        total_routes,
                        0,
                        total_segments_route,
                        first_snapshot_step,
                        edge_idx,
                        total_edges,
                        0.0,
                        route[0],
                        route[0],
                        route[0],
                        route[0],
                        False,
                        False,
                    )
                )
            elif frames[-1][0] != first_x or frames[-1][1] != first_y:
                frames.append(
                    (
                        first_x,
                        first_y,
                        frames[-1][2],
                        route_idx,
                        total_routes,
                        0,
                        total_segments_route,
                        first_snapshot_step,
                        edge_idx,
                        total_edges,
                        0.0,
                        route[0],
                        route[0],
                        route[0],
                        route[0],
                        False,
                        False,
                    )
                )

            for segment_idx, (u_log, v_log) in enumerate(
                zip(route, route[1:]),
                start=1,
            ):
                edge_idx += 1
                edge_snapshots[edge_idx] = rolling_snapshot
                snapshot_step = rolling_snapshot.step
                step_cost = rolling_snapshot.completed_costs[u_log][v_log]

                real_path = self._real_path_between(u_log, v_log)
                real_sub_edges = list(zip(real_path, real_path[1:]))
                if not real_sub_edges:
                    real_sub_edges = [(u_log, v_log)]
                last_sub = len(real_sub_edges)

                for sub_idx, (ru, rv) in enumerate(real_sub_edges, start=1):
                    x1, y1 = self.instance.coordinates[ru]
                    x2, y2 = self.instance.coordinates[rv]
                    dx = x2 - x1
                    segment_len = math.hypot(x2 - x1, y2 - y1)
                    sub_frames = self._frames_for_subedge(segment_len, ref_len)
                    is_last_sub = sub_idx == last_sub
                    for step in range(1, sub_frames + 1):
                        t = step / sub_frames
                        is_real_end = step == sub_frames
                        is_logical_end = is_real_end and is_last_sub
                        frames.append(
                            (
                                x1 + (x2 - x1) * t,
                                y1 + (y2 - y1) * t,
                                dx,
                                route_idx,
                                total_routes,
                                segment_idx,
                                total_segments_route,
                                snapshot_step,
                                edge_idx,
                                total_edges,
                                step_cost,
                                ru,
                                rv,
                                u_log,
                                v_log,
                                is_real_end,
                                is_logical_end,
                            )
                        )

                if edge_idx < total_edges:
                    rolling_snapshot = preview_simulator.advance(rolling_snapshot)

            if route_idx < total_routes:
                end_x, end_y = self.instance.coordinates[route[-1]]
                hold_dx = frames[-1][2]
                hold_snapshot_step = rolling_snapshot.step
                for _ in range(self.DEPOT_PAUSE_FRAMES):
                    frames.append(
                        (
                            end_x,
                            end_y,
                            hold_dx,
                            route_idx,
                            total_routes,
                            total_segments_route,
                            total_segments_route,
                            hold_snapshot_step,
                            edge_idx,
                            total_edges,
                            0.0,
                            route[-1],
                            route[-1],
                            route[-1],
                            route[-1],
                            False,
                            False,
                        )
                    )

        return frames, edge_snapshots

    def _start_truck_animation(self, session: GraphVisualizationSession) -> None:
        if session.solution is None:
            return

        frames, edge_snapshots = self._build_truck_frames(session)
        if len(frames) < 2:
            return

        routes = self._solution_routes(session.solution)
        clients_per_route = [max(0, len(route) - 2) for route in routes]
        cumulative_delivered_before = [0]
        for count in clients_per_route:
            cumulative_delivered_before.append(cumulative_delivered_before[-1] + count)
        total_clients = cumulative_delivered_before[-1]

        initial_sprite = self._truck_right if self._truck_right is not None else self._truck_left
        if initial_sprite is None:
            return

        image_box = OffsetImage(initial_sprite, zoom=self.TRUCK_ZOOM)
        artist = AnnotationBbox(
            image_box,
            (frames[0][0], frames[0][1]),
            xybox=(frames[0][0], frames[0][1]),
            xycoords="data",
            boxcoords="data",
            frameon=False,
            box_alignment=(0.5, 0.5),
            zorder=9,
        )
        session.ax.add_artist(artist)
        session.truck_artist = artist

        trail_line, = session.ax.plot(
            [],
            [],
            color=self.ROUTE_COLOR,
            linewidth=3.2,
            alpha=0.96,
            zorder=8,
        )
        if session.info_callback is not None:
            info_text = None
        else:
            info_text = session.ax.text(
                0.02,
                0.98,
                "",
                transform=session.ax.transAxes,
                ha="left",
                va="top",
                fontsize=9,
                color="#102a43",
                bbox={"facecolor": "white", "edgecolor": "#cbd5e1", "boxstyle": "round,pad=0.25", "alpha": 0.9},
                zorder=10,
            )
        trail_x: list[float] = []
        trail_y: list[float] = []
        total_steps = len(frames)
        last_visual_edge = -1
        last_route_idx = -1
        visited_nodes: set[int] = set()
        visited_artists: dict[int, object] = {}

        def _mark_node_visited(node: int) -> None:
            if node in visited_nodes:
                return
            visited_nodes.add(node)
            x, y = self.instance.coordinates[node]
            if node == self.instance.depot:
                marker_size = 260
            elif self.instance.demands.get(node, 0) > 0:
                marker_size = 170
            else:
                marker_size = 50
            visited_artists[node] = session.ax.scatter(
                [x],
                [y],
                c=self.ROUTE_COLOR,
                s=marker_size,
                edgecolors="white",
                linewidths=0.9,
                zorder=7.8,
            )

        def _update(frame_idx: int):
            nonlocal last_visual_edge, last_route_idx
            if frame_idx == 0:
                trail_x.clear()
                trail_y.clear()
                trail_line.set_data([], [])
                last_visual_edge = -1
                last_route_idx = -1

            (
                x,
                y,
                dx,
                route_idx,
                route_total,
                segment_idx,
                segment_total,
                snapshot_step,
                edge_idx,
                edge_total,
                step_cost,
                real_from,
                real_to,
                logical_from,
                logical_to,
                is_real_end,
                is_logical_end,
            ) = frames[frame_idx]

            if route_idx != last_route_idx:
                trail_x.clear()
                trail_y.clear()
                trail_line.set_data([], [])
                last_route_idx = route_idx

            if edge_idx > 0 and edge_idx != last_visual_edge:
                snapshot_state = edge_snapshots.get(edge_idx)
                if snapshot_state is not None:
                    self._refresh_dynamic_edge_artists(session, snapshot_state)
                _mark_node_visited(logical_from)
                last_visual_edge = edge_idx

            artist.xy = (x, y)
            artist.xybox = (x, y)
            trail_x.append(x)
            trail_y.append(y)
            trail_line.set_data(trail_x, trail_y)

            if dx < -1e-9 and self._truck_left is not None:
                image_box.set_data(self._truck_left)
            elif dx > 1e-9 and self._truck_right is not None:
                image_box.set_data(self._truck_right)

            if is_real_end:
                _mark_node_visited(real_to)
            if is_logical_end and segment_idx == segment_total:
                # Fin de sous-tournee: on retire le trace bleu
                # pour revenir au rendu dynamique colore des aretes.
                trail_x.clear()
                trail_y.clear()
                trail_line.set_data([], [])

            route_pos = max(0, min(route_idx - 1, len(clients_per_route) - 1))
            clients_on_truck_at_start = clients_per_route[route_pos] if clients_per_route else 0
            delivered_this_route = segment_idx if is_logical_end else max(0, segment_idx - 1)
            delivered_this_route = min(delivered_this_route, clients_on_truck_at_start)
            current_load = max(0, clients_on_truck_at_start - delivered_this_route)
            delivered_total = cumulative_delivered_before[route_pos] + delivered_this_route
            delivered_total = min(delivered_total, total_clients)
            remaining_total = max(0, total_clients - delivered_total)

            if segment_idx == 0 or logical_to == self.instance.depot:
                destination_label = f"depot v{self.instance.depot}"
            else:
                destination_label = f"ville v{logical_to}"

            info_msg = (
                f"Tournee {route_idx}/{route_total}   •   destination : {destination_label}\n"
                f"Charge camion : {current_load} colis   "
                f"(livraison {delivered_this_route}/{clients_on_truck_at_start} sur cette tournee)\n"
                f"Villes restantes a livrer : {remaining_total}/{total_clients}"
            )
            if info_text is not None:
                info_text.set_text(info_msg)
            if session.info_callback is not None:
                try:
                    session.info_callback(info_msg)
                except Exception:
                    pass
            artists: list[object] = [artist, trail_line]
            if info_text is not None:
                artists.append(info_text)
            return tuple(artists)

        base_interval = max(1, int(round(self.ANIMATION_INTERVAL_MS / max(0.01, session.speed_multiplier))))
        session.animation = FuncAnimation(
            session.fig,
            _update,
            frames=len(frames),
            interval=base_interval,
            blit=False,
            repeat=False,
        )
        # Demarrage en pause: l'utilisateur lance explicitement via Start.
        event_source = session.animation.event_source
        if event_source is not None:
            event_source.stop()
        if session.initial_pause_hook_id is not None:
            session.fig.canvas.mpl_disconnect(session.initial_pause_hook_id)
            session.initial_pause_hook_id = None
        # Matplotlib peut relancer le timer sur le premier draw_event.
        # On force donc une pause juste apres ce premier rendu.
        def _pause_after_first_draw(_: object) -> None:
            if session.animation is not None and session.animation.event_source is not None:
                session.animation.event_source.stop()
            session.animation_paused = True
            self._set_button_label(session.button, "Start")
            if session.initial_pause_hook_id is not None:
                session.fig.canvas.mpl_disconnect(session.initial_pause_hook_id)
                session.initial_pause_hook_id = None

        session.initial_pause_hook_id = session.fig.canvas.mpl_connect("draw_event", _pause_after_first_draw)
        session.animation_paused = True
        self._set_button_label(session.button, "Start")

    @staticmethod
    def _stop_animation(session: GraphVisualizationSession) -> None:
        if session.animation is not None:
            event_source = session.animation.event_source
            if event_source is not None:
                event_source.stop()
            session.animation = None
        if session.initial_pause_hook_id is not None:
            session.fig.canvas.mpl_disconnect(session.initial_pause_hook_id)
            session.initial_pause_hook_id = None
        session.animation_paused = True
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
