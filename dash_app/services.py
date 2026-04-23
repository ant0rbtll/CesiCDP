"""Shared Dash service layer: parsing, validation and typed service contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
from typing import Any, Callable


def _coerce_text(raw: Any, field_name: str) -> str:
    """Normalize user input text and enforce required values."""

    if raw is None:
        raise ValueError(f"{field_name}: value is required.")
    text = str(raw).strip()
    if not text:
        raise ValueError(f"{field_name}: value is required.")
    return text


def _parse_int_like(raw: Any, field_name: str) -> int:
    """Parse integers from plain int strings or integral float strings."""

    text = _coerce_text(raw, field_name)
    try:
        return int(text)
    except ValueError:
        try:
            as_float = float(text)
        except ValueError as exc:
            raise ValueError(f"{field_name}: '{text}' is not a valid integer.") from exc
        if not as_float.is_integer():
            raise ValueError(f"{field_name}: '{text}' is not a valid integer.")
        return int(as_float)


def parse_int_list(raw: str, field_name: str) -> list[int]:
    """Parse comma/space separated strictly positive integers."""

    tokens = [token for chunk in raw.split(",") for token in chunk.split()]
    if not tokens:
        raise ValueError(f"{field_name}: no values were provided.")

    values: list[int] = []
    for token in tokens:
        value = _parse_int_like(token, field_name)
        if value <= 0:
            raise ValueError(f"{field_name}: each value must be > 0.")
        values.append(value)
    return values


def parse_float(raw: str, field_name: str) -> float:
    """Parse a floating-point value from user text input."""

    text = _coerce_text(raw, field_name)
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"{field_name}: '{text}' is not a valid number.") from exc


def parse_positive_int(raw: str, field_name: str) -> int:
    """Parse a strictly positive integer (> 0)."""

    value = _parse_int_like(raw, field_name)
    if value <= 0:
        raise ValueError(f"{field_name}: value must be > 0.")
    return value


def parse_optional_int(raw: str, field_name: str) -> int | None:
    """Parse an optional integer, returning ``None`` for blank inputs."""

    text = str(raw).strip()
    if not text:
        return None
    return _parse_int_like(text, field_name)


def int_list_validator(field_name: str) -> Callable[[Any], tuple[bool, str]]:
    """Build a validator for comma/space-separated positive integer lists."""

    def _validator(value: Any) -> tuple[bool, str]:
        try:
            parse_int_list(str(value or ""), field_name)
        except ValueError as exc:
            return False, str(exc)
        return True, ""

    return _validator


def positive_int_validator(field_name: str) -> Callable[[Any], tuple[bool, str]]:
    """Build a validator for strictly positive integers."""

    def _validator(value: Any) -> tuple[bool, str]:
        try:
            parse_positive_int(str(value or ""), field_name)
        except ValueError as exc:
            return False, str(exc)
        return True, ""

    return _validator


def float_validator(field_name: str) -> Callable[[Any], tuple[bool, str]]:
    """Build a validator for floating-point fields."""

    def _validator(value: Any) -> tuple[bool, str]:
        try:
            parse_float(str(value or ""), field_name)
        except ValueError as exc:
            return False, str(exc)
        return True, ""

    return _validator


def validate_benchmark_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate benchmark form payload and return normalized values."""

    sizes = parse_int_list(str(payload.get("sizes_raw", "")), "Tailles")
    seed_mode = str(payload.get("seed_mode", "manual")).strip() or "manual"
    if seed_mode not in {"manual", "random_count"}:
        raise ValueError("Seed mode: invalid selection.")

    if seed_mode == "manual":
        seeds = parse_int_list(str(payload.get("seeds_raw", "")), "Seeds")
        seed_count = len(seeds)
    else:
        seed_count = parse_positive_int(str(payload.get("seed_count", "")), "Nombre de seeds")
        seeds = sorted(random.sample(range(1, 1_000_000_000), seed_count))

    output_dir = str(payload.get("output_dir", "")).strip()
    if not output_dir:
        raise ValueError("Output directory: a non-empty path is required.")

    algorithms_raw = payload.get("algorithms") or []
    algorithms = [str(algo).strip() for algo in algorithms_raw if str(algo).strip()]
    if not algorithms:
        raise ValueError("Algorithms: select at least one algorithm.")

    return {
        "sizes": sizes,
        "seeds": seeds,
        "seed_mode": seed_mode,
        "seed_count": seed_count,
        "algorithms": algorithms,
        "output_dir": output_dir,
        "verbose": bool(payload.get("verbose", False)),
    }


