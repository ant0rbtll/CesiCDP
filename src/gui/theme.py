"""Theme centralise pour l'interface Tkinter - Design System Moderne."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# Palette modernisée avec design system professionnel
PALETTE = {
    # Couleurs primaires - Bleu professionnel moderne
    "primary": "#1F2937",           # Gris foncé pour texte principal
    "primary_light": "#374151",     # Gris plus clair
    
    # Accent - Bleu vibrant
    "accent": "#0EA5E9",            # Bleu ciel éclatant
    "accent_hover": "#0284C7",      # Bleu plus foncé pour hover
    "accent_dark": "#0369A1",       # Bleu très foncé
    "accent_soft": "#E0F2FE",       # Bleu très pâle pour backgrounds
    "accent_muted": "#7DD3FC",      # Bleu moyen
    
    # États de succès
    "success": "#10B981",           # Vert émeraude
    "success_light": "#D1FAE5",     # Vert très pâle
    "success_hover": "#059669",     # Vert plus foncé
    
    # États d'erreur
    "error": "#EF4444",             # Rouge vif
    "error_light": "#FEE2E2",       # Rose très pâle
    "error_hover": "#DC2626",       # Rouge plus foncé
    
    # États d'avertissement
    "warning": "#F59E0B",           # Ambre
    "warning_light": "#FEF3C7",     # Ambre très pâle
    "warning_hover": "#D97706",     # Ambre plus foncé
    
    # Backgrounds et surfaces
    "bg": "#F8FAFC",                # Gris très clair (background principal)
    "bg_secondary": "#F1F5F9",      # Gris clair secondaire
    "surface": "#FFFFFF",           # Blanc pur pour cartes
    "surface_soft": "#F8FAFC",      # Gris très clair
    "surface_alt": "#F1F5F9",       # Gris clair alternatif
    "surface_hover": "#F0F9FF",     # Gris très clair avec teinte bleu
    
    # Bordures et séparateurs
    "border": "#E2E8F0",            # Gris doux
    "border_dark": "#CBD5E1",       # Gris plus foncé
    "border_light": "#F1F5F9",      # Gris très pâle
    "divider": "#E5E7EB",           # Gris neutre
    
    # Texte
    "text": "#1F2937",              # Gris foncé (texte principal)
    "text_secondary": "#6B7280",    # Gris moyen
    "text_dim": "#9CA3AF",          # Gris pâle
    "text_disabled": "#D1D5DB",     # Gris très pâle
    "text_inverse": "#FFFFFF",      # Blanc (sur backgrounds sombres)
    
    # Console (dark mode)
    "console_bg": "#0F172A",        # Gris très foncé
    "console_text": "#E2E8F0",      # Gris clair
    "console_border": "#1E293B",    # Gris foncé
}

# Typographie
FONT_FAMILY = "Segoe UI"
FONT_FAMILY_ALT = "-apple-system, BlinkMacSystemFont, system-ui, sans-serif"
MONO_FONT_FAMILY = "Menlo"

# Tailles de fonts
FONT_SIZE_XS = 9
FONT_SIZE_SM = 10
FONT_SIZE_BASE = 11
FONT_SIZE_LG = 12
FONT_SIZE_XL = 14
FONT_SIZE_2XL = 18
FONT_SIZE_3XL = 24

# Espacements
SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16
SPACING_XL = 24
SPACING_2XL = 32

# Rayons de bordure
RADIUS_SM = 4
RADIUS_MD = 8
RADIUS_LG = 12

# Ombres
SHADOW_SM = "0 1px 2px 0 rgba(0, 0, 0, 0.05)"
SHADOW_MD = "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)"
SHADOW_LG = "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)"


def apply_theme(root: tk.Tk) -> None:
    """Applique un design system moderne et coherent sur l'interface."""

    root.configure(bg=PALETTE["bg"])

    style = ttk.Style(root)
    style.theme_use("clam")

    # === FRAMES ===
    style.configure("App.TFrame", background=PALETTE["bg"])
    style.configure("Surface.TFrame", background=PALETTE["surface"])
    style.configure("Header.TFrame", background=PALETTE["bg"])
    style.configure("Accent.TFrame", background=PALETTE["accent"])
    style.configure("Soft.TFrame", background=PALETTE["surface_soft"])

    # === CARDS & CONTAINERS ===
    style.configure(
        "Card.TLabelframe",
        background=PALETTE["surface"],
        borderwidth=1,
        relief="solid",
        bordercolor=PALETTE["border"],
        lightcolor=PALETTE["border"],
        darkcolor=PALETTE["border"],
        padding=SPACING_LG,
    )
    style.configure(
        "Card.TLabelframe.Label",
        background=PALETTE["surface"],
        foreground=PALETTE["primary"],
        font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
    )
    
    style.configure(
        "Section.TLabelframe",
        background=PALETTE["surface_soft"],
        borderwidth=0,
        padding=SPACING_MD,
    )
    style.configure(
        "Section.TLabelframe.Label",
        background=PALETTE["surface_soft"],
        foreground=PALETTE["accent"],
        font=(FONT_FAMILY, FONT_SIZE_BASE, "bold"),
    )

    # === LABELS - HEADERS ===
    style.configure(
        "H1.TLabel",
        background=PALETTE["bg"],
        foreground=PALETTE["primary"],
        font=(FONT_FAMILY, FONT_SIZE_3XL, "bold"),
    )
    style.configure(
        "H2.TLabel",
        background=PALETTE["bg"],
        foreground=PALETTE["primary"],
        font=(FONT_FAMILY, FONT_SIZE_2XL, "bold"),
    )
    style.configure(
        "H3.TLabel",
        background=PALETTE["surface"],
        foreground=PALETTE["primary"],
        font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
    )
    
    # === LABELS - BODY ===
    style.configure(
        "Body.TLabel",
        background=PALETTE["surface"],
        foreground=PALETTE["text"],
        font=(FONT_FAMILY, FONT_SIZE_BASE),
    )
    style.configure(
        "BodyBold.TLabel",
        background=PALETTE["surface"],
        foreground=PALETTE["primary"],
        font=(FONT_FAMILY, FONT_SIZE_BASE, "bold"),
    )
    style.configure(
        "BodySecondary.TLabel",
        background=PALETTE["surface"],
        foreground=PALETTE["text_secondary"],
        font=(FONT_FAMILY, FONT_SIZE_BASE),
    )
    
    # === LABELS - HELPERS ===
    style.configure(
        "Hint.TLabel",
        background=PALETTE["surface"],
        foreground=PALETTE["text_dim"],
        font=(FONT_FAMILY, FONT_SIZE_SM),
    )
    style.configure(
        "Caption.TLabel",
        background=PALETTE["surface"],
        foreground=PALETTE["text_dim"],
        font=(FONT_FAMILY, FONT_SIZE_XS),
    )
    style.configure(
        "Chip.TLabel",
        background=PALETTE["accent_soft"],
        foreground=PALETTE["accent"],
        font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
        padding=(SPACING_SM, SPACING_XS),
    )

    # === LABELS - PAGE ===
    style.configure(
        "PageBody.TLabel",
        background=PALETTE["bg"],
        foreground=PALETTE["text"],
        font=(FONT_FAMILY, FONT_SIZE_BASE),
    )
    style.configure(
        "PageHint.TLabel",
        background=PALETTE["bg"],
        foreground=PALETTE["text_dim"],
        font=(FONT_FAMILY, FONT_SIZE_SM),
    )

    # === CHECKBUTTON ===
    style.configure(
        "TCheckbutton",
        background=PALETTE["surface"],
        foreground=PALETTE["text"],
        font=(FONT_FAMILY, FONT_SIZE_BASE),
        focuscolor=PALETTE["accent_soft"],
    )
    style.map(
        "TCheckbutton",
        background=[("active", PALETTE["surface_hover"])],
        foreground=[("disabled", PALETTE["text_disabled"])],
    )

    # === COMBOBOX ===
    style.configure(
        "TCombobox",
        fieldbackground=PALETTE["surface"],
        background=PALETTE["surface"],
        foreground=PALETTE["text"],
        bordercolor=PALETTE["border_dark"],
        lightcolor=PALETTE["border"],
        darkcolor=PALETTE["border_dark"],
        arrowsize=13,
        padding=SPACING_SM,
        font=(FONT_FAMILY, FONT_SIZE_BASE),
    )
    style.map(
        "TCombobox",
        fieldbackground=[
            ("readonly", PALETTE["surface"]),
            ("focus", PALETTE["surface"]),
        ],
        selectbackground=[("readonly", PALETTE["accent_soft"])],
        selectforeground=[("readonly", PALETTE["text"])],
        bordercolor=[
            ("focus", PALETTE["accent"]),
            ("readonly", PALETTE["border_dark"]),
        ],
        lightcolor=[("focus", PALETTE["accent"])],
        darkcolor=[("focus", PALETTE["accent"])],
    )

    # === NOTEBOOK (TABS) ===
    style.configure(
        "App.TNotebook",
        background=PALETTE["bg"],
        borderwidth=0,
        tabposition="n",
    )
    style.configure(
        "App.TNotebook.Tab",
        font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
        padding=(SPACING_LG, SPACING_MD),
        background=PALETTE["surface_soft"],
        foreground=PALETTE["text_secondary"],
        borderwidth=0,
    )
    style.map(
        "App.TNotebook.Tab",
        background=[
            ("selected", PALETTE["accent"]),
            ("active", PALETTE["accent_hover"]),
        ],
        foreground=[
            ("selected", PALETTE["text_inverse"]),
            ("active", PALETTE["text_inverse"]),
        ],
    )

    # === PROGRESSBAR ===
    style.configure(
        "Accent.Horizontal.TProgressbar",
        troughcolor=PALETTE["surface_alt"],
        background=PALETTE["accent"],
        bordercolor=PALETTE["border"],
        lightcolor=PALETTE["accent"],
        darkcolor=PALETTE["accent"],
    )
    style.configure(
        "Success.Horizontal.TProgressbar",
        troughcolor=PALETTE["surface_alt"],
        background=PALETTE["success"],
        bordercolor=PALETTE["border"],
        lightcolor=PALETTE["success"],
        darkcolor=PALETTE["success"],
    )

    # === SEPARATOR ===
    style.configure(
        "TSeparator",
        background=PALETTE["divider"],
    )
