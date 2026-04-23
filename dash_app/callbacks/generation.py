"""Callbacks de l onglet Generation."""

from __future__ import annotations

import base64
import math
from pathlib import Path
import threading
from typing import Any
from uuid import uuid4

from dash import Input, Output, State, dcc, html, no_update
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go

from cesipath.algorithms.genetic import genetic_algorithm
from cesipath.algorithms.grasp import grasp
from cesipath.algorithms.neighborhood import VRPSolution
from cesipath.algorithms.simulated_annealing import simulated_annealing
from cesipath.algorithms.tabu_search import tabu_search
from cesipath.dynamic_network import DynamicNetworkSimulator
from cesipath.models import DynamicGraphSnapshot, GraphGenerationConfig, GraphInstance
from cesipath.solver_input import SolverInput

from components.log_console import LOG_STORE, render_log_lines
from services import calculate_vrp_solution_stats, validate_generation_payload, validate_quartier_simulation_payload
from theme import ANIMATION_COLORS, PALETTE

_MAX_LOG_LINES = 800
_LOG_HISTORY: list[dict[str, str]] = []

ALGO_FUNCTIONS = {
    "grasp": grasp,
    "tabu_search": tabu_search,
    "simulated_annealing": simulated_annealing,
    "genetic_algorithm": genetic_algorithm,
}

ANIMATION_SIZES = {
    "network_width": 2.0,
    "disabled_width": 1.5,
    "route_width": 3.2,
    "client": 14,
    "depot": 16,
    "truck": 72,
}

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_TRUCK_RIGHT_PATH = _PROJECT_ROOT / "image" / "camionD.png"
_TRUCK_LEFT_PATH = _PROJECT_ROOT / "image" / "camionG.png"
_TRUCK_URI_CACHE: dict[str, str | None] = {"right": None, "left": None}


def _enqueue_log(level: str, message: str) -> None:
    LOG_STORE.push("generation", level, message)


def _render_logs() -> list[html.Div]:
    fresh = LOG_STORE.drain("generation", max=50)
    if fresh:
        _LOG_HISTORY.extend(fresh)
        if len(_LOG_HISTORY) > _MAX_LOG_LINES:
            del _LOG_HISTORY[:-_MAX_LOG_LINES]
    return render_log_lines(_LOG_HISTORY)


def _placeholder_animation(status: str = "idle") -> html.Div:
    messages = {
        "idle": "Lancez la generation et la simulation pour afficher l'animation.",
        "running": "Generation et simulation en cours...",
        "error": "La simulation n'a pas pu etre construite.",
    }
    return html.Div(
        messages.get(status, messages["idle"]),
        className="generation-animation-placeholder",
    )


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
        return _mix_hex_color(
            ANIMATION_COLORS["traffic_low"],
            ANIMATION_COLORS["traffic_mid"],
            ratio / 0.5,
        )
    if ratio <= 0.8:
        return _mix_hex_color(
            ANIMATION_COLORS["traffic_mid"],
            ANIMATION_COLORS["traffic_high"],
            (ratio - 0.5) / 0.3,
        )
    return _mix_hex_color(
        ANIMATION_COLORS["traffic_high"],
        ANIMATION_COLORS["traffic_max"],
        (ratio - 0.8) / 0.2,
    )


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


def _compute_bounds(instance: GraphInstance) -> dict[str, float]:
    xs = [coord[0] for coord in instance.coordinates.values()]
    ys = [coord[1] for coord in instance.coordinates.values()]
    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)

    pad_x = (max_x - min_x) * 0.08 if max_x > min_x else 3.0
    pad_y = (max_y - min_y) * 0.08 if max_y > min_y else 3.0

    return {
        "lon_min": min_x - pad_x,
        "lon_max": max_x + pad_x,
        "lat_min": min_y - pad_y,
        "lat_max": max_y + pad_y,
    }


