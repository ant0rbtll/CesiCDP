"""Composants carte OSM pour l onglet Quartier."""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

from dash import dcc, html
import numpy as np
from PIL import Image
import plotly.graph_objects as go
from theme import PALETTE as MAP_COLORS

try:
    import contextily as ctx
    from contextily.tile import warp_tiles
    from rasterio.enums import Resampling

    CONTEXTILY_AVAILABLE = True
except Exception:
    ctx = None
    warp_tiles = None
    Resampling = None
    CONTEXTILY_AVAILABLE = False

_SESSION_CACHE: dict[str, Any] = {}

MAP_SIZES = {
    "edge_free": 1.5,
    "edge_surcharged": 1.5,
    "edge_forbidden": 1.0,
    "transit": 5,
    "depot": 20,
    "depot_text": 10,
}


def _compute_bounds(nodes: list[dict[str, Any]]) -> dict[str, float]:
    lons = [float(node["lon"]) for node in nodes]
    lats = [float(node["lat"]) for node in nodes]
    min_lon = min(lons)
    max_lon = max(lons)
    min_lat = min(lats)
    max_lat = max(lats)

    pad_lon = (max_lon - min_lon) * 0.05 if max_lon > min_lon else 0.0003
    pad_lat = (max_lat - min_lat) * 0.05 if max_lat > min_lat else 0.0003

    return {
        "lon_min": min_lon - pad_lon,
        "lon_max": max_lon + pad_lon,
        "lat_min": min_lat - pad_lat,
        "lat_max": max_lat + pad_lat,
    }


def _pick_zoom(node_count: int) -> int:
    if node_count > 700:
        return 13
    if node_count > 320:
        return 14
    return 15


