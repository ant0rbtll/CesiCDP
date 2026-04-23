"""Layout principal Dash avec onglets Benchmark, Generation et Quartier."""

from __future__ import annotations

from dash import dcc, html

from components.log_console import build_log_console
from components.running_indicator import build_running_indicator


def _benchmark_tab() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.H3("Parametres benchmark", className="section-title"),
                    html.P(
                        "Selection des tailles, seeds et algorithmes a comparer.",
                        className="section-hint",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("Tailles de graphes", className="field-label"),
                                    dcc.Input(
                                        id="benchmark-sizes",
                                        type="text",
                                        value="10, 15, 20",
                                        className="input-text",
                                    ),
                                    html.Small("Ex: 10, 15, 20", className="field-hint"),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Mode seeds", className="field-label"),
                                    dcc.RadioItems(
                                        id="benchmark-seed-mode",
                                        options=[
                                            {"label": "Liste manuelle", "value": "manual"},
                                            {"label": "Nombre aleatoire", "value": "random_count"},
                                        ],
                                        value="manual",
                                        className="radio-inline",
                                    ),
                                    html.Small(
                                        "Choisissez une liste explicite ou un nombre de seeds tirees au hasard.",
                                        className="field-hint",
                                    ),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Seeds", className="field-label"),
                                    dcc.Input(
                                        id="benchmark-seeds",
                                        type="text",
                                        value="1, 2, 3",
                                        className="input-text",
                                    ),
                                    html.Small("Ex: 1, 2, 3", className="field-hint"),
                                ],
                                id="benchmark-seeds-field",
                                className="field full",
                            ),
                            html.Div(
                                [
                                    html.Label("Nombre de seeds", className="field-label"),
                                    dcc.Input(
                                        id="benchmark-seed-count",
                                        type="number",
                                        value=4,
                                        min=1,
                                        step=1,
                                        className="input-text",
                                    ),
                                    html.Small(
                                        "Ex: 4. Le serveur tirera 4 seeds uniques au hasard.",
                                        className="field-hint",
                                    ),
                                ],
                                id="benchmark-seed-count-field",
                                className="field full field-hidden",
                            ),
                        ],
                        className="field-grid two-cols",
                    ),
                    html.Div(
                        [
                            html.Label("Dossier de sortie", className="field-label"),
                            dcc.Input(
                                id="benchmark-output-dir",
                                type="text",
                                value="image",
                                className="input-text",
                            ),
                            html.Small(
                                "Chemin local serveur (pas de file dialog en web).",
                                className="field-hint",
                            ),
                        ],
                        className="field",
                    ),
                    html.Div(
                        [
                            html.Label("Algorithmes", className="field-label"),
                            dcc.Checklist(
                                id="benchmark-algorithms",
                                options=[
                                    {"label": "GRASP", "value": "grasp"},
                                    {"label": "Tabu Search", "value": "tabu_search"},
                                    {"label": "Simulated Annealing", "value": "simulated_annealing"},
                                    {"label": "Genetic Algorithm", "value": "genetic_algorithm"},
                                ],
                                value=[
                                    "grasp",
                                    "tabu_search",
                                    "simulated_annealing",
                                    "genetic_algorithm",
                                ],
                                className="checklist-grid",
                            ),
                        ],
                        className="field",
                    ),
                    dcc.Checklist(
                        id="benchmark-verbose",
                        options=[{"label": "Mode verbose", "value": "verbose"}],
                        value=[],
                        className="checklist-inline",
                    ),
                    html.Div(
                        [
                            build_running_indicator("benchmark"),
                            html.Button(
                                "Lancer le benchmark",
                                id="benchmark-run",
                                n_clicks=0,
                                className="btn btn-primary",
                            ),
                        ],
                        className="action-row",
                    ),
                ],
                className="card",
            ),
            build_log_console(prefix="benchmark", title="Journal benchmark"),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.H3("Resultats benchmark", className="section-title"),
                                            html.P(
                                                "Activez le mode plein ecran pour analyser les courbes sans contrainte de place.",
                                                className="section-hint",
                                            ),
                                        ]
                                    ),
                                    html.Div(
                                        [
                                            html.Button(
                                                "Plein ecran resultats",
                                                id="benchmark-results-toggle",
                                                n_clicks=0,
                                                className="btn btn-primary",
                                            )
                                        ],
                                        className="benchmark-results-actions",
                                    ),
                                ],
                                className="benchmark-results-header",
                            ),
                            html.Div(
                                [
                                    dcc.Graph(
                                        id="graph-benchmark-quality",
                                        className="graph-card",
                                        config={"responsive": True, "displaylogo": False},
                                        style={"height": "100%"},
                                    ),
                                    dcc.Graph(
                                        id="graph-benchmark-gap",
                                        className="graph-card",
                                        config={"responsive": True, "displaylogo": False},
                                        style={"height": "100%"},
                                    ),
                                    dcc.Graph(
                                        id="graph-benchmark-runtime",
                                        className="graph-card",
                                        config={"responsive": True, "displaylogo": False},
                                        style={"height": "100%"},
                                    ),
                                ],
                                className="graph-grid benchmark-results-grid",
                            ),
                        ],
                        id="benchmark-results-shell",
                        className="card benchmark-results-shell",
                    ),
                ],
                className="benchmark-results-wrap",
            ),
        ],
        className="tab-content",
    )


