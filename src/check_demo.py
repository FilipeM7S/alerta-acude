"""Check that the demo interface (outputs/demo.html + demo_data.json) shows exactly what the map shows.

1. For every reservoir, compare what risk_map.html's popup says (priority, band, score, image date, volume,
   reasons, low-confidence note, last lab result, Castanhão context) with demo_data.json.
2. Check the KPI counts in demo_data.json against counts recomputed from its reservoir list and from the map.
3. Check every number on the Evidence and Limits tabs against the results tables and notebook outputs.

Usage: python src/check_demo.py   (from the repo root; exits 1 on any mismatch)
"""
import html
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
problems = []


def check(ok, msg):
    if not ok:
        problems.append(msg)


# ---------------------------------------------------------------- 1. map popups vs demo data
data = json.loads((OUT / "demo_data.json").read_text(encoding="utf-8"))
page = (OUT / "risk_map.html").read_text(encoding="utf-8")
popups = re.findall(r'= \$\(`<div id="html_\w+" style="[^"]*">(.*?)</div>`\)\[0\];', page, re.S)
POP = re.compile(
    r"<b>(?P<name>.*?)</b> \((?P<basin>.*?)\)<br><b>Priority (?P<rank>\d+) of (?P<n>\d+)</b> · "
    r"<span style='color:#\w+'><b>(?P<band>.*?)</b></span> <span[^>]*>\(score (?P<score>[\d.]+), not a probability\)</span><br>"
    r"Image: (?P<img>[\d-]+) · Volume: (?P<vol>-?\d+)%<br>(?P<reasons>.*?)<br><i>Last lab result: (?P<lab>.*?)</i>"
    r"(?:<br><b>(?P<ctx>.*?)</b>)?(?:<br><span style='color:#555'>◌ Low confidence: (?P<lc>.*?)\. Check with the last lab result\.</span>)?$",
    re.S)
seen = {}
for p in popups:
    m = POP.match(p)
    check(m is not None, f"popup not parsed: {p[:80]}")
    if m:
        seen[html.unescape(m["name"])] = m
recs = {r["name"]: r for r in data["reservoirs"]}
check(set(seen) == set(recs), f"reservoir sets differ: map-only {set(seen) - set(recs)}, data-only {set(recs) - set(seen)}")

fields = 0
for name, r in recs.items():
    m = seen.get(name)
    if m is None:
        continue
    lab = (f"{r['last_lab_cyano']:,.0f} cells/mL on {r['last_lab_date']} {r['last_lab_note']}"
           if r["last_lab_cyano"] is not None else "none")
    pairs = {
        "basin": (m["basin"], r["basin"]),
        "priority": (int(m["rank"]), r["rank"]),
        "of N": (int(m["n"]), data["counts"]["imaged"]),
        "band": (m["band"], r["band"]),
        "score": (m["score"], f"{r['score']:.2f}"),
        "image date": (m["img"], r["img_date"]),
        "volume": (m["vol"], f"{r['volume_pct']:.0f}"),
        "reasons": (m["reasons"].split("<br>"), r["reasons"]),
        "low confidence": (m["lc"] is not None, r["low_confidence"]),
        "confidence note": (m["lc"] or "", r["confidence_note"]),
        "last lab": (m["lab"], lab),
        "context": (m["ctx"] or "", r["context"]),
    }
    for f, (a, b) in pairs.items():
        fields += 1
        check(a == b, f"{name}: {f} differs (map {a!r} vs demo {b!r})")

# The low-confidence markers on the map are the dashed ones.
dashed = len(re.findall(r'"dashArray": "3 3"', page))
check(dashed == data["counts"]["low_confidence"], f"dashed markers on map {dashed} vs low_confidence {data['counts']['low_confidence']}")

# ---------------------------------------------------------------- 2. KPI counts
rs = data["reservoirs"]
kpi = {"imaged": len(rs), "alert": sum(r["band"] == "Alert" for r in rs), "lower": sum(r["band"] == "Lower risk" for r in rs),
       "low_confidence": sum(r["low_confidence"] for r in rs), "no_image": len(data["no_image"])}
for k, v in kpi.items():
    check(data["counts"][k] == v, f"KPI {k}: stored {data['counts'][k]} vs recomputed {v}")
