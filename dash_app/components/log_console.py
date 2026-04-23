"""Composant log console avec file de logs thread-safe."""

from __future__ import annotations

from datetime import datetime
from queue import Empty, Queue
from typing import Any

from dash import dcc, html

TAB_KEYS = ("benchmark", "generation", "quartier")
LEVEL_KEYS = ("info", "success", "error", "warning", "running", "plain")


class LogStore:
    """Stockage thread-safe des logs par onglet."""

    def __init__(self) -> None:
        self._queues: dict[str, Queue] = {tab: Queue() for tab in TAB_KEYS}

    def _normalize_tab(self, tab: str) -> str:
        if tab not in self._queues:
            raise ValueError(f"Onglet de log inconnu: {tab}")
        return tab

    @staticmethod
    def _normalize_level(level: str) -> str:
        if level in LEVEL_KEYS:
            return level
        return "plain"

    def push(self, tab: str, level: str, message: str) -> None:
        """Ajoute un log dans la queue de l onglet."""

        safe_tab = self._normalize_tab(tab)
        payload = {
            "level": self._normalize_level(level),
            "message": str(message),
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }
        self._queues[safe_tab].put(payload)

    def drain(self, tab: str, max: int = 50) -> list[dict[str, str]]:
        """Vide jusqu a ``max`` logs de la queue et les retourne."""

        safe_tab = self._normalize_tab(tab)
        queue_obj = self._queues[safe_tab]
        drained: list[dict[str, str]] = []

        while len(drained) < max:
            try:
                item = queue_obj.get_nowait()
            except Empty:
                break
            drained.append(item)
        return drained


def build_log_console(prefix: str, title: str) -> html.Div:
    """Construit le bloc log d un onglet."""

    return html.Div(
        [
            html.H3(title, className="section-title"),
            html.Div(id=f"log-output-{prefix}", className="log-console"),
            dcc.Interval(id=f"log-interval-{prefix}", interval=500, n_intervals=0),
        ],
        className="card",
    )


def render_log_lines(entries: list[dict[str, Any]]) -> list[html.Div]:
    """Convertit les logs en lignes HTML."""

    rendered: list[html.Div] = []
    for idx, entry in enumerate(entries):
        level = str(entry.get("level", "plain"))
        if level not in LEVEL_KEYS:
            level = "plain"
        timestamp = str(entry.get("timestamp", "--:--:--"))
        message = str(entry.get("message", ""))
        rendered.append(
            html.Div(
                [
                    html.Span(f"[{timestamp}]", className="log-timestamp"),
                    html.Span(message, className=f"log-{level}"),
                ],
                id=f"log-line-{idx}",
                className="log-line",
            )
        )
    return rendered


LOG_STORE = LogStore()
