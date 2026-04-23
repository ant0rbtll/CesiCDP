"""Callbacks de l onglet Benchmark."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

from dash import Input, Output, State, html, no_update
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go

from cesipath.algorithms.benchmark import run_benchmark, save_benchmark_figures
from cesipath.algorithms.genetic import genetic_algorithm
from cesipath.algorithms.grasp import grasp
from cesipath.algorithms.simulated_annealing import simulated_annealing
from cesipath.algorithms.tabu_search import tabu_search
from gui.services import parse_int_list

from components.log_console import LOG_STORE, render_log_lines

ALGO_FUNCTIONS = {
    "grasp": grasp,
    "tabu_search": tabu_search,
    "simulated_annealing": simulated_annealing,
    "genetic_algorithm": genetic_algorithm,
}

ALGO_COLORS = ["#4A9EBF", "#5CB85C", "#F0AD4E", "#D9534F"]

_MAX_LOG_LINES = 800
_LOG_HISTORY: list[dict[str, str]] = []


def _enqueue_log(level: str, message: str) -> None:
    LOG_STORE.push("benchmark", level, message)


def _render_logs() -> list[html.Div]:
    fresh = LOG_STORE.drain("benchmark", max=50)
    if fresh:
        _LOG_HISTORY.extend(fresh)
        if len(_LOG_HISTORY) > _MAX_LOG_LINES:
            del _LOG_HISTORY[:-_MAX_LOG_LINES]
    return render_log_lines(_LOG_HISTORY)


def _placeholder_figure(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=title,
        margin={"l": 40, "r": 20, "t": 50, "b": 40},
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[
            {
                "text": "Aucun resultat benchmark",
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
            }
        ],
    )
    return _apply_common_layout(fig)


def _ordered_unique(values: list[Any]) -> list[Any]:
    seen: list[Any] = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _apply_common_layout(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Segoe UI, system-ui, sans-serif", "color": "#E8E8E8"},
        legend={"bgcolor": "rgba(0,0,0,0)"},
    )
    return fig


def _build_quality_figure(results: list[dict[str, Any]]) -> go.Figure:
    algos = _ordered_unique([row["algo"] for row in results])
    fig = go.Figure()

    for idx, algo in enumerate(algos):
        values = [float(row["cost"]) for row in results if row["algo"] == algo]
        fig.add_trace(
            go.Box(
                x=[algo] * len(values),
                y=values,
                name=algo,
                marker={"color": ALGO_COLORS[idx % len(ALGO_COLORS)]},
                boxmean=True,
            )
        )

    fig.update_layout(
        title="Qualite des solutions par algorithme",
        xaxis={"title": "Algorithme"},
        yaxis={"title": "Cout solution"},
        margin={"l": 60, "r": 20, "t": 60, "b": 50},
    )
    return _apply_common_layout(fig)


def _build_gap_figure(results: list[dict[str, Any]]) -> go.Figure:
    sizes = sorted(_ordered_unique([int(row["size"]) for row in results]))
    algos = _ordered_unique([row["algo"] for row in results])

    best_per_instance: dict[tuple[int, int], float] = {}
    for row in results:
        key = (int(row["size"]), int(row["seed"]))
        cost = float(row["cost"])
        current = best_per_instance.get(key)
        if current is None or cost < current:
            best_per_instance[key] = cost

    gap_by_size_algo: dict[tuple[int, str], float] = {}
    for size in sizes:
        for algo in algos:
            values: list[float] = []
            for row in results:
                if int(row["size"]) != size or row["algo"] != algo:
                    continue
                key = (int(row["size"]), int(row["seed"]))
                best = best_per_instance.get(key)
                if best is None or best <= 0:
                    continue
                values.append(100.0 * (float(row["cost"]) - best) / best)
            gap_by_size_algo[(size, algo)] = _safe_mean(values)

    fig = go.Figure()
    for idx, algo in enumerate(algos):
        y_values = [gap_by_size_algo.get((size, algo), 0.0) for size in sizes]
        fig.add_trace(
            go.Bar(
                x=sizes,
                y=y_values,
                name=algo,
                marker={"color": ALGO_COLORS[idx % len(ALGO_COLORS)]},
            )
        )

    fig.update_layout(
        barmode="group",
        title="Ecart au meilleur (%) par taille",
        xaxis={"title": "Taille instance"},
        yaxis={"title": "Gap moyen (%)"},
        margin={"l": 60, "r": 20, "t": 60, "b": 50},
    )
    return _apply_common_layout(fig)


def _build_runtime_figure(results: list[dict[str, Any]]) -> go.Figure:
    sizes = sorted(_ordered_unique([int(row["size"]) for row in results]))
    algos = _ordered_unique([row["algo"] for row in results])

    fig = go.Figure()
    for idx, algo in enumerate(algos):
        means: list[float] = []
        for size in sizes:
            values = [
                float(row["runtime"])
                for row in results
                if int(row["size"]) == size and row["algo"] == algo
            ]
            means.append(max(1e-9, _safe_mean(values)))

        fig.add_trace(
            go.Scatter(
                x=sizes,
                y=means,
                mode="lines+markers",
                name=algo,
                marker={"color": ALGO_COLORS[idx % len(ALGO_COLORS)]},
                line={"color": ALGO_COLORS[idx % len(ALGO_COLORS)]},
            )
        )

    fig.update_layout(
        title="Temps d'execution moyen (echelle log)",
        xaxis={"title": "Taille instance"},
        yaxis={"title": "Temps moyen (s)", "type": "log"},
        margin={"l": 60, "r": 20, "t": 60, "b": 50},
    )
    return _apply_common_layout(fig)


def register_callbacks(app, session_cache: dict[str, Any], background_callback_manager=None) -> None:
    _ = background_callback_manager

    def _benchmark_worker(
        session_id: str,
        sizes: list[int],
        seeds: list[int],
        algos: list[str],
        output_dir: str,
        verbose: bool,
    ) -> None:
        try:
            for algo in algos:
                _enqueue_log("running", f"Demarrage algo {algo}...")

            selected_algorithms = {name: ALGO_FUNCTIONS[name] for name in algos}

            def _progress_callback(progress: dict[str, Any]) -> None:
                algo = str(progress.get("algo", ""))
                done = int(progress.get("done", 0))
                total = int(progress.get("total", 0))
                _enqueue_log("running", f"{algo}: {done}/{total}")

            results = run_benchmark(
                sizes=sizes,
                seeds=seeds,
                algos=selected_algorithms,
                progress_callback=_progress_callback,
                verbose=verbose,
            )

            target_dir = Path(output_dir).expanduser()
            save_benchmark_figures(results, directory=target_dir)

            session_cache[session_id]["benchmark_results"] = results
            session_cache[session_id]["status"] = "done"
            _enqueue_log("success", f"Benchmark termine: {len(results)} executions")
        except Exception as exc:
            session_cache.setdefault(session_id, {})
            session_cache[session_id]["status"] = "error"
            session_cache[session_id]["error"] = str(exc)
            _enqueue_log("error", f"Erreur benchmark: {exc}")

    @app.callback(
        Output("store-benchmark", "data", allow_duplicate=True),
        Input("benchmark-sizes", "value"),
        Input("benchmark-seeds", "value"),
        Input("benchmark-output-dir", "value"),
        Input("benchmark-algorithms", "value"),
        Input("benchmark-verbose", "value"),
        State("store-benchmark", "data"),
        prevent_initial_call=True,
    )
    def sync_store_from_form(
        sizes_raw: str,
        seeds_raw: str,
        output_dir: str,
        algorithms: list[str],
        verbose_values: list[str],
        store_data: dict[str, Any],
    ) -> dict[str, Any] | Any:
        data = dict(store_data or {})
        if data.get("status") == "running":
            return no_update

        data["sizes_raw"] = sizes_raw
        data["seeds_raw"] = seeds_raw
        data["output_dir"] = output_dir
        data["algorithms"] = list(algorithms or [])
        data["verbose"] = "verbose" in (verbose_values or [])
        return data

    @app.callback(
        Output("store-benchmark", "data", allow_duplicate=True),
        Input("benchmark-run", "n_clicks"),
        State("store-benchmark", "data"),
        prevent_initial_call=True,
    )
    def launch_benchmark(
        n_clicks: int,
        store_data: dict[str, Any],
    ) -> dict[str, Any]:
        if not n_clicks:
            raise PreventUpdate

        payload = dict(store_data or {})

        try:
            sizes = parse_int_list(str(payload.get("sizes_raw", "")), field_name="Tailles")
            seeds = parse_int_list(str(payload.get("seeds_raw", "")), field_name="Seeds")

            selected_algorithms = [
                algo
                for algo in payload.get("algorithms", [])
                if algo in ALGO_FUNCTIONS
            ]
            if not selected_algorithms:
                raise ValueError("Selectionner au moins un algorithme")

            output_value = str(payload.get("output_dir", "")).strip()
            if not output_value:
                raise ValueError("Dossier de sortie invalide")

            verbose = bool(payload.get("verbose", False))
        except Exception as exc:
            _enqueue_log("error", str(exc))
            return {
                "status": "error",
                "session_id": None,
                "sizes_raw": payload.get("sizes_raw", ""),
                "seeds_raw": payload.get("seeds_raw", ""),
                "output_dir": payload.get("output_dir", ""),
                "algorithms": payload.get("algorithms", []),
                "verbose": bool(payload.get("verbose", False)),
            }

        session_id = str(uuid4())
        session_cache[session_id] = {
            "status": "running",
            "benchmark_results": None,
            "error": None,
        }

        worker = threading.Thread(
            daemon=True,
            target=_benchmark_worker,
            args=(session_id, sizes, seeds, selected_algorithms, output_value, verbose),
        )
        worker.start()

        _enqueue_log("running", f"Benchmark lance (session={session_id})")

        return {
            "status": "running",
            "session_id": session_id,
            "sizes_raw": payload.get("sizes_raw", ""),
            "seeds_raw": payload.get("seeds_raw", ""),
            "output_dir": output_value,
            "algorithms": selected_algorithms,
            "verbose": verbose,
        }

    @app.callback(
        Output("benchmark-status-message", "children"),
        Output("benchmark-status-message", "className"),
        Output("benchmark-loading-target", "children"),
        Input("store-benchmark", "data"),
    )
    def sync_status(store_data: dict[str, Any]) -> tuple[str, str, html.Span]:
        data = store_data or {}
        status = str(data.get("status", "idle"))

        if status == "running":
            message = "Benchmark en cours"
            class_name = "status-message status-running"
        elif status == "done":
            message = "Benchmark termine"
            class_name = "status-message status-success"
        elif status == "error":
            message = "Benchmark en erreur"
            class_name = "status-message status-error"
        else:
            message = "Idle"
            class_name = "status-message status-idle"

        return message, class_name, html.Span(message, className="loading-token")

    @app.callback(
        Output("benchmark-run", "disabled"),
        Output("benchmark-run", "children"),
        Input("store-benchmark", "data"),
    )
    def sync_button_state(store_data: dict[str, Any]) -> tuple[bool, str]:
        status = str((store_data or {}).get("status", "idle"))
        if status == "running":
            return True, "En cours..."
        return False, "Lancer le benchmark"

    @app.callback(
        Output("log-output-benchmark", "children"),
        Output("store-benchmark", "data", allow_duplicate=True),
        Input("log-interval-benchmark", "n_intervals"),
        State("store-benchmark", "data"),
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
        Output("graph-benchmark-quality", "figure"),
        Output("graph-benchmark-gap", "figure"),
        Output("graph-benchmark-runtime", "figure"),
        Input("store-benchmark", "data"),
    )
    def update_benchmark_figures(store_data: dict[str, Any]):
        data = store_data or {}
        status = str(data.get("status", "idle"))
        session_id = data.get("session_id")

        if status != "done" or not session_id:
            return (
                _placeholder_figure("Qualite des solutions par algorithme"),
                _placeholder_figure("Ecart au meilleur (%) par taille"),
                _placeholder_figure("Temps d'execution moyen (echelle log)"),
            )

        session_state = session_cache.get(session_id)
        if not session_state:
            return (
                _placeholder_figure("Qualite des solutions par algorithme"),
                _placeholder_figure("Ecart au meilleur (%) par taille"),
                _placeholder_figure("Temps d'execution moyen (echelle log)"),
            )

        results = session_state.get("benchmark_results")
        if not isinstance(results, list) or not results:
            return (
                _placeholder_figure("Qualite des solutions par algorithme"),
                _placeholder_figure("Ecart au meilleur (%) par taille"),
                _placeholder_figure("Temps d'execution moyen (echelle log)"),
            )

        return (
            _build_quality_figure(results),
            _build_gap_figure(results),
            _build_runtime_figure(results),
        )
