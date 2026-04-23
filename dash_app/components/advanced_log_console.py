"""Advanced log console component with search, filter and export controls."""

from __future__ import annotations

from dash import dcc, html

from theme import FONT_SIZE_SM, PALETTE, SPACING_MD, SPACING_SM


def build_advanced_log_console(
    tab_prefix: str,
    title: str = "Logs",
) -> html.Div:
    """Build an advanced log console toolbar and output area.

    Args:
        tab_prefix: Prefix used to generate unique component ids.
        title: Card title displayed above controls.

    Returns:
        html.Div: Composable log card with controls, output and polling interval.

    Usage:
        `build_advanced_log_console("generation", title="Journal génération")`
    """

    return html.Div(
        [
            html.H3(
                title,
                className="section-title",
                style={"color": PALETTE["primary"]},
            ),
            html.Div(
                [
                    dcc.Input(
                        id=f"{tab_prefix}-log-search",
                        type="text",
                        placeholder="Rechercher dans les logs...",
                        className="input-text",
                        debounce=True,
                        style={
                            "flex": "1 1 220px",
                            "borderColor": PALETTE["border_dark"],
                            "backgroundColor": PALETTE["surface"],
                            "color": PALETTE["text"],
                        },
                    ),
                    dcc.Dropdown(
                        id=f"{tab_prefix}-log-filter",
                        options=[
                            {"label": "Tous", "value": "all"},
                            {"label": "Info", "value": "info"},
                            {"label": "Success", "value": "success"},
                            {"label": "Warning", "value": "warning"},
                            {"label": "Error", "value": "error"},
                        ],
                        value="all",
                        clearable=False,
                        style={"minWidth": "170px"},
                    ),
                    html.Button(
                        "Exporter",
                        id=f"{tab_prefix}-log-export",
                        className="btn btn-primary",
                        style={
                            "backgroundColor": PALETTE["accent"],
                            "color": PALETTE["text_inverse"],
                            "border": f"1px solid {PALETTE['accent_dark']}",
                            "padding": f"{SPACING_SM}rem {SPACING_MD}rem",
                        },
                    ),
                ],
                className="quartier-controls-row",
                style={"gap": f"{SPACING_MD}rem"},
            ),
            html.Div(
                id=f"log-output-{tab_prefix}",
                className="log-console",
                style={
                    "borderColor": PALETTE["console_border"],
                    "backgroundColor": PALETTE["console_bg"],
                    "color": PALETTE["console_text"],
                    "fontSize": f"{FONT_SIZE_SM}rem",
                },
            ),
            dcc.Interval(id=f"log-interval-{tab_prefix}", interval=500, n_intervals=0),
        ],
        className="card",
    )
