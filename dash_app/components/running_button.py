"""Reusable action button with integrated running spinner."""

from __future__ import annotations

from dash import html

from theme import PALETTE, SPACING_MD, SPACING_SM

_ROLE_TO_COLOR = {
    "primary": PALETTE["accent"],
    "success": PALETTE["success"],
    "danger": PALETTE["error"],
}


def build_running_button(
    button_id: str,
    label: str,
    role: str = "primary",
) -> html.Div:
    """Build a button container with a hidden spinner overlay.

    Args:
        button_id: Main button id used by callbacks.
        label: Button text displayed when idle.
        role: Color role (`primary`, `success`, `danger`).

    Returns:
        html.Div: Container with a `Button` and a spinner element.

    Usage:
        `build_running_button("benchmark-run", "Lancer le benchmark", role="primary")`
    """

    background = _ROLE_TO_COLOR.get(role, _ROLE_TO_COLOR["primary"])
    return html.Div(
        [
            html.Button(
                label,
                id=button_id,
                className=f"btn btn-{role}",
                n_clicks=0,
                style={
                    "backgroundColor": background,
                    "color": PALETTE["text_inverse"],
                    "border": f"1px solid {background}",
                    "padding": f"{SPACING_SM}rem {SPACING_MD}rem",
                },
            ),
            html.Div(
                id=f"{button_id}-spinner",
                className="button-spinner",
                style={
                    "display": "none",
                    "borderTopColor": PALETTE["text_inverse"],
                    "borderRightColor": PALETTE["text_inverse"],
                    "borderBottomColor": PALETTE["text_inverse"],
                    "borderLeftColor": PALETTE["transparent"],
                },
            ),
        ],
        className="running-button",
        style={"position": "relative", "display": "inline-flex", "alignItems": "center"},
    )
