"""Shared design tokens and color helpers for the Dash UI."""

from __future__ import annotations

PALETTE: dict[str, str] = {
    # Brand and action colors
    "primary": "#1F2937",
    "primary_hover": "#374151",
    "primary_dark": "#111827",
    "primary_light": "#4B5563",
    "accent": "#0EA5E9",
    "accent_hover": "#0284C7",
    "accent_dark": "#0369A1",
    "accent_soft": "#E0F2FE",
    "accent_muted": "#7DD3FC",
    # Semantic states
    "success": "#10B981",
    "success_light": "#D1FAE5",
    "success_hover": "#059669",
    "error": "#EF4444",
    "error_light": "#FEE2E2",
    "error_hover": "#DC2626",
    "warning": "#F59E0B",
    "warning_light": "#FEF3C7",
    "warning_hover": "#D97706",
    # Surfaces and borders
    "bg": "#F8FAFC",
    "bg_secondary": "#F1F5F9",
    "surface": "#FFFFFF",
    "surface_soft": "#F8FAFC",
    "surface_alt": "#F1F5F9",
    "surface_hover": "#F0F9FF",
    "border": "#E2E8F0",
    "border_dark": "#CBD5E1",
    "border_light": "#F1F5F9",
    "divider": "#E5E7EB",
    # Typography colors
    "text": "#1F2937",
    "text_secondary": "#6B7280",
    "text_dim": "#9CA3AF",
    "text_disabled": "#D1D5DB",
    "text_inverse": "#FFFFFF",
    # Console colors
    "console_bg": "#0F172A",
    "console_text": "#E2E8F0",
    "console_border": "#1E293B",
    # Map colors
    "map_bg": "#1A1A2E",
    "map_network": "#2A2A4A",
    "map_text": "#E8E8E8",
    "map_panel": "rgba(20, 20, 40, 0.8)",
    # Compatibility aliases used by existing components
    "empty_text": "#6B7280",
    "free": "#4A9EBF",
    "surcharged": "#F0AD4E",
    "forbidden": "#C1121F",
    "transit": "#888888",
    "transit_border": "#555555",
    "depot": "#F0AD4E",
    "depot_text": "#000000",
    "light": "#FFFFFF",
    "dark": "#000000",
    "transparent": "rgba(0, 0, 0, 0)",
    "bg_plot": "#1A1A2E",
    "font_light": "#E8E8E8",
    "legend_bg": "rgba(20, 20, 40, 0.8)",
    "neutral_strong": "#555555",
    "neutral_mid": "#888888",
    "map_free": "#4A9EBF",
    "map_surcharged": "#F0AD4E",
    "map_forbidden": "#D9534F",
}

ANIMATION_COLORS: dict[str, str] = {
    "bg_network": PALETTE["map_network"],
    "route": "#1F4F8B",
    "depot": PALETTE["depot"],
    "traffic_low": "#2ECC71",
    "traffic_mid": "#F1C40F",
    "traffic_high": "#F39C12",
    "traffic_max": "#E74C3C",
    "client_default": "#8ECAE6",
    "client_delivered": "#1F4F8B",
    "truck": "#FFD700",
    "forbidden": PALETTE["forbidden"],
    # Legacy keys still used by callbacks
    "black": PALETTE["dark"],
    "light": PALETTE["light"],
    "plot_bg": PALETTE["bg_plot"],
    "font_light": PALETTE["font_light"],
    "warn": PALETTE["warning"],
}

FONT_FAMILY = "Segoe UI"
FONT_SIZE_XS = 0.75
FONT_SIZE_SM = 0.875
FONT_SIZE_MD = 1.0
FONT_SIZE_LG = 1.125
FONT_SIZE_XL = 1.5

SPACING_XS = 0.5
SPACING_SM = 0.75
SPACING_MD = 1.0
SPACING_LG = 1.5
SPACING_XL = 2.0


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert ``#RRGGBB`` to an RGB tuple."""

    value = hex_color.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Invalid hex color '{hex_color}'. Expected #RRGGBB.")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """Convert an RGB tuple to ``#RRGGBB``."""

    red, green, blue = rgb
    for channel in (red, green, blue):
        if not 0 <= int(channel) <= 255:
            raise ValueError(f"Invalid RGB channel '{channel}'. Expected range 0..255.")
    return f"#{int(red):02X}{int(green):02X}{int(blue):02X}"


def blend(color_a: str, color_b: str, factor: float) -> str:
    """Linearly interpolate between two hex colors."""

    alpha = max(0.0, min(1.0, float(factor)))
    ar, ag, ab = hex_to_rgb(color_a)
    br, bg, bb = hex_to_rgb(color_b)
    return rgb_to_hex(
        (
            round(ar + (br - ar) * alpha),
            round(ag + (bg - ag) * alpha),
            round(ab + (bb - ab) * alpha),
        )
    )


def lighten(color: str, amount: float = 0.2) -> str:
    """Lighten a hex color by blending it with white."""

    return blend(color, "#FFFFFF", amount)


def darken(color: str, amount: float = 0.2) -> str:
    """Darken a hex color by blending it with black."""

    return blend(color, "#000000", amount)


def export_css_vars() -> str:
    """Export palette entries as CSS custom properties under ``:root``."""

    lines = [":root {"]
    for key, value in PALETTE.items():
        css_key = key.replace("_", "-")
        lines.append(f"  --color-{css_key}: {value};")
    lines.append("}")
    return "\n".join(lines)
