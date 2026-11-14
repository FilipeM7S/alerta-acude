"""Small helpers for notebook 04: time split, metrics, threshold choice."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, balanced_accuracy_score, confusion_matrix,
                             f1_score, precision_score, recall_score)

SATELLITE = ["NDCI", "NDTI", "MNDWI", "water_frac"]
WEATHER = ["tmax_7d", "tmax_30d", "rain_30d", "rain_90d", "wind_7d", "sw_7d"]
WATER = ["volume_pct", "volume_change"]
SEASON = ["month_sin", "month_cos", "rainy_season"]
FEATURES = SATELLITE + WEATHER + WATER + SEASON


def time_split(df: pd.DataFrame, train_frac=0.6, val_frac=0.2):
    """Split by campaign in time order: oldest campaigns train, next validate, newest test."""
    camps = sorted(df["campaign"].unique())
    n_tr = round(len(camps) * train_frac)
    n_va = round(len(camps) * val_frac)
    split = {c: "train" if i < n_tr else "val" if i < n_tr + n_va else "test" for i, c in enumerate(camps)}
    return df["campaign"].map(split)


def metrics(y, pred, score=None) -> dict:
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    out = {"n": len(y), "positives": int(np.sum(y)), "recall": recall_score(y, pred, zero_division=0),
           "precision": precision_score(y, pred, zero_division=0), "F1": f1_score(y, pred, zero_division=0),
           "balanced_acc": balanced_accuracy_score(y, pred),
           "missed_blooms (FN)": int(fn), "false_alarms (FP)": int(fp), "TP": int(tp), "TN": int(tn)}
    out["PR_AUC"] = average_precision_score(y, score) if score is not None else np.nan
    return out


def threshold_for_recall(y, score, min_recall=0.80):
    """Highest threshold that still catches >= min_recall of the blooms. Raising the threshold
    removes alarms, so the highest one that keeps the recall gives the fewest false alarms."""
    for t in np.unique(score)[::-1]:
        if recall_score(y, (score >= t).astype(int), zero_division=0) >= min_recall:
            return float(t)
    return float(np.min(score))


def best_f1_threshold(y, score):
    ts = np.unique(score)
    f1s = [f1_score(y, (score >= t).astype(int), zero_division=0) for t in ts]
    return float(ts[int(np.argmax(f1s))])
