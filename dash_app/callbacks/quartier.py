"""Callbacks de l onglet Quartier."""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
import threading
from typing import Any
from uuid import uuid4

from dash import Input, Output, State, dcc, html, no_update
from dash.exceptions import PreventUpdate
import numpy as np
from PIL import Image
import plotly.graph_objects as go

try:
    import dash_leaflet as dl
    LEAFLET_AVAILABLE = True
except ImportError:
    dl = None
    LEAFLET_AVAILABLE = False

try:
    import contextily as ctx
    from contextily.tile import warp_tiles
    from rasterio.enums import Resampling

    CONTEXTILY_AVAILABLE = True
except Exception:
    ctx = None
    warp_tiles = None
    Resampling = None
    CONTEXTILY_AVAILABLE = False

from components.log_console import LOG_STORE, render_log_lines
from services import calculate_vrp_solution_stats, validate_quartier_payload, validate_quartier_simulation_payload
from theme import ANIMATION_COLORS, PALETTE

_MAX_LOG_LINES = 800
_LOG_HISTORY: list[dict[str, str]] = []

ALGO_MAP = {
    "grasp": ("cesipath.algorithms.grasp", "grasp"),
    "tabu_search": ("cesipath.algorithms.tabu_search", "tabu_search"),
    "simulated_annealing": ("cesipath.algorithms.simulated_annealing", "simulated_annealing"),
    "genetic_algorithm": ("cesipath.algorithms.genetic", "genetic_algorithm"),
}

ANIMATION_SIZES = {
    "network_width": 1.0,
    "route_width": 3.2,
    "client": 14,
    "depot": 14,
    "depot_text": 10,
    "truck": 72,
}

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_TRUCK_RIGHT_PATH = _PROJECT_ROOT / "image" / "camionD.png"
_TRUCK_LEFT_PATH = _PROJECT_ROOT / "image" / "camionG.png"
_TRUCK_URI_CACHE: dict[str, str | None] = {"right": None, "left": None}


def _enqueue_log(level: str, message: str) -> None:
    LOG_STORE.push("quartier", level, message)


def _render_logs() -> list[html.Div]:
    fresh = LOG_STORE.drain("quartier", max=50)
    if fresh:
        _LOG_HISTORY.extend(fresh)
        if len(_LOG_HISTORY) > _MAX_LOG_LINES:
            del _LOG_HISTORY[:-_MAX_LOG_LINES]
    return render_log_lines(_LOG_HISTORY)


