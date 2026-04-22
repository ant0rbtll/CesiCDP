"""Interface GUI modernisee pour benchmark, visualizer CESIPATH et reconnaissance quartier."""

from __future__ import annotations

import os
import sys
import threading
import traceback
import warnings
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

if "MPLCONFIGDIR" not in os.environ:
    mpl_dir = Path(os.getenv("TMPDIR", "/tmp")) / "cesipath-mplconfig"
    mpl_dir.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(mpl_dir)

# Bruit connu joblib/loky (contextily) a la fermeture du process.
warnings.filterwarnings(
    "ignore",
    message=r"resource_tracker: There appear to be .* leaked semlock objects to clean up at shutdown",
    category=UserWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r"resource_tracker: There appear to be .* leaked folder objects to clean up at shutdown",
    category=UserWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r"resource_tracker: .*FileNotFoundError.*",
    category=UserWarning,
)

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from cesipath.models import GraphGenerationConfig
from gui.components import (
    ColoredButton,
    LabeledCombobox,
    LabeledEntry,
    LogConsole,
    RunningIndicator,
)
from gui.icons import create_tab_icon
from gui.services import (
    NETWORK_TYPES,
    build_quartier_dynamic_session,
    generate_and_build_visualizer,
    parse_float,
    parse_int_list,
    parse_optional_int,
    parse_positive_int,
    run_benchmark_service,
    run_quartier_service,
)
from gui.theme import PALETTE, SPACING_LG, SPACING_MD, SPACING_SM, apply_theme


def get_quartier_graph_class():
    """Charge QuartierGraph depuis le package interne cesipath."""

    try:
        from cesipath.quartier_graph import QuartierGraph

        return QuartierGraph
    except ModuleNotFoundError as exc:
        missing = exc.name or "module"
        req_file = PROJECT_ROOT / "requirements.txt"
        raise ModuleNotFoundError(
            f"Dependance manquante: {missing}. Installer les dependances avec "
            f"`python3 -m pip install -r '{req_file}'`."
        ) from exc


def ok_validator(_: str) -> tuple[bool, str]:
    return True, "ok"


def int_list_validator(field_name: str):
    def _validate(raw: str) -> tuple[bool, str]:
        try:
            values = parse_int_list(raw, field_name=field_name)
            return True, f"{len(values)} valeur(s)"
        except Exception as exc:
            return False, str(exc)

    return _validate


def positive_int_validator(field_name: str):
    def _validate(raw: str) -> tuple[bool, str]:
        try:
            parse_positive_int(raw, field_name=field_name)
            return True, "valide"
        except Exception as exc:
            return False, str(exc)

    return _validate


def float_validator(field_name: str):
    def _validate(raw: str) -> tuple[bool, str]:
        try:
            parse_float(raw, field_name=field_name)
            return True, "valide"
        except Exception as exc:
            return False, str(exc)

    return _validate


def optional_int_validator(field_name: str):
    def _validate(raw: str) -> tuple[bool, str]:
        try:
            parse_optional_int(raw, field_name=field_name)
            return True, "valide"
        except Exception as exc:
            return False, str(exc)

    return _validate


