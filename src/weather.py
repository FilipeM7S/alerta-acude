"""Daily weather from NASA POWER and window features before each lab sample.

Source: NASA POWER daily point API (https://power.larc.nasa.gov), no key needed.
We use it instead of Open-Meteo because Open-Meteo's free tier counts a multi-year request as
hundreds of calls (10 years x 143 reservoirs would exceed the daily limit).

POWER's meteorology comes from MERRA-2 on a 0.5 x 0.625 degree grid (~50 km), so reservoirs in
the same grid cell share one series and one request.

Features, from the days BEFORE the sample date (the sample day itself is excluded):
  tmax_7d, tmax_30d  mean daily maximum temperature (C)
  rain_30d, rain_90d total rainfall (mm)
  wind_7d            mean wind speed at 2 m (m/s)
  sw_7d              mean daily shortwave radiation (MJ/m2/day)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMS = {"T2M_MAX": "tmax", "PRECTOTCORR": "rain", "WS2M": "wind", "ALLSKY_SFC_SW_DWN": "sw"}
START, END = "20150901", "20261113"


def grid_cell(lat, lon):
    """Nearest MERRA-2 grid centre (0.5 deg latitude, 0.625 deg longitude)."""
    return round(round(lat / 0.5) * 0.5, 3), round(round(lon / 0.625) * 0.625, 3)


def fetch_cell(lat, lon, cache: Path, pause=1.0) -> pd.DataFrame:
    cache.mkdir(parents=True, exist_ok=True)
    f = cache / f"power_{lat:+.3f}_{lon:+.3f}_{START}_{END}.json"
    if not f.exists():
        r = requests.get(URL, params={"parameters": ",".join(PARAMS), "community": "AG", "latitude": lat,
                                      "longitude": lon, "start": START, "end": END, "format": "JSON"},
                         headers={"User-Agent": "alerta-acude-research/0.1"}, timeout=180)
        r.raise_for_status()
        f.write_text(r.text, encoding="utf-8")
        time.sleep(pause)
    p = json.loads(f.read_text(encoding="utf-8"))["properties"]["parameter"]
    df = pd.DataFrame(p).rename(columns=PARAMS)
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    return df.replace(-999.0, np.nan)


def window_features(daily: pd.DataFrame, date, min_coverage=0.8) -> dict:
    """Weather features over the days before `date`; NaN if too many days are missing."""
    d = pd.Timestamp(date).normalize()

    def win(col, days, how):
        s = daily.loc[d - pd.Timedelta(days=days): d - pd.Timedelta(days=1), col]
        if len(s) < days or s.notna().mean() < min_coverage:
            return np.nan
        return float(s.mean() * days) if how == "sum" else float(s.mean())

    return {"tmax_7d": win("tmax", 7, "mean"), "tmax_30d": win("tmax", 30, "mean"),
            "rain_30d": win("rain", 30, "sum"), "rain_90d": win("rain", 90, "sum"),
            "wind_7d": win("wind", 7, "mean"), "sw_7d": win("sw", 7, "mean")}
