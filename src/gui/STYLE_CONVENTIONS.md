# Conventions de style GUI

## Objectif
Maintenir une interface coherente, lisible et evolutive sans impacter la logique metier.

## Organisation
- `theme.py` contient la palette, les fonts et les styles `ttk`.
- `components.py` contient les widgets reutilisables (boutons, champs, logs, indicateurs).
- `icons.py` genere les icones d'onglets via Pillow.
- `services.py` contient la logique metier appelee par la GUI.
- `main_gui.py` orchestre les onglets et les interactions utilisateur.

## Regles visuelles
- Utiliser les couleurs de `PALETTE` uniquement (pas de couleurs hardcodees hors cas ponctuels).
- Les actions principales utilisent `ColoredButton(role=\"primary\")` ou `role=\"success\"`.
- Les sections sont regroupees dans des `LabelFrame` avec separateurs visuels.
- Les sorties utilisateur passent par `LogConsole` avec niveaux (`info`, `success`, `error`, `running`).

## Regles UX
- Toute action potentiellement longue doit afficher un `RunningIndicator`.
- Les champs numeriques doivent utiliser un validateur live (`LabeledEntry(..., validator=...)`).
- Les erreurs bloquantes remontent via `messagebox.showerror` et sont aussi ecrites dans les logs.
- Les calculs de visualisation lourds se font en thread worker, puis l'injection Tkinter (`FigureCanvasTkAgg`) se fait sur le thread principal.
- En reconnaissance quartier, conserver le fond de carte et optimiser son chargement (parallelisation/caching).