class BenchmarkTab(ttk.Frame):
    ALGO_LABELS = {
        "grasp": "GRASP",
        "tabu_search": "Tabu Search",
        "simulated_annealing": "Simulated Annealing",
        "genetic_algorithm": "Genetic Algorithm",
    }

    def __init__(self, master: ttk.Notebook) -> None:
        super().__init__(master, style="App.TFrame")

        self.sizes_var = tk.StringVar(value="10, 15, 20")
        self.seeds_var = tk.StringVar(value="1, 2, 3")
        self.output_dir_var = tk.StringVar(value=str(PROJECT_ROOT / "image"))
        self.verbose_var = tk.BooleanVar(value=False)

        self.algo_vars = {
            name: tk.BooleanVar(value=True)
            for name in ("grasp", "tabu_search", "simulated_annealing", "genetic_algorithm")
        }

        self.sizes_field: LabeledEntry | None = None
        self.seeds_field: LabeledEntry | None = None
        self.run_button: ColoredButton | None = None
        self.indicator: RunningIndicator | None = None
        self.log_console: LogConsole | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        controls = ttk.LabelFrame(self, text="Parametres benchmark", style="Card.TLabelframe")
        controls.grid(row=0, column=0, sticky="ew", padx=SPACING_LG, pady=(SPACING_LG, SPACING_MD))
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)
        ttk.Label(
            controls,
            text="Selectionnez la taille des instances, les seeds et les algorithmes a comparer.",
            style="Hint.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, SPACING_MD))

        self.sizes_field = LabeledEntry(
            controls,
            label="Tailles de graphes",
            variable=self.sizes_var,
            hint="Ex: 10, 15, 20",
            tooltip="Liste des tailles de graphes benchmarkees.",
            validator=int_list_validator("Tailles"),
        )
        self.sizes_field.grid(row=1, column=0, sticky="ew", padx=(0, SPACING_LG), pady=(0, SPACING_MD))

        self.seeds_field = LabeledEntry(
            controls,
            label="Seeds",
            variable=self.seeds_var,
            hint="Ex: 1, 2, 3",
            tooltip="Liste des seeds pour repetition statistique.",
            validator=int_list_validator("Seeds"),
        )
        self.seeds_field.grid(row=1, column=1, sticky="ew", pady=(0, SPACING_MD))

        output_wrap = ttk.Frame(controls, style="Surface.TFrame")
        output_wrap.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, SPACING_MD))
        output_wrap.columnconfigure(0, weight=1)

        ttk.Label(output_wrap, text="Dossier de sortie", style="BodyBold.TLabel").grid(row=0, column=0, sticky="w")
        out_row = ttk.Frame(output_wrap, style="Surface.TFrame")
        out_row.grid(row=1, column=0, sticky="ew", pady=(SPACING_SM, 0))
        out_row.columnconfigure(0, weight=1)

        out_entry = tk.Entry(
            out_row,
            textvariable=self.output_dir_var,
            relief="solid",
            bd=1,
            highlightthickness=2,
            highlightbackground=PALETTE["border_dark"],
            highlightcolor=PALETTE["accent"],
            bg=PALETTE["surface"],
            fg=PALETTE["text"],
            font=("Segoe UI", 10),
        )
        out_entry.grid(row=0, column=0, sticky="ew")
        browse_btn = ColoredButton(out_row, text="Parcourir", command=self._choose_output_dir, role="secondary", width=12, size="sm")
        browse_btn.grid(row=0, column=1, padx=(SPACING_MD, 0))

        ttk.Separator(controls, orient="horizontal").grid(row=3, column=0, columnspan=2, sticky="ew", pady=SPACING_MD)

        algo_frame = ttk.LabelFrame(controls, text="Algorithmes", style="Card.TLabelframe")
        algo_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, SPACING_MD))

        for idx, name in enumerate(self.algo_vars):
            cb = ttk.Checkbutton(algo_frame, text=self.ALGO_LABELS[name], variable=self.algo_vars[name])
            cb.grid(row=idx // 2, column=idx % 2, sticky="w", padx=SPACING_MD, pady=SPACING_SM)

        options_row = ttk.Frame(controls, style="Surface.TFrame")
        options_row.grid(row=5, column=0, columnspan=2, sticky="ew")
        ttk.Checkbutton(
            options_row,
            text="Afficher trace verbose dans la console",
            variable=self.verbose_var,
        ).grid(row=0, column=0, sticky="w")

        action_row = ttk.Frame(controls, style="Surface.TFrame")
        action_row.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(SPACING_MD, 0))
        action_row.columnconfigure(0, weight=1)

        self.indicator = RunningIndicator(action_row)
        self.indicator.grid(row=0, column=0, sticky="ew", padx=(0, SPACING_MD))
        self.indicator.stop("Idle", success=True)

        self.run_button = ColoredButton(
            action_row,
            text="Executer le benchmark",
            command=self._run_benchmark,
            role="primary",
            width=20,
        )
        self.run_button.grid(row=0, column=1, sticky="e")

        log_frame = ttk.LabelFrame(self, text="Journal benchmark", style="Card.TLabelframe")
        log_frame.grid(row=1, column=0, sticky="nsew", padx=SPACING_LG, pady=(0, SPACING_LG))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_console = LogConsole(log_frame, height=18)
        self.log_console.grid(row=0, column=0, sticky="nsew")

    def _choose_output_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_dir_var.get() or str(PROJECT_ROOT))
        if selected:
            self.output_dir_var.set(selected)

    def _set_running(self, running: bool) -> None:
        if self.run_button is not None:
            self.run_button.set_running(running, running_text="⏳ Benchmark en cours...")
        if self.indicator is not None:
            if running:
                self.indicator.start("Benchmark en cours")
            else:
                self.indicator.stop("Benchmark termine", success=True)

    def _validate_inputs(self) -> tuple[bool, str]:
        for field in (self.sizes_field, self.seeds_field):
            if field is None:
                continue
            ok, message = field.validate_now()
            if not ok:
                return False, message
        return True, ""

    def _run_benchmark(self) -> None:
        ok, message = self._validate_inputs()
        if not ok:
            messagebox.showerror("Benchmark", message)
            return

        try:
            sizes = parse_int_list(self.sizes_var.get(), field_name="Tailles")
            seeds = parse_int_list(self.seeds_var.get(), field_name="Seeds")
        except Exception as exc:
            messagebox.showerror("Benchmark", str(exc))
            return

        selected_algorithms = [name for name, var in self.algo_vars.items() if var.get()]
        if not selected_algorithms:
            messagebox.showerror("Benchmark", "Selectionner au moins un algorithme")
            return

        total_per_algo = len(sizes) * len(seeds)
        job = {
            "sizes": sizes,
            "seeds": seeds,
            "selected_algorithms": selected_algorithms,
            "output_dir": Path(self.output_dir_var.get()).expanduser(),
            "verbose": bool(self.verbose_var.get()),
        }

        if self.log_console is not None:
            self.log_console.clear()
            self.log_console.log("running", "Preparation du benchmark...")
            self.log_console.log("info", f"Progression par algorithme (0/{total_per_algo})")
            for algo in selected_algorithms:
                label = self.ALGO_LABELS.get(algo, algo)
                self.log_console.upsert_status(
                    f"algo:{algo}",
                    "running",
                    f"{label} (0/{total_per_algo})",
                )
        self._set_running(True)

        thread = threading.Thread(target=self._benchmark_worker, args=(job,), daemon=True)
        thread.start()

    def _benchmark_worker(self, job: dict[str, object]) -> None:
        try:
            def _progress_callback(progress: dict[str, object]) -> None:
                self.after(0, self._on_benchmark_progress, progress)

            result = run_benchmark_service(
                sizes=list(job["sizes"]),
                seeds=list(job["seeds"]),
                selected_algorithms=list(job["selected_algorithms"]),
                output_dir=Path(job["output_dir"]),
                verbose=bool(job["verbose"]),
                progress_callback=_progress_callback,
            )
            self.after(0, self._on_benchmark_success, result)
        except Exception as exc:
            details = traceback.format_exc(limit=10)
            self.after(0, self._on_benchmark_failure, str(exc), details)

    def _on_benchmark_progress(self, progress: dict[str, object]) -> None:
        if self.log_console is None:
            return

        algo = str(progress.get("algo", ""))
        done = int(progress.get("done", 0))
        total = int(progress.get("total", 0))
        label = self.ALGO_LABELS.get(algo, algo)
        level = "success" if total > 0 and done >= total else "running"
        self.log_console.upsert_status(
            f"algo:{algo}",
            level,
            f"{label} ({done}/{total})",
        )

    def _on_benchmark_success(self, result) -> None:
        if self.log_console is not None:
            self.log_console.log("success", f"Benchmark termine: {len(result.results)} executions")
            self.log_console.log("info", "Figures generees:")
            for label, path in result.figure_paths.items():
                self.log_console.log("info", f"{label}: {path}")

            self.log_console.log("info", "Resume (size, algo, n, cost_mean, runtime_mean):")
            for row in result.summary:
                self.log_console.log(
                    "plain",
                    f"{row['size']}, {row['algo']}, {row['n_instances']}, "
                    f"{row['cost_mean']:.2f}, {row['runtime_mean']:.4f}s",
                )

        self._set_running(False)

    def _on_benchmark_failure(self, error_message: str, details: str) -> None:
        if self.indicator is not None:
            self.indicator.stop("Benchmark en erreur", success=False)
        if self.run_button is not None:
            self.run_button.set_running(False)
        if self.log_console is not None:
            self.log_console.log("error", error_message)
            self.log_console.log("plain", details)
        messagebox.showerror("Benchmark", error_message)


