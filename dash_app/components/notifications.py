"""Composants de notifications toast."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from dash import html


def build_toast_container() -> html.Div:
    """Construit le container fixe des toasts."""

    return html.Div(id="toast-container", className="toast-container")


def create_toast(message: str, type_: str = "info") -> dict[str, Any]:
    """Construit un payload toast serialisable."""

    normalized = str(type_ or "info").strip().lower()
    if normalized not in {"info", "success", "warning", "error"}:
        normalized = "info"

    return {
        "id": datetime.now().strftime("%H%M%S%f"),
        "message": str(message),
        "type": normalized,
        "created_at": datetime.now().isoformat(),
    }


def render_toasts(items: list[dict[str, Any]]) -> list[html.Div]:
    """Rend une liste de toasts en composants HTML."""

    rendered: list[html.Div] = []
    for item in items[-4:]:
        toast_type = str(item.get("type", "info"))
        rendered.append(
            html.Div(
                str(item.get("message", "")),
                className=f"toast toast-{toast_type}",
            )
        )
    return rendered
