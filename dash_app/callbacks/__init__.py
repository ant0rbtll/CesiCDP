"""Enregistrement central des callbacks Dash."""

from __future__ import annotations

from typing import Any

from . import benchmark, generation, quartier


def _ensure_runtime_cache(session_cache: dict[str, Any]) -> None:
    session_cache.setdefault("sessions", {})
    session_cache.setdefault("objects", {})
    session_cache.setdefault("osm_geojson", {})


def register_all_callbacks(app, session_cache: dict[str, Any], background_callback_manager=None) -> None:
    _ensure_runtime_cache(session_cache)

    benchmark.register_callbacks(
        app=app,
        session_cache=session_cache,
        background_callback_manager=background_callback_manager,
    )
    generation.register_callbacks(
        app=app,
        session_cache=session_cache,
        background_callback_manager=background_callback_manager,
    )
    quartier.register_callbacks(
        app=app,
        session_cache=session_cache,
        background_callback_manager=background_callback_manager,
    )