class GenerationTab(ttk.Frame):
    def __init__(self, master: ttk.Notebook) -> None:
        super().__init__(master, style="App.TFrame")

        self.nodes_var = tk.StringVar(value="15")
        self.seed_var = tk.StringVar(value="42")
        self.sigma_var = tk.StringVar(value="0.18")
        self.mean_reversion_var = tk.StringVar(value="0.35")
        self.max_multiplier_var = tk.StringVar(value="1.80")
        self.forbid_prob_var = tk.StringVar(value="0.03")
        self.restore_prob_var = tk.StringVar(value="0.20")
        self.max_disabled_ratio_var = tk.StringVar(value="0.20")

        self.fields: list[LabeledEntry] = []
        self.run_button: ColoredButton | None = None
        self.indicator: RunningIndicator | None = None
        self.log_console: LogConsole | None = None
        self._sessions: list = []

        self._build_ui()

    def _add_field(self, parent: tk.Widget, row: int, column: int, **kwargs) -> LabeledEntry:
        field = LabeledEntry(parent, **kwargs)
        field.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else SPACING_LG, 0), pady=(0, SPACING_MD))
        self.fields.append(field)
        return field

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        controls = ttk.LabelFrame(self, text="Parametres generation", style="Card.TLabelframe")
        controls.grid(row=0, column=0, sticky="ew", padx=SPACING_LG, pady=(SPACING_LG, SPACING_MD))
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)
        ttk.Label(
            controls,
            text="Configurez les parametres de generation avant d'ouvrir le visualizer interactif.",
            style="Hint.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, SPACING_MD))

        grid = ttk.Frame(controls, style="Surface.TFrame")
        grid.grid(row=1, column=0, columnspan=2, sticky="ew")
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        self._add_field(
            grid,
            0,
            0,
            label="Nombre de noeuds",
            variable=self.nodes_var,
            hint="Entier > 1",
            tooltip="Taille du graphe genere.",
            validator=positive_int_validator("Noeuds"),
        )
        self._add_field(
            grid,
            0,
            1,
            label="Seed",
            variable=self.seed_var,
            hint="Vide pour aleatoire",
            tooltip="Seed deterministe optionnelle.",
            validator=optional_int_validator("Seed"),
        )
        self._add_field(
            grid,
            1,
            0,
            label="Sigma",
            variable=self.sigma_var,
            hint="Volatilite dynamique",
            tooltip="Ecart-type de la dynamique gaussienne.",
            validator=float_validator("Sigma"),
        )
        self._add_field(
            grid,
            1,
            1,
            label="Mean reversion",
            variable=self.mean_reversion_var,
            hint="Retour vers cout statique",
            tooltip="Force de rappel vers le cout statique.",
            validator=float_validator("Mean reversion"),
        )
        self._add_field(
            grid,
            2,
            0,
            label="Max multiplier",
            variable=self.max_multiplier_var,
            hint="Borne sup dynamique",
            tooltip="Multiplicateur max du cout statique.",
            validator=float_validator("Max multiplier"),
        )
        self._add_field(
            grid,
            2,
            1,
            label="Forbid prob",
            variable=self.forbid_prob_var,
            hint="Prob. OFF aretes",
            tooltip="Probabilite qu'une arete active devienne OFF.",
            validator=float_validator("Forbid prob"),
        )
        self._add_field(
            grid,
            3,
            0,
            label="Restore prob",
            variable=self.restore_prob_var,
            hint="Prob. restauration",
            tooltip="Probabilite qu'une arete OFF redevienne active.",
            validator=float_validator("Restore prob"),
        )
        self._add_field(
            grid,
            3,
            1,
            label="Max disabled ratio",
            variable=self.max_disabled_ratio_var,
            hint="Ratio OFF max",
            tooltip="Part maximale d'aretes OFF en dynamique.",
            validator=float_validator("Max disabled ratio"),
        )

        ttk.Separator(controls, orient="horizontal").grid(row=2, column=0, columnspan=2, sticky="ew", pady=SPACING_MD)

        action_row = ttk.Frame(controls, style="Surface.TFrame")
        action_row.grid(row=3, column=0, columnspan=2, sticky="ew")
        action_row.columnconfigure(0, weight=1)

        self.indicator = RunningIndicator(action_row)
        self.indicator.grid(row=0, column=0, sticky="ew", padx=(0, SPACING_MD))
        self.indicator.stop("Idle", success=True)

        self.run_button = ColoredButton(
            action_row,
            text="Lancer la generation",
            command=self._generate_and_show,
            role="success",
            width=26,
        )
        self.run_button.grid(row=0, column=1, sticky="e")

        log_frame = ttk.LabelFrame(self, text="Journal generation", style="Card.TLabelframe")
        log_frame.grid(row=1, column=0, sticky="nsew", padx=SPACING_LG, pady=(0, SPACING_LG))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_console = LogConsole(log_frame, height=16)
        self.log_console.grid(row=0, column=0, sticky="nsew")

    def _set_running(self, running: bool, *, success: bool = True, message: str = "") -> None:
        if self.run_button is not None:
            self.run_button.set_running(running, running_text="⏳ Generation en cours...")
        if self.indicator is not None:
            if running:
                self.indicator.start("Generation en cours")
            else:
                self.indicator.stop(message or "Generation terminee", success=success)

    def _validate_fields(self) -> tuple[bool, str]:
        for field in self.fields:
            ok, msg = field.validate_now()
            if not ok:
                return False, msg
        return True, ""

    def _generate_and_show(self) -> None:
        ok, message = self._validate_fields()
        if not ok:
            messagebox.showerror("Generation", message)
            return

        try:
            self._set_running(True)
            if self.log_console is not None:
                self.log_console.clear()
                self.log_console.log("running", "Generation de l'instance...")

            config = GraphGenerationConfig(
                node_count=parse_positive_int(self.nodes_var.get(), field_name="Noeuds"),
                seed=parse_optional_int(self.seed_var.get(), field_name="Seed"),
                auto_density_profile=True,
                dynamic_sigma=parse_float(self.sigma_var.get(), field_name="Sigma"),
                dynamic_mean_reversion_strength=parse_float(self.mean_reversion_var.get(), field_name="Mean reversion"),
                dynamic_max_multiplier=parse_float(self.max_multiplier_var.get(), field_name="Max multiplier"),
                dynamic_forbid_probability=parse_float(self.forbid_prob_var.get(), field_name="Forbid prob"),
                dynamic_restore_probability=parse_float(self.restore_prob_var.get(), field_name="Restore prob"),
                dynamic_max_disabled_ratio=parse_float(self.max_disabled_ratio_var.get(), field_name="Max disabled ratio"),
            )

            result = generate_and_build_visualizer(config)
            self._sessions.append(result.session)

            if self.log_console is not None:
                self.log_console.log("success", "Instance generee. Visualizer ouvert.")
                for key, value in result.summary.items():
                    self.log_console.log("info", f"{key}: {value}")

            plt.show(block=False)
            self._set_running(False, success=True, message="Visualizer ouvert")
        except Exception as exc:
            details = traceback.format_exc(limit=10)
            self._set_running(False, success=False, message="Erreur generation")
            if self.log_console is not None:
                self.log_console.log("error", str(exc))
                self.log_console.log("plain", details)
            messagebox.showerror("Generation", str(exc))


class QuartierTab(ttk.Frame):
    def __init__(self, master: ttk.Notebook) -> None:
        super().__init__(master, style="App.TFrame")

        self.place_var = tk.StringVar(value="Place de la Concorde, Paris")
        self.network_display_var = tk.StringVar(value="Drive")
        self.distance_var = tk.StringVar(value="600")
        self.max_clients_var = tk.StringVar(value="35")
        self.export_format_var = tk.StringVar(value="none")
        self.preview_var = tk.StringVar(value="Apercu: Place de la Concorde, Paris | type=drive")

        self.place_field: LabeledEntry | None = None
        self.distance_field: LabeledEntry | None = None
        self.max_clients_field: LabeledEntry | None = None
        self.network_combo: LabeledCombobox | None = None
        self.run_button: ColoredButton | None = None
        self.indicator: RunningIndicator | None = None
        self.log_console: LogConsole | None = None
        self._sessions: list = []
        self._is_plot_fullscreen = False

        self._plot_container: ttk.Frame | None = None
        self._figure_canvas: FigureCanvasTkAgg | None = None
        self._current_figure = None
        self._controls_frame: ttk.LabelFrame | None = None
        self._log_frame: ttk.LabelFrame | None = None
        self._plot_frame: ttk.LabelFrame | None = None
        self._plot_mode_button: ColoredButton | None = None
        self._has_dynamic_graph = False

        self._build_ui()
        self.place_var.trace_add("write", self._update_preview)
        self.network_display_var.trace_add("write", self._update_preview)
        self.max_clients_var.trace_add("write", self._update_preview)
        self._update_preview()
        self._apply_plot_mode()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=5)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        controls = ttk.LabelFrame(self, text="Parametres reconnaissance quartier", style="Card.TLabelframe")
        controls.grid(
            row=0,
            column=0,
            sticky="new",
            padx=(SPACING_LG, SPACING_MD),
            pady=(SPACING_LG, SPACING_MD),
        )
        self._controls_frame = controls
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)
        ttk.Label(
            controls,
            text="Chargez un reseau OSM reel puis lancez la simulation dynamique CESIPATH sur ce quartier.",
            style="Hint.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, SPACING_MD))

        self.place_field = LabeledEntry(
            controls,
            label="Lieu",
            variable=self.place_var,
            hint="Ex: Marais, Paris",
            tooltip="Adresse ou nom de quartier pour OSM.",
            validator=lambda raw: (len(raw.strip()) > 0, "obligatoire" if len(raw.strip()) > 0 else "Lieu requis"),
            width=34,
        )
        self.place_field.grid(row=1, column=0, sticky="ew", padx=(0, SPACING_LG), pady=(0, SPACING_MD))

        self.network_combo = LabeledCombobox(
            controls,
            label="Type de reseau",
            variable=self.network_display_var,
            values=list(NETWORK_TYPES.keys()),
            tooltip="Mode de graphe OSM charge.",
            width=28,
        )
        self.network_combo.grid(row=1, column=1, sticky="ew", pady=(0, SPACING_MD))

        self.distance_field = LabeledEntry(
            controls,
            label="Distance (m)",
            variable=self.distance_var,
            hint="Rayon autour du lieu",
            tooltip="Distance en metres autour du point geocode.",
            validator=positive_int_validator("Distance"),
        )
        self.distance_field.grid(row=2, column=0, sticky="ew", padx=(0, SPACING_LG), pady=(0, SPACING_MD))

        self.max_clients_field = LabeledEntry(
            controls,
            label="Clients dynamiques",
            variable=self.max_clients_var,
            hint="Nombre de clients VRP",
            tooltip="Nombre max de points de livraison utilises dans la resolution dynamique.",
            validator=positive_int_validator("Clients dynamiques"),
        )
        self.max_clients_field.grid(row=2, column=1, sticky="ew", pady=(0, SPACING_MD))

        export_combo = LabeledCombobox(
            controls,
            label="Export optionnel",
            variable=self.export_format_var,
            values=["none", "graphml", "gexf", "json_graph"],
            tooltip="Exporter une copie du graphe non oriente.",
            width=28,
        )
        export_combo.grid(row=3, column=0, sticky="ew", padx=(0, SPACING_LG), pady=(0, SPACING_MD))

        ttk.Label(controls, textvariable=self.preview_var, style="Hint.TLabel").grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(0, SPACING_MD),
        )

        ttk.Separator(controls, orient="horizontal").grid(row=5, column=0, columnspan=2, sticky="ew", pady=SPACING_MD)

        action_row = ttk.Frame(controls, style="Surface.TFrame")
        action_row.grid(row=6, column=0, columnspan=2, sticky="ew")
        action_row.columnconfigure(0, weight=1)

        self.indicator = RunningIndicator(action_row)
        self.indicator.grid(row=0, column=0, sticky="ew", padx=(0, SPACING_MD))
        self.indicator.stop("Idle", success=True)

        self.run_button = ColoredButton(
            action_row,
            text="Analyser et simuler",
            command=self._run_quartier,
            role="primary",
            width=22,
        )
        self.run_button.grid(row=0, column=1, sticky="e")

        plot_frame = ttk.LabelFrame(self, text="Visualisation dynamique OSM (imbriquee)", style="Card.TLabelframe")
        plot_frame.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(0, SPACING_LG),
            pady=(SPACING_LG, SPACING_MD),
        )
        self._plot_frame = plot_frame
        plot_frame.columnconfigure(0, weight=1)
        plot_frame.rowconfigure(1, weight=1)

        plot_header = ttk.Frame(plot_frame, style="Surface.TFrame")
        plot_header.grid(row=0, column=0, sticky="ew", padx=SPACING_MD, pady=(SPACING_SM, SPACING_SM))
        plot_header.columnconfigure(0, weight=1)
        ttk.Label(plot_header, text="Mode d'affichage", style="Hint.TLabel").grid(row=0, column=0, sticky="w")

        self._plot_mode_button = ColoredButton(
            plot_header,
            text="Plein ecran",
            command=self._toggle_plot_mode,
            role="secondary",
            width=14,
            size="sm",
        )
        self._plot_mode_button.grid(row=0, column=1, sticky="e")
        self._set_plot_mode_button_ready(False)

        plot_frame.columnconfigure(0, weight=1)

        self._plot_container = ttk.Frame(plot_frame, style="Surface.TFrame")
        self._plot_container.grid(row=1, column=0, sticky="nsew")
        ttk.Label(
            self._plot_container,
            text="Aucune simulation affichee. Lancez l'analyse quartier pour afficher le visualizer dynamique ici.",
            style="Hint.TLabel",
        ).pack(anchor="w", padx=SPACING_MD, pady=SPACING_MD)

        log_frame = ttk.LabelFrame(self, text="Journal reconnaissance", style="Card.TLabelframe")
        log_frame.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="nsew",
            padx=SPACING_LG,
            pady=(0, SPACING_LG),
        )
        self._log_frame = log_frame
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_console = LogConsole(log_frame, height=10)
        self.log_console.grid(row=0, column=0, sticky="nsew")

    def _toggle_plot_mode(self) -> None:
        self._is_plot_fullscreen = not self._is_plot_fullscreen
        self._apply_plot_mode()

    def _set_plot_mode_button_ready(self, ready: bool) -> None:
        if self._plot_mode_button is None:
            return
        self._has_dynamic_graph = ready
        if ready:
            base = PALETTE["error"]
            hover = PALETTE["error_hover"]
            active = PALETTE["error_hover"]
        else:
            base = PALETTE["primary"]
            hover = PALETTE["primary_light"]
            active = PALETTE["primary_light"]

        self._plot_mode_button._base_color = base
        self._plot_mode_button._hover_color = hover
        self._plot_mode_button._active_color = active
        self._plot_mode_button.configure(
            bg=base,
            activebackground=active,
            fg=PALETTE["text_inverse"],
            activeforeground=PALETTE["text_inverse"],
        )

    def _apply_plot_mode(self) -> None:
        if (
            self._controls_frame is None
            or self._plot_frame is None
            or self._log_frame is None
            or self._plot_container is None
        ):
            return

        if self._is_plot_fullscreen:
            self.columnconfigure(0, weight=1)
            self.columnconfigure(1, weight=1)
            self.rowconfigure(0, weight=1)
            self.rowconfigure(1, weight=0)

            self._controls_frame.grid_remove()
            self._log_frame.grid_remove()
            self._plot_frame.grid_configure(
                row=0,
                column=0,
                columnspan=2,
                rowspan=2,
                sticky="nsew",
                padx=SPACING_LG,
                pady=(SPACING_LG, SPACING_LG),
            )
            self._plot_frame.rowconfigure(1, weight=1)
            self._plot_container.grid()
            if self._plot_mode_button is not None:
                self._plot_mode_button.configure(text="Mode mini")
            return

        self.columnconfigure(0, weight=5)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._controls_frame.grid()
        self._log_frame.grid()
        self._plot_frame.grid_configure(
            row=0,
            column=1,
            columnspan=1,
            rowspan=1,
            sticky="nsew",
            padx=(0, SPACING_LG),
            pady=(SPACING_LG, SPACING_MD),
        )
        self._plot_frame.rowconfigure(1, weight=0)
        self._plot_container.grid_remove()
        if self._plot_mode_button is not None:
            self._plot_mode_button.configure(text="Plein ecran")

    def _update_preview(self, *_: object) -> None:
        label = self.network_display_var.get()
        network_type = NETWORK_TYPES.get(label, "drive")
        self.preview_var.set(
            f"Apercu: {self.place_var.get().strip() or '-'} | type={network_type} | clients={self.max_clients_var.get().strip() or '?'}"
        )

    def _set_running(self, running: bool, *, success: bool = True, message: str = "") -> None:
        if self.run_button is not None:
            self.run_button.set_running(running, running_text="⏳ Chargement OSM + simulation...")
        if self.indicator is not None:
            if running:
                self.indicator.start("Chargement OSM + dynamique")
            else:
                self.indicator.stop(message or "Termine", success=success)

    def _validate_fields(self) -> tuple[bool, str]:
        fields = [self.place_field, self.distance_field, self.max_clients_field]
        for field in fields:
            if field is None:
                continue
            ok, msg = field.validate_now()
            if not ok:
                return False, msg
        return True, ""

    def _run_quartier(self) -> None:
        ok, message = self._validate_fields()
        if not ok:
            messagebox.showerror("Reconnaissance quartier", message)
            return

        job = {
            "place": self.place_var.get().strip(),
            "distance_raw": self.distance_var.get(),
            "max_clients_raw": self.max_clients_var.get(),
            "network_display": self.network_display_var.get(),
            "export_format": self.export_format_var.get(),
        }

        self._set_running(True)
        if self.log_console is not None:
            self.log_console.clear()
            self.log_console.log("running", "Recuperation du reseau OSM...")
            self.log_console.log("info", "Preparation simulation dynamique (GRASP + couts dynamiques + OFF/ON)")

        thread = threading.Thread(target=self._quartier_worker, args=(job,), daemon=True)
        thread.start()

    def _quartier_worker(self, job: dict[str, object]) -> None:
        try:
            place = str(job["place"])
            distance = parse_positive_int(str(job["distance_raw"]), field_name="Distance")
            max_solver_clients = parse_positive_int(str(job["max_clients_raw"]), field_name="Clients dynamiques")
            network_type = NETWORK_TYPES.get(str(job["network_display"]), "drive")
            export_format = str(job["export_format"])

            result = run_quartier_service(
                quartier_graph_cls=get_quartier_graph_class(),
                place=place,
                network_type=network_type,
                distance=distance,
                export_format=export_format,
                max_solver_clients=max_solver_clients,
            )
            self.after(0, self._on_quartier_success, result)
        except Exception as exc:
            details = traceback.format_exc(limit=10)
            self.after(0, self._on_quartier_failure, str(exc), details)

    def _on_quartier_success(self, result) -> None:
        try:
            session = build_quartier_dynamic_session(result)
            self._sessions.append(session)
            figure = session.fig
        except Exception as exc:
            details = traceback.format_exc(limit=10)
            self._on_quartier_failure(str(exc), details)
            return

        self._set_running(False, success=True, message="Simulation quartier active")

        if self.log_console is not None:
            self.log_console.log("success", "Quartier charge: simulation dynamique active sur fond OSM")
            if result.export_path is not None:
                self.log_console.log("info", f"Export: {result.export_path}")
            for key, value in result.stats.items():
                self.log_console.log("info", f"{key}: {value}")
            self.log_console.log("info", "Meta conversion quartier -> CESIPATH:")
            for key, value in result.dynamic_metadata.items():
                self.log_console.log("plain", f"  - {key}: {value}")
            self.log_console.log("info", "Resume instance dynamique:")
            for key in (
                "node_count",
                "residual_edge_count",
                "residual_density",
                "dynamic_forbid_probability",
                "dynamic_restore_probability",
                "dynamic_min_density",
                "dynamic_max_disabled_ratio",
                "minimum_route_count",
            ):
                if key in result.dynamic_instance_summary:
                    self.log_console.log("plain", f"  - {key}: {result.dynamic_instance_summary[key]}")

        self._render_figure(figure)
        self._set_plot_mode_button_ready(True)

    def _render_figure(self, figure) -> None:
        if self._plot_container is None:
            return

        for child in self._plot_container.winfo_children():
            child.destroy()

        if self._current_figure is not None:
            plt.close(self._current_figure)
        self._current_figure = figure

        self._figure_canvas = FigureCanvasTkAgg(figure, master=self._plot_container)
        self._figure_canvas.draw()
        self._figure_canvas.get_tk_widget().pack(fill="both", expand=True)

    def _on_quartier_failure(self, error_message: str, details: str) -> None:
        self._set_running(False, success=False, message="Erreur reconnaissance")
        if self.log_console is not None:
            self.log_console.log("error", error_message)
            self.log_console.log("plain", details)
        if self._current_figure is None:
            self._set_plot_mode_button_ready(False)
        messagebox.showerror("Reconnaissance quartier", error_message)


class CesiGuiApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("CESIPATH - Optimization Toolkit")
        self.geometry("1400x950")
        self.minsize(1200, 800)
        apply_theme(self)

        root_frame = ttk.Frame(self, style="App.TFrame")
        root_frame.pack(fill="both", expand=True, padx=SPACING_LG, pady=SPACING_LG)
        root_frame.rowconfigure(2, weight=1)
        root_frame.columnconfigure(0, weight=1)

        # === HEADER MODERNE ===
        header = ttk.Frame(root_frame, style="Header.TFrame")
        header.grid(row=0, column=0, sticky="ew", padx=SPACING_MD, pady=(0, SPACING_MD))
        header.columnconfigure(0, weight=1)
        
        # Titre principal
        ttk.Label(header, text="CESIPATH", style="H1.TLabel").grid(row=0, column=0, sticky="w")
        
        # Sous-titre avec description
        ttk.Label(
            header,
            text="Benchmark, generation d'instances et reconnaissance quartier OSM",
            style="BodySecondary.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(SPACING_SM, 0))



        # Séparateur
        ttk.Separator(root_frame, orient="horizontal").grid(row=1, column=0, sticky="ew", padx=SPACING_MD, pady=(0, SPACING_MD))

        # === NOTEBOOK ===
        notebook = ttk.Notebook(root_frame, style="App.TNotebook")
        notebook.grid(row=2, column=0, sticky="nsew")

        self.benchmark_tab = BenchmarkTab(notebook)
        self.generation_tab = GenerationTab(notebook)
        self.quartier_tab = QuartierTab(notebook)

        self._tab_icons = {
            "benchmark": create_tab_icon("B", PALETTE["accent"]),
            "generation": create_tab_icon("G", PALETTE["success"]),
            "quartier": create_tab_icon("Q", PALETTE["primary"]),
        }

        self._add_tab(notebook, self.benchmark_tab, "Benchmark", self._tab_icons["benchmark"], "Benchmark")
        self._add_tab(notebook, self.generation_tab, "Generation", self._tab_icons["generation"], "Generation")
        self._add_tab(notebook, self.quartier_tab, "Quartier", self._tab_icons["quartier"], "Quartier")

    @staticmethod
    def _add_tab(
        notebook: ttk.Notebook,
        tab: ttk.Frame,
        text: str,
        icon: tk.PhotoImage | None,
        fallback_text: str,
    ) -> None:
        if icon is not None:
            notebook.add(tab, text=text, image=icon, compound="left")
            return
        notebook.add(tab, text=fallback_text)


def main() -> None:
    app = CesiGuiApp()
    app.mainloop()


if __name__ == "__main__":
    main()
