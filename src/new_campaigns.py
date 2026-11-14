"""Second, untouched test set: lab samples that COGERH published in its online database after the
last PDF report (campaigns May/2025 to Aug/2026). No model, threshold or choice ever saw them.

Jaguaribe-system reservoirs only, samples with a cyanobacteria count. These counts cannot be
cross-checked against a PDF (none is published yet); we drop values that look like the database's
thousands-separator slip (below 1,000 with decimals), as in notebook 05.

Usage: python new_campaigns.py <repo_root>   -> data/processed/new_campaign_samples.csv
"""
import sys
from pathlib import Path

import geopandas as gpd

FIRST_NEW_CAMPAIGN = "2025-05"  # the last PDF report is Feb/2025


def build(root: Path):
    from fetch_hidro import load_db_records

    db = load_db_records(root)
    db = db[db["cyano_db"].notna()].sort_values("date_db")
    res = gpd.read_file(root / "data" / "processed" / "reservoirs.geojson")
    db = db[db["reservoir"].isin(res.loc[res["jaguaribe_system"], "reservoir"])].copy()
    # the previous lab result of the same reservoir (what the technician knows), from the database too
    g = db.groupby("reservoir")
    db["prev_cyano"], db["prev_date"] = g["cyano_db"].shift(), g["date_db"].shift()
    new = db[db["campaign"] >= FIRST_NEW_CAMPAIGN].copy()
    slip = (new["cyano_db"] < 1000) & (new["cyano_db"] % 1 != 0)
    print(f"{len(new)} samples with a count, {int(slip.sum())} dropped as likely separator slips")
    new = new[~slip].rename(columns={"date_db": "date", "cyano_db": "cyano", "chla_db": "chla"})
    return new[["reservoir", "campaign", "date", "cyano", "chla", "prev_cyano", "prev_date"]]


if __name__ == "__main__":
    root = Path(sys.argv[1])
    sys.path.insert(0, str(root / "src"))
    out = build(root)
    out.to_csv(root / "data" / "processed" / "new_campaign_samples.csv", index=False, date_format="%Y-%m-%d")
    print(out.groupby("campaign").size().to_string())
