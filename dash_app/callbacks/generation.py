"""Callbacks de l onglet Generation."""

from __future__ import annotations

import threading
from typing import Any
from uuid import uuid4

from dash import Input, Output, State, html, no_update
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go

from cesipath.graph_generator import GraphGenerator
from cesipath.models import EdgeStatus, GraphGenerationConfig, GraphInstance
from cesipath.solver_input import build_static_solver_input

from components.log_console import LOG_STORE, render_log_lines

_MAX_LOG_LINES = 800
_LOG_HISTORY: list[dict[str, str]] = []


class FieldValidationError(ValueError):
    """Erreur de validation de champ formulaire."""

    def __init__(self, field_name: str, reason: str) -> None:
        super().__init__(f"{field_name}: {reason}")
        self.field_name = field_name
        self.reason = reason


def _enqueue_log(level: str, message: str) -> None:
    LOG_STORE.push("generation", level, message)


def _render_logs() -> list[html.Div]:
    fresh = LOG_STORE.drain("generation", max=50)
    if fresh:
        _LOG_HISTORY.extend(fresh)
        if len(_LOG_HISTORY) > _MAX_LOG_LINES:
            del _LOG_HISTORY[:-_MAX_LOG_LINES]
    return render_log_lines(_LOG_HISTORY)


def _placeholder_figure() -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title="Instance VRP - aucun resultat",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Segoe UI, system-ui, sans-serif", "color": "#E8E8E8"},
        legend={"bgcolor": "rgba(0,0,0,0)"},
        xaxis={"visible": False},
        yaxis={"visible": False},
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
        annotations=[
            {
                "text": "Lancez la generation pour afficher l'instance",
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
            }
        ],
    )
    return fig


