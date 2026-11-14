"""Reservoir water polygons from OpenStreetMap (Overpass API), matched to COGERH sampling points.

Matching rule (simple and explainable):
1. Candidates: OSM water polygons (natural=water or landuse=reservoir) within SEARCH_M of the
   sampling point, excluding rivers, canals and aquaculture tanks.
2. If polygons contain the point, take the largest one (a multipolygon relation is larger than
   its member ways). Otherwise take the nearest polygon within NEAREST_MAX_M.
3. The OSM name is only used as a check: we report where it does not match the COGERH name
   (e.g. Banabuiú is "Açude Arrojado Lisboa" in OSM, its official name).
Reservoirs with no match fall back to a circle around the point (water is masked per image later).
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import geopandas as gpd
import requests
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import polygonize, unary_union

from common import normalize_name

OVERPASS = "https://overpass-api.de/api/interpreter"
UTM = "EPSG:31984"  # SIRGAS 2000 / UTM zone 24S, covers Ceará; distances and areas in metres
SEARCH_M = 1500
NEAREST_MAX_M = 1000
FALLBACK_RADIUS_M = 1000
EXCLUDE_WATER = {"river", "canal", "stream", "aquaculture", "wastewater", "ditch", "moat", "stream_pool"}
GENERIC = {"acude", "barragem", "lagoa", "reservatorio", "represa", "lago", "de", "do", "da", "dos", "das"}


def overpass_query(points, radius=SEARCH_M):
    skip = '["water"!~"^(' + "|".join(sorted(EXCLUDE_WATER)) + ')$"]'  # passes when 'water' is absent
    parts = []
    for lat, lon in points:
        for kind in ("way", "relation"):
            parts.append(f'{kind}(around:{radius},{lat:.6f},{lon:.6f})["natural"="water"]{skip};')
            parts.append(f'{kind}(around:{radius},{lat:.6f},{lon:.6f})["landuse"="reservoir"]{skip};')
    return "[out:json][timeout:300];(" + "".join(parts) + ");out geom;"


def fetch_osm_water(points, cache: Path, batch=15, pause=5.0, retries=4):
    """Query Overpass in batches; cache each batch's raw JSON so nothing is downloaded twice.
    The cache key is the batch's coordinates, so changing the point list never reuses a wrong file."""
    cache.mkdir(parents=True, exist_ok=True)
    elements = {}
    for i in range(0, len(points), batch):
        chunk = points[i:i + batch]
        key = hashlib.md5(repr([(round(a, 5), round(b, 5)) for a, b in chunk]).encode()).hexdigest()[:12]
        f = cache / f"overpass_{key}.json"
        if not f.exists():
            for attempt in range(retries):
                r = requests.post(OVERPASS, data={"data": overpass_query(chunk)},
                                  headers={"User-Agent": "alerta-acude-research/0.1"}, timeout=400)
                if r.status_code == 200:
                    break
                print(f"overpass HTTP {r.status_code}, retry in {30 * (attempt + 1)} s", flush=True)
                time.sleep(30 * (attempt + 1))
            r.raise_for_status()
            f.write_text(r.text, encoding="utf-8")
            time.sleep(pause)
        for e in json.loads(f.read_text(encoding="utf-8"))["elements"]:
            elements[(e["type"], e["id"])] = e
    return list(elements.values())


def element_polygon(e):
    """Shapely polygon for a closed way or a multipolygon relation (outer minus inner rings)."""
    if e["type"] == "way":
        pts = [(n["lon"], n["lat"]) for n in e.get("geometry", [])]
        if len(pts) >= 4 and pts[0] == pts[-1]:
            poly = Polygon(pts)
            return poly if poly.is_valid else poly.buffer(0)
        return None
    outer, inner = [], []
    for m in e.get("members", []):
        if m.get("type") != "way" or "geometry" not in m:
            continue
        line = LineString([(n["lon"], n["lat"]) for n in m["geometry"]])
        (inner if m.get("role") == "inner" else outer).append(line)
    if not outer:
        return None
    shell = unary_union(list(polygonize(unary_union(outer))))
    if shell.is_empty:
        return None
    if inner:
        holes = unary_union(list(polygonize(unary_union(inner))))
        shell = shell.difference(holes)
    return shell if shell.is_valid else shell.buffer(0)


