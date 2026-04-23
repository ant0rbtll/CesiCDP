"""Animated status indicator component for async Dash actions."""

from __future__ import annotations

from dash import html

from theme import FONT_SIZE_SM, PALETTE, SPACING_SM


def build_status_indicator(indicator_id: str) -> html.Div:
    """Build an icon + text status indicator.

    Args:
        indicator_id: Prefix used to generate icon/text ids.

    Returns:
        html.Div: Composable status container with icon and status text.

    Usage:
        `build_status_indicator("benchmark")`
    """

    return html.Div(
        [
            html.Span(
                "●",
                id=f"{indicator_id}-status-icon",
                className="status-icon status-idle",
                style={
                    "color": PALETTE["text_dim"],
                    "display": "inline-flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "minWidth": f"{SPACING_SM}rem",
                },
            ),
            html.Span(
                "Idle",
                id=f"{indicator_id}-status-text",
                className="status-message status-idle",
                style={"color": PALETTE["text_dim"], "fontSize": f"{FONT_SIZE_SM}rem"},
            ),
        ],
        id=f"{indicator_id}-status-indicator",
        className="status-indicator",
        style={
            "display": "inline-flex",
            "alignItems": "center",
            "gap": f"{SPACING_SM}rem",
            "color": PALETTE["text_dim"],
        },
    )