map_bands = pd.Series([m["band"] for m in seen.values()]).value_counts().to_dict()
check(map_bands.get("Alert") == kpi["alert"] and map_bands.get("Lower risk") == kpi["lower"], f"map band counts {map_bands} vs KPIs {kpi}")
check(len(re.findall(r"no clear image in the last 30 days", page)) >= kpi["no_image"], "no-image count differs from the map")
check(sorted(r["rank"] for r in rs) == list(range(1, len(rs) + 1)), "ranks are not 1..N")

# ---------------------------------------------------------------- 3. Evidence / Limits numbers
demo = (OUT / "demo.html").read_text(encoding="utf-8")
t1 = pd.read_csv(OUT / "test_results.csv", index_col=0)
t2 = pd.read_csv(OUT / "test2_results.csv", index_col=0)


def row(t, name):
    r = t.loc[name]
    return f"<td>{r['PR_AUC']:.3f}</td><td>{int(r['missed_blooms (FN)'])}</td><td>{int(r['false_alarms (FP)'])}</td>"


expect = {
    "Test 1 persistence row": "<td>Last lab result (persistence)</td>" + row(t1, "Persistence (last lab result)"),
    "Test 1 model A row": "<td>Satellite model A</td>" + row(t1, "Logistic regression"),
    "Test 2 persistence row": "<td>Last lab result (persistence)</td>" + row(t2, "Persistence (last lab result)"),
    "Test 2 model B row": "<td>Model B, used in this map</td>" + row(t2, "B: satellite + stored water, 6 inputs"),
    "Test 2 model A row": "<td>Model A</td>" + row(t2, "A: logistic regression, 15 inputs"),
    "Test 1 chance": f"scores {t1.loc['Majority class (always bloom)', 'PR_AUC']:.3f} here",
    "Test 2 chance": f"scores {t2.loc['Majority class (always bloom)', 'PR_AUC']:.3f}.",
    "Test 1 samples": f"{int(t1.loc['Logistic regression', 'n'])} samples",
    "Test 2 samples": f"{int(t2.loc['Persistence (last lab result)', 'n'])} samples",
}
for what, s in expect.items():
    check(s in demo, f"Evidence: {what} not found as {s!r}")


def nb_text(name):
    nb = json.loads((ROOT / "notebooks" / name).read_text(encoding="utf-8"))
    return "".join("".join(o.get("text", "")) + "".join(o.get("data", {}).get("text/plain", ""))
                   for c in nb["cells"] if c["cell_type"] == "code" for o in c.get("outputs", []))


nb04, nb04b = nb_text("04_model.ipynb"), nb_text("04b_second_test.ipynb")
check("PR-AUC(Logistic regression) - PR-AUC(persistence): mean +0.013, 95% interval [-0.030, +0.056]" in nb04
      and "−0.030 to +0.056" in demo, "Test 1 bootstrap interval")
check("PR-AUC(B) - PR-AUC(persistence): mean -0.004, 95% interval [-0.026, +0.020]" in nb04b
      and "−0.026 to +0.020" in demo, "Test 2 bootstrap interval")
dry = re.search(r"dry \(Aug, Nov\) A\s+\d+\s+\d+\s+[\d.]+\s+(\d+).*?\n\s+B\s+\d+\s+\d+\s+[\d.]+\s+(\d+).*?\n\s+persistence\s+\d+\s+\d+\s+[\d.]+\s+(\d+)", nb04b)
check(dry is not None, "dry-season table not found in notebook 04b")
if dry:
    a, b, p = dry.groups()
    for label, v in [("Last lab result", p), ("Model B (map)", b), ("Model A", a)]:
        check(re.search(rf'<span class="bl">{re.escape(label)}</span><span class="bt"><i [^>]*></i><b>{v}</b>', demo) is not None,
              f"dry-season bar {label} != {v}")
    check(f"missed {b} dry-season blooms, against {p} for the last lab result" in demo, "Limits dry-season sentence")
readme = (ROOT / "README.md").read_text(encoding="utf-8")
for s in ["3,679 lab samples from 156 reservoirs", "99.6% of counts agree", "614 samples have a clear image",
          "Spearman 0.81", "(0.41)", "191,134 cells/mL but only 12.85 µg/L", "NDCI dominates (+1.39)", "were blooms 77% of the time",
          "commit/50b694b"]:
    check(s in readme, f"README no longer says {s!r}")

print(f"{len(recs)} reservoirs, {fields} fields compared against risk_map.html popups; "
      f"KPIs {kpi}; {len(expect) + 4} evidence checks")
if problems:
    print(f"{len(problems)} MISMATCHES:")
    print("\n".join(" - " + p for p in problems))
    sys.exit(1)
print("0 mismatches")