def _generation_tab() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.H3("Parametres generation", className="section-title"),
                    html.P(
                        "Generation d instance puis visualisation dynamique.",
                        className="section-hint",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("Nombre de villes", className="field-label"),
                                    dcc.Input(
                                        id="generation-node-count",
                                        type="number",
                                        value=15,
                                        className="input-text",
                                    ),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Seed", className="field-label"),
                                    dcc.Input(
                                        id="generation-seed",
                                        type="text",
                                        value="42",
                                        className="input-text",
                                    ),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Variabilite trafic", className="field-label"),
                                    dcc.Input(
                                        id="generation-sigma",
                                        type="number",
                                        value=0.18,
                                        className="input-text",
                                    ),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Retour vers normale", className="field-label"),
                                    dcc.Input(
                                        id="generation-mean-reversion",
                                        type="number",
                                        value=0.35,
                                        className="input-text",
                                    ),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Pic congestion max", className="field-label"),
                                    dcc.Input(
                                        id="generation-max-multiplier",
                                        type="number",
                                        value=1.8,
                                        className="input-text",
                                    ),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Proba fermeture route", className="field-label"),
                                    dcc.Input(
                                        id="generation-forbid-prob",
                                        type="number",
                                        value=0.03,
                                        className="input-text",
                                    ),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Proba reouverture route", className="field-label"),
                                    dcc.Input(
                                        id="generation-restore-prob",
                                        type="number",
                                        value=0.2,
                                        className="input-text",
                                    ),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Part max routes indisponibles", className="field-label"),
                                    dcc.Input(
                                        id="generation-max-disabled-ratio",
                                        type="number",
                                        value=0.2,
                                        className="input-text",
                                    ),
                                ],
                                className="field",
                            ),
                        ],
                        className="field-grid two-cols",
                    ),
                    html.Div(
                        [
                            html.H3("Simulation VRP", className="section-title"),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Label("Algorithme", className="field-label"),
                                            dcc.Dropdown(
                                                id="generation-algo",
                                                options=[
                                                    {"label": "GRASP", "value": "grasp"},
                                                    {"label": "Recherche Tabou", "value": "tabu_search"},
                                                    {"label": "Recuit Simule", "value": "simulated_annealing"},
                                                    {"label": "Algorithme Genetique", "value": "genetic_algorithm"},
                                                ],
                                                value="grasp",
                                                clearable=False,
                                                className="dropdown",
                                            ),
                                            html.Small(
                                                "Methode utilisee pour resoudre la tournee sur le graphe genere.",
                                                className="field-hint",
                                            ),
                                        ],
                                        className="field",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Capacite vehicule", className="field-label"),
                                            dcc.Input(
                                                id="generation-capacity",
                                                type="number",
                                                value=40,
                                                min=1,
                                                step=1,
                                                className="input-text",
                                            ),
                                            html.Small(
                                                "Charge maximale transportee par camion.",
                                                className="field-hint",
                                            ),
                                        ],
                                        className="field",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Seed simulation", className="field-label"),
                                            dcc.Input(
                                                id="generation-sim-seed",
                                                type="number",
                                                value=42,
                                                min=0,
                                                step=1,
                                                className="input-text",
                                            ),
                                            html.Small(
                                                "Controle la reproductibilite du solveur et de la dynamique.",
                                                className="field-hint",
                                            ),
                                        ],
                                        className="field",
                                    ),
                                ],
                                className="field-grid three-cols",
                            ),
                        ],
                        className="generation-sim-settings",
                    ),
                    html.Div(
                        [
                            build_running_indicator("generation"),
                            html.Button(
                                "Generer et simuler",
                                id="generation-run",
                                n_clicks=0,
                                className="btn btn-success",
                            ),
                        ],
                        className="action-row",
                    ),
                ],
                className="card",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.H3("Simulation instance", className="section-title"),
                                    html.P(
                                        "Simulation dynamique du graphe genere, avec animation du camion comme dans l'onglet Quartier.",
                                        className="section-hint",
                                    ),
                                ]
                            ),
                            html.Div(
                                [
                                    html.Button(
                                        "Plein ecran simulation",
                                        id="generation-graph-toggle",
                                        n_clicks=0,
                                        className="btn btn-primary",
                                    )
                                ],
                                className="generation-graph-actions",
                            ),
                        ],
                        className="generation-graph-header",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Button(
                                        "Start",
                                        id="generation-play",
                                        className="btn btn-primary",
                                        n_clicks=0,
                                    ),
                                    html.Button(
                                        "Pause",
                                        id="generation-pause",
                                        className="btn",
                                        n_clicks=0,
                                        style={"background": "var(--color-error)"},
                                    ),
                                ],
                                className="generation-playback-actions",
                            ),
                            html.Div(
                                [
                                    html.Label("Vitesse animation :", className="quartier-speed-label"),
                                    dcc.Slider(
                                        id="slider-generation-vitesse",
                                        min=0.5,
                                        max=10.0,
                                        step=0.5,
                                        value=1.0,
                                        updatemode="drag",
                                        marks={
                                            0.5: "0.5x",
                                            1.0: "1x",
                                            2.0: "2x",
                                            5.0: "5x",
                                            10.0: "10x",
                                        },
                                        tooltip={"placement": "bottom"},
                                    ),
                                ],
                                className="quartier-speed-block",
                            ),
                            html.Div(
                                id="animation-container-generation",
                                className="generation-animation-container",
                            ),
                        ],
                        className="generation-graph-body",
                    ),
                ],
                id="generation-graph-shell",
                className="card generation-graph-shell",
            ),
            build_log_console(prefix="generation", title="Journal generation"),
        ],
        className="tab-content",
    )


