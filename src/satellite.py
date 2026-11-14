"""Sentinel-2 L2A water features for one reservoir AOI and one date (Microsoft Planetary Computer).

Per sample:
1. candidate images: acquisitions within +-MAX_GAP_DAYS of the lab date, closest first;
2. water pixels: SCL class 6 (water) AND MNDWI > 0 inside the AOI, mask eroded by 2 pixels
   so shoreline pixels (mixed land/water) are dropped; clouds, shadows and cirrus are never
   class 6, so they are excluded too;
3. the first candidate with >= MIN_WATER_PX clean water pixels is used (the cheap SCL layer is
   checked first, so cloudy images cost almost nothing);
4. reflectance = (DN - offset) / 10000, offset = 1000 for processing baseline >= 04.00;
5. per-band median over the clean water pixels, then indices from the medians:
   NDCI (chlorophyll), NDTI (turbidity), MNDWI, and water_frac (share of the clear AOI that is water).
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
# Only the bands the features need: green (B03), red (B04), red-edge (B05), SWIR (B11).
# Each band read costs ~0.8 MB on our connection, so we keep the list short.
BANDS = ["B03", "B04", "B05", "B11"]
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


def coverage(item, aoi_bounds_ll) -> float:
    """Share of the AOI box inside the image footprint (images at swath edges cover only part)."""
    aoi_box = box(*aoi_bounds_ll)
    return shape(item.geometry).intersection(aoi_box).area / aoi_box.area


def search_items(aoi_bounds_ll, date, max_gap=MAX_GAP_DAYS, min_coverage=0.5):
    """Sentinel-2 L2A items within +-max_gap days of the date covering at least half of the AOI
    box. One small search per sample is much faster than one search over ten years."""
    d = pd.Timestamp(date)
    window = f"{(d - timedelta(days=max_gap)).date()}/{(d + timedelta(days=max_gap)).date()}"
    items = catalog().search(collections=["sentinel-2-l2a"], bbox=list(aoi_bounds_ll),
                             datetime=window).item_collection()
    return [it for it in items if coverage(it, aoi_bounds_ll) >= min_coverage]


def baseline_offset(item) -> int:
    b = item.properties.get("s2:processing_baseline")
    return 1000 if b is not None and float(b) >= 4.0 else 0


def _load(item, bands, aoi_bounds_ll):
    return odc.stac.load([item], bands=bands, bbox=aoi_bounds_ll, crs=CRS, resolution=RES_M,
                         resampling={"SCL": "nearest", "*": "average"}, pool=len(bands)).isel(time=0)


def water_features(item, aoi_utm, aoi_bounds_ll):
    """Load one image over the AOI and return the water-pixel features (or the reason it failed).
    Step 1 reads only the scene classification (about 0.1 MB) and skips the image if it cannot
    have enough water pixels; step 2 reads the four reflectance bands (about 0.8 MB each)."""
    signed = pc.sign(item)
    scl_ds = _load(signed, ["SCL"], aoi_bounds_ll)
    xs, ys = np.meshgrid(scl_ds.x.values, scl_ds.y.values)
    in_aoi = shapely.contains_xy(aoi_utm, xs, ys)
    scl = scl_ds["SCL"].values
    clear = in_aoi & ~np.isin(scl, [0, 1, 3, 8, 9, 10])  # not nodata, saturated, shadow, cloud, cirrus
    info = {"item_id": item.id, "n_clear_px": int(clear.sum()), "n_aoi_px": int(in_aoi.sum()),
            "processing_baseline": item.properties.get("s2:processing_baseline")}
    if binary_erosion(in_aoi & (scl == 6), iterations=2).sum() < MIN_WATER_PX:
        info["n_water_px"] = 0
        return None, info

    ds = _load(signed, BANDS, aoi_bounds_ll)
    dn = {b: ds[b].values.astype("float64") for b in BANDS}
    off = baseline_offset(item)
    refl = {b: (v - off) / 10000.0 for b, v in dn.items()}
    with np.errstate(divide="ignore", invalid="ignore"):
        mndwi = (refl["B03"] - refl["B11"]) / (refl["B03"] + refl["B11"])
    water = in_aoi & (dn["B03"] > 0) & (scl == 6) & (mndwi > 0)
    clean = binary_erosion(water, iterations=2)
    n = int(clean.sum())
    info.update({"n_water_px": n, "offset": off})
    if n < MIN_WATER_PX:
        return None, info
    med = {b: float(np.median(refl[b][clean])) for b in BANDS}
    f = dict(med)
    f["NDCI"] = (med["B05"] - med["B04"]) / (med["B05"] + med["B04"])
    f["NDTI"] = (med["B04"] - med["B03"]) / (med["B04"] + med["B03"])
    f["MNDWI"] = float(np.median(mndwi[clean]))
    f["water_frac"] = float(water.sum() / clear.sum()) if clear.sum() else np.nan
    return f, info


def features_for_sample(reservoir, date, aoi_utm, aoi_bounds_ll, cache: Path, max_gap=MAX_GAP_DAYS,
                        cache_only=False):
    """Closest image within +-max_gap days that has enough clean water pixels (cached per sample).
    cache_only=True never downloads: it returns status 'not extracted yet' for missing samples."""
    date = pd.Timestamp(date)
    f = cache / f"{reservoir.replace(' ', '_')}_{date.date()}_gap{max_gap}.json"
    if f.exists():
        return json.loads(f.read_text())
    if cache_only:
        return {"status": "not extracted yet"}
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
            cands.append((gap, -round(coverage(it, aoi_bounds_ll), 2), it.properties.get("eo:cloud_cover", 100), it))
    cands.sort(key=lambda c: c[:3])  # closest date, then fullest coverage, then least cloudy tile
    cands = [(c[0], c[2], c[3]) for c in cands]
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


def latest_clear(reservoir, aoi_utm, aoi_bounds_ll, start, end, cache: Path):
    """Most recent image between start and end with enough clean water pixels (for the live map)."""
    f = cache / f"latest_{reservoir.replace(' ', '_')}_{start}_{end}.json"
    if f.exists():
        return json.loads(f.read_text())
    items = catalog().search(collections=["sentinel-2-l2a"], bbox=list(aoi_bounds_ll),
                             datetime=f"{start}/{end}").item_collection()
    items = sorted([it for it in items if coverage(it, aoi_bounds_ll) >= 0.5],
                   key=lambda it: (it.datetime, coverage(it, aoi_bounds_ll)), reverse=True)
    out = {"status": "no clear image in window"}
    for it in items:
        feats, info = water_features(it, aoi_utm, aoi_bounds_ll)
        if feats is not None:
            out = {**feats, **info, "img_date": str(pd.Timestamp(it.datetime).date()), "status": "ok"}
            break
    f.write_text(json.dumps(out))
    return out


def rgb_thumbnail(item_id, aoi_bounds_ll, size=200, pad_deg=0.005):
    """True-colour thumbnail (Sentinel-2 'visual' asset, 8-bit) around the AOI, for failure analysis."""
    import rasterio
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds

    item = catalog().get_collection("sentinel-2-l2a").get_item(item_id)
    href = pc.sign(item).assets["visual"].href
    w, s, e, n = aoi_bounds_ll
    with rasterio.open(href) as src:
        b = transform_bounds("EPSG:4326", src.crs, w - pad_deg, s - pad_deg, e + pad_deg, n + pad_deg)
        win = from_bounds(*b, transform=src.transform)
        arr = src.read([1, 2, 3], window=win, out_shape=(3, size, size), boundless=True, fill_value=0)
    return arr.transpose(1, 2, 0)
