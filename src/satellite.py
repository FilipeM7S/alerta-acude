"""Sentinel-2 L2A water features for one reservoir AOI and one date (Microsoft Planetary Computer).

Per sample:
1. candidate images: acquisitions within +-MAX_GAP_DAYS of the lab date, closest first;
2. water pixels: SCL class 6 (water) AND MNDWI > 0 inside the AOI, mask eroded by 2 pixels
   so shoreline pixels (mixed land/water) are dropped; clouds, shadows and cirrus are never
   class 6, so they are excluded too;
3. the first candidate with >= MIN_WATER_PX clean water pixels is used;
4. reflectance = (DN - offset) / 10000, offset = 1000 for processing baseline >= 04.00;
5. per-band median over the clean water pixels, then indices from the medians.
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import threading

import numpy as np
import odc.stac
import pandas as pd
import planetary_computer as pc
import pystac_client
import shapely
from scipy.ndimage import binary_erosion
from shapely.geometry import box, shape

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
# Only the bands the indices need: green (B03), red (B04), red-edge (B05, B06), NIR (B08), SWIR (B11).
BANDS = ["B03", "B04", "B05", "B06", "B08", "B11"]
MAX_GAP_DAYS = 5
MIN_WATER_PX = 30
RES_M = 20
CRS = "EPSG:32724"  # WGS 84 / UTM 24S, the native grid of most Sentinel-2 tiles over Ceará

odc.stac.configure_rio(cloud_defaults=True)
_local = threading.local()


def catalog():
    if not hasattr(_local, "catalog"):  # one client per thread
        _local.catalog = pystac_client.Client.open(STAC)
    return _local.catalog


def search_items(aoi_bounds_ll, date, max_gap=MAX_GAP_DAYS):
    """Sentinel-2 L2A items within +-max_gap days of the date whose footprint covers the whole
    AOI box. One small search per sample is much faster than one search over ten years."""
    d = pd.Timestamp(date)
    window = f"{(d - timedelta(days=max_gap)).date()}/{(d + timedelta(days=max_gap)).date()}"
    items = catalog().search(collections=["sentinel-2-l2a"], bbox=list(aoi_bounds_ll),
                             datetime=window).item_collection()
    aoi_box = box(*aoi_bounds_ll)
    return [it for it in items if shape(it.geometry).contains(aoi_box)]


def baseline_offset(item) -> int:
    b = item.properties.get("s2:processing_baseline")
    return 1000 if b is not None and float(b) >= 4.0 else 0


def water_features(item, aoi_utm, aoi_bounds_ll):
    """Load one image over the AOI and return the water-pixel features (or the reason it failed)."""
    signed = pc.sign(item)
    ds = odc.stac.load([signed], bands=BANDS + ["SCL"], bbox=aoi_bounds_ll, crs=CRS, resolution=RES_M,
                       resampling={"SCL": "nearest", "*": "average"}, pool=len(BANDS) + 1).isel(time=0)
    xs, ys = np.meshgrid(ds.x.values, ds.y.values)
    in_aoi = shapely.contains_xy(aoi_utm, xs, ys)
    scl = ds["SCL"].values
    dn = {b: ds[b].values.astype("float64") for b in BANDS}
    valid = in_aoi & (dn["B03"] > 0) & (dn["B11"] > 0)
    off = baseline_offset(item)
    refl = {b: (v - off) / 10000.0 for b, v in dn.items()}
    with np.errstate(divide="ignore", invalid="ignore"):
        mndwi = (refl["B03"] - refl["B11"]) / (refl["B03"] + refl["B11"])
    water = valid & (scl == 6) & (mndwi > 0)
    clean = binary_erosion(water, iterations=2)
    clear = valid & ~np.isin(scl, [0, 1, 3, 8, 9, 10])  # not nodata, saturated, shadow, cloud, cirrus
    n = int(clean.sum())
    info = {"item_id": item.id, "n_water_px": n, "n_clear_px": int(clear.sum()), "n_aoi_px": int(in_aoi.sum()),
            "processing_baseline": item.properties.get("s2:processing_baseline"), "offset": off}
    if n < MIN_WATER_PX:
        return None, info
    med = {b: float(np.median(refl[b][clean])) for b in BANDS}
    f = {f"{b}": med[b] for b in BANDS}
    b03, b04, b05, b06, b11 = med["B03"], med["B04"], med["B05"], med["B06"], med["B11"]
    f["NDCI"] = (b05 - b04) / (b05 + b04)
    f["3BSI"] = (1 / b04 - 1 / b05) * b06 if b04 > 0 and b05 > 0 else np.nan
    f["MCI"] = b05 - b04 - (b06 - b04) * (705 - 665) / (740 - 665)
    f["NDTI"] = (b04 - b03) / (b04 + b03)
    f["MNDWI"] = float(np.median(mndwi[clean]))
    f["water_frac"] = float(water.sum() / clear.sum()) if clear.sum() else np.nan
    return f, info


def features_for_sample(reservoir, date, aoi_utm, aoi_bounds_ll, cache: Path, max_gap=MAX_GAP_DAYS):
    """Closest image within +-max_gap days that has enough clean water pixels (cached per sample)."""
    date = pd.Timestamp(date)
    f = cache / f"{reservoir.replace(' ', '_')}_{date.date()}_gap{max_gap}.json"
    if f.exists():
        return json.loads(f.read_text())
    out = _features_for_sample(date, aoi_utm, aoi_bounds_ll, search_items(aoi_bounds_ll, date, max_gap), max_gap)
    if "error" not in out.get("status", ""):
        f.write_text(json.dumps(out))
    return out


def _features_for_sample(date, aoi_utm, aoi_bounds_ll, items, max_gap):
    cands = []
    for it in items:
        d = pd.Timestamp(it.datetime).tz_localize(None).normalize()
        gap = abs((d - date).days)
        if gap <= max_gap:
            cands.append((gap, it.properties.get("eo:cloud_cover", 100), it))
    cands.sort(key=lambda c: (c[0], c[1]))
    tried = []
    for gap, cc, it in cands:
        try:
            f, info = water_features(it, aoi_utm, aoi_bounds_ll)
        except Exception as e:  # network or read error: record and try the next image
            tried.append({"item_id": it.id, "error": f"{type(e).__name__}: {e}"[:200]})
            continue
        info["day_gap"] = gap
        info["img_date"] = str(pd.Timestamp(it.datetime).date())
        if f is not None:
            return {**f, **info, "status": "ok", "n_tried": len(tried) + 1}
        tried.append(info)
    reason = "no image within +-%d days" % max_gap if not cands else "no image with >= %d clean water pixels" % MIN_WATER_PX
    return {"status": reason, "n_tried": len(tried), "n_candidates": len(cands)}
