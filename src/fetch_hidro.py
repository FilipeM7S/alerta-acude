"""Fetch the reservoir list and per-reservoir lab history from the Portal Hidrológico do Ceará.

- Reservoir list (id, name, lat, lon): the reservoir dropdown on
  https://www.hidro.ce.gov.br/acude/eutrofizacao (saved as data/raw/hidro/eutrofizacao.html).
- Per-campaign records (with hydrographic region): the same page with ?campanha=MMM/YYYY.
- Lab history per reservoir: the JSON the same page loads,
  https://www.hidro.ce.gov.br/acude/eutrofizacao/dadosanuais?id=<id>

The site has no robots.txt. Requests go one at a time with a pause, and every response is
cached in data/raw/hidro/dadosanuais/ so nothing is downloaded twice.

Usage: python fetch_hidro.py <repo_root>
"""
import csv
import html
import json
import re
import sys
import time
from pathlib import Path

import requests

BASE = "https://www.hidro.ce.gov.br"
OPTION_RE = re.compile(
    r'<option value="([^"]*)" data-id="(\d+)"\s+data-lat="([-\d.]+)" data-lon="([-\d.]+)">\s*([^<]+?)\s*</option>')


def reservoir_list(page_html: str):
    rows = []
    for value, rid, lat, lon, label in OPTION_RE.findall(page_html):
        rows.append({"hidro_id": int(rid), "name": html.unescape(label).strip(),
                     "lat": float(lat), "lon": float(lon)})
    return rows


CAMPAIGN_OPT_RE = re.compile(r'<option value="([A-Z]{3}/\d{4})"')
EMBEDDED_RE = re.compile(r"var pontos_eutrofizados = (\[.*?\]);?\s*\n", re.S)
MONTHS = {"FEV": 2, "MAI": 5, "AGO": 8, "NOV": 11}


def fetch_campaign_pages(root: Path, session, pause=1.5):
    """Each campaign page embeds every reservoir sampled in it (id, name, point, lat/lon,
    hydrographic region, lab values). We keep only that embedded JSON, one file per campaign."""
    raw = root / "data" / "raw" / "hidro"
    page = (raw / "eutrofizacao.html").read_text(encoding="utf-8")
    campaigns = CAMPAIGN_OPT_RE.findall(page)
    out = raw / "campanhas"
    out.mkdir(exist_ok=True)
    print(f"{len(campaigns)} campaigns in the selector")
    for c in campaigns:
        mon, year = c.split("/")
        target = out / f"{year}_{MONTHS[mon]:02d}.json"
        if target.exists():
            continue
        resp = session.get(f"{BASE}/acude/eutrofizacao", params={"campanha": c}, timeout=60)
        resp.raise_for_status()
        m = EMBEDDED_RE.search(resp.text)
        data = json.loads(m.group(1)) if m else []
        target.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
        print(f"{c}  {len(data):>3} reservoirs", flush=True)
        time.sleep(pause)


def main(root: Path):
    raw = root / "data" / "raw" / "hidro"
    page = (raw / "eutrofizacao.html").read_text(encoding="utf-8")
    rows = reservoir_list(page)
    ids = {r["hidro_id"] for r in rows}
    print(f"{len(rows)} reservoirs in the dropdown ({len(ids)} unique ids)")
    with (raw / "reservoir_list.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["hidro_id", "name", "lat", "lon"])
        w.writeheader()
        w.writerows(rows)

    out = raw / "dadosanuais"
    out.mkdir(exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "alerta-acude-research/0.1 (student hackathon project)"
    for r in rows:
        target = out / f"{r['hidro_id']}.json"
        if target.exists():
            continue
        resp = session.get(f"{BASE}/acude/eutrofizacao/dadosanuais", params={"id": r["hidro_id"]}, timeout=60)
        resp.raise_for_status()
        data = resp.json() or []  # some ids return null (no history)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
        print(f"{r['hidro_id']:>4} {r['name']:<32} {len(data):>3} records", flush=True)
        time.sleep(1.5)
    fetch_campaign_pages(root, session)
    print("done")


if __name__ == "__main__":
    main(Path(sys.argv[1]))


def load_db_records(root: Path):
    """All saved lab records from the portal database, one row per reservoir and campaign.
    Reservoirs with two sampling points in the same campaign are left out (ambiguous)."""
    import pandas as pd
    from common import normalize_name

    raw = root / "data" / "raw" / "hidro"
    names = pd.read_csv(raw / "reservoir_list.csv")
    rows = []
    for f in (raw / "dadosanuais").glob("*.json"):
        rows += json.loads(f.read_text(encoding="utf-8")) or []
    db = pd.DataFrame(rows)
    db["campaign"] = db["campanha"].map(lambda c: f"{c[4:]}-{MONTHS[c[:3]]:02d}")
    db = db.merge(names[["hidro_id", "name"]], left_on="reservatorio", right_on="hidro_id")
    db["reservoir"] = db["name"].map(normalize_name)
    db["date_db"] = pd.to_datetime(db["data"])
    db = db.rename(columns={"cianobacterias": "cyano_db", "clorofila": "chla_db"})
    db = db[~db.duplicated(["reservoir", "campaign"], keep=False)]
    return db[["reservoir", "campaign", "date_db", "cyano_db", "chla_db", "ponto"]]
