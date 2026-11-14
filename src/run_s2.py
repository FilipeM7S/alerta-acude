"""Extract Sentinel-2 water features for every usable lab sample (resumable: results are cached
per sample in data/processed/s2_cache/). Newest campaigns first.

Usage: python run_s2.py <repo_root> [workers]
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / "src"))
import geopandas as gpd
import pandas as pd

from satellite import CRS, features_for_sample

workers = int(sys.argv[2]) if len(sys.argv) > 2 else 16
res = gpd.read_file(root / "data/processed/reservoirs.geojson").set_index("reservoir")
aoi_utm = res.to_crs(CRS).geometry
s = pd.read_csv(root / "data/processed/samples.csv", parse_dates=["date"])
todo = s[s["usable"] & s["reservoir"].isin(res.index)][["reservoir", "date", "campaign"]].drop_duplicates(["reservoir", "date"])
todo = todo.sort_values(["campaign", "reservoir"], ascending=[False, True])
cache = root / "data/processed/s2_cache"
cache.mkdir(parents=True, exist_ok=True)
print(f"{len(todo)} samples, {workers} workers", flush=True)


def job(r):
    return features_for_sample(r.reservoir, r.date, aoi_utm[r.reservoir], res.geometry[r.reservoir].bounds, cache)


t0, done, ok = time.time(), 0, 0
with ThreadPoolExecutor(max_workers=workers) as ex:
    futures = {ex.submit(job, r): r for r in todo.itertuples()}
    for fut in as_completed(futures):
        done += 1
        try:
            ok += fut.result().get("status") == "ok"
        except Exception as e:
            r = futures[fut]
            print(f"ERROR {r.reservoir} {r.date.date()}: {type(e).__name__}: {e}"[:200], flush=True)
        if done % 100 == 0:
            el = time.time() - t0
            print(f"{done}/{len(todo)}  ok={ok}  {el/60:.1f} min  eta {el/done*(len(todo)-done)/60:.0f} min", flush=True)
print(f"finished {done} samples, ok={ok}, {(time.time()-t0)/60:.1f} min", flush=True)