def validate_generation_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate generation form payload and return normalized values."""

    node_count = parse_positive_int(str(payload.get("node_count", "")), "node_count")
    if node_count < 3:
        raise ValueError("node_count: value must be >= 3.")

    seed_value = parse_optional_int(str(payload.get("seed", "")), "seed")
    if seed_value is None:
        raise ValueError("seed: value is required.")
    if seed_value < 0:
        raise ValueError("seed: value must be >= 0.")

    sigma = parse_float(str(payload.get("dynamic_sigma", "")), "dynamic_sigma")
    if sigma <= 0:
        raise ValueError("dynamic_sigma: value must be > 0.")

    mean_reversion = parse_float(
        str(payload.get("dynamic_mean_reversion_strength", "")),
        "dynamic_mean_reversion_strength",
    )
    if not (0 < mean_reversion <= 1):
        raise ValueError("dynamic_mean_reversion_strength: value must be in (0, 1].")

    max_multiplier = parse_float(
        str(payload.get("dynamic_max_multiplier", "")),
        "dynamic_max_multiplier",
    )
    if max_multiplier < 1.0:
        raise ValueError("dynamic_max_multiplier: value must be >= 1.0.")

    forbid_probability = parse_float(
        str(payload.get("dynamic_forbid_probability", "")),
        "dynamic_forbid_probability",
    )
    if not (0 <= forbid_probability <= 1):
        raise ValueError("dynamic_forbid_probability: value must be in [0, 1].")

    restore_probability = parse_float(
        str(payload.get("dynamic_restore_probability", "")),
        "dynamic_restore_probability",
    )
    if not (0 <= restore_probability <= 1):
        raise ValueError("dynamic_restore_probability: value must be in [0, 1].")

    max_disabled_ratio = parse_float(
        str(payload.get("dynamic_max_disabled_ratio", "")),
        "dynamic_max_disabled_ratio",
    )
    if not (0 <= max_disabled_ratio <= 1):
        raise ValueError("dynamic_max_disabled_ratio: value must be in [0, 1].")

    return {
        "node_count": node_count,
        "seed": seed_value,
        "dynamic_sigma": sigma,
        "dynamic_mean_reversion_strength": mean_reversion,
        "dynamic_max_multiplier": max_multiplier,
        "dynamic_forbid_probability": forbid_probability,
        "dynamic_restore_probability": restore_probability,
        "dynamic_max_disabled_ratio": max_disabled_ratio,
    }


def validate_quartier_payload(payload: dict[str, Any]) -> tuple[str, float]:
    """Validate OSM quartier load payload."""

    place = str(payload.get("place", "")).strip()
    if not place:
        raise ValueError("place: value is required.")

    distance = parse_float(str(payload.get("distance_raw", "")), "distance")
    if distance <= 0:
        raise ValueError("distance: value must be > 0.")

    return place, distance


def validate_quartier_simulation_payload(
    payload: dict[str, Any],
    allowed_algorithms: set[str],
) -> dict[str, int | str]:
    """Validate quartier simulation inputs for algorithm execution."""

    algorithm_name = str(payload.get("algo_name", "")).strip()
    if algorithm_name not in allowed_algorithms:
        raise ValueError("algo_name: selected algorithm is invalid.")

    capacity = parse_positive_int(str(payload.get("capacity", "")), "capacity")

    seed = parse_optional_int(str(payload.get("seed", "")), "seed")
    if seed is None:
        raise ValueError("seed: value is required.")
    if seed < 0:
        raise ValueError("seed: value must be >= 0.")

    max_clients = parse_positive_int(str(payload.get("max_clients", "")), "max_clients")

    return {
        "algo_name": algorithm_name,
        "capacity": capacity,
        "seed": seed,
        "max_clients": max_clients,
    }


@dataclass
class BenchmarkServiceResult:
    """Structured benchmark outputs."""

    results: list[dict[str, Any]]
    figure_paths: dict[str, Path]
    summary: list[dict[str, Any]]


@dataclass
class GenerationServiceResult:
    """Structured generation outputs."""

    summary: dict[str, Any]
    session: Any


@dataclass
class QuartierServiceResult:
    """Structured quartier outputs."""

    quartier_graph: Any
    stats: dict[str, Any]
    export_path: str | None
    dynamic_instance_summary: dict[str, Any]
    dynamic_metadata: dict[str, Any]
    dynamic_instance: Any
