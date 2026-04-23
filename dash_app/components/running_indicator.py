"""Composant indicateur d execution avec dcc.Loading."""

from __future__ import annotations

from dash import dcc, html


def build_running_indicator(prefix: str) -> html.Div:
    return html.Div(
        [
            dcc.Loading(
                id=f"{prefix}-loading",
                type="circle",
                children=html.Div(id=f"{prefix}-loading-target", className="loading-target"),
            ),
            html.Div("Idle", id=f"{prefix}-status-message", className="status-message status-idle"),
        ],
        className="running-indicator",
    )