def _quartier_tab() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.H3("Parametres quartier", className="section-title"),
                    html.P(
                        "Chargement OSM puis simulation dynamique.",
                        className="section-hint",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("Lieu", className="field-label"),
                                    dcc.Input(
                                        id="quartier-place",
                                        type="text",
                                        value="Place de la Concorde, Paris",
                                        className="input-text",
                                    ),
                                ],
                                className="field full",
                            ),
                            html.Div(
                                [
                                    html.Label("Distance (m)", className="field-label"),
                                    dcc.Input(
                                        id="quartier-distance",
                                        type="number",
                                        value=600,
                                        className="input-text",
                                    ),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Export optionnel", className="field-label"),
                                    dcc.Dropdown(
                                        id="quartier-export-format",
                                        options=[
                                            {"label": "none", "value": "none"},
                                            {"label": "graphml", "value": "graphml"},
                                            {"label": "gexf", "value": "gexf"},
                                            {"label": "json_graph", "value": "json_graph"},
                                        ],
                                        value="none",
                                        clearable=False,
                                        className="dropdown",
                                    ),
                                ],
                                className="field",
                            ),
                        ],
                        className="field-grid two-cols",
                    ),
                    html.P(id="quartier-preview", className="preview-text"),
                    html.Div(
                        [
                            build_running_indicator("quartier"),
                            html.Button(
                                "Charger le quartier",
                                id="quartier-load",
                                n_clicks=0,
                                className="btn btn-primary",
                            ),
                        ],
                        className="action-row",
                    ),
                ],
                className="card",
            ),
            build_log_console(prefix="quartier", title="Journal quartier"),
            html.Div(id="map-container-quartier", style={"display": "none"}),
            html.Div(
                [
                    html.Div(
                        [
                            html.H3("Simulation VRP", className="section-title"),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Label("Algorithme", className="field-label"),
                                            dcc.Dropdown(
                                                id="dropdown-quartier-algo",
                                                options=[
                                                    {"label": "GRASP", "value": "grasp"},
                                                    {"label": "Recherche Tabou", "value": "tabu_search"},
                                                    {"label": "Recuit Simulé", "value": "simulated_annealing"},
                                                    {"label": "Algorithme Génétique", "value": "genetic_algorithm"},
                                                ],
                                                value="grasp",
                                                clearable=False,
                                                style={"width": "250px"},
                                            ),
                                            html.Small("Methode utilisee pour resoudre la tournee.", className="field-hint"),
                                        ],
                                        className="quartier-max-clients",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Capacite vehicule", className="field-label"),
                                            dcc.Input(
                                                id="input-quartier-capacity",
                                                type="number",
                                                value=10,
                                                min=1,
                                                step=1,
                                                placeholder="Capacite vehicule",
                                            ),
                                            html.Small("Charge maximale transportee par camion.", className="field-hint"),
                                        ],
                                        className="quartier-max-clients",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Seed", className="field-label"),
                                            dcc.Input(
                                                id="input-quartier-seed",
                                                type="number",
                                                value=42,
                                                min=0,
                                                step=1,
                                                placeholder="Seed",
                                            ),
                                            html.Small("Controle la reproductibilite de la simulation.", className="field-hint"),
                                        ],
                                        className="quartier-max-clients",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Nombre de clients (max quartier)", className="field-label"),
                                            dcc.Input(
                                                id="input-quartier-max-clients",
                                                type="number",
                                                value=8,
                                                min=1,
                                                step=1,
                                                placeholder="Nombre de clients (max quartier)",
                                            ),
                                            html.Small(
                                                "Nombre de sommets de livraison utilises. Max quartier: inconnu.",
                                                id="hint-quartier-max-clients",
                                                className="field-hint",
                                            ),
                                        ],
                                        className="quartier-max-clients",
                                    ),
                                    html.Button(
                                        "Lancer simulation",
                                        id="quartier-run",
                                        className="btn btn-primary",
                                    ),
                                    html.Div(
                                        [
                                            html.Button(
                                                "Start",
                                                id="quartier-play",
                                                className="btn btn-primary",
                                                n_clicks=0,
                                            ),
                                            html.Button(
                                                "Pause",
                                                id="quartier-pause",
                                                className="btn",
                                                n_clicks=0,
                                                style={"background": "var(--color-error)"},
                                            ),
                                        ],
                                        style={"display": "flex", "gap": "0"},
                                    ),
                                ],
                                className="quartier-controls-row",
                            ),
                            html.Div(
                                [
                                    html.Label("Vitesse animation :", className="quartier-speed-label"),
                                    dcc.Slider(
                                        id="slider-quartier-vitesse",
                                        min=0.5,
                                        max=10.0,
                                        step=0.5,
                                        value=1.0,
                                        updatemode="drag",
                                        marks={
                                            0.5: "0.5x",
                                            1.0: "1x",
                                            2.0: "2x",
                                            5.0: "5x",
                                            10.0: "10x",
                                        },
                                        tooltip={"placement": "bottom"},
                                    ),
                                ],
                                className="quartier-speed-block",
                            ),
                            html.Div(id="animation-container-quartier", className="quartier-animation-container"),
                        ],
                    ),
                ],
                className="card quartier-sim-card",
            ),
        ],
        className="tab-content",
    )