def osm_water_frame(elements):
    rows = []
    for e in elements:
        tags = e.get("tags", {})
        if tags.get("water") in EXCLUDE_WATER:
            continue
        geom = element_polygon(e)
        if geom is None or geom.is_empty:
            continue
        rows.append({"osm_type": e["type"], "osm_id": e["id"], "osm_name": tags.get("name", ""),
                     "osm_water": tags.get("water", ""), "geometry": geom})
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    gdf["area_km2"] = gdf.to_crs(UTM).area / 1e6
    return gdf


def name_matches(cogerh: str, osm: str) -> bool:
    a = set(normalize_name(cogerh).split()) - GENERIC
    b = set(normalize_name(osm).split()) - GENERIC
    return bool(a) and a <= b


def match_reservoirs(points: gpd.GeoDataFrame, water: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """points: one row per reservoir with columns reservoir, name, lat, lon (EPSG:4326)."""
    pts = points.to_crs(UTM)
    wat = water.to_crs(UTM)
    out = []
    for i, p in pts.iterrows():
        geom_pt = p.geometry
        near = wat[wat.distance(geom_pt) <= SEARCH_M]
        inside = near[near.contains(geom_pt)]
        if len(inside):
            best, method, dist = inside.loc[inside["area_km2"].idxmax()], "contains_point", 0.0
        else:
            d = near.distance(geom_pt)
            close = near[d <= NEAREST_MAX_M]
            if len(close):
                j = d[close.index].idxmin()
                best, method, dist = close.loc[j], "nearest", float(d[j])
            else:
                best, method, dist = None, "fallback_circle", None
        if best is None:
            geom = geom_pt.buffer(FALLBACK_RADIUS_M)
            rec = {"osm_type": "", "osm_id": None, "osm_name": "", "osm_water": "", "name_check": ""}
        else:
            geom = best.geometry
            rec = {k: best[k] for k in ("osm_type", "osm_id", "osm_name", "osm_water")}
            rec["name_check"] = "match" if name_matches(p["name"], best["osm_name"]) else (
                "no_osm_name" if not best["osm_name"] else "different")
        out.append({"reservoir": p["reservoir"], "name": p["name"], "basin": p["basin"],
                    "lat": p["lat"], "lon": p["lon"], "match": method, "dist_m": dist, **rec,
                    "geometry": geom})
    res = gpd.GeoDataFrame(out, geometry="geometry", crs=UTM)
    res["area_km2"] = res.area / 1e6
    return res.to_crs("EPSG:4326")


AOI_RADIUS_M = 1000   # water within 1 km of the reservoir's reference point
POLY_MARGIN_M = 100   # tolerance for OSM outlines drawn at a different water level
TRUST_MIN_KM2 = 0.1   # smaller matches next to large reservoirs were wrong (Figueiredo, Pirabibu)
TRUST_MAX_DIST_M = 200


def build_aoi(matched: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Area of interest per reservoir: a disc around the reference point, clipped to the OSM
    polygon (plus a margin) when the OSM match is trustworthy. Water pixels are still selected
    per image later (SCL water + MNDWI > 0, eroded 2 px), so the disc alone is a safe fallback."""
    m = matched.to_crs(UTM).copy()
    pts = gpd.GeoSeries(gpd.points_from_xy(matched["lon"], matched["lat"]), crs="EPSG:4326").to_crs(UTM)
    disc = pts.buffer(AOI_RADIUS_M).values
    m["osm_area_km2"] = m.area / 1e6
    m["osm_trusted"] = (m["match"] != "fallback_circle") & (m["osm_area_km2"] >= TRUST_MIN_KM2) & (
        m["dist_m"].fillna(1e9) <= TRUST_MAX_DIST_M)
    aoi = []
    for i, (geom, trusted) in enumerate(zip(m.geometry.values, m["osm_trusted"])):
        aoi.append(disc[i].intersection(geom.buffer(POLY_MARGIN_M)) if trusted else disc[i])
    m = m.set_geometry(gpd.GeoSeries(aoi, crs=UTM, index=m.index))
    m["aoi_km2"] = m.area / 1e6
    m["aoi_type"] = m["osm_trusted"].map({True: "disc_x_osm", False: "disc"})
    return m.to_crs("EPSG:4326")
