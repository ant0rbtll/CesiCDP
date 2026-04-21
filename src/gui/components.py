"""Composants GUI reutilisables - Design System Moderne."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from .theme import (
    FONT_FAMILY,
    MONO_FONT_FAMILY,
    PALETTE,
    SPACING_SM,
    SPACING_MD,
    SPACING_XS,
    FONT_SIZE_BASE,
    FONT_SIZE_SM,
)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convertit une couleur hex en RGB."""
    c = hex_color.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """Convertit RGB en hex."""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def blend(color_a: str, color_b: str, factor: float) -> str:
    """Melange lineaire lisse entre deux couleurs hex."""
    factor = max(0.0, min(1.0, factor))
    ar, ag, ab = _hex_to_rgb(color_a)
    br, bg, bb = _hex_to_rgb(color_b)
    return _rgb_to_hex(
        (
            int(ar + (br - ar) * factor),
            int(ag + (bg - ag) * factor),
            int(ab + (bb - ab) * factor),
        )
    )


def lighten(color: str, amount: float = 0.2) -> str:
    """Eclaircit une couleur."""
    return blend(color, "#FFFFFF", amount)


def darken(color: str, amount: float = 0.2) -> str:
    """Assombrit une couleur."""
    return blend(color, "#000000", amount)


class ToolTip:
    """Tooltip moderne avec style cohérent."""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip_window: tk.Toplevel | None = None
        self.widget.bind("<Enter>", self._show, add="+")
        self.widget.bind("<Leave>", self._hide, add="+")

    def _show(self, _: tk.Event) -> None:
        if self.tip_window is not None or not self.text:
            return

        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8

        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(bg=PALETTE["primary"])

        label = tk.Label(
            tw,
            text=self.text,
            justify="left",
            bg=PALETTE["primary"],
            fg=PALETTE["text_inverse"],
            relief="solid",
            borderwidth=1,
            padx=SPACING_SM,
            pady=SPACING_XS,
            font=(FONT_FAMILY, FONT_SIZE_SM),
            wraplength=300,
        )
        label.pack()

    def _hide(self, _: tk.Event) -> None:
        if self.tip_window is not None:
            self.tip_window.destroy()
            self.tip_window = None


class ColoredButton(tk.Button):
    """Bouton moderne avec animations et états visuels sophistiqués."""

    ROLE_COLORS = {
        "primary": PALETTE["accent"],
        "secondary": PALETTE["primary"],
        "success": PALETTE["success"],
        "danger": PALETTE["error"],
        "warning": PALETTE["warning"],
    }

    def __init__(
        self,
        master: tk.Widget,
        *,
        text: str,
        command: Callable | None,
        role: str = "primary",
        width: int = 24,
        size: str = "md",
    ) -> None:
        self.idle_text = text
        self.running_text = "⏳ En cours..."
        self.role = role
        self.is_running = False

        # Déterminer les dimensions basées sur la taille
        if size == "sm":
            padx, pady = 10, 6
            font_size = FONT_SIZE_SM
        elif size == "lg":
            padx, pady = 18, 12
            font_size = 11
        else:  # md
            padx, pady = 14, 9
            font_size = FONT_SIZE_BASE

        base = self.ROLE_COLORS.get(role, PALETTE["accent"])
        hover = lighten(base, 0.1)
        active = darken(base, 0.1)
        disabled = blend(base, PALETTE["surface_alt"], 0.6)

        super().__init__(
            master,
            text=text,
            command=command,
            width=width,
            bg=base,
            fg=PALETTE["text_inverse"],
            activebackground=active,
            activeforeground=PALETTE["text_inverse"],
            relief="flat",
            bd=0,
            padx=padx,
            pady=pady,
            cursor="hand2",
            disabledforeground=blend(PALETTE["text_inverse"], PALETTE["surface_alt"], 0.5),
            font=(FONT_FAMILY, font_size, "bold"),
            highlightthickness=0,
        )

        self._base_color = base
        self._hover_color = hover
        self._active_color = active
        self._disabled_color = disabled
        self._animation_step = 0
        
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, _: tk.Event) -> None:
        if self["state"] != "disabled" and not self.is_running:
            self.configure(bg=self._hover_color)

    def _on_leave(self, _: tk.Event) -> None:
        if self["state"] != "disabled" and not self.is_running:
            self.configure(bg=self._base_color)

    def set_running(self, running: bool, *, running_text: str | None = None) -> None:
        if running_text is not None:
            self.running_text = running_text

        self.is_running = running
        if running:
            self.configure(
                state="disabled",
                text=self.running_text,
                bg=self._disabled_color,
                cursor="wait",
            )
        else:
            self.configure(
                state="normal",
                text=self.idle_text,
                bg=self._base_color,
                cursor="hand2",
            )