def _is_int_like(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return value.is_integer()
    text = str(value).strip()
    if text == "":
        return False
    if text.startswith("+"):
        text = text[1:]
    return text.isdigit()


def _parse_int(value: Any, field_name: str, *, minimum: int) -> int:
    if value is None or str(value).strip() == "":
        raise FieldValidationError(field_name, "valeur obligatoire")
    if not _is_int_like(value):
        raise FieldValidationError(field_name, "doit etre un entier")

    parsed = int(float(value))
    if parsed < minimum:
        raise FieldValidationError(field_name, f"doit etre >= {minimum}")
    return parsed


def _parse_float(
    value: Any,
    field_name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    min_strict: bool = False,
) -> float:
    if value is None or str(value).strip() == "":
        raise FieldValidationError(field_name, "valeur obligatoire")

    try:
        parsed = float(value)
    except Exception as exc:
        raise FieldValidationError(field_name, "doit etre un nombre") from exc

    if minimum is not None:
        if min_strict and parsed <= minimum:
            raise FieldValidationError(field_name, f"doit etre > {minimum}")
        if not min_strict and parsed < minimum:
            raise FieldValidationError(field_name, f"doit etre >= {minimum}")

    if maximum is not None and parsed > maximum:
        raise FieldValidationError(field_name, f"doit etre <= {maximum}")

    return parsed


def _validate_generation_payload(payload: dict[str, Any]) -> dict[str, Any]:
    node_count = _parse_int(payload.get("node_count"), "node_count", minimum=3)
    seed = _parse_int(payload.get("seed"), "seed", minimum=0)
    dynamic_sigma = _parse_float(
        payload.get("dynamic_sigma"),
        "dynamic_sigma",
        minimum=0.0,
        min_strict=True,
    )
    dynamic_mean_reversion_strength = _parse_float(
        payload.get("dynamic_mean_reversion_strength"),
        "dynamic_mean_reversion_strength",
        minimum=0.0,
        maximum=1.0,
        min_strict=True,
    )
    dynamic_max_multiplier = _parse_float(
        payload.get("dynamic_max_multiplier"),
        "dynamic_max_multiplier",
        minimum=1.0,
    )
    dynamic_forbid_probability = _parse_float(
        payload.get("dynamic_forbid_probability"),
        "dynamic_forbid_probability",
        minimum=0.0,
        maximum=1.0,
    )
    dynamic_restore_probability = _parse_float(
        payload.get("dynamic_restore_probability"),
        "dynamic_restore_probability",
        minimum=0.0,
        maximum=1.0,
    )
    dynamic_max_disabled_ratio = _parse_float(
        payload.get("dynamic_max_disabled_ratio"),
        "dynamic_max_disabled_ratio",
        minimum=0.0,
        maximum=1.0,
    )

    return {
        "node_count": node_count,
        "seed": seed,
        "dynamic_sigma": dynamic_sigma,
        "dynamic_mean_reversion_strength": dynamic_mean_reversion_strength,
        "dynamic_max_multiplier": dynamic_max_multiplier,
        "dynamic_forbid_probability": dynamic_forbid_probability,
        "dynamic_restore_probability": dynamic_restore_probability,
        "dynamic_max_disabled_ratio": dynamic_max_disabled_ratio,
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
    return GraphGenerator(config).generate()


def _instance_edge_count(instance: GraphInstance) -> int:
    graph_obj = getattr(instance, "graph", None)
    if graph_obj is not None and hasattr(graph_obj, "edges"):
        try:
            return len(graph_obj.edges())
        except Exception:
            pass
    return len(instance.residual_edges)


def _build_instance_figure(instance: GraphInstance) -> go.Figure:
    status_colors = {
        EdgeStatus.FREE: "#4A9EBF",
        EdgeStatus.SURCHARGED: "#F0AD4E",
        EdgeStatus.FORBIDDEN: "#D9534F",
    }

    fig = go.Figure()

    for status in (EdgeStatus.FREE, EdgeStatus.SURCHARGED, EdgeStatus.FORBIDDEN):
        edge_x: list[float | None] = []
        edge_y: list[float | None] = []

        for (u, v), edge in instance.residual_edges.items():
            if edge.status != status:
                continue
            x1, y1 = instance.coordinates[u]
            x2, y2 = instance.coordinates[v]
            edge_x.extend([x1, x2, None])
            edge_y.extend([y1, y2, None])

        if edge_x:
            fig.add_trace(
                go.Scatter(
                    x=edge_x,
                    y=edge_y,
                    mode="lines",
                    line={"color": status_colors[status], "width": 2},
                    name=status.name,
                    showlegend=True,
                    hoverinfo="skip",
                )
            )

    nodes_list = sorted(instance.coordinates.keys())
    node_x = [instance.coordinates[node][0] for node in nodes_list]
    node_y = [instance.coordinates[node][1] for node in nodes_list]
    marker_size = [16 if node == instance.depot else 8 for node in nodes_list]
    marker_symbol = ["star" if node == instance.depot else "circle" for node in nodes_list]
    marker_color = ["#F0AD4E" if node == instance.depot else "#E8E8E8" for node in nodes_list]
    customdata = [instance.demands.get(node, 0) for node in nodes_list]

    fig.add_trace(
        go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            name="Noeuds",
            showlegend=False,
            text=[str(node) for node in nodes_list],
            textposition="top center",
            customdata=customdata,
            hovertemplate="Noeud %{text}<br>Demande : %{customdata}<extra></extra>",
            marker={
                "size": marker_size,
                "symbol": marker_symbol,
                "color": marker_color,
            },
        )
    )

    node_count = len(nodes_list)
    fig.update_layout(
        title=f"Instance VRP - {node_count} noeuds",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Segoe UI, system-ui, sans-serif", "color": "#E8E8E8"},
        legend={"bgcolor": "rgba(0,0,0,0)"},
        xaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
        yaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
    )

    return fig


def register_callbacks(app, session_cache: dict[str, Any], background_callback_manager=None) -> None:
    _ = background_callback_manager

    def _generation_worker(session_id: str, payload: dict[str, Any]) -> None:
        try:
            node_count = int(payload["node_count"])
            seed = int(payload["seed"])
            dynamic_sigma = float(payload["dynamic_sigma"])
            dynamic_mean_reversion_strength = float(payload["dynamic_mean_reversion_strength"])
            dynamic_max_multiplier = float(payload["dynamic_max_multiplier"])
            dynamic_forbid_probability = float(payload["dynamic_forbid_probability"])
            dynamic_restore_probability = float(payload["dynamic_restore_probability"])
            dynamic_max_disabled_ratio = float(payload["dynamic_max_disabled_ratio"])

            _enqueue_log("running", "Generation du graphe...")
            instance = generate_graph(
                node_count=node_count,
                seed=seed,
                dynamic_sigma=dynamic_sigma,
                dynamic_mean_reversion_strength=dynamic_mean_reversion_strength,
                dynamic_max_multiplier=dynamic_max_multiplier,
                dynamic_forbid_probability=dynamic_forbid_probability,
                dynamic_restore_probability=dynamic_restore_probability,
                dynamic_max_disabled_ratio=dynamic_max_disabled_ratio,
            )

            _enqueue_log("running", "Fermeture métrique (Dijkstra)...")
            solver_input = build_static_solver_input(instance)

            session_cache.setdefault(session_id, {})
            session_cache[session_id]["instance"] = instance
            session_cache[session_id]["solver_input"] = solver_input
            session_cache[session_id]["status"] = "done"
            _enqueue_log(
                "success",
                f"Instance générée : {node_count} noeuds, {_instance_edge_count(instance)} arêtes",
            )
        except Exception as exc:
            session_cache.setdefault(session_id, {})
            session_cache[session_id]["status"] = "error"
            session_cache[session_id]["error"] = str(exc)
            _enqueue_log("error", f"Erreur génération : {str(exc)}")

    @app.callback(
        Output("store-generation", "data", allow_duplicate=True),
        Input("generation-node-count", "value"),
        Input("generation-seed", "value"),
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
            validated = _validate_generation_payload(payload)
        except FieldValidationError as exc:
            _enqueue_log("error", f"Champ invalide : {exc.field_name} — {exc.reason}")
            payload["status"] = "error"
            payload["session_id"] = None
            return payload

        session_id = str(uuid4())
        session_cache[session_id] = {
            "status": "running",
            "instance": None,
            "solver_input": None,
            "error": None,
        }

        worker = threading.Thread(
            daemon=True,
            target=_generation_worker,
            args=(session_id, validated),
        )
        worker.start()

        validated["status"] = "running"
        validated["session_id"] = session_id
        return validated

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
            message = "Génération en cours"
            class_name = "status-message status-running"
        elif status == "done":
            message = "Génération terminee"
            class_name = "status-message status-success"
        elif status == "error":
            message = "Génération en erreur"
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
            return True, "Génération en cours..."
        return False, "Générer"

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
        Output("graph-generation-instance", "figure"),
        Input("store-generation", "data"),
    )
    def update_instance_graph(store_data: dict[str, Any]) -> go.Figure:
        data = store_data or {}
        status = str(data.get("status", "idle"))
        session_id = data.get("session_id")

        if status != "done" or not session_id:
            return _placeholder_figure()

        session_state = session_cache.get(session_id)
        if not session_state:
            return _placeholder_figure()

        instance = session_state.get("instance")
        if not isinstance(instance, GraphInstance):
            return _placeholder_figure()

        return _build_instance_figure(instance)