def build_layout() -> html.Div:
    return html.Div(
        [
            dcc.Store(
                id="store-global",
                storage_type="session",
                data={
                    "active_tab": "tab-benchmark",
                    "benchmark_session_id": None,
                    "generation_session_id": None,
                    "quartier_session_id": None,
                },
            ),
            dcc.Store(
                id="store-benchmark",
                storage_type="session",
                data={
                    "status": "idle",
                    "session_id": None,
                    "sizes_raw": "10, 15, 20",
                    "seed_mode": "manual",
                    "seeds_raw": "1, 2, 3",
                    "seed_count": 4,
                    "resolved_seeds": [1, 2, 3],
                    "output_dir": "image",
                    "algorithms": [
                        "grasp",
                        "tabu_search",
                        "simulated_annealing",
                        "genetic_algorithm",
                    ],
                    "verbose": False,
                },
            ),
            dcc.Store(
                id="store-generation",
                storage_type="session",
                data={
                    "status": "idle",
                    "session_id": None,
                    "node_count": 15,
                    "seed": 42,
                    "algo_name": "grasp",
                    "capacity": 40,
                    "simulation_seed": 42,
                    "dynamic_sigma": 0.18,
                    "dynamic_mean_reversion_strength": 0.35,
                    "dynamic_max_multiplier": 1.8,
                    "dynamic_forbid_probability": 0.03,
                    "dynamic_restore_probability": 0.2,
                    "dynamic_max_disabled_ratio": 0.2,
                },
            ),
            dcc.Store(
                id="store-quartier",
                storage_type="session",
                data={
                    "status": "idle",
                    "session_id": None,
                    "place": "Place de la Concorde, Paris",
                    "distance_raw": 600,
                    "max_solver_clients": 8,
                    "max_solver_clients_available": None,
                },
            ),
            html.Div(
                [
                    html.H1("CESIPATH", className="app-title"),
                    html.P(
                        "Benchmark, generation et quartier OSM en interface web Dash.",
                        className="app-subtitle",
                    ),
                ],
                className="app-header",
            ),
            dcc.Tabs(
                id="tabs-main",
                value="tab-benchmark",
                className="tabs-root",
                children=[
                    dcc.Tab(
                        label="Benchmark",
                        value="tab-benchmark",
                        className="tab-trigger",
                        selected_className="tab-trigger-selected",
                        children=_benchmark_tab(),
                    ),
                    dcc.Tab(
                        label="Generation",
                        value="tab-generation",
                        className="tab-trigger",
                        selected_className="tab-trigger-selected",
                        children=_generation_tab(),
                    ),
                    dcc.Tab(
                        label="Quartier",
                        value="tab-quartier",
                        className="tab-trigger",
                        selected_className="tab-trigger-selected",
                        children=_quartier_tab(),
                    ),
                ],
            ),
        ],
        className="app-shell",
    )