class RunningIndicator(ttk.Frame):
    """Indicateur d'état avec progression et animation."""

    def __init__(self, master: tk.Widget) -> None:
        super().__init__(master, style="Surface.TFrame")
        self.columnconfigure(1, weight=1)

        self.dot = ttk.Label(
            self,
            text="●",
            style="Body.TLabel",
            foreground=PALETTE["text_dim"],
            font=(FONT_FAMILY, FONT_SIZE_BASE),
        )
        self.dot.grid(row=0, column=0, sticky="w", padx=(0, SPACING_SM))

        self.status = ttk.Label(self, text="Idle", style="Body.TLabel")
        self.status.grid(row=0, column=1, sticky="w")

        self.bar = ttk.Progressbar(
            self,
            mode="indeterminate",
            style="Accent.Horizontal.TProgressbar",
        )
        self.bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(SPACING_MD, 0))

    def start(self, message: str) -> None:
        self.dot.configure(foreground=PALETTE["warning"])
        self.status.configure(text=message, foreground=PALETTE["warning"])
        self.bar.start(8)

    def stop(self, message: str = "Idle", success: bool = True) -> None:
        self.bar.stop()
        color = PALETTE["success"] if success else PALETTE["error"]
        self.dot.configure(foreground=color)
        self.status.configure(text=message, foreground=color)


class LogConsole(ttk.Frame):
    """Console de logs moderne avec syntaxe colorée."""

    ICONS = {
        "info": "ℹ  ",
        "success": "✓  ",
        "error": "✗  ",
        "warning": "⚠  ",
        "running": "⏳ ",
    }

    TAG_COLORS = {
        "info": "#3B82F6",        # Bleu
        "success": "#10B981",     # Vert
        "error": "#EF4444",       # Rouge
        "warning": "#F59E0B",     # Ambre
        "running": "#F59E0B",     # Ambre
        "plain": PALETTE["console_text"],
    }

    def __init__(self, master: tk.Widget, *, height: int = 14) -> None:
        super().__init__(master, style="Surface.TFrame")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self._status_tags: dict[str, str] = {}
        self._status_counter = 0

        self.text = tk.Text(
            self,
            wrap="word",
            height=height,
            bg=PALETTE["console_bg"],
            fg=PALETTE["console_text"],
            insertbackground=PALETTE["accent"],
            selectbackground=blend(PALETTE["accent"], PALETTE["console_bg"], 0.3),
            selectforeground=PALETTE["console_text"],
            relief="flat",
            padx=SPACING_MD,
            pady=SPACING_MD,
            font=(MONO_FONT_FAMILY, FONT_SIZE_BASE),
            undo=True,
            highlightthickness=1,
            highlightbackground=PALETTE["console_border"],
            highlightcolor=PALETTE["accent"],
            takefocus=False,
        )
        self.text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scrollbar.set)

        for tag, color in self.TAG_COLORS.items():
            self.text.tag_configure(tag, foreground=color)

        self.text.bind("<Control-a>", self._select_all)

    def _select_all(self, _: tk.Event) -> str:
        self.text.tag_add("sel", "1.0", "end")
        return "break"

    def clear(self) -> None:
        self.text.delete("1.0", "end")
        self._status_tags.clear()
        self._status_counter = 0

    def log(self, level: str, message: str) -> None:
        icon = self.ICONS.get(level, "• ")
        line = f"{icon}{message}\n"
        tag = level if level in self.TAG_COLORS else "plain"
        self.text.insert("end", line, tag)
        self.text.see("end")

    def upsert_status(self, key: str, level: str, message: str) -> None:
        """Cree ou met a jour une ligne de statut sans flood de la console."""

        icon = self.ICONS.get(level, "• ")
        line = f"{icon}{message}\n"
        tag = level if level in self.TAG_COLORS else "plain"

        status_tag = self._status_tags.get(key)
        if status_tag is None:
            status_tag = f"log_status_{self._status_counter}"
            self._status_counter += 1
            self._status_tags[key] = status_tag
            self.text.insert("end", line, (status_tag, tag))
            self.text.see("end")
            return

        ranges = self.text.tag_ranges(status_tag)
        if len(ranges) >= 2:
            line_start, line_end = ranges[0], ranges[1]
            self.text.delete(line_start, line_end)
            self.text.insert(line_start, line, (status_tag, tag))
        else:
            self.text.insert("end", line, (status_tag, tag))
        self.text.see("end")