def _mix_hex_color(color_a: str, color_b: str, factor: float) -> str:
    factor = max(0.0, min(1.0, float(factor)))

    def _hex_to_rgb(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

    ar, ag, ab = _hex_to_rgb(color_a)
    br, bg, bb = _hex_to_rgb(color_b)
    rr = int(round(ar + (br - ar) * factor))
    rg = int(round(ag + (bg - ag) * factor))
    rb = int(round(ab + (bb - ab) * factor))
    return f"#{rr:02x}{rg:02x}{rb:02x}"


def _interpolate_traffic_color(ratio: float) -> str:
    ratio = max(0.0, min(1.0, float(ratio)))
    if ratio <= 0.5:
        local = ratio / 0.5
        return _mix_hex_color(ANIMATION_COLORS["traffic_low"], ANIMATION_COLORS["traffic_mid"], local)
    if ratio <= 0.8:
        local = (ratio - 0.5) / 0.3
        return _mix_hex_color(ANIMATION_COLORS["traffic_mid"], ANIMATION_COLORS["traffic_high"], local)
    local = (ratio - 0.8) / 0.2
    return _mix_hex_color(ANIMATION_COLORS["traffic_high"], ANIMATION_COLORS["traffic_max"], local)


def _image_to_data_uri(image: np.ndarray) -> str:
    if image.dtype != np.uint8:
        clipped = np.clip(image, 0.0, 1.0)
        image = (clipped * 255).astype(np.uint8)

    png_buffer = BytesIO()
    Image.fromarray(image).save(png_buffer, format="PNG")
    encoded = base64.b64encode(png_buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _load_truck_sprite_uri(direction: str) -> str | None:
    if direction in _TRUCK_URI_CACHE and _TRUCK_URI_CACHE[direction] is not None:
        return _TRUCK_URI_CACHE[direction]

    sprite_path = _TRUCK_RIGHT_PATH if direction == "right" else _TRUCK_LEFT_PATH
    if not sprite_path.exists():
        _TRUCK_URI_CACHE[direction] = None
        return None

    try:
        encoded = base64.b64encode(sprite_path.read_bytes()).decode("ascii")
        uri = f"data:image/png;base64,{encoded}"
        _TRUCK_URI_CACHE[direction] = uri
        return uri
    except Exception:
        _TRUCK_URI_CACHE[direction] = None
        return None


def _compute_bounds_from_nodes(nodes: list[dict[str, Any]]) -> dict[str, float]:
    lons = [float(node["lon"]) for node in nodes]
    lats = [float(node["lat"]) for node in nodes]
    min_lon = min(lons)
    max_lon = max(lons)
    min_lat = min(lats)
    max_lat = max(lats)

    pad_lon = (max_lon - min_lon) * 0.05 if max_lon > min_lon else 0.0003
    pad_lat = (max_lat - min_lat) * 0.05 if max_lat > min_lat else 0.0003

    return {
        "lon_min": min_lon - pad_lon,
        "lon_max": max_lon + pad_lon,
        "lat_min": min_lat - pad_lat,
        "lat_max": max_lat + pad_lat,
    }


def _pick_zoom(node_count: int) -> int:
    if node_count > 700:
        return 13
    if node_count > 320:
        return 14
    return 15


def _get_cached_basemap_overlay(
    session_cache: dict[str, Any],
    session_id: str,
    *,
    cache_slot: str,
    nodes: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not CONTEXTILY_AVAILABLE or not nodes:
        return None

    bounds = _compute_bounds_from_nodes(nodes)
    zoom = _pick_zoom(len(nodes))
    cache_key = (
        round(bounds["lon_min"], 6),
        round(bounds["lat_min"], 6),
        round(bounds["lon_max"], 6),
        round(bounds["lat_max"], 6),
        zoom,
    )

    session_bucket = session_cache.setdefault(session_id, {})
    cached = session_bucket.get(cache_slot)
    if isinstance(cached, dict) and cached.get("key") == cache_key:
        return cached.get("overlay")

    try:
        image, extent = ctx.bounds2img(
            bounds["lon_min"],
            bounds["lat_min"],
            bounds["lon_max"],
            bounds["lat_max"],
            zoom=zoom,
            source=ctx.providers.CartoDB.Positron,
            ll=True,
            n_connections=1,
            use_cache=False,
            headers={"User-Agent": "CESIPATH/1.0"},
        )
        image, extent = warp_tiles(image, extent, t_crs="EPSG:4326", resampling=Resampling.bilinear)
        xmin, xmax, ymin, ymax = [float(v) for v in extent]
        if xmax <= xmin or ymax <= ymin:
            return None

        overlay = {
            "source": _image_to_data_uri(image),
            "xref": "x",
            "yref": "y",
            "x": xmin,
            "y": ymax,
            "sizex": xmax - xmin,
            "sizey": ymax - ymin,
            "xanchor": "left",
            "yanchor": "top",
            "sizing": "stretch",
            "opacity": 0.92,
            "layer": "below",
        }
        session_bucket[cache_slot] = {"key": cache_key, "overlay": overlay}
        return overlay
    except Exception:
        return None


def _build_truck_overlay(
    truck_lon: float,
    truck_lat: float,
    truck_dx: float,
    *,
    bounds: dict[str, float],
) -> dict[str, Any] | None:
    if truck_dx < -1e-9:
        source = _load_truck_sprite_uri("left")
    else:
        source = _load_truck_sprite_uri("right")
    if source is None:
        source = _load_truck_sprite_uri("right") or _load_truck_sprite_uri("left")
    if source is None:
        return None

    span_lon = max(bounds["lon_max"] - bounds["lon_min"], 0.0001)
    span_lat = max(bounds["lat_max"] - bounds["lat_min"], 0.0001)
    truck_w = span_lon * 0.09
    truck_h = span_lat * 0.12

    return {
        "source": source,
        "xref": "x",
        "yref": "y",
        "x": truck_lon,
        "y": truck_lat,
        "sizex": truck_w,
        "sizey": truck_h,
        "xanchor": "center",
        "yanchor": "middle",
        "sizing": "stretch",
        "opacity": 1.0,
        "layer": "above",
    }


def register_callbacks(app, session_cache: dict[str, Any], background_callback_manager=None) -> None:
    _ = background_callback_manager

    def _osm_worker(session_id: str, place: str, distance: float) -> None:
        try:
            _enqueue_log("running", f"Chargement OSM : {place}...")

            import osmnx as ox
            import networkx as nx

            graph_osm = ox.graph_from_address(
                place,
                dist=distance,
                network_type="drive",
                simplify=True,
            )
            graph_osm = ox.project_graph(graph_osm, to_crs="EPSG:4326")

            nodes_data: list[dict[str, float | int]] = []
            for node_id, data in graph_osm.nodes(data=True):
                if "y" in data and "x" in data:
                    nodes_data.append(
                        {
                            "id": int(node_id),
                            "lat": float(data["y"]),
                            "lon": float(data["x"]),
                        }
                    )

            if not nodes_data:
                raise ValueError("Aucun noeud OSM exploitable")

            edges_data: list[dict[str, float | int]] = []
            for u, v, data in graph_osm.edges(data=True):
                edges_data.append(
                    {
                        "u": int(u),
                        "v": int(v),
                        "length": float(data.get("length", 1.0)),
                    }
                )

            # Calcule la composante reellement exploitable (aretes avec longueur > 0)
            graph_for_limits = nx.Graph()
            for edge in edges_data:
                u = int(edge["u"])
                v = int(edge["v"])
                length = float(edge["length"])
                if length <= 0:
                    continue
                if graph_for_limits.has_edge(u, v):
                    previous = float(graph_for_limits[u][v].get("length", length))
                    if length < previous:
                        graph_for_limits[u][v]["length"] = length
                else:
                    graph_for_limits.add_edge(u, v, length=length)

            center = {
                "lat": sum(node["lat"] for node in nodes_data) / len(nodes_data),
                "lon": sum(node["lon"] for node in nodes_data) / len(nodes_data),
            }

            if graph_for_limits.number_of_nodes() > 0:
                largest_component_nodes = max(nx.connected_components(graph_for_limits), key=len)
                candidate_node_ids = sorted(int(node_id) for node_id in largest_component_nodes)
            else:
                candidate_node_ids = sorted(int(node["id"]) for node in nodes_data)
            max_solver_clients_available = max(1, int(len(candidate_node_ids)) - 1)

            session_cache.setdefault(session_id, {})
            session_cache[session_id]["osm_nodes"] = nodes_data
            session_cache[session_id]["osm_edges"] = edges_data
            session_cache[session_id]["osm_center"] = center
            session_cache[session_id]["osm_graph"] = graph_osm
            session_cache[session_id]["osm_candidate_node_ids"] = candidate_node_ids
            session_cache[session_id]["max_solver_clients_available"] = max_solver_clients_available
            session_cache[session_id]["status"] = "osm_ready"

            _enqueue_log(
                "success",
                f"Quartier charge : {len(nodes_data)} noeuds OSM (clients max: {max_solver_clients_available})",
            )
        except Exception as exc:
            session_cache.setdefault(session_id, {})
            session_cache[session_id]["status"] = "error"
            session_cache[session_id]["error"] = str(exc)
            _enqueue_log("error", f"Erreur OSM : {str(exc)}")

    def _simulation_worker(
        session_id: str,
        algo_name: str,
        capacity: int,
        seed: int,
        max_clients: int,
    ) -> None:
        try:
            _enqueue_log("running", "Construction matrice de couts dynamiques...")

            nodes = session_cache[session_id]["osm_nodes"]
            graph_osm = session_cache[session_id]["osm_graph"]

            import networkx as nx
            import numpy as np
            import random
            from cesipath.dynamic_costs import sample_dynamic_edge_cost
            from cesipath.models import EdgeAttributes

            dynamic_sigma = 0.18
            dynamic_mean_reversion_strength = 0.35
            dynamic_max_multiplier = 1.80

            graph_static = nx.Graph()
            for u, v, data in graph_osm.edges(data=True):
                if u == v:
                    continue
                length = float(data.get("length", 1.0))
                if length <= 0:
                    continue
                if graph_static.has_edge(u, v):
                    if length < float(graph_static[u][v].get("length", length)):
                        graph_static[u][v]["length"] = length
                else:
                    graph_static.add_edge(u, v, length=length)

            if graph_static.number_of_edges() == 0:
                raise ValueError("Aucune arete exploitable pour la simulation")

            node_by_id = {int(node["id"]): node for node in nodes}
            candidate_ids_raw = session_cache[session_id].get("osm_candidate_node_ids")
            if candidate_ids_raw:
                ordered_ids = [
                    int(node_id)
                    for node_id in candidate_ids_raw
                    if int(node_id) in node_by_id
                ]
            else:
                largest_component = max(nx.connected_components(graph_static), key=len)
                ordered_ids = [
                    int(node["id"])
                    for node in nodes
                    if int(node["id"]) in largest_component
                ]

            selected_ids = ordered_ids[: max_clients + 1]
            selected = [node_by_id[node_id] for node_id in selected_ids]
            if len(selected) < 2:
                raise ValueError("Pas assez de noeuds connectes pour simuler")

            osm_ids = selected_ids
            node_count = len(selected)

            rng = random.Random(seed)
            graph_dynamic = nx.Graph()
            dynamic_edge_ratio: dict[tuple[int, int], float] = {}
            dynamic_edge_base_costs: dict[tuple[int, int], float] = {}
            dynamic_edge_costs_initial: dict[tuple[int, int], float] = {}
            for u, v, data in graph_static.edges(data=True):
                base_length = float(data.get("length", 1.0))
                edge_attr = EdgeAttributes(base_cost=base_length)
                dynamic_cost = sample_dynamic_edge_cost(
                    edge_attr,
                    previous_cost=base_length,
                    rng=rng,
                    sigma=dynamic_sigma,
                    mean_reversion_strength=dynamic_mean_reversion_strength,
                    max_multiplier=dynamic_max_multiplier,
                )
                graph_dynamic.add_edge(
                    u,
                    v,
                    weight=float(dynamic_cost),
                    base_length=base_length,
                )
                edge_key = (min(int(u), int(v)), max(int(u), int(v)))
                dynamic_edge_base_costs[edge_key] = base_length
                dynamic_edge_costs_initial[edge_key] = float(dynamic_cost)
                if base_length > 0:
                    dynamic_edge_ratio[edge_key] = float(dynamic_cost) / base_length
                else:
                    dynamic_edge_ratio[edge_key] = 1.0

            cost_matrix = np.full((node_count, node_count), 1e9)
            shortest_paths: dict[int, dict[int, list[int]]] = {}
            real_shortest_paths: dict[int, dict[int, list[int]]] = {}
            progress_step = max(1, node_count // 10)

            for i in range(node_count):
                cost_matrix[i][i] = 0.0
                shortest_paths[i] = {i: [i]}
                real_shortest_paths[i] = {i: [osm_ids[i]]}
                try:
                    lengths, paths = nx.single_source_dijkstra(
                        graph_dynamic,
                        osm_ids[i],
                        weight="weight",
                    )
                except Exception:
                    lengths, paths = {}, {}
                for j in range(node_count):
                    if i == j:
                        continue
                    path_osm = paths.get(osm_ids[j])
                    path_cost = lengths.get(osm_ids[j])
                    if path_osm is not None and path_cost is not None:
                        cost_matrix[i][j] = float(path_cost)
                        shortest_paths[i][j] = [i, j]
                        real_shortest_paths[i][j] = [int(node) for node in path_osm]
                    else:
                        shortest_paths[i][j] = [i, j]
                        real_shortest_paths[i][j] = [osm_ids[i], osm_ids[j]]
                if (i + 1) % progress_step == 0 or i + 1 == node_count:
                    _enqueue_log("running", f"Preparation des chemins: {i + 1}/{node_count}")

            from cesipath.solver_input import SolverInput

            demands = {i: 1 for i in range(1, node_count)}
            demands[0] = 0

            solver_input = SolverInput(
                cost_matrix=cost_matrix,
                depot=0,
                demands=demands,
                vehicle_capacity=capacity,
                shortest_paths=shortest_paths,
                source="osm",
                dynamic_step=None,
            )
            session_cache[session_id]["solver_input"] = solver_input
            session_cache[session_id]["osm_selected_nodes"] = selected
            session_cache[session_id]["osm_selected_osm_ids"] = osm_ids
            session_cache[session_id]["real_shortest_paths"] = real_shortest_paths
            session_cache[session_id]["dynamic_edge_ratio"] = dynamic_edge_ratio
            session_cache[session_id]["dynamic_edge_base_costs"] = dynamic_edge_base_costs
            session_cache[session_id]["dynamic_edge_costs_initial"] = dynamic_edge_costs_initial
            session_cache[session_id]["dynamic_sigma"] = dynamic_sigma
            session_cache[session_id]["dynamic_mean_reversion_strength"] = dynamic_mean_reversion_strength
            session_cache[session_id]["dynamic_max_multiplier"] = dynamic_max_multiplier
            session_cache[session_id]["simulation_seed"] = seed

            _enqueue_log(
                "running",
                f"Matrice dynamique {node_count}x{node_count} construite. Resolution {algo_name}...",
            )

            import importlib

            mod_path, func_name = ALGO_MAP[algo_name]
            module = importlib.import_module(mod_path)
            solution = getattr(module, func_name)(solver_input, seed=seed)

            session_cache[session_id]["vrp_solution"] = solution
            session_cache[session_id]["status"] = "sim_done"

            total_cost = getattr(solution, "cost", None)
            if total_cost is None:
                total_cost = getattr(solution, "total_cost", 0.0)
            _enqueue_log(
                "success",
                f"Solution : {len(solution.routes)} routes, cout total {float(total_cost):.1f}",
            )

        except Exception as exc:
            session_cache.setdefault(session_id, {})
            session_cache[session_id]["status"] = "error"
            _enqueue_log("error", f"Erreur simulation : {str(exc)}")

    @app.callback(
        Output("quartier-preview", "children"),
        Input("quartier-place", "value"),
        Input("input-quartier-max-clients", "value"),
        Input("store-quartier", "data"),
    )
    def update_preview(place: str, max_clients: int, store_data: dict[str, Any]) -> str:
        place_text = (place or "").strip() or "-"
        clients = max_clients if max_clients is not None else "?"
        available = (store_data or {}).get("max_solver_clients_available")
        available_text = str(available) if available is not None else "?"
        return f"Apercu: {place_text} | mode=drive | clients={clients}/{available_text}"

    @app.callback(
        Output("input-quartier-max-clients", "max"),
        Output("input-quartier-max-clients", "value"),
        Output("hint-quartier-max-clients", "children"),
        Input("store-quartier", "data"),
        State("input-quartier-max-clients", "value"),
    )
    def sync_max_clients_limit(
        store_data: dict[str, Any],
        current_value: Any,
    ) -> tuple[int | None, int | Any, str]:
        data = store_data or {}
        available_raw = data.get("max_solver_clients_available")
        if available_raw is None:
            return None, no_update, "Nombre de sommets de livraison utilises. Max quartier: inconnu."

        try:
            available = max(1, int(available_raw))
        except Exception:
            return None, no_update, "Nombre de sommets de livraison utilises. Max quartier: inconnu."

        value = current_value
        try:
            value_int = int(value) if value is not None else None
        except Exception:
            value_int = None

        if value_int is None:
            value_int = min(8, available)
        value_int = max(1, min(value_int, available))
        hint = f"Nombre de sommets de livraison utilises. Max quartier: {available}."
        return available, value_int, hint

    @app.callback(
        Output("store-quartier", "data", allow_duplicate=True),
        Input("quartier-place", "value"),
        Input("quartier-distance", "value"),
        State("store-quartier", "data"),
        prevent_initial_call=True,
    )
    def sync_store_from_form(
        place: str,
        distance_raw: Any,
        store_data: dict[str, Any],
    ) -> dict[str, Any] | Any:
        data = dict(store_data or {})
        if data.get("status") == "loading_osm":
            return no_update

        data["place"] = place
        data["distance_raw"] = distance_raw
        return data

    @app.callback(
        Output("store-quartier", "data", allow_duplicate=True),
        Input("quartier-load", "n_clicks"),
        State("store-quartier", "data"),
        prevent_initial_call=True,
    )
    def launch_osm_loading(n_clicks: int, store_data: dict[str, Any]) -> dict[str, Any]:
        if not n_clicks:
            raise PreventUpdate

        payload = dict(store_data or {})

        try:
            place, distance = validate_quartier_payload(payload)
        except ValueError as exc:
            _enqueue_log("error", f"Parametres OSM invalides : {exc}")
            payload["status"] = "error"
            payload["session_id"] = None
            return payload

        session_id = str(uuid4())
        session_cache[session_id] = {
            "status": "loading_osm",
            "osm_nodes": None,
            "osm_edges": None,
            "osm_center": None,
            "osm_graph": None,
            "solver_input": None,
            "vrp_solution": None,
            "error": None,
        }

        worker = threading.Thread(
            daemon=True,
            target=_osm_worker,
            args=(session_id, place, distance),
        )
        worker.start()

        payload["status"] = "loading_osm"
        payload["session_id"] = session_id
        payload["place"] = place
        payload["distance_raw"] = distance
        return payload

    @app.callback(
        Output("store-quartier", "data", allow_duplicate=True),
        Output("quartier-run", "disabled", allow_duplicate=True),
        Output("quartier-run", "children", allow_duplicate=True),
        Input("quartier-run", "n_clicks"),
        State("store-quartier", "data"),
        State("dropdown-quartier-algo", "value"),
        State("input-quartier-capacity", "value"),
        State("input-quartier-seed", "value"),
        State("input-quartier-max-clients", "value"),
        prevent_initial_call=True,
    )
    def launch_simulation(
        n_clicks: int,
        store_data: dict[str, Any],
        algo_name: str,
        capacity_raw: Any,
        seed_raw: Any,
        max_clients_raw: Any,
    ):
        if not n_clicks:
            raise PreventUpdate

        data = dict(store_data or {})
        status = data.get("status")
        if status not in {"osm_ready", "sim_done"}:
            _enqueue_log("error", "Chargez d'abord un quartier")
            return no_update, no_update, no_update

        try:
            simulation_payload = validate_quartier_simulation_payload(
                payload={
                    "algo_name": algo_name,
                    "capacity": capacity_raw,
                    "seed": seed_raw,
                    "max_clients": max_clients_raw,
                },
                allowed_algorithms=set(ALGO_MAP),
            )
            capacity = int(simulation_payload["capacity"])
            seed = int(simulation_payload["seed"])
            max_clients = int(simulation_payload["max_clients"])
            algo_name = str(simulation_payload["algo_name"])
        except ValueError as exc:
            _enqueue_log("error", f"Parametres simulation invalides : {exc}")
            return no_update, no_update, no_update

        session_id = data.get("session_id")
        if not session_id or session_id not in session_cache:
            _enqueue_log("error", "Session quartier invalide")
            return no_update, no_update, no_update

        available_raw = session_cache[session_id].get("max_solver_clients_available")
        if available_raw is None:
            candidate_ids = session_cache[session_id].get("osm_candidate_node_ids") or []
            if candidate_ids:
                available_raw = max(1, len(candidate_ids) - 1)
            else:
                node_list = session_cache[session_id].get("osm_nodes") or []
                available_raw = max(1, len(node_list) - 1)
        try:
            available = max(1, int(available_raw))
        except Exception:
            available = 1

        if max_clients > available:
            _enqueue_log("error", f"Parametres simulation invalides : max_clients doit etre <= {available}")
            return no_update, no_update, no_update

        data["status"] = "sim_running"
        data["max_solver_clients"] = max_clients
        data["max_solver_clients_available"] = available
        session_cache[session_id]["max_solver_clients"] = max_clients
        session_cache[session_id]["status"] = "sim_running"

        worker = threading.Thread(
            daemon=True,
            target=_simulation_worker,
            args=(session_id, algo_name, capacity, seed, max_clients),
        )
        worker.start()

        return data, True, "Simulation en cours..."

    @app.callback(
        Output("quartier-status-message", "children"),
        Output("quartier-status-message", "className"),
        Output("quartier-loading-target", "children"),
        Input("store-quartier", "data"),
    )
    def sync_status(store_data: dict[str, Any]) -> tuple[str, str, html.Span]:
        data = store_data or {}
        status = str(data.get("status", "idle"))

        if status == "loading_osm":
            message = "Chargement OSM en cours"
            class_name = "status-message status-running"
        elif status == "osm_ready":
            message = "Quartier charge"
            class_name = "status-message status-success"
        elif status == "sim_running":
            message = "Simulation VRP en cours"
            class_name = "status-message status-running"
        elif status == "sim_done":
            message = "Simulation VRP terminee"
            class_name = "status-message status-success"
        elif status == "error":
            message = "Erreur OSM/Simulation"
            class_name = "status-message status-error"
        else:
            message = "Idle"
            class_name = "status-message status-idle"

        return message, class_name, html.Span(message, className="loading-token")

    @app.callback(
        Output("quartier-load", "disabled"),
        Output("quartier-load", "children"),
        Input("store-quartier", "data"),
    )
    def sync_load_button(store_data: dict[str, Any]) -> tuple[bool, str]:
        status = str((store_data or {}).get("status", "idle"))
        if status == "loading_osm":
            return True, "Chargement..."
        return False, "Charger le quartier"

    @app.callback(
        Output("log-output-quartier", "children"),
        Output("store-quartier", "data", allow_duplicate=True),
        Output("quartier-run", "disabled", allow_duplicate=True),
        Output("quartier-run", "children", allow_duplicate=True),
        Input("log-interval-quartier", "n_intervals"),
        State("store-quartier", "data"),
        prevent_initial_call=True,
    )
    def poll_logs_and_sync_status(
        _: int,
        store_data: dict[str, Any],
    ):
        data = dict(store_data or {})
        session_id = data.get("session_id")

        next_store: dict[str, Any] | Any = no_update
        next_disabled: bool | Any = no_update
        next_text: str | Any = no_update

        if session_id:
            session_data = session_cache.get(session_id)
            if session_data is not None:
                session_status = session_data.get("status")
                current_status = data.get("status")

                if session_status == "osm_ready" and current_status != "osm_ready":
                    data["status"] = "osm_ready"
                    data["max_solver_clients_available"] = session_data.get("max_solver_clients_available")
                    next_store = data

                elif session_status == "error" and current_status != "error":
                    data["status"] = "error"
                    next_store = data
                    if current_status == "sim_running":
                        next_disabled = False
                        next_text = "Lancer simulation"

                if current_status == "sim_running" and session_status == "sim_done":
                    data["status"] = "sim_done"
                    next_store = data
                    next_disabled = False
                    next_text = "Lancer simulation"

                if current_status == "sim_running" and session_status == "error":
                    data["status"] = "error"
                    next_store = data
                    next_disabled = False
                    next_text = "Lancer simulation"

        return _render_logs(), next_store, next_disabled, next_text

    @app.callback(
        Output("animation-container-quartier", "children"),
        Input("store-quartier", "data"),
        prevent_initial_call=True,
    )
    def render_animation(data: dict[str, Any]):
        if not data or data.get("status") != "sim_done":
            return no_update

        session_id = data.get("session_id")
        if not session_id or session_id not in session_cache:
            return no_update

        solution = session_cache[session_id].get("vrp_solution")
        nodes = session_cache[session_id].get("osm_selected_nodes")
        solver_input = session_cache[session_id].get("solver_input")
        if solution is None or not nodes or solver_input is None:
            return no_update

        shortest_paths = solver_input.shortest_paths
        real_shortest_paths = session_cache[session_id].get("real_shortest_paths") or {}
        full_nodes = session_cache[session_id].get("osm_nodes") or nodes
        bounds = _compute_bounds_from_nodes(full_nodes)
        basemap_overlay = _get_cached_basemap_overlay(
            session_cache,
            session_id,
            cache_slot="_anim_basemap_overlay",
            nodes=full_nodes,
        )
        left_sprite = _load_truck_sprite_uri("left")
        right_sprite = _load_truck_sprite_uri("right")
        truck_png_available = left_sprite is not None or right_sprite is not None

        client_colors = [ANIMATION_COLORS["client_default"]] * len(nodes)
        client_colors[0] = ANIMATION_COLORS["depot"]

        edges = session_cache[session_id].get("osm_edges") or []
        node_index = {
            int(node["id"]): node
            for node in (session_cache[session_id].get("osm_nodes") or [])
        }
        dynamic_edge_ratio = session_cache[session_id].get("dynamic_edge_ratio") or {}
        dynamic_edge_base_costs = session_cache[session_id].get("dynamic_edge_base_costs") or {}
        dynamic_edge_costs_initial = session_cache[session_id].get("dynamic_edge_costs_initial") or {}
        dynamic_sigma = float(session_cache[session_id].get("dynamic_sigma", 0.18))
        dynamic_mean_reversion_strength = float(
            session_cache[session_id].get("dynamic_mean_reversion_strength", 0.35)
        )
        dynamic_max_multiplier = float(session_cache[session_id].get("dynamic_max_multiplier", 1.8))
        simulation_seed = int(session_cache[session_id].get("simulation_seed", 42))
        ratio_den = max(dynamic_max_multiplier - 1.0, 1e-9)

        import random
        from cesipath.dynamic_costs import sample_dynamic_edge_cost
        from cesipath.models import EdgeAttributes

        node_count = len(nodes)
        if node_count >= 120:
            traffic_bins_count = 4
        elif node_count >= 80:
            traffic_bins_count = 5
        else:
            traffic_bins_count = 10
        dynamic_rng = random.Random(simulation_seed + 13007)
        if dynamic_edge_costs_initial:
            current_dynamic_costs = {
                (int(key[0]), int(key[1])): float(value)
                for key, value in dynamic_edge_costs_initial.items()
            }
        else:
            current_dynamic_costs = {}
            for key, ratio in dynamic_edge_ratio.items():
                base_cost = float(dynamic_edge_base_costs.get(key, 1.0))
                current_dynamic_costs[(int(key[0]), int(key[1]))] = base_cost * float(ratio)

        def build_traffic_segments(
            dynamic_costs: dict[tuple[int, int], float],
        ) -> list[dict[str, Any]]:
            traffic_bins_x: list[list[float | None]] = [[] for _ in range(traffic_bins_count)]
            traffic_bins_y: list[list[float | None]] = [[] for _ in range(traffic_bins_count)]
            for edge in edges:
                u = node_index.get(int(edge["u"]))
                v = node_index.get(int(edge["v"]))
                if not u or not v:
                    continue
                edge_key = (min(int(edge["u"]), int(edge["v"])), max(int(edge["u"]), int(edge["v"])))
                base_cost = float(dynamic_edge_base_costs.get(edge_key, float(edge.get("length", 1.0))))
                dyn_cost = float(dynamic_costs.get(edge_key, base_cost))
                dyn_ratio = (dyn_cost / base_cost) if base_cost > 0 else 1.0
                congestion = max(0.0, min(1.0, (dyn_ratio - 1.0) / ratio_den))
                bin_idx = min(traffic_bins_count - 1, int(congestion * traffic_bins_count))
                traffic_bins_x[bin_idx] += [float(u["lon"]), float(v["lon"]), None]
                traffic_bins_y[bin_idx] += [float(u["lat"]), float(v["lat"]), None]

            segments: list[dict[str, Any]] = []
            for idx in range(traffic_bins_count):
                color = _interpolate_traffic_color((idx + 0.5) / traffic_bins_count)
                segments.append({"x": traffic_bins_x[idx], "y": traffic_bins_y[idx], "color": color})
            return segments

        def evolve_dynamic_costs(
            dynamic_costs: dict[tuple[int, int], float],
        ) -> dict[tuple[int, int], float]:
            next_costs: dict[tuple[int, int], float] = {}
            for edge_key, base_cost in dynamic_edge_base_costs.items():
                prev_cost = float(dynamic_costs.get(edge_key, base_cost))
                dyn_cost = sample_dynamic_edge_cost(
                    EdgeAttributes(base_cost=float(base_cost)),
                    previous_cost=prev_cost,
                    rng=dynamic_rng,
                    sigma=dynamic_sigma,
                    mean_reversion_strength=dynamic_mean_reversion_strength,
                    max_multiplier=dynamic_max_multiplier,
                )
                next_costs[(int(edge_key[0]), int(edge_key[1]))] = float(dyn_cost)
            return next_costs

        def make_frame_images(truck_lon: float, truck_lat: float, truck_dx: float) -> list[dict[str, Any]]:
            images: list[dict[str, Any]] = []
            if basemap_overlay is not None:
                images.append(dict(basemap_overlay))
            truck_overlay = _build_truck_overlay(truck_lon, truck_lat, truck_dx, bounds=bounds)
            if truck_overlay is not None:
                images.append(truck_overlay)
            return images

        def make_base_traces(
            traffic_segments: list[dict[str, Any]],
            route_lons: list[float | None],
            route_lats: list[float | None],
            colors: list[str],
            truck_lon: float,
            truck_lat: float,
        ) -> list[go.Scatter]:
            client_nodes = nodes[1:]
            if truck_png_available:
                truck_marker = {
                    "color": PALETTE["transparent"],
                    "size": 1,
                    "symbol": "circle",
                    "line": {"color": PALETTE["transparent"], "width": 0},
                    "opacity": 0.0,
                }
            else:
                truck_marker = {
                    "color": ANIMATION_COLORS["truck"],
                    "size": ANIMATION_SIZES["truck"],
                    "symbol": "triangle-up",
                    "line": {"color": ANIMATION_COLORS["black"], "width": 2},
                    "opacity": 1.0,
                }
            traces: list[go.Scatter] = []
            for segment in traffic_segments:
                traces.append(
                    go.Scatter(
                        x=segment["x"],
                        y=segment["y"],
                        mode="lines",
                        line={"color": segment["color"], "width": ANIMATION_SIZES["network_width"]},
                        hoverinfo="skip",
                        showlegend=False,
                    )
                )
            traces.extend(
                [
                    go.Scatter(
                    x=route_lons,
                    y=route_lats,
                    mode="lines",
                    line={"color": ANIMATION_COLORS["route"], "width": ANIMATION_SIZES["route_width"]},
                    hoverinfo="skip",
                ),
                    go.Scatter(
                    x=[float(node["lon"]) for node in client_nodes],
                    y=[float(node["lat"]) for node in client_nodes],
                    mode="markers",
                    marker={
                        "color": colors[1:],
                        "size": ANIMATION_SIZES["client"],
                        "line": {"color": ANIMATION_COLORS["black"], "width": 1.5},
                    },
                    hoverinfo="skip",
                ),
                    go.Scatter(
                    x=[float(nodes[0]["lon"])],
                    y=[float(nodes[0]["lat"])],
                    mode="markers",
                    marker={
                        "color": ANIMATION_COLORS["depot"],
                        "size": ANIMATION_SIZES["depot"],
                        "symbol": "circle",
                        "line": {"color": ANIMATION_COLORS["black"], "width": 1.2},
                    },
                    hoverinfo="skip",
                ),
                    go.Scatter(
                    x=[truck_lon],
                    y=[truck_lat],
                    mode="markers",
                    marker=truck_marker,
                    hoverinfo="skip",
                ),
                ]
            )
            return traces

        frames: list[go.Frame] = []
        truck_lon = float(nodes[0]["lon"])
        truck_lat = float(nodes[0]["lat"])
        truck_dx = 0.0
        initial_images = make_frame_images(truck_lon, truck_lat, truck_dx)
        if node_count >= 120:
            max_total_frames = 300
            target_frames_per_edge = 1
        elif node_count >= 80:
            max_total_frames = 450
            target_frames_per_edge = 1
        elif node_count >= 50:
            max_total_frames = 700
            target_frames_per_edge = 2
        else:
            max_total_frames = 1600
            target_frames_per_edge = 10

        estimated_real_segments = 0
        estimated_logical_edges = 0
        for route in solution.routes:
            visits_est = route.visits if hasattr(route, "visits") else list(route)
            if len(visits_est) < 2:
                continue
            estimated_logical_edges += len(visits_est) - 1
            for step_est in range(len(visits_est) - 1):
                i_est = int(visits_est[step_est])
                j_est = int(visits_est[step_est + 1])
                path_est = real_shortest_paths.get(i_est, {}).get(j_est)
                if path_est:
                    estimated_real_segments += max(1, len(path_est) - 1)
                else:
                    estimated_real_segments += 1

        import math

        segment_frame_budget = max(1, max_total_frames - estimated_logical_edges)
        segment_stride = max(1, int(math.ceil(estimated_real_segments / segment_frame_budget)))
        stop_generation = False

        for route in solution.routes:
            route_lons_acc: list[float | None] = []
            route_lats_acc: list[float | None] = []
            visits = route.visits if hasattr(route, "visits") else list(route)
            if len(visits) < 2:
                continue

            for step in range(len(visits) - 1):
                i, j = int(visits[step]), int(visits[step + 1])
                traffic_segments_step = build_traffic_segments(current_dynamic_costs)
                path_osm = real_shortest_paths.get(i, {}).get(j)
                if not path_osm:
                    path_local = shortest_paths.get(i, {}).get(j, [i, j]) or [i, j]
                    path_osm = []
                    for local_idx in path_local:
                        try:
                            idx = int(local_idx)
                        except Exception:
                            continue
                        if 0 <= idx < len(nodes):
                            path_osm.append(int(nodes[idx]["id"]))
                path_osm_clean: list[int] = []
                for osm_id in path_osm:
                    oid = int(osm_id)
                    if not path_osm_clean or path_osm_clean[-1] != oid:
                        path_osm_clean.append(oid)

                if len(path_osm_clean) < 2:
                    if i < len(nodes) and j < len(nodes):
                        path_osm_clean = [int(nodes[i]["id"]), int(nodes[j]["id"])]
                    else:
                        continue

                path_points: list[dict[str, Any]] = []
                for osm_id in path_osm_clean:
                    point = node_index.get(int(osm_id))
                    if point is not None:
                        path_points.append(point)
                if len(path_points) < 2:
                    if i < len(nodes) and j < len(nodes):
                        path_points = [nodes[i], nodes[j]]
                    else:
                        continue

                segment_count = max(1, len(path_points) - 1)
                substeps = max(1, int(round(target_frames_per_edge / segment_count)))

                for k in range(1, len(path_points)):
                    prev = path_points[k - 1]
                    seg_end = path_points[k]
                    is_last_segment = k == (len(path_points) - 1)
                    should_emit_this_segment = is_last_segment or (k % segment_stride == 0)

                    start_lon = float(prev["lon"])
                    start_lat = float(prev["lat"])
                    end_lon = float(seg_end["lon"])
                    end_lat = float(seg_end["lat"])

                    for sub_idx in range(1, substeps + 1):
                        t = sub_idx / substeps
                        interp_lon = start_lon + (end_lon - start_lon) * t
                        interp_lat = start_lat + (end_lat - start_lat) * t
                        truck_dx = interp_lon - truck_lon
                        truck_lon = interp_lon
                        truck_lat = interp_lat

                        route_lons_current = route_lons_acc.copy()
                        route_lats_current = route_lats_acc.copy()
                        route_lons_current += [start_lon, interp_lon]
                        route_lats_current += [start_lat, interp_lat]

                        should_emit_substep = should_emit_this_segment and (
                            node_count < 80 or sub_idx == substeps
                        )
                        if should_emit_substep:
                            frames.append(
                                go.Frame(
                                    data=make_base_traces(
                                        traffic_segments_step,
                                        route_lons_current,
                                        route_lats_current,
                                        client_colors.copy(),
                                        truck_lon,
                                        truck_lat,
                                    ),
                                    layout=go.Layout(images=make_frame_images(truck_lon, truck_lat, truck_dx)),
                                    name=str(len(frames)),
                                )
                            )
                            if len(frames) >= max_total_frames:
                                stop_generation = True
                                break

                    route_lons_acc += [start_lon, end_lon, None]
                    route_lats_acc += [start_lat, end_lat, None]
                    if stop_generation:
                        break

                if stop_generation:
                    break

                if j != 0 and j < len(client_colors):
                    client_colors[j] = ANIMATION_COLORS["client_delivered"]

                if len(frames) < max_total_frames:
                    frames.append(
                        go.Frame(
                            data=make_base_traces(
                                traffic_segments_step,
                                route_lons_acc.copy(),
                                route_lats_acc.copy(),
                                client_colors.copy(),
                                truck_lon,
                                truck_lat,
                            ),
                            layout=go.Layout(images=make_frame_images(truck_lon, truck_lat, truck_dx)),
                            name=str(len(frames)),
                        )
                    )

                # Le reseau evolue apres chaque arete logique, comme dans le GUI.
                current_dynamic_costs = evolve_dynamic_costs(current_dynamic_costs)
                if len(frames) >= max_total_frames:
                    stop_generation = True
                    break

            if stop_generation:
                break

        if not frames:
            return html.Div(
                "Aucune frame generee - solution vide.",
                style={"color": ANIMATION_COLORS["warn"]},
            )

        fig = go.Figure(
            data=frames[0].data if frames else [],
            frames=frames,
            layout=go.Layout(
                paper_bgcolor=PALETTE["transparent"],
                plot_bgcolor=PALETTE["transparent"] if basemap_overlay is not None else ANIMATION_COLORS["plot_bg"],
                font={"family": "Segoe UI, system-ui", "color": ANIMATION_COLORS["font_light"]},
                xaxis={
                    "showgrid": False,
                    "zeroline": False,
                    "showticklabels": False,
                    "scaleanchor": "y",
                    "scaleratio": 1,
                    "range": [bounds["lon_min"], bounds["lon_max"]],
                },
                yaxis={
                    "showgrid": False,
                    "zeroline": False,
                    "showticklabels": False,
                    "range": [bounds["lat_min"], bounds["lat_max"]],
                },
                margin={"l": 0, "r": 0, "t": 40, "b": 40},
                height=550,
                title={
                    "text": f"Simulation VRP - {len(solution.routes)} routes",
                    "font": {"size": 14},
                },
                showlegend=False,
                images=initial_images,
            ),
        )

        # Calculer les stats pour la tournee
        stats = calculate_vrp_solution_stats(
            solution,
            demands=solver_input.demands,
            depot=solver_input.depot,
        )

        return html.Div(
            [
                dcc.Graph(
                    id="graph-quartier-animation",
                    figure=fig,
                    config={"scrollZoom": True, "displayModeBar": True},
                    style={"flex": "1 1 auto", "minWidth": "0"},
                ),
                html.Div(
                    [
                        html.H4(
                            "Legende simulation",
                            style={
                                "margin": "0 0 10px 0",
                                "color": ANIMATION_COLORS["font_light"],
                                "fontSize": "14px",
                            },
                        ),
                        html.Div(
                            [
                                html.Span(
                                    style={
                                        "display": "inline-block",
                                        "width": "26px",
                                        "height": "0",
                                        "borderTop": f"3px solid {ANIMATION_COLORS['route']}",
                                        "marginRight": "8px",
                                    }
                                ),
                                html.Span("Trajet camion (sous-tournee)", style={"color": ANIMATION_COLORS["font_light"], "fontSize": "12px"}),
                            ],
                            style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
                        ),
                        html.Div(
                            [
                                html.Span(
                                    style={
                                        "display": "inline-block",
                                        "width": "12px",
                                        "height": "12px",
                                        "borderRadius": "50%",
                                        "backgroundColor": ANIMATION_COLORS["client_default"],
                                        "border": f"1px solid {ANIMATION_COLORS['black']}",
                                        "marginRight": "8px",
                                    }
                                ),
                                html.Span("Client non livre", style={"color": ANIMATION_COLORS["font_light"], "fontSize": "12px"}),
                            ],
                            style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
                        ),
                        html.Div(
                            [
                                html.Span(
                                    style={
                                        "display": "inline-block",
                                        "width": "12px",
                                        "height": "12px",
                                        "borderRadius": "50%",
                                        "backgroundColor": ANIMATION_COLORS["client_delivered"],
                                        "border": f"1px solid {ANIMATION_COLORS['black']}",
                                        "marginRight": "8px",
                                    }
                                ),
                                html.Span("Client livre", style={"color": ANIMATION_COLORS["font_light"], "fontSize": "12px"}),
                            ],
                            style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
                        ),
                        html.Div(
                            [
                                html.Span(
                                    style={
                                        "display": "inline-block",
                                        "width": "12px",
                                        "height": "12px",
                                        "borderRadius": "50%",
                                        "backgroundColor": ANIMATION_COLORS["depot"],
                                        "border": f"1px solid {ANIMATION_COLORS['black']}",
                                        "marginRight": "8px",
                                    }
                                ),
                                html.Span("Depot", style={"color": ANIMATION_COLORS["font_light"], "fontSize": "12px"}),
                            ],
                            style={"display": "flex", "alignItems": "center", "marginBottom": "12px"},
                        ),
                        html.Div("Congestion reseau", style={"color": ANIMATION_COLORS["font_light"], "fontSize": "12px", "marginBottom": "6px"}),
                        html.Div(
                            style={
                                "height": "12px",
                                "borderRadius": "6px",
                                "border": f"1px solid {ANIMATION_COLORS['light']}",
                                "background": (
                                    "linear-gradient(90deg, "
                                    f"{ANIMATION_COLORS['traffic_low']} 0%, "
                                    f"{ANIMATION_COLORS['traffic_mid']} 50%, "
                                    f"{ANIMATION_COLORS['traffic_high']} 80%, "
                                    f"{ANIMATION_COLORS['traffic_max']} 100%)"
                                ),
                                "marginBottom": "6px",
                            }
                        ),
                        html.Div(
                            [
                                html.Span("Fluide", style={"color": ANIMATION_COLORS["font_light"], "fontSize": "11px"}),
                                html.Span("Chargee", style={"color": ANIMATION_COLORS["font_light"], "fontSize": "11px"}),
                            ],
                            style={"display": "flex", "justifyContent": "space-between"},
                        ),
                        # Separator before stats
                        html.Hr(
                            style={
                                "borderColor": PALETTE["border_dark"],
                                "margin": "12px 0",
                            }
                        ),
                        # Stats section
                        html.H4(
                            "Recapitulatif tournee",
                            style={
                                "margin": "0 0 10px 0",
                                "color": ANIMATION_COLORS["font_light"],
                                "fontSize": "13px",
                                "fontWeight": "600",
                            },
                        ),
                        html.Div(
                            [
                                html.Span(
                                    "Livraisons :",
                                    style={"color": ANIMATION_COLORS["font_light"], "fontSize": "11px"},
                                ),
                                html.Span(
                                    str(stats["num_deliveries"]),
                                    style={"color": ANIMATION_COLORS["light"], "fontSize": "11px", "fontWeight": "600"},
                                ),
                            ],
                            style={"display": "flex", "justifyContent": "space-between", "marginBottom": "6px"},
                        ),
                        html.Div(
                            [
                                html.Span(
                                    "Sous-tournees :",
                                    style={"color": ANIMATION_COLORS["font_light"], "fontSize": "11px"},
                                ),
                                html.Span(
                                    str(stats["num_routes"]),
                                    style={"color": ANIMATION_COLORS["light"], "fontSize": "11px", "fontWeight": "600"},
                                ),
                            ],
                            style={"display": "flex", "justifyContent": "space-between", "marginBottom": "6px"},
                        ),
                        html.Div(
                            [
                                html.Span(
                                    "Cout total :",
                                    style={"color": ANIMATION_COLORS["font_light"], "fontSize": "11px"},
                                ),
                                html.Span(
                                    f"{stats['total_cost']:.2f}",
                                    style={"color": ANIMATION_COLORS["light"], "fontSize": "11px", "fontWeight": "600"},
                                ),
                            ],
                            style={"display": "flex", "justifyContent": "space-between", "marginBottom": "6px"},
                        ),
                        html.Div(
                            [
                                html.Span(
                                    "Cout/tournee :",
                                    style={"color": ANIMATION_COLORS["font_light"], "fontSize": "11px"},
                                ),
                                html.Span(
                                    f"{stats['avg_cost_per_route']:.2f}",
                                    style={"color": ANIMATION_COLORS["light"], "fontSize": "11px", "fontWeight": "600"},
                                ),
                            ],
                            style={"display": "flex", "justifyContent": "space-between"},
                        ),
                    ],
                    style={
                        "width": "260px",
                        "flex": "0 0 260px",
                        "alignSelf": "stretch",
                        "background": PALETTE["map_panel"],
                        "border": f"1px solid {PALETTE['border_dark']}",
                        "borderRadius": "8px",
                        "padding": "12px",
                    },
                ),
            ],
            style={"display": "flex", "gap": "12px", "alignItems": "stretch"},
        )
