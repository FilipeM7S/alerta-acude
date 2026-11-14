"""Plain-language reasons for one prediction.

For logistic regression, each feature's contribution to the log-odds is
    coefficient x standardized value,
so the biggest contributions are the reasons. For LightGBM we use SHAP values the same way.
The phrase depends on whether the value is above or below the training average.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PHRASES = {
    "NDCI": ("green water (chlorophyll index {v:.3f})", "little chlorophyll seen (index {v:.3f})"),
    "NDTI": ("turbid water (turbidity index {v:.2f})", "clear water (turbidity index {v:.2f})"),
    "MNDWI": ("strong water signal (MNDWI {v:.2f})", "weak water signal (MNDWI {v:.2f})"),
    "water_frac": ("{v:.0%} of the area near the dam is water", "only {v:.0%} of the area near the dam is water"),
    "tmax_7d": ("hot week (max {v:.1f} °C)", "mild week (max {v:.1f} °C)"),
    "tmax_30d": ("hot month (max {v:.1f} °C)", "mild month (max {v:.1f} °C)"),
    "rain_30d": ("rain in the last 30 days ({v:.0f} mm)", "dry last 30 days ({v:.0f} mm)"),
    "rain_90d": ("rain in the last 90 days ({v:.0f} mm)", "dry last 90 days ({v:.0f} mm)"),
    "wind_7d": ("windy week ({v:.1f} m/s)", "calm week ({v:.1f} m/s)"),
    "sw_7d": ("strong sunlight ({v:.1f} MJ/m²/day)", "weak sunlight ({v:.1f} MJ/m²/day)"),
    "volume_pct": ("reservoir {v:.0f}% full", "low volume ({v:.0f}% of capacity)"),
    "volume_change": ("volume rose {v:+.0f} points in 3 months", "volume fell {v:+.0f} points in 3 months"),
    "month_sin": ("time of year", "time of year"),
    "month_cos": ("time of year", "time of year"),
    "rainy_season": ("rainy season", "dry season"),
}


def contributions(bundle, X: pd.DataFrame) -> pd.DataFrame:
    """Per-feature contribution to the log-odds, same shape as X."""
    model, feats = bundle["model"], bundle["features"]
    if bundle["name"].startswith("Logistic"):
        imp, scaler, lr = model[0], model[1], model[-1]
        z = scaler.transform(imp.transform(X[feats]))
        return pd.DataFrame(z * lr.coef_[0], index=X.index, columns=feats)
    import shap
    sv = shap.TreeExplainer(model)(X[feats]).values
    return pd.DataFrame(sv, index=X.index, columns=feats)


def reasons(bundle, X: pd.DataFrame, train_means: pd.Series, k=3) -> list[str]:
    """Top-k contributions per row, as short phrases with an arrow (↑ raises risk, ↓ lowers it)."""
    c = contributions(bundle, X)
    out = []
    for i, row in c.iterrows():
        parts, seen = [], set()
        for f in row.abs().sort_values(ascending=False).index:
            high, low = PHRASES[f]
            v = X.at[i, f]
            if pd.isna(v):
                continue
            text = (high if v >= train_means[f] else low).format(v=v)
            if text in seen:
                continue
            seen.add(text)
            parts.append(("↑ " if row[f] > 0 else "↓ ") + text)
            if len(parts) == k:
                break
        out.append(parts)
    return out