def _image_to_data_uri(image: np.ndarray) -> str:
    if image.dtype != np.uint8:
        clipped = np.clip(image, 0.0, 1.0)
        image = (clipped * 255).astype(np.uint8)

    png_buffer = BytesIO()
    Image.fromarray(image).save(png_buffer, format="PNG")
    encoded = base64.b64encode(png_buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _get_basemap_overlay(session_id: str, nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not CONTEXTILY_AVAILABLE:
        return None

    bounds = _compute_bounds(nodes)
    zoom = _pick_zoom(len(nodes))
    cache_key = (
        round(bounds["lon_min"], 6),
        round(bounds["lat_min"], 6),
        round(bounds["lon_max"], 6),
        round(bounds["lat_max"], 6),
        zoom,
    )

    session_bucket = _SESSION_CACHE.setdefault(session_id, {})
    cached = session_bucket.get("_map_basemap_overlay")
    if isinstance(cached, dict) and cached.get("key") == cache_key:
        return cached.get("overlay")

    try:
        image, extent = ctx.bounds2img(
            bounds["lon_min"],
            bounds["lat_min"],
            bounds["lon_max"],
            bounds["lat_max"],
            zoom=zoom,
            source=ctx.providers.CartoDB.Positron,
            ll=True,
            n_connections=1,
            use_cache=False,
            headers={"User-Agent": "CESIPATH/1.0"},
        )
        image, extent = warp_tiles(image, extent, t_crs="EPSG:4326", resampling=Resampling.bilinear)
        xmin, xmax, ymin, ymax = [float(v) for v in extent]
        if xmax <= xmin or ymax <= ymin:
            return None

        overlay = {
            "source": _image_to_data_uri(image),
            "xref": "x",
            "yref": "y",
            "x": xmin,
            "y": ymax,
            "sizex": xmax - xmin,
            "sizey": ymax - ymin,
            "xanchor": "left",
            "yanchor": "top",
            "sizing": "stretch",
            "opacity": 0.92,
            "layer": "below",
        }
        session_bucket["_map_basemap_overlay"] = {"key": cache_key, "overlay": overlay}
        return overlay
    except Exception:
        return None


def is_leaflet_available() -> bool:
    """Compatibilite retroactive avec anciens imports."""

    return False


def configure_session_cache(session_cache: dict[str, Any]) -> None:
    """Reference le cache serveur utilise par les callbacks."""

    global _SESSION_CACHE
    _SESSION_CACHE = session_cache


def build_map(session_id: str | None):
    """Construit le rendu du graphe OSM en mode mathematique."""

    if session_id is None or session_id not in _SESSION_CACHE:
        return html.Div(
            "Aucun quartier charge.",
            style={"color": MAP_COLORS["empty_text"], "padding": "20px"},
        )

    nodes = _SESSION_CACHE[session_id].get("osm_nodes") or []
    edges = _SESSION_CACHE[session_id].get("osm_edges") or []
    center = _SESSION_CACHE[session_id].get("osm_center")

    if not nodes:
        return html.Div(
            "Aucun quartier charge.",
            style={"color": MAP_COLORS["empty_text"], "padding": "20px"},
        )

    bounds = _compute_bounds(nodes)
    basemap_overlay = _get_basemap_overlay(session_id, nodes)

    # Index nodes par id pour lookup rapide
    node_index = {int(node["id"]): node for node in nodes}

    lengths = [float(edge.get("length", 1.0)) for edge in edges if float(edge.get("length", 1.0)) < 1e8]
    if lengths:
        sorted_lengths = sorted(lengths)
        p33 = sorted_lengths[min(len(sorted_lengths) - 1, int(len(sorted_lengths) * 0.33))]
        p66 = sorted_lengths[min(len(sorted_lengths) - 1, int(len(sorted_lengths) * 0.66))]
    else:
        p33, p66 = 50.0, 150.0

    free_x: list[float | None] = []
    free_y: list[float | None] = []
    surcharged_x: list[float | None] = []
    surcharged_y: list[float | None] = []
    forbidden_x: list[float | None] = []
    forbidden_y: list[float | None] = []

    for edge in edges:
        u = node_index.get(int(edge["u"]))
        v = node_index.get(int(edge["v"]))
        if not u or not v:
            continue
        seg_x = [float(u["lon"]), float(v["lon"]), None]
        seg_y = [float(u["lat"]), float(v["lat"]), None]
        length = float(edge.get("length", 1.0))
        if length <= p33:
            free_x += seg_x
            free_y += seg_y
        elif length <= p66:
            surcharged_x += seg_x
            surcharged_y += seg_y
        else:
            forbidden_x += seg_x
            forbidden_y += seg_y

    trace_free = go.Scatter(
        x=free_x,
        y=free_y,
        mode="lines",
        name="Libre",
        line={"color": MAP_COLORS["free"], "width": MAP_SIZES["edge_free"]},
        hoverinfo="skip",
    )
    trace_surcharged = go.Scatter(
        x=surcharged_x,
        y=surcharged_y,
        mode="lines",
        name="Chargé",
        line={"color": MAP_COLORS["surcharged"], "width": MAP_SIZES["edge_surcharged"], "dash": "dot"},
        hoverinfo="skip",
    )
    trace_forbidden = go.Scatter(
        x=forbidden_x,
        y=forbidden_y,
        mode="lines",
        name="Lent",
        line={"color": MAP_COLORS["forbidden"], "width": MAP_SIZES["edge_forbidden"], "dash": "dash"},
        hoverinfo="skip",
    )

    depot_node = nodes[0]
    transit_nodes = nodes[1:]

    trace_transit = go.Scatter(
        x=[float(node["lon"]) for node in transit_nodes],
        y=[float(node["lat"]) for node in transit_nodes],
        mode="markers",
        name="Intersections",
        showlegend=False,
        marker={
            "color": MAP_COLORS["transit"],
            "size": MAP_SIZES["transit"],
            "line": {"color": MAP_COLORS["transit_border"], "width": 0.5},
        },
        hovertemplate="Noeud %{customdata}<extra></extra>",
        customdata=[int(node["id"]) for node in transit_nodes],
    )
    trace_depot = go.Scatter(
        x=[float(depot_node["lon"])],
        y=[float(depot_node["lat"])],
        mode="markers+text",
        name="Depot",
        showlegend=False,
        marker={
            "color": MAP_COLORS["depot"],
            "size": MAP_SIZES["depot"],
            "symbol": "square",
            "line": {"color": MAP_COLORS["light"], "width": 2},
        },
        text=["D"],
        textposition="middle center",
        textfont={"color": MAP_COLORS["depot_text"], "size": MAP_SIZES["depot_text"]},
        hoverinfo="skip",
    )

    fig = go.Figure(
        data=[
            trace_free,
            trace_surcharged,
            trace_forbidden,
            trace_transit,
            trace_depot,
        ]
    )
    fig.update_layout(
        paper_bgcolor=MAP_COLORS["transparent"],
        plot_bgcolor=MAP_COLORS["transparent"] if basemap_overlay is not None else MAP_COLORS["bg_plot"],
        font={"family": "Segoe UI, system-ui", "color": MAP_COLORS["font_light"]},
        xaxis={
            "showgrid": False,
            "zeroline": False,
            "showticklabels": False,
            "scaleanchor": "y",
            "scaleratio": 1,
            "range": [bounds["lon_min"], bounds["lon_max"]],
            "fixedrange": False,
        },
        yaxis={
            "showgrid": False,
            "zeroline": False,
            "showticklabels": False,
            "range": [bounds["lat_min"], bounds["lat_max"]],
            "fixedrange": False,
        },
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        height=500,
        showlegend=True,
        legend={
            "bgcolor": MAP_COLORS["legend_bg"],
            "bordercolor": MAP_COLORS["free"],
            "borderwidth": 1,
            "font": {"color": MAP_COLORS["font_light"], "size": 11},
            "x": 0.01,
            "y": 0.99,
            "xanchor": "left",
            "yanchor": "top",
        },
        images=[basemap_overlay] if basemap_overlay is not None else [],
        hovermode="closest",
    )

    # centre conserve pour usage futur (ex: annotations / recentrage)
    _ = center

    return dcc.Graph(
        id="map-quartier",
        figure=fig,
        config={"scrollZoom": True, "displayModeBar": True},
    )


def build_map_view() -> html.Div:
    """Bloc visuel de la carte dans l onglet Quartier."""

    return html.Div(
        [
            html.H3("Carte OSM", className="section-title"),
            html.P("Rendu graphe OSM", className="section-hint"),
            html.Div(id="map-container-quartier", children=build_map(None)),
        ],
        className="card",
    )
