"""Reconnaissance de quartier via graphe OSM.

- Noeuds: intersections
- Aretes: routes ponderees par distance
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import contextily as ctx
import networkx as nx
import numpy as np
import osmnx as ox
from contextily.tile import warp_tiles
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import FancyArrowPatch, Rectangle
from rasterio.enums import Resampling
from scipy.cluster.hierarchy import fclusterdata


class QuartierGraph:
    """Composant pour generer et visualiser un graphe de quartier."""

    def __init__(self, lieu: str, network_type: str = "drive") -> None:
        self.lieu = lieu
        self.network_type = network_type
        self.graph: nx.MultiGraph | None = None
        self._boundary_node_ids: set = set()

    def charger_quartier(self, distance: int = 1000) -> nx.MultiGraph:
        """Charge le graphe OSM autour d'un lieu, puis le convertit en non oriente."""

        directed_graph = ox.graph_from_address(
            self.lieu,
            dist=distance,
            network_type=self.network_type,
        )

        try:
            self.graph = ox.convert.to_undirected(directed_graph)
        except AttributeError:
            self.graph = nx.MultiGraph(directed_graph.to_undirected())

        return self.graph

    def obtenir_stats(self) -> dict:
        """Retourne les statistiques du graphe courant."""

        if self.graph is None:
            return {}

        is_connected = nx.is_connected(self.graph) if self.graph.number_of_nodes() else False
        return {
            "noeuds": self.graph.number_of_nodes(),
            "aretes": self.graph.number_of_edges(),
            "densite": nx.density(self.graph),
            "diametre": nx.diameter(self.graph) if is_connected else None,
        }

    def exporter_graphe(self, format: str = "graphml") -> str:
        """Exporte le graphe au format graphml, gexf ou json_graph."""

        if self.graph is None:
            raise ValueError("Charger le quartier d'abord (charger_quartier)")

        stem = self.lieu.split(",")[0].replace(" ", "_")
        if format not in {"graphml", "gexf", "json_graph"}:
            raise ValueError("format doit etre graphml, gexf ou json_graph")

        suffix = "json" if format == "json_graph" else format
        filepath = f"graphe_{stem}.{suffix}"

        if format == "graphml":
            nx.write_graphml(self.graph, filepath)
        elif format == "gexf":
            nx.write_gexf(self.graph, filepath)
        else:
            payload = nx.node_link_data(self.graph)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)

        return filepath

    def visualiser(
        self,
        output_path: Optional[str] = None,
        size: tuple[int, int] = (14, 10),
        show_arrows_oneway: bool = False,
    ) -> str:
        """Genere une image PNG superposant routes OSM et graphe theorique."""

        if self.graph is None:
            raise ValueError("Charger le quartier d'abord (charger_quartier)")

        default_name = f"graphe_{self.lieu.split(',')[0].replace(' ', '_')}.png"
        target = Path(output_path or default_name)
        if not target.is_absolute():
            target = Path.cwd() / target
        target.parent.mkdir(parents=True, exist_ok=True)

        fig = self.build_figure(size=size, show_arrows_oneway=show_arrows_oneway)
        FigureCanvasAgg(fig)

        fig.savefig(target, dpi=100, bbox_inches="tight")
        return str(target)

    def build_figure(
        self,
        *,
        size: tuple[int, int] = (14, 10),
        show_arrows_oneway: bool = False,
    ) -> Figure:
        """Construit une figure matplotlib prete a etre affichee ou imbriquee."""

        if self.graph is None:
            raise ValueError("Charger le quartier d'abord (charger_quartier)")

        fig = Figure(figsize=size)
        ax = fig.add_subplot(111)
        self._draw_graph(
            ax,
            show_arrows_oneway=show_arrows_oneway,
        )
        fig.tight_layout()
        return fig

    def _draw_graph(
        self,
        ax: Axes,
        *,
        show_arrows_oneway: bool,
    ) -> tuple[int, int, int, int]:
        if self.graph is None:
            raise ValueError("Charger le quartier d'abord (charger_quartier)")

        self._add_edge_boundary_nodes()

        node_x = [self.graph.nodes[node].get("x") for node in self.graph.nodes() if "x" in self.graph.nodes[node]]
        node_y = [self.graph.nodes[node].get("y") for node in self.graph.nodes() if "y" in self.graph.nodes[node]]

        if node_x and node_y:
            min_x, max_x = min(node_x), max(node_x)
            min_y, max_y = min(node_y), max(node_y)
            if min_x == max_x:
                min_x -= 1e-6
                max_x += 1e-6
            if min_y == max_y:
                min_y -= 1e-6
                max_y += 1e-6
            ax.set_xlim(min_x, max_x)
            ax.set_ylim(min_y, max_y)

        try:
            self._add_basemap_optimized(ax)
        except Exception:
            # Fallback robuste en cas d'echec du chemin optimise.
            try:
                ctx.add_basemap(
                    ax,
                    crs="EPSG:4326",
                    source=ctx.providers.CartoDB.Positron,
                    zoom=15,
                    alpha=0.9,
                    zorder=0,
                )
            except Exception:
                pass

        edge_count = 0
        edge_count_fallback = 0

        for u, v, key, data in self.graph.edges(keys=True, data=True):
            _ = key
            is_oneway = data.get("oneway", False)

            if "geometry" in data:
                try:
                    coords_list = list(data["geometry"].coords)
                    if len(coords_list) >= 2:
                        xs = [c[0] for c in coords_list]
                        ys = [c[1] for c in coords_list]
                        ax.plot(xs, ys, "#2563eb", linewidth=1.2, alpha=0.7, zorder=1)

                        show_arrow = show_arrows_oneway and is_oneway
                        if show_arrow:
                            self._draw_mid_arrow(ax, coords_list)
                        edge_count += 1
                except Exception:
                    pass
            else:
                try:
                    if u in self.graph.nodes() and v in self.graph.nodes():
                        x1 = self.graph.nodes[u].get("x")
                        y1 = self.graph.nodes[u].get("y")
                        x2 = self.graph.nodes[v].get("x")
                        y2 = self.graph.nodes[v].get("y")

                        if None not in (x1, y1, x2, y2):
                            ax.plot([x1, x2], [y1, y2], "#2563eb", linewidth=1.2, alpha=0.7, zorder=1)
                            show_arrow = show_arrows_oneway and is_oneway
                            if show_arrow:
                                self._draw_segment_arrow(ax, x1, y1, x2, y2)
                            edge_count_fallback += 1
                except Exception:
                    pass

        num_nodes = len(self.graph.nodes())
        num_edges = len([e for e in self.graph.edges(data=True) if "geometry" in e[2]])

        try:
            pos = {
                node: (data["x"], data["y"])
                for node, data in self.graph.nodes(data=True)
                if "x" in data and "y" in data
            }
            boundary_nodes = self._boundary_node_ids

            normal_nodes = {n: pos[n] for n in pos if n not in boundary_nodes}
            boundary_nodes_pos = {n: pos[n] for n in pos if n in boundary_nodes}

            if len(normal_nodes) > 1:
                coords = np.array([[pos[node][0], pos[node][1]] for node in normal_nodes])
                node_list = list(normal_nodes.keys())
                clusters = fclusterdata(coords, t=0.0002, criterion="distance", method="complete")

                cluster_dict: dict[int, list] = {}
                for i, cluster_id in enumerate(clusters):
                    cluster_dict.setdefault(int(cluster_id), []).append(node_list[i])

                for nodes in cluster_dict.values():
                    if len(nodes) == 1:
                        x, y = normal_nodes[nodes[0]]
                        ax.scatter(x, y, c="red", s=20, alpha=0.8, zorder=4, edgecolors="darkred", linewidth=1)
                    else:
                        most_connected = max(nodes, key=lambda n: self.graph.degree(n))
                        x, y = normal_nodes[most_connected]
                        size_val = 20 + len(nodes) * 5
                        ax.scatter(
                            x,
                            y,
                            c="red",
                            s=size_val,
                            alpha=0.8,
                            zorder=4,
                            edgecolors="darkred",
                            linewidth=1,
                        )
            elif len(normal_nodes) == 1:
                node = list(normal_nodes.keys())[0]
                x, y = normal_nodes[node]
                ax.scatter(x, y, c="red", s=20, alpha=0.8, zorder=4)

            if pos and boundary_nodes_pos:
                all_x = [pos[n][0] for n in pos]
                all_y = [pos[n][1] for n in pos]
                min_x_all, max_x_all = min(all_x), max(all_x)
                min_y_all, max_y_all = min(all_y), max(all_y)

                for node, (x, y) in boundary_nodes_pos.items():
                    _ = node
                    is_left = abs(x - min_x_all) < 1e-7
                    is_right = abs(x - max_x_all) < 1e-7
                    is_bottom = abs(y - min_y_all) < 1e-7
                    is_top = abs(y - max_y_all) < 1e-7

                    if is_left:
                        ax.plot([x, min_x_all], [y, y], "orange", linewidth=1.5, alpha=0.5, linestyle=":", zorder=4)
                    elif is_right:
                        ax.plot([x, max_x_all], [y, y], "orange", linewidth=1.5, alpha=0.5, linestyle=":", zorder=4)
                    elif is_bottom:
                        ax.plot([x, x], [y, min_y_all], "orange", linewidth=1.5, alpha=0.5, linestyle=":", zorder=4)
                    elif is_top:
                        ax.plot([x, x], [y, max_y_all], "orange", linewidth=1.5, alpha=0.5, linestyle=":", zorder=4)

                    ax.scatter(
                        x,
                        y,
                        c="orange",
                        s=80,
                        alpha=0.95,
                        zorder=6,
                        edgecolors="darkorange",
                        linewidth=2.5,
                        marker="^",
                    )
        except Exception:
            pass

        if node_x and node_y:
            min_x, max_x = min(node_x), max(node_x)
            min_y, max_y = min(node_y), max(node_y)
            rect = Rectangle(
                (min_x, min_y),
                max_x - min_x,
                max_y - min_y,
                linewidth=2,
                edgecolor="darkorange",
                facecolor="none",
                linestyle="--",
                alpha=0.7,
                zorder=3,
            )
            ax.add_patch(rect)

        ax.set_title(
            f"Routes + Graphe non oriente: {self.lieu}\\n"
            f"Routes (gris) | Graphe ({num_nodes} noeuds, {num_edges} aretes)",
            fontsize=12,
            fontweight="bold",
        )
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.grid(True, alpha=0.2)

        return edge_count, edge_count_fallback, num_nodes, num_edges

    def _add_basemap_optimized(self, ax: Axes) -> None:
        """Ajoute le fond de carte avec telechargement parallele des tuiles."""

        xmin, xmax = ax.get_xlim()
        ymin, ymax = ax.get_ylim()
        node_count = self.graph.number_of_nodes() if self.graph is not None else 0

        if node_count > 700:
            zoom = 13
        elif node_count > 320:
            zoom = 14
        else:
            zoom = 15

        image, extent = ctx.bounds2img(
            xmin,
            ymin,
            xmax,
            ymax,
            zoom=zoom,
            source=ctx.providers.CartoDB.Positron,
            ll=True,
            n_connections=4,
            use_cache=True,
            headers={"User-Agent": "CESIPATH/1.0"},
        )
        image, extent = warp_tiles(image, extent, t_crs="EPSG:4326", resampling=Resampling.bilinear)
        ax.imshow(
            image,
            extent=extent,
            interpolation="bilinear",
            aspect=ax.get_aspect(),
            zorder=0,
            alpha=0.9,
        )
        ax.axis((xmin, xmax, ymin, ymax))

    def _identify_boundary_nodes(self) -> set:
        """Identifie les noeuds situes sur les bords du graphe."""

        if self.graph is None:
            return set()

        coords_dict: dict = {}
        for node in self.graph.nodes():
            attrs = self.graph.nodes[node]
            if "x" in attrs and "y" in attrs:
                coords_dict[node] = (attrs["x"], attrs["y"])

        if not coords_dict:
            return set()

        xs = [c[0] for c in coords_dict.values()]
        ys = [c[1] for c in coords_dict.values()]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        boundary_nodes: set = set()
        for node, (x, y) in coords_dict.items():
            is_on_left = abs(x - min_x) < 1e-7
            is_on_right = abs(x - max_x) < 1e-7
            is_on_bottom = abs(y - min_y) < 1e-7
            is_on_top = abs(y - max_y) < 1e-7
            if is_on_left or is_on_right or is_on_bottom or is_on_top:
                boundary_nodes.add(node)

        return boundary_nodes

    def _add_edge_boundary_nodes(self) -> None:
        """Marque les noeuds de limite pour la visualisation."""

        self._boundary_node_ids = self._identify_boundary_nodes()

    @staticmethod
    def _draw_mid_arrow(ax: Axes, coords_list: list[tuple[float, float]]) -> None:
        mid_idx = len(coords_list) // 2
        if mid_idx > 0 and mid_idx < len(coords_list) - 1:
            before = coords_list[mid_idx - 1]
            after = coords_list[mid_idx]
        else:
            before = coords_list[0]
            after = coords_list[-1]

        offset = 0.2
        arrow_start_x = before[0] + (after[0] - before[0]) * (1 - offset)
        arrow_start_y = before[1] + (after[1] - before[1]) * (1 - offset)

        arrow = FancyArrowPatch(
            (arrow_start_x, arrow_start_y),
            (after[0], after[1]),
            arrowstyle="->",
            mutation_scale=20,
            color="black",
            alpha=0.8,
            linewidth=1.2,
            zorder=2,
        )
        ax.add_patch(arrow)

    @staticmethod
    def _draw_segment_arrow(ax: Axes, x1: float, y1: float, x2: float, y2: float) -> None:
        dx = x2 - x1
        dy = y2 - y1

        mid_x = x1 + dx * 0.5
        mid_y = y1 + dy * 0.5

        arrow_offset = 0.1
        arrow_start_x = mid_x - dx * arrow_offset
        arrow_start_y = mid_y - dy * arrow_offset
        arrow_end_x = mid_x + dx * arrow_offset
        arrow_end_y = mid_y + dy * arrow_offset

        arrow = FancyArrowPatch(
            (arrow_start_x, arrow_start_y),
            (arrow_end_x, arrow_end_y),
            arrowstyle="->",
            mutation_scale=20,
            color="black",
            alpha=0.8,
            linewidth=1.2,
            zorder=2,
        )
        ax.add_patch(arrow)


def analyze_chemin(graph: nx.Graph | nx.MultiGraph | nx.MultiDiGraph, start_node, end_node) -> dict:
    """Trouve le chemin le plus court entre deux croisements."""

    undirected = graph.to_undirected()
    try:
        path = nx.shortest_path(undirected, start_node, end_node, weight="length")
        distance = nx.shortest_path_length(undirected, start_node, end_node, weight="length")
        return {"chemin": path, "distance_m": distance}
    except nx.NetworkXNoPath:
        return {"erreur": "Pas de chemin trouve"}
