"""Point d entree Dash pour VRP-CDR."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from dash import Dash

try:
    from dash import DiskcacheManager
    import diskcache

    _disk_cache_dir = PROJECT_ROOT / "cache" / "dash_diskcache"
    _disk_cache_dir.mkdir(parents=True, exist_ok=True)
    _disk_cache = diskcache.Cache(str(_disk_cache_dir))
    BACKGROUND_CALLBACK_MANAGER = DiskcacheManager(_disk_cache)
except Exception:
    BACKGROUND_CALLBACK_MANAGER = None

# Cache serveur global pour objets non serialisables.
SESSION_CACHE: dict[str, Any] = {}

from callbacks import register_all_callbacks
from layout import build_layout

app = Dash(
    __name__,
    assets_folder="assets",
    suppress_callback_exceptions=True,
    background_callback_manager=BACKGROUND_CALLBACK_MANAGER,
)
app.layout = build_layout()

register_all_callbacks(
    app=app,
    session_cache=SESSION_CACHE,
    background_callback_manager=BACKGROUND_CALLBACK_MANAGER,
)

if __name__ == "__main__":
    app.run(debug=True, port=8050, processes=1, threaded=True)