class LabeledEntry(ttk.Frame):
    """Champ de saisie avec label, hint et validation en temps réel."""

    def __init__(
        self,
        master: tk.Widget,
        *,
        label: str,
        variable: tk.StringVar,
        hint: str = "",
        tooltip: str = "",
        validator: Callable[[str], tuple[bool, str]] | None = None,
        width: int = 22,
    ) -> None:
        super().__init__(master, style="Surface.TFrame")
        self.validator = validator
        self.variable = variable
        self.columnconfigure(0, weight=1)

        self.label_widget = ttk.Label(self, text=label, style="BodyBold.TLabel")
        self.label_widget.grid(row=0, column=0, sticky="w")

        self.entry = tk.Entry(
            self,
            textvariable=self.variable,
            width=width,
            relief="solid",
            bd=1,
            highlightthickness=2,
            highlightbackground=PALETTE["border_dark"],
            highlightcolor=PALETTE["accent"],
            bg=PALETTE["surface"],
            fg=PALETTE["text"],
            insertbackground=PALETTE["accent"],
            font=(FONT_FAMILY, FONT_SIZE_BASE),
        )
        self.entry.grid(row=1, column=0, sticky="ew", pady=(SPACING_XS, 0))

        self.hint_widget = ttk.Label(self, text=hint, style="Hint.TLabel")
        self.hint_widget.grid(row=2, column=0, sticky="w", pady=(SPACING_XS, 0))

        self.state_widget = ttk.Label(self, text="", style="Hint.TLabel")
        self.state_widget.grid(row=3, column=0, sticky="w")

        if tooltip:
            ToolTip(self.label_widget, tooltip)
            ToolTip(self.entry, tooltip)

        self.entry.bind("<KeyRelease>", self._on_change)
        self.entry.bind("<FocusOut>", self._on_change)
        self.entry.bind("<FocusIn>", self._on_focus_in)

    def _set_valid(self, ok: bool, message: str = "") -> None:
        color = PALETTE["success"] if ok else PALETTE["error"]
        icon = "✓" if ok else "✗"
        self.entry.configure(highlightbackground=color, highlightcolor=color)
        self.state_widget.configure(
            text=f"{icon} {message}" if message else "", foreground=color
        )

    def _set_neutral(self) -> None:
        self.entry.configure(
            highlightbackground=PALETTE["border_dark"],
            highlightcolor=PALETTE["accent"],
        )
        self.state_widget.configure(text="", foreground=PALETTE["text_dim"])

    def _on_focus_in(self, _: tk.Event) -> None:
        """Désélectionne le texte quand le champ reçoit le focus."""
        self.entry.selection_clear()

    def _on_change(self, _: tk.Event) -> None:
        if self.validator is None:
            return

        raw = self.variable.get().strip()
        if raw == "":
            self._set_neutral()
            return

        ok, msg = self.validator(raw)
        self._set_valid(ok, msg)

    def validate_now(self) -> tuple[bool, str]:
        if self.validator is None:
            return True, ""

        raw = self.variable.get().strip()
        ok, msg = self.validator(raw)
        self._set_valid(ok, msg)
        return ok, msg


class LabeledCombobox(ttk.Frame):
    """Combobox avec label et validation."""

    def __init__(
        self,
        master: tk.Widget,
        *,
        label: str,
        variable: tk.StringVar,
        values: list[str],
        tooltip: str = "",
        width: int = 22,
    ) -> None:
        super().__init__(master, style="Surface.TFrame")
        self.columnconfigure(0, weight=1)

        self.label_widget = ttk.Label(self, text=label, style="BodyBold.TLabel")
        self.label_widget.grid(row=0, column=0, sticky="w")

        self.combo = ttk.Combobox(
            self,
            textvariable=variable,
            values=values,
            width=width,
            state="readonly",
        )
        self.combo.grid(row=1, column=0, sticky="ew", pady=(SPACING_XS, 0))

        if tooltip:
            ToolTip(self.label_widget, tooltip)
            ToolTip(self.combo, tooltip)
