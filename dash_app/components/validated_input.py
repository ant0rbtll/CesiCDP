"""Reusable validated input component for Dash forms."""

from __future__ import annotations

from typing import Any, Callable

from dash import dcc, html

from theme import FONT_SIZE_SM, FONT_SIZE_XS, PALETTE, SPACING_MD, SPACING_XS

ValidatorFn = Callable[[Any], tuple[bool, str]]


def build_validated_input(
    component_id: str,
    label: str,
    placeholder: str = "",
    type_: str = "text",
    validator_fn: ValidatorFn | None = None,
    default_value: str = "",
    hint: str = "",
) -> html.Div:
    """Build an input block with label, hint and validation feedback.

    Args:
        component_id: Input component id used by Dash callbacks.
        label: Text displayed above the input.
        placeholder: Placeholder text displayed when empty.
        type_: Dash input type (`text`, `number`, ...).
        validator_fn: Optional callable returning `(is_valid, message)`.
        default_value: Initial input value.
        hint: Optional help text displayed under the input.

    Returns:
        html.Div: Composable block containing label, input, hint and feedback span.

    Usage:
        `build_validated_input("generation-seed", "Seed", type_="number", default_value="42")`
    """

    feedback_message = ""
    feedback_color = PALETTE["text_dim"]
    if validator_fn is not None and str(default_value).strip() != "":
        is_valid, message = validator_fn(default_value)
        if is_valid:
            feedback_message = message or "Valeur valide."
            feedback_color = PALETTE["success"]
        else:
            feedback_message = message
            feedback_color = PALETTE["error"]

    return html.Div(
        [
            html.Label(
                label,
                htmlFor=component_id,
                className="field-label",
                style={"color": PALETTE["primary"]},
            ),
            dcc.Input(
                id=component_id,
                type=type_,
                value=default_value,
                placeholder=placeholder,
                className="input-text",
                debounce=True,
                style={
                    "borderColor": PALETTE["border_dark"],
                    "backgroundColor": PALETTE["surface"],
                    "color": PALETTE["text"],
                },
            ),
            html.Small(
                hint,
                id=f"{component_id}-hint",
                className="field-hint",
                style={"color": PALETTE["text_dim"], "fontSize": f"{FONT_SIZE_SM}rem"},
            ),
            html.Span(
                feedback_message,
                id=f"{component_id}-feedback",
                className="field-feedback",
                style={
                    "color": feedback_color,
                    "fontSize": f"{FONT_SIZE_XS}rem",
                    "minHeight": f"{SPACING_MD}rem",
                    "display": "inline-flex",
                    "alignItems": "center",
                    "gap": f"{SPACING_XS}rem",
                },
            ),
        ],
        className="field",
    )
