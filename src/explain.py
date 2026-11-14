"""Plain-language reasons for one prediction.

For logistic regression, each feature's contribution to the log-odds is
    coefficient x standardized value,
so the biggest contributions are the reasons. For LightGBM we use SHAP values the same way.

Inputs that measure almost the same thing (the two temperature windows, the two rain windows, the
month and the rainy-season flag) are added together first, because a model can split one effect
between correlated inputs with opposite signs. The phrase depends on whether the value is above or
below the training average; the arrow is the sign of the contribution (up raises risk, down lowers it).
"""
from __future__ import annotations

import pandas as pd

PHRASES = {
    "NDCI": ("green water (chlorophyll index {v:.3f})", "little chlorophyll seen (index {v:.3f})"),
    "NDTI": ("turbid water (turbidity index {v:.2f})", "clear water (turbidity index {v:.2f})"),
    "MNDWI": ("strong water signal (MNDWI {v:.2f})", "weak water signal (MNDWI {v:.2f})"),
    "water_frac": ("{v:.0%} of the area near the sampling point is water",
                   "only {v:.0%} of the area near the sampling point is water"),
    "wind_7d": ("windy week ({v:.1f} m/s)", "calm week ({v:.1f} m/s)"),
    "sw_7d": ("strong sunlight ({v:.1f} MJ/m²/day)", "weak sunlight ({v:.1f} MJ/m²/day)"),
    "volume_pct": ("reservoir {v:.0f}% full", "low volume ({v:.0f}% of capacity)"),
    "volume_change": ("volume changed {v:+.0f} points in 3 months", "volume changed {v:+.0f} points in 3 months"),
}

# group name -> (features added together, feature that picks the phrase, (phrase if high, phrase if low))
GROUPS = {
    "heat": (["tmax_7d", "tmax_30d"], "tmax_30d",
             ("hot last 30 days (max {tmax_30d:.1f} °C; last week {tmax_7d:.1f} °C)",
              "mild last 30 days (max {tmax_30d:.1f} °C; last week {tmax_7d:.1f} °C)")),
    "rain": (["rain_30d", "rain_90d"], "rain_90d",
             ("wet last 90 days ({rain_90d:.0f} mm; {rain_30d:.0f} mm in the last 30)",
              "dry last 90 days ({rain_90d:.0f} mm; {rain_30d:.0f} mm in the last 30)")),
    "season": (["month_sin", "month_cos", "rainy_season"], "rainy_season",
               ("time of year: rainy season", "time of year: dry season")),
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


def reasons(bundle, X: pd.DataFrame, train_means: pd.Series, k=3) -> list[list[str]]:
    """Top-k contributions per row (related inputs added together), as short phrases with an arrow."""
    c = contributions(bundle, X)
    grouped = {f for fs, _, _ in GROUPS.values() for f in fs}
    units = {f: [f] for f in c.columns if f not in grouped}
    units.update({g: fs for g, (fs, _, _) in GROUPS.items() if set(fs) <= set(c.columns)})
    out = []
    for i in X.index:
        total = {u: c.loc[i, fs].sum() for u, fs in units.items()}
        parts = []
        for u in sorted(total, key=lambda u: -abs(total[u])):
            vals = X.loc[i, units[u]]
            if vals.isna().any():
                continue
            if u in GROUPS:
                _, key, (high, low) = GROUPS[u]
                text = (high if X.at[i, key] >= train_means[key] else low).format(**vals.to_dict())
            else:
                high, low = PHRASES[u]
                text = (high if X.at[i, u] >= train_means[u] else low).format(v=X.at[i, u])
            parts.append(("↑ " if total[u] > 0 else "↓ ") + text)
            if len(parts) == k:
                break
        out.append(parts)
    return out