def _build_truck_overlay(
    truck_x: float,
    truck_y: float,
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

    span_x = max(bounds["lon_max"] - bounds["lon_min"], 0.0001)
    span_y = max(bounds["lat_max"] - bounds["lat_min"], 0.0001)
    truck_w = span_x * 0.07
    truck_h = span_y * 0.09

    return {
        "source": source,
        "xref": "x",
        "yref": "y",
        "x": truck_x,
        "y": truck_y,
        "sizex": truck_w,
        "sizey": truck_h,
        "xanchor": "center",
        "yanchor": "middle",
        "sizing": "stretch",
        "opacity": 1.0,
        "layer": "above",
    }


def generate_graph(
    *,
    node_count: int,
    seed: int,
    dynamic_sigma: float,
    dynamic_mean_reversion_strength: float,
    dynamic_max_multiplier: float,
    dynamic_forbid_probability: float,
    dynamic_restore_probability: float,
    dynamic_max_disabled_ratio: float,
) -> GraphInstance:
    """Construit une instance via GraphGenerator."""

    config = GraphGenerationConfig(
        node_count=node_count,
        seed=seed,
        auto_density_profile=True,
        dynamic_sigma=dynamic_sigma,
        dynamic_mean_reversion_strength=dynamic_mean_reversion_strength,
        dynamic_max_multiplier=dynamic_max_multiplier,
        dynamic_forbid_probability=dynamic_forbid_probability,
        dynamic_restore_probability=dynamic_restore_probability,
        dynamic_max_disabled_ratio=dynamic_max_disabled_ratio,
    )
    from cesipath.graph_generator import GraphGenerator

    return GraphGenerator(config).generate()


def _instance_edge_count(instance: GraphInstance) -> int:
    return len(instance.residual_edges)


def _resolve_path(paths: dict[tuple[int, int], list[int]], start: int, end: int) -> list[int]:
    if start == end:
        return [start]
    key = (min(start, end), max(start, end))
    path = paths.get(key)
    if not path:
        return [start, end]
    if start <= end:
        return list(path)
    return list(reversed(path))


def _build_network_segments(
    instance: GraphInstance,
    snapshot: DynamicGraphSnapshot,
    *,
    bins_count: int,
) -> tuple[list[dict[str, Any]], dict[str, list[float | None]]]:
    ratio_den = max(instance.config.dynamic_max_multiplier - 1.0, 1e-9)
    bins_x: list[list[float | None]] = [[] for _ in range(bins_count)]
    bins_y: list[list[float | None]] = [[] for _ in range(bins_count)]
    disabled_x: list[float | None] = []
    disabled_y: list[float | None] = []

    for key, edge in instance.residual_edges.items():
        if edge.static_cost == float("inf"):
            continue

        u, v = key
        x1, y1 = instance.coordinates[u]
        x2, y2 = instance.coordinates[v]
        seg_x = [x1, x2, None]
        seg_y = [y1, y2, None]

        if not snapshot.edge_availability.get(key, False):
            disabled_x.extend(seg_x)
            disabled_y.extend(seg_y)
            continue

        dynamic_cost = float(snapshot.edge_costs.get(key, edge.static_cost))
        static_cost = float(edge.static_cost)
        dynamic_ratio = (dynamic_cost / static_cost) if static_cost > 0 else 1.0
        congestion = max(0.0, min(1.0, (dynamic_ratio - 1.0) / ratio_den))
        bin_idx = min(bins_count - 1, int(congestion * bins_count))
        bins_x[bin_idx].extend(seg_x)
        bins_y[bin_idx].extend(seg_y)

    segments: list[dict[str, Any]] = []
    for idx in range(bins_count):
        segments.append(
            {
                "x": bins_x[idx],
                "y": bins_y[idx],
                "color": _interpolate_traffic_color((idx + 0.5) / bins_count),
            }
        )

    return segments, {"x": disabled_x, "y": disabled_y}


def _build_generation_animation(
    instance: GraphInstance,
    solution: VRPSolution,
    initial_snapshot: DynamicGraphSnapshot,
    simulation_seed: int,
) -> html.Div:
    node_count = instance.node_count
    if node_count >= 120:
        traffic_bins_count = 4
    elif node_count >= 80:
        traffic_bins_count = 5
    else:
        traffic_bins_count = 10

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

    bounds = _compute_bounds(instance)
    client_ids = [
        node
        for node in sorted(instance.coordinates)
        if node != instance.depot and instance.demands.get(node, 0) > 0
    ]
    delivered_colors = {node: ANIMATION_COLORS["client_default"] for node in client_ids}
    replay_simulator = DynamicNetworkSimulator(instance, seed=simulation_seed)
    warmup = replay_simulator.initialize_snapshot()
    _ = replay_simulator.advance(warmup)
    current_snapshot = initial_snapshot

    left_sprite = _load_truck_sprite_uri("left")
    right_sprite = _load_truck_sprite_uri("right")
    truck_png_available = left_sprite is not None or right_sprite is not None

    def make_frame_images(truck_x: float, truck_y: float, truck_dx: float) -> list[dict[str, Any]]:
        images: list[dict[str, Any]] = []
        truck_overlay = _build_truck_overlay(truck_x, truck_y, truck_dx, bounds=bounds)
        if truck_overlay is not None:
            images.append(truck_overlay)
        return images

    def make_base_traces(
        snapshot: DynamicGraphSnapshot,
        route_x: list[float | None],
        route_y: list[float | None],
        truck_x: float,
        truck_y: float,
        truck_dx: float,
    ) -> list[go.Scatter]:
        traffic_segments, disabled_segments = _build_network_segments(
            instance,
            snapshot,
            bins_count=traffic_bins_count,
        )
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

        traces.append(
            go.Scatter(
                x=disabled_segments["x"],
                y=disabled_segments["y"],
                mode="lines",
                line={
                    "color": ANIMATION_COLORS["forbidden"],
                    "width": ANIMATION_SIZES["disabled_width"],
                    "dash": "dash",
                },
                hoverinfo="skip",
                showlegend=False,
            )
        )
        traces.append(
            go.Scatter(
                x=route_x,
                y=route_y,
                mode="lines",
                line={"color": ANIMATION_COLORS["route"], "width": ANIMATION_SIZES["route_width"]},
                hoverinfo="skip",
                showlegend=False,
            )
        )
        traces.append(
            go.Scatter(
                x=[instance.coordinates[node][0] for node in client_ids],
                y=[instance.coordinates[node][1] for node in client_ids],
                mode="markers",
                marker={
                    "color": [delivered_colors[node] for node in client_ids],
                    "size": ANIMATION_SIZES["client"],
                    "line": {"color": ANIMATION_COLORS["black"], "width": 1.5},
                },
                customdata=client_ids,
                hovertemplate="Client %{customdata}<extra></extra>",
                showlegend=False,
            )
        )
        traces.append(
            go.Scatter(
                x=[instance.coordinates[instance.depot][0]],
                y=[instance.coordinates[instance.depot][1]],
                mode="markers",
                marker={
                    "color": ANIMATION_COLORS["depot"],
                    "size": ANIMATION_SIZES["depot"],
                    "symbol": "circle",
                    "line": {"color": ANIMATION_COLORS["black"], "width": 1.2},
                },
                hovertemplate=f"Depot {instance.depot}<extra></extra>",
                showlegend=False,
            )
        )
        traces.append(
            go.Scatter(
                x=[truck_x],
                y=[truck_y],
                mode="markers",
                marker=truck_marker,
                hoverinfo="skip",
                showlegend=False,
            )
        )
        return traces

    estimated_real_segments = 0
    estimated_logical_edges = 0
    for route in solution.routes:
        if len(route) < 2:
            continue
        estimated_logical_edges += len(route) - 1
        for idx in range(len(route) - 1):
            path_est = _resolve_path(current_snapshot.completed_paths, int(route[idx]), int(route[idx + 1]))
            estimated_real_segments += max(1, len(path_est) - 1)

    segment_frame_budget = max(1, max_total_frames - estimated_logical_edges)
    segment_stride = max(1, int(math.ceil(estimated_real_segments / segment_frame_budget)))

    frames: list[go.Frame] = []
    truck_x, truck_y = instance.coordinates[instance.depot]
    truck_dx = 0.0
    stop_generation = False

    for route in solution.routes:
        route_x_acc: list[float | None] = []
        route_y_acc: list[float | None] = []
        visits = list(route)
        if len(visits) < 2:
            continue

        for step in range(len(visits) - 1):
            start = int(visits[step])
            end = int(visits[step + 1])
            path_nodes = _resolve_path(current_snapshot.completed_paths, start, end)
            if len(path_nodes) < 2:
                path_nodes = [start, end]

            segment_count = max(1, len(path_nodes) - 1)
            substeps = max(1, int(round(target_frames_per_edge / segment_count)))

            for segment_idx in range(1, len(path_nodes)):
                prev_node = int(path_nodes[segment_idx - 1])
                next_node = int(path_nodes[segment_idx])
                start_x, start_y = instance.coordinates[prev_node]
                end_x, end_y = instance.coordinates[next_node]
                is_last_segment = segment_idx == (len(path_nodes) - 1)
                should_emit_this_segment = is_last_segment or (segment_idx % segment_stride == 0)

                for sub_idx in range(1, substeps + 1):
                    t = sub_idx / substeps
                    interp_x = start_x + (end_x - start_x) * t
                    interp_y = start_y + (end_y - start_y) * t
                    truck_dx = interp_x - truck_x
                    truck_x = interp_x
                    truck_y = interp_y

                    route_x_current = route_x_acc.copy() + [start_x, interp_x]
                    route_y_current = route_y_acc.copy() + [start_y, interp_y]

                    should_emit_substep = should_emit_this_segment and (
                        node_count < 80 or sub_idx == substeps
                    )
                    if should_emit_substep:
                        frames.append(
                            go.Frame(
                                data=make_base_traces(
                                    current_snapshot,
                                    route_x_current,
                                    route_y_current,
                                    truck_x,
                                    truck_y,
                                    truck_dx,
                                ),
                                layout=go.Layout(images=make_frame_images(truck_x, truck_y, truck_dx)),
                                name=str(len(frames)),
                            )
                        )
                        if len(frames) >= max_total_frames:
                            stop_generation = True
                            break

                route_x_acc += [start_x, end_x, None]
                route_y_acc += [start_y, end_y, None]
                if stop_generation:
                    break

            if stop_generation:
                break

            if end != instance.depot:
                delivered_colors[end] = ANIMATION_COLORS["client_delivered"]

            if len(frames) < max_total_frames:
                frames.append(
                    go.Frame(
                        data=make_base_traces(
                            current_snapshot,
                            route_x_acc.copy(),
                            route_y_acc.copy(),
                            truck_x,
                            truck_y,
                            truck_dx,
                        ),
                        layout=go.Layout(images=make_frame_images(truck_x, truck_y, truck_dx)),
                        name=str(len(frames)),
                    )
                )

            current_snapshot = replay_simulator.advance(current_snapshot)
            if len(frames) >= max_total_frames:
                stop_generation = True
                break

        if stop_generation:
            break

    if not frames:
        return html.Div(
            "Aucune frame generee - solution vide.",
            className="generation-animation-placeholder",
        )

    fig = go.Figure(
        data=frames[0].data,
        frames=frames,
        layout=go.Layout(
            paper_bgcolor=PALETTE["transparent"],
            plot_bgcolor=ANIMATION_COLORS["plot_bg"],
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
            title={
                "text": f"Simulation VRP - {len(solution.routes)} routes",
                "font": {"size": 14},
            },
            showlegend=False,
            images=make_frame_images(instance.coordinates[instance.depot][0], instance.coordinates[instance.depot][1], 0.0),
        ),
    )

    # Calculer les stats pour la tournee
    stats = calculate_vrp_solution_stats(
        solution,
        demands=instance.demands,
        depot=instance.depot,
    )

    legend_panel = html.Div(
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
                    html.Span(
                        "Trajet camion",
                        style={"color": ANIMATION_COLORS["font_light"], "fontSize": "12px"},
                    ),
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
                    html.Span(
                        "Client non livre",
                        style={"color": ANIMATION_COLORS["font_light"], "fontSize": "12px"},
                    ),
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
                    html.Span(
                        "Client livre",
                        style={"color": ANIMATION_COLORS["font_light"], "fontSize": "12px"},
                    ),
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
                    html.Span(
                        "Depot",
                        style={"color": ANIMATION_COLORS["font_light"], "fontSize": "12px"},
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
            ),
            html.Div(
                [
                    html.Span(
                        style={
                            "display": "inline-block",
                            "width": "26px",
                            "height": "0",
                            "borderTop": f"2px dashed {ANIMATION_COLORS['forbidden']}",
                            "marginRight": "8px",
                        }
                    ),
                    html.Span(
                        "Route temporairement indisponible",
                        style={"color": ANIMATION_COLORS["font_light"], "fontSize": "12px"},
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "marginBottom": "12px"},
            ),
            html.Div(
                "Congestion reseau",
                style={"color": ANIMATION_COLORS["font_light"], "fontSize": "12px", "marginBottom": "6px"},
            ),
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
                    html.Span(
                        "Fluide",
                        style={"color": ANIMATION_COLORS["font_light"], "fontSize": "11px"},
                    ),
                    html.Span(
                        "Chargee",
                        style={"color": ANIMATION_COLORS["font_light"], "fontSize": "11px"},
                    ),
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
    )

    return html.Div(
        [
            dcc.Graph(
                id="graph-generation-animation",
                figure=fig,
                config={
                    "scrollZoom": True,
                    "displayModeBar": True,
                    "displaylogo": False,
                    "responsive": True,
                },
                style={"flex": "1 1 auto", "minWidth": "0", "height": "100%"},
            ),
            legend_panel,
        ],
        style={"display": "flex", "gap": "12px", "alignItems": "stretch", "height": "100%"},
    )


def register_callbacks(app, session_cache: dict[str, Any], background_callback_manager=None) -> None:
    _ = background_callback_manager

    def _generation_worker(session_id: str, generation_payload: dict[str, Any], simulation_payload: dict[str, Any]) -> None:
        try:
            node_count = int(generation_payload["node_count"])
            generation_seed = int(generation_payload["seed"])
            dynamic_sigma = float(generation_payload["dynamic_sigma"])
            dynamic_mean_reversion_strength = float(generation_payload["dynamic_mean_reversion_strength"])
            dynamic_max_multiplier = float(generation_payload["dynamic_max_multiplier"])
            dynamic_forbid_probability = float(generation_payload["dynamic_forbid_probability"])
            dynamic_restore_probability = float(generation_payload["dynamic_restore_probability"])
            dynamic_max_disabled_ratio = float(generation_payload["dynamic_max_disabled_ratio"])

            algo_name = str(simulation_payload["algo_name"])
            capacity = int(simulation_payload["capacity"])
            simulation_seed = int(simulation_payload["seed"])

            _enqueue_log("running", "Generation du graphe...")
            instance = generate_graph(
                node_count=node_count,
                seed=generation_seed,
                dynamic_sigma=dynamic_sigma,
                dynamic_mean_reversion_strength=dynamic_mean_reversion_strength,
                dynamic_max_multiplier=dynamic_max_multiplier,
                dynamic_forbid_probability=dynamic_forbid_probability,
                dynamic_restore_probability=dynamic_restore_probability,
                dynamic_max_disabled_ratio=dynamic_max_disabled_ratio,
            )
            _enqueue_log(
                "info",
                f"Instance generee : {node_count} noeuds, {_instance_edge_count(instance)} aretes residuelles",
            )

            _enqueue_log("running", "Initialisation de la ponderation dynamique...")
            simulator = DynamicNetworkSimulator(instance, seed=simulation_seed)
            initial_static_snapshot = simulator.initialize_snapshot()
            dynamic_snapshot = simulator.advance(initial_static_snapshot)

            solver_input = SolverInput(
                cost_matrix=dynamic_snapshot.completed_costs,
                depot=instance.depot,
                demands=instance.demands,
                vehicle_capacity=capacity,
                shortest_paths=dynamic_snapshot.completed_paths,
                source="dynamic",
                dynamic_step=dynamic_snapshot.step,
            )

            _enqueue_log("running", f"Resolution {algo_name}...")
            solution = ALGO_FUNCTIONS[algo_name](solver_input, seed=simulation_seed)

            session_cache.setdefault(session_id, {})
            session_cache[session_id]["instance"] = instance
            session_cache[session_id]["solver_input"] = solver_input
            session_cache[session_id]["solution"] = solution
            session_cache[session_id]["initial_snapshot"] = dynamic_snapshot
            session_cache[session_id]["simulation_seed"] = simulation_seed
            session_cache[session_id]["status"] = "done"

            summary = instance.summary()
            _enqueue_log(
                "success",
                f"Simulation prete : {len(solution.routes)} routes, cout total {float(solution.total_cost):.1f}",
            )
            _enqueue_log(
                "info",
                (
                    f"Demande uniforme={summary['uniform_demand']}, capacite vehicule={capacity}, "
                    f"nb minimal de routes theorique={summary['minimum_route_count']}"
                ),
            )
        except Exception as exc:
            session_cache.setdefault(session_id, {})
            session_cache[session_id]["status"] = "error"
            session_cache[session_id]["error"] = str(exc)
            _enqueue_log("error", f"Erreur generation/simulation : {str(exc)}")

    @app.callback(
        Output("store-generation", "data", allow_duplicate=True),
        Input("generation-node-count", "value"),
        Input("generation-seed", "value"),
        Input("generation-algo", "value"),
        Input("generation-capacity", "value"),
        Input("generation-sim-seed", "value"),
        Input("generation-sigma", "value"),
        Input("generation-mean-reversion", "value"),
        Input("generation-max-multiplier", "value"),
        Input("generation-forbid-prob", "value"),
        Input("generation-restore-prob", "value"),
        Input("generation-max-disabled-ratio", "value"),
        State("store-generation", "data"),
        prevent_initial_call=True,
    )
    def sync_store_from_form(
        node_count: Any,
        seed: Any,
        algo_name: str,
        capacity: Any,
        simulation_seed: Any,
        sigma: Any,
        mean_reversion: Any,
        max_multiplier: Any,
        forbid_prob: Any,
        restore_prob: Any,
        max_disabled_ratio: Any,
        store_data: dict[str, Any],
    ) -> dict[str, Any] | Any:
        data = dict(store_data or {})
        if data.get("status") == "running":
            return no_update

        data["node_count"] = node_count
        data["seed"] = seed
        data["algo_name"] = algo_name
        data["capacity"] = capacity
        data["simulation_seed"] = simulation_seed
        data["dynamic_sigma"] = sigma
        data["dynamic_mean_reversion_strength"] = mean_reversion
        data["dynamic_max_multiplier"] = max_multiplier
        data["dynamic_forbid_probability"] = forbid_prob
        data["dynamic_restore_probability"] = restore_prob
        data["dynamic_max_disabled_ratio"] = max_disabled_ratio
        return data

    @app.callback(
        Output("store-generation", "data", allow_duplicate=True),
        Input("generation-run", "n_clicks"),
        State("store-generation", "data"),
        prevent_initial_call=True,
    )
    def launch_generation(n_clicks: int, store_data: dict[str, Any]) -> dict[str, Any]:
        if not n_clicks:
            raise PreventUpdate

        payload = dict(store_data or {})
        try:
            generation_payload = validate_generation_payload(payload)
            simulation_payload = validate_quartier_simulation_payload(
                payload={
                    "algo_name": payload.get("algo_name"),
                    "capacity": payload.get("capacity"),
                    "seed": payload.get("simulation_seed"),
                    "max_clients": max(1, int(payload.get("node_count", 1)) - 1),
                },
                allowed_algorithms=set(ALGO_FUNCTIONS),
            )
        except Exception as exc:
            _enqueue_log("error", f"Parametres generation invalides : {exc}")
            payload["status"] = "error"
            payload["session_id"] = None
            return payload

        session_id = str(uuid4())
        session_cache[session_id] = {
            "status": "running",
            "instance": None,
            "solver_input": None,
            "solution": None,
            "initial_snapshot": None,
            "error": None,
        }

        worker = threading.Thread(
            daemon=True,
            target=_generation_worker,
            args=(session_id, generation_payload, simulation_payload),
        )
        worker.start()

        payload["status"] = "running"
        payload["session_id"] = session_id
        return payload

    @app.callback(
        Output("generation-status-message", "children"),
        Output("generation-status-message", "className"),
        Output("generation-loading-target", "children"),
        Input("store-generation", "data"),
    )
    def sync_status(store_data: dict[str, Any]) -> tuple[str, str, html.Span]:
        data = store_data or {}
        status = str(data.get("status", "idle"))

        if status == "running":
            message = "Generation et simulation en cours"
            class_name = "status-message status-running"
        elif status == "done":
            message = "Simulation terminee"
            class_name = "status-message status-success"
        elif status == "error":
            message = "Generation/Simulation en erreur"
            class_name = "status-message status-error"
        else:
            message = "Idle"
            class_name = "status-message status-idle"

        return message, class_name, html.Span(message, className="loading-token")

    @app.callback(
        Output("generation-run", "disabled"),
        Output("generation-run", "children"),
        Input("store-generation", "data"),
    )
    def sync_button_state(store_data: dict[str, Any]) -> tuple[bool, str]:
        status = str((store_data or {}).get("status", "idle"))
        if status == "running":
            return True, "Generation + simulation en cours..."
        return False, "Generer et simuler"

    @app.callback(
        Output("generation-graph-shell", "className"),
        Output("generation-graph-toggle", "children"),
        Input("generation-graph-toggle", "n_clicks"),
    )
    def sync_graph_display_mode(n_clicks: int | None) -> tuple[str, str]:
        expanded = bool(n_clicks and n_clicks % 2 == 1)
        if expanded:
            return (
                "card generation-graph-shell generation-graph-shell-expanded",
                "Quitter le plein ecran",
            )
        return "card generation-graph-shell", "Plein ecran simulation"

    @app.callback(
        Output("log-output-generation", "children"),
        Output("store-generation", "data", allow_duplicate=True),
        Input("log-interval-generation", "n_intervals"),
        State("store-generation", "data"),
        prevent_initial_call=True,
    )
    def poll_logs_and_sync_status(
        _: int,
        store_data: dict[str, Any],
    ) -> tuple[list[html.Div], dict[str, Any] | Any]:
        data = dict(store_data or {})
        session_id = data.get("session_id")

        next_store: dict[str, Any] | Any = no_update
        if session_id:
            session_state = session_cache.get(session_id)
            if session_state is not None:
                status = session_state.get("status")
                current_status = data.get("status")
                if status == "done" and current_status != "done":
                    data["status"] = "done"
                    next_store = data
                elif status == "error" and current_status != "error":
                    data["status"] = "error"
                    next_store = data

        return _render_logs(), next_store

    @app.callback(
        Output("animation-container-generation", "children"),
        Input("store-generation", "data"),
    )
    def render_animation(store_data: dict[str, Any]):
        data = store_data or {}
        status = str(data.get("status", "idle"))
        session_id = data.get("session_id")

        if status != "done" or not session_id:
            return _placeholder_animation(status)

        session_state = session_cache.get(session_id)
        if not session_state:
            return _placeholder_animation("error")

        instance = session_state.get("instance")
        solution = session_state.get("solution")
        initial_snapshot = session_state.get("initial_snapshot")
        simulation_seed = session_state.get("simulation_seed", 42)

        if not isinstance(instance, GraphInstance):
            return _placeholder_animation("error")
        if not isinstance(solution, VRPSolution):
            return _placeholder_animation("error")
        if not isinstance(initial_snapshot, DynamicGraphSnapshot):
            return _placeholder_animation("error")

        return _build_generation_animation(
            instance,
            solution,
            initial_snapshot,
            int(simulation_seed),
        )
