"""Reconnaissance de quartier via graphe OSM.

- Noeuds: intersections
- Aretes: routes ponderees par distance
"""

from __future__ import annotations

import json
import math
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

from .metric_closure import build_cost_matrix, complete_graph_with_shortest_paths, normalize_edge
from .models import EdgeAttributes, GraphGenerationConfig, GraphInstance


class QuartierGraph:
    """Composant pour generer et visualiser un graphe de quartier."""

    def __init__(self, lieu: str, network_type: str = "drive") -> None:
        self.lieu = lieu
        self.network_type = network_type
        self.graph: nx.MultiGraph | None = None
        self._boundary_node_ids: set = set()
        self._osm_to_solver_node: dict[int, int] = {}
        self._solver_to_osm_node: dict[int, int] = {}
        self._basemap_cache_key: tuple[float, float, float, float, int] | None = None
        self._basemap_cache_image = None
        self._basemap_cache_extent = None

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

        self._basemap_cache_key = None
        self._basemap_cache_image = None
        self._basemap_cache_extent = None

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

    def draw_basemap(self, ax: Axes) -> None:
        """Dessine uniquement le fond OSM dans un axe existant."""

        if self.graph is None:
            raise ValueError("Charger le quartier d'abord (charger_quartier)")

        node_x = [self.graph.nodes[node].get("x") for node in self.graph.nodes() if "x" in self.graph.nodes[node]]
        node_y = [self.graph.nodes[node].get("y") for node in self.graph.nodes() if "y" in self.graph.nodes[node]]
        if not node_x or not node_y:
            return

        min_x, max_x = min(node_x), max(node_x)
        min_y, max_y = min(node_y), max(node_y)
        pad_x = (max_x - min_x) * 0.04 if max_x > min_x else 2e-4
        pad_y = (max_y - min_y) * 0.04 if max_y > min_y else 2e-4
        ax.set_xlim(min_x - pad_x, max_x + pad_x)
        ax.set_ylim(min_y - pad_y, max_y + pad_y)
        self._add_basemap_optimized(ax)

    def build_dynamic_instance(
        self,
        *,
        seed: int | None = 42,
        max_solver_clients: int = 35,
        dynamic_sigma: float = 0.18,
        dynamic_mean_reversion_strength: float = 0.35,
        dynamic_max_multiplier: float = 1.80,
        dynamic_forbid_probability: float = 0.03,
        dynamic_restore_probability: float = 0.20,
        dynamic_max_disabled_ratio: float = 0.20,
    ) -> tuple[GraphInstance, dict[str, int | float]]:
        """Convertit le graphe OSM en GraphInstance CESIPATH pour simulation dynamique."""

        if self.graph is None:
            raise ValueError("Charger le quartier d'abord (charger_quartier)")
        if max_solver_clients <= 0:
            raise ValueError("max_solver_clients doit etre > 0")

        component = self._largest_connected_subgraph_with_coordinates(self.graph)
        osm_nodes = sorted(component.nodes())
        node_count = len(osm_nodes)
        if node_count < 2:
            raise ValueError("Le quartier charge ne contient pas assez de sommets exploitables")

        self._osm_to_solver_node = {osm_node: idx for idx, osm_node in enumerate(osm_nodes)}
        self._solver_to_osm_node = {idx: osm_node for osm_node, idx in self._osm_to_solver_node.items()}

        coordinates = {
            idx: (
                float(component.nodes[osm_node]["x"]),
                float(component.nodes[osm_node]["y"]),
            )
            for osm_node, idx in self._osm_to_solver_node.items()
        }

        edge_costs = self._build_edge_costs(component)
        if not edge_costs:
            raise ValueError("Impossible de construire les aretes du graphe quartier")

        depot = self._select_depot_node(coordinates)
        client_nodes = self._select_client_nodes(
            coordinates,
            depot,
            max_solver_clients=max_solver_clients,
            seed=seed,
        )

        edge_count = len(edge_costs)
        max_edges = node_count * (node_count - 1) / 2
        residual_density = edge_count / max_edges if max_edges else 0.0
        residual_avg_degree = (2 * edge_count) / node_count if node_count else 0.0

        dynamic_min_density = max(0.0, round(residual_density * 0.55, 6))
        dynamic_min_avg_degree = max(1.0, round(residual_avg_degree * 0.55, 3))
        vehicle_capacity = max(6, min(40, max(1, math.ceil(len(client_nodes) / 3))))

        config = GraphGenerationConfig(
            node_count=node_count,
            depot=depot,
            seed=seed,
            edge_density=min(1.0, residual_density),
            auto_density_profile=False,
            min_base_density=0.0,
            max_base_density=1.0,
            min_residual_density=0.0,
            max_residual_density=1.0,
            min_average_residual_degree=0.0,
            forbidden_rate=0.0,
            surcharge_rate=0.0,
            surcharge_min=0.0,
            surcharge_max=0.0,
            demand_min=1,
            demand_max=1,
            vehicle_capacity=vehicle_capacity,
            dynamic_sigma=dynamic_sigma,
            dynamic_mean_reversion_strength=dynamic_mean_reversion_strength,
            dynamic_max_multiplier=dynamic_max_multiplier,
            dynamic_forbid_probability=dynamic_forbid_probability,
            dynamic_restore_probability=dynamic_restore_probability,
            dynamic_min_density=dynamic_min_density,
            dynamic_min_average_degree=dynamic_min_avg_degree,
            dynamic_max_disabled_ratio=dynamic_max_disabled_ratio,
            generation_max_attempts=1,
        )

        base_edges = {key: EdgeAttributes(base_cost=cost) for key, cost in edge_costs.items()}
        residual_edges = {key: EdgeAttributes(base_cost=cost) for key, cost in edge_costs.items()}
        base_costs = build_cost_matrix(node_count, edge_costs)
        residual_costs = build_cost_matrix(node_count, edge_costs)
        completed_costs, completed_paths = complete_graph_with_shortest_paths(node_count, edge_costs)

        demands = {node: (1 if node in client_nodes else 0) for node in range(node_count)}
        demands[depot] = 0

        instance = GraphInstance(
            config=config,
            coordinates=coordinates,
            base_costs=base_costs,
            base_edges=base_edges,
            residual_costs=residual_costs,
            residual_edges=residual_edges,
            completed_costs=completed_costs,
            completed_paths=completed_paths,
            demands=demands,
        )

        metadata: dict[str, int | float] = {
            "osm_node_count": self.graph.number_of_nodes(),
            "osm_edge_count": self.graph.number_of_edges(),
            "solver_node_count": node_count,
            "solver_edge_count": edge_count,
            "solver_client_count": len(client_nodes),
            "solver_depot": depot,
            "solver_depot_osm_id": int(self._solver_to_osm_node.get(depot, -1)),
            "solver_residual_density": round(residual_density, 6),
            "solver_residual_avg_degree": round(residual_avg_degree, 4),
            "dynamic_min_density": round(dynamic_min_density, 6),
            "dynamic_min_average_degree": round(dynamic_min_avg_degree, 4),
        }
        return instance, metadata

    def _largest_connected_subgraph_with_coordinates(self, graph: nx.MultiGraph) -> nx.MultiGraph:
        undirected = nx.Graph(graph)
        if undirected.number_of_nodes() == 0:
            raise ValueError("Graphe quartier vide")

        largest_component = max(nx.connected_components(undirected), key=len)
        subgraph = graph.subgraph(largest_component).copy()
        valid_nodes = [
            node
            for node, data in subgraph.nodes(data=True)
            if "x" in data and "y" in data
        ]
        subgraph = subgraph.subgraph(valid_nodes).copy()

        if subgraph.number_of_nodes() == 0:
            raise ValueError("Aucun noeud geographique exploitable trouve")

        simple = nx.Graph(subgraph)
        if not nx.is_connected(simple):
            largest_valid_component = max(nx.connected_components(simple), key=len)
            subgraph = subgraph.subgraph(largest_valid_component).copy()
        return subgraph

    def _build_edge_costs(self, graph: nx.MultiGraph) -> dict[tuple[int, int], float]:
        edge_costs: dict[tuple[int, int], float] = {}
        for u, v, _key, data in graph.edges(keys=True, data=True):
            if u == v:
                continue
            if u not in self._osm_to_solver_node or v not in self._osm_to_solver_node:
                continue
            length = self._edge_length_meters(graph, u, v, data)
            if length <= 0:
                continue
            solver_key = normalize_edge(self._osm_to_solver_node[u], self._osm_to_solver_node[v])
            previous = edge_costs.get(solver_key)
            if previous is None or length < previous:
                edge_costs[solver_key] = round(length, 2)
        return edge_costs

    def _edge_length_meters(self, graph: nx.MultiGraph, u, v, data: dict) -> float:
        raw = data.get("length")
        if raw is not None:
            try:
                value = float(raw)
                if value > 0:
                    return value
            except (TypeError, ValueError):
                pass

        x1 = graph.nodes[u].get("x")
        y1 = graph.nodes[u].get("y")
        x2 = graph.nodes[v].get("x")
        y2 = graph.nodes[v].get("y")
        if None in (x1, y1, x2, y2):
            return 0.0
        return self._haversine_meters(float(y1), float(x1), float(y2), float(x2))

    @staticmethod
    def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius = 6_371_000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def _select_depot_node(coordinates: dict[int, tuple[float, float]]) -> int:
        center_x = sum(x for x, _ in coordinates.values()) / len(coordinates)
        center_y = sum(y for _, y in coordinates.values()) / len(coordinates)
        return min(
            coordinates,
            key=lambda node: (coordinates[node][0] - center_x) ** 2 + (coordinates[node][1] - center_y) ** 2,
        )

    @staticmethod
    def _select_client_nodes(
        coordinates: dict[int, tuple[float, float]],
        depot: int,
        *,
        max_solver_clients: int,
        seed: int | None,
    ) -> set[int]:
        candidates = [node for node in coordinates if node != depot]
        if len(candidates) <= max_solver_clients:
            return set(candidates)

        rng = np.random.default_rng(seed)
        selected: list[int] = []

        depot_coords = np.array(coordinates[depot])
        first = max(
            candidates,
            key=lambda node: float(np.sum((np.array(coordinates[node]) - depot_coords) ** 2)),
        )
        selected.append(first)

        while len(selected) < max_solver_clients:
            remaining = [node for node in candidates if node not in selected]
            if not remaining:
                break

            best_node = remaining[0]
            best_score = -1.0
            for node in remaining:
                current = np.array(coordinates[node])
                min_dist = min(
                    float(np.sum((current - np.array(coordinates[sel])) ** 2))
                    for sel in selected
                )
                score = min_dist + float(rng.random() * 1e-9)
                if score > best_score:
                    best_score = score
                    best_node = node
            selected.append(best_node)

        return set(selected)

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

        cache_key = (
            round(float(xmin), 6),
            round(float(ymin), 6),
            round(float(xmax), 6),
            round(float(ymax), 6),
            zoom,
        )
        if self._basemap_cache_key == cache_key and self._basemap_cache_image is not None:
            image = self._basemap_cache_image
            extent = self._basemap_cache_extent
        else:
            image, extent = ctx.bounds2img(
                xmin,
                ymin,
                xmax,
                ymax,
                zoom=zoom,
                source=ctx.providers.CartoDB.Positron,
                ll=True,
                # Evite les warnings loky/resource_tracker en sortie de process.
                n_connections=1,
                use_cache=False,
                headers={"User-Agent": "CESIPATH/1.0"},
            )
            image, extent = warp_tiles(image, extent, t_crs="EPSG:4326", resampling=Resampling.bilinear)
            self._basemap_cache_key = cache_key
            self._basemap_cache_image = image
            self._basemap_cache_extent = extent
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
