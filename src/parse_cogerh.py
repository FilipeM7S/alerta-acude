"""Parse COGERH trophic-state (IET) PDF reports into one row per reservoir sample.

Table 3 gives the lab results (date, N, P, chlorophyll-a, cyanobacteria, transparency).
Table 2 gives the stored volume (%) and the trophic class.

Values are read from the PDF text layer with pdfplumber. Each number is assigned to a
column by its horizontal position relative to the column header, so an empty cell never
shifts the other values. Rows that cannot be read unambiguously are logged, not guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pdfplumber

from common import normalize_name

MONTHS = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
          "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}

DATE_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{2}|\d{4})$")
DECIMAL_RE = re.compile(r"^\d+(,\d+)?$")
# Cell counts use '.' for thousands; 2022+ reports add a decimal part ("375.191,0").
# At most two decimals, so an ambiguous "56,680" (Cocó, Nov/2020) is rejected, not read as 56.68.
CELLS_RE = re.compile(r"^\d{1,3}(\.\d{3})*(,\d{1,2})?$")
PERCENT_RE = re.compile(r"^(\d+(,\d+)?)%?$")  # 2022+ reports drop the '%'
CLASS_RE = re.compile(r"^(ultraoligo|oligo|meso|eu|supereu|hipereu)tr[oó]fica$", re.I)
# "Campanha Nov/2020" (2016-2021) or "(camp. fev/2022)" / "(campanha ago/2024)" (2022+)
CAMPAIGN_RE = re.compile(r"(?:[Cc]ampanha|camp\.)\s+([A-Za-z]{3})/(\d{4})")

COL_TOL = 20  # max distance (pt) between a value's centre and its column centre
VALUE_COLS = ["n_total", "p_total", "chla", "cyano", "transparency"]


@dataclass
class ParseLog:
    rows: list = field(default_factory=list)

    def add(self, file, table, page, text, reason):
        self.rows.append({"file": file, "table": table, "page": page, "text": text, "reason": reason})

    def frame(self):
        return pd.DataFrame(self.rows, columns=["file", "table", "page", "text", "reason"])


def group_lines(words, tol=3.0):
    """Cluster words into text lines by their vertical position."""
    lines = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(w["top"] - lines[-1][0]["top"]) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(ln, key=lambda w: w["x0"]) for ln in lines]


def centre(ws):
    return (min(w["x0"] for w in ws) + max(w["x1"] for w in ws)) / 2


def line_text(ws):
    return " ".join(w["text"] for w in ws)


def name_column_right(lines, header_idx):
    """Right edge of the 'Reservatório' column header; a table row must start left of it."""
    for ln in lines[max(0, header_idx - 3):header_idx + 3]:
        for w in ln:
            if w["text"] == "Reservatório":
                return w["x1"]
    raise ValueError("no 'Reservatório' header found near the table header")


def merge_less_than(words):
    """Join a detached '<' with the number that follows it ('<' '3,00' -> '<3,00')."""
    out, i = [], 0
    while i < len(words):
        w = words[i]
        if w["text"] == "<" and i + 1 < len(words):
            nxt = words[i + 1]
            out.append({**nxt, "text": "<" + nxt["text"], "x0": w["x0"]})
            i += 2
        else:
            out.append(w)
            i += 1
    return out


def parse_decimal(tok):
    return float(tok.replace(",", ".")) if DECIMAL_RE.match(tok) else None


def parse_cells(tok):
    return float(tok.replace(".", "").replace(",", ".")) if CELLS_RE.match(tok) else None


def parse_date(tok):
    m = DATE_RE.match(tok)
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    y = 2000 + y if y < 100 else y
    try:
        return pd.Timestamp(year=y, month=mo, day=d)
    except ValueError:
        return None


def campaign_above(lines, header_idx):
    """Campaign month from the 'Parâmetros - Campanha Mmm/YYYY' line just above the
    Table 3 column header. (The table caption can be wrong: Nov/2020 says 'Ago/2020'.)"""
    for ln in reversed(lines[max(0, header_idx - 4):header_idx]):
        m = CAMPAIGN_RE.search(line_text(ln))
        if m and MONTHS.get(m.group(1).lower()):
            return f"{m.group(2)}-{MONTHS[m.group(1).lower()]:02d}"
    return None


# ---------------------------------------------------------------- Table 3

def table3_columns(lines):
    """Return (header_index, column centres) if this page holds a Table 3 header."""
    for i, ln in enumerate(lines):
        texts = [w["text"] for w in ln]
        cyano_word = next((t for t in texts if t.startswith("Cianobact")), None)  # singular in 2022+
        if "Clorofila-a" in texts and cyano_word and "Transparência" in texts:
            n_idx, p_idx = texts.index("N"), texts.index("P")
            cols = {
                "n_total": centre(ln[n_idx:n_idx + 2]),  # "N total" / "N Total"
                "p_total": centre(ln[p_idx:p_idx + 2]),
                "chla": centre([ln[texts.index("Clorofila-a")]]),
                "cyano": centre([ln[texts.index(cyano_word)]]),
                "transparency": centre([ln[texts.index("Transparência")]]),
            }
            # "Data" sits on the header line (2020), below it (2016-2021) or beside "Reservatório" (2022+).
            date_col, units_idx = None, i
            for j in range(i, min(i + 4, len(lines))):
                tj = [w["text"] for w in lines[j]]
                if "Data" in tj:
                    date_col = centre([lines[j][tj.index("Data")]])
                if j > i and any(t.startswith("(") for t in tj):
                    units_idx = j
            if date_col is None:
                raise ValueError("Table 3 header found but no 'Data' column")
            cols["date"] = date_col
            cols["campaign"] = campaign_above(lines, i)
            return units_idx, cols
    return None, None


def parse_table3(path: Path, log: ParseLog):
    rows, campaigns = [], []
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            lines = group_lines(page.extract_words())
            start, cols = table3_columns(lines)
            if cols is None:
                continue
            campaigns.append((pno, cols["campaign"]))
            name_limit = cols["date"] - 15
            row_left = name_column_right(lines, start)
            for ln in lines[start + 1:]:
                if ln[0]["x0"] > row_left:  # not a table row (page number, centred note)
                    continue
                text = line_text(ln)
                name_ws = [w for w in ln if w["x1"] <= name_limit]
                rest = [w for w in ln if w["x1"] > name_limit]
                name = line_text(name_ws)
                if not rest:
                    log.add(path.name, 3, pno, text, "no values (name only or note)")
                    continue
                date = parse_date(rest[0]["text"]) if abs(centre([rest[0]]) - cols["date"]) < COL_TOL else None
                if date is None:
                    if any(re.search(r"[A-Za-zÀ-ú]", w["text"]) for w in rest):
                        log.add(path.name, 3, pno, text, "status: " + line_text(rest))
                    else:
                        log.add(path.name, 3, pno, text, "no valid date")
                    continue
                rec = {"reservoir_raw": name, "date": date, "page": pno, "censored": ""}
                ok = True
                tokens = merge_less_than(rest[1:])
                for w in tokens:
                    c = centre([w])
                    col = min(VALUE_COLS, key=lambda k: abs(cols[k] - c))
                    if abs(cols[col] - c) > COL_TOL:
                        log.add(path.name, 3, pno, text, f"token '{w['text']}' not under any column")
                        ok = False
                        continue
                    if col in rec:
                        log.add(path.name, 3, pno, text, f"two tokens under column {col}")
                        ok = False
                        continue
                    if w["text"].startswith("<"):
                        # Below the lab's detection limit: keep the bound as text, value stays NaN.
                        rec[col] = None
                        bound = w["text"][1:].replace(",", ".")
                        rec["censored"] = (rec["censored"] + f" {col}<{bound}").strip()
                        continue
                    val = parse_cells(w["text"]) if col == "cyano" else parse_decimal(w["text"])
                    if val is None:
                        log.add(path.name, 3, pno, text, f"unreadable {col} value '{w['text']}' -> NaN")
                        continue
                    rec[col] = val
                if not ok:
                    continue
                missing = [k for k in VALUE_COLS if k not in rec]
                if missing:
                    log.add(path.name, 3, pno, text, "empty cells: " + ",".join(missing))
                rows.append(rec)
    # The campaign comes from the first Table 3 page. Continuation pages can carry a stale
    # header (May/2019 pages 15-16 say "Nov/2018" while their dates are Apr-May 2019); we log
    # those, and the date check in parse_report flags any row that really belongs elsewhere.
    if not campaigns or campaigns[0][1] is None:
        raise ValueError(f"{path.name}: no campaign found above the Table 3 header")
    campaign = campaigns[0][1]
    for pno, c in campaigns[1:]:
        if c != campaign:
            log.add(path.name, 3, pno, f"page header says {c}", f"campaign header differs from first page ({campaign})")
    df = pd.DataFrame(rows).reindex(columns=["reservoir_raw", "date", "page", "censored", *VALUE_COLS])
    df["campaign"] = campaign
    df["file"] = path.name
    return df


# ---------------------------------------------------------------- Table 2

def table2_layout(lines):
    for i, ln in enumerate(lines):
        texts = [w["text"] for w in ln]
        # First page says "Classe Trófica", continuation pages say "Estado Trófico".
        if texts.count("Volume") == 2 and (texts.count("Classe") == 2 or texts.count("Estado") == 2):
            vol = [w for w in ln if w["text"] == "Volume"]
            cls = [w for w in ln if w["text"] in ("Trófica", "Trófico")]
            boundary = (cls[0]["x1"] + vol[1]["x0"]) / 2
            return i, boundary, vol[0]["x0"] - 4
    return None, None, None


def parse_table2(path: Path, log: ParseLog):
    rows = []
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            lines = group_lines(page.extract_words())
            start, boundary, name_limit = table2_layout(lines)
            if start is None:
                continue
            row_left = name_column_right(lines, start)
            for ln in lines[start + 1:]:
                if ln[0]["x0"] > row_left:
                    continue
                text = line_text(ln)
                name = line_text([w for w in ln if w["x1"] <= name_limit])
                current = [w for w in ln if w["x0"] >= boundary]
                if not name or not current:
                    log.add(path.name, 2, pno, text, "no current-campaign cell")
                    continue
                vol = [PERCENT_RE.match(w["text"]) for w in current]
                vol = [float(m.group(1).replace(",", ".")) for m in vol if m]
                cls = [w["text"] for w in current if CLASS_RE.match(w["text"])]
                if len(vol) == 1:
                    rows.append({"reservoir_raw": name, "volume_pct": vol[0],
                                 "trophic_class": cls[0] if len(cls) == 1 else None})
                else:
                    log.add(path.name, 2, pno, text, "status: " + line_text(current))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- report

def parse_report(path: Path, log: ParseLog) -> pd.DataFrame:
    """One report -> samples with lab values and stored volume, joined on normalized name."""
    t3 = parse_table3(path, log)
    t2 = parse_table2(path, log)
    for t in (t3, t2):
        t["reservoir"] = t["reservoir_raw"].map(normalize_name)
    dup3 = t3[t3.duplicated("reservoir", keep=False)]
    for _, r in dup3.iterrows():
        log.add(path.name, 3, r["page"], r["reservoir_raw"], "duplicate reservoir in Table 3")
    t2 = t2.drop_duplicates("reservoir")
    df = t3.merge(t2[["reservoir", "volume_pct", "trophic_class"]], on="reservoir", how="left")
    for _, r in df[df["volume_pct"].isna()].iterrows():
        log.add(path.name, 2, None, r["reservoir_raw"], "no volume in Table 2 for this sample")
    # A count repeated exactly in another reservoir of the same campaign could be a copy error
    # or an artefact of how the lab counts; we cannot tell which. We keep the printed value,
    # flag it, and check later that results hold without these rows.
    big = df["cyano"] > 1000
    repeated = big & df.duplicated("cyano", keep=False)
    df["qc_flag"] = ""
    df.loc[repeated, "qc_flag"] = "cyano_repeated"
    for _, r in df[repeated].iterrows():
        log.add(path.name, 3, r["page"], f"{r['reservoir_raw']} cyano={r['cyano']:.0f}",
                "cyano value repeated in another reservoir of the same campaign")
    # A sample date far from the campaign month is likely a date copied forward in the report
    # (e.g. Pedras Brancas keeps 04/02/2016 in seven campaigns with different values).
    # Satellite matching needs the true date, so these rows are flagged and not matched.
    mid = pd.Period(df["campaign"].iloc[0], "M").to_timestamp() + pd.Timedelta(days=14)
    far = (df["date"] - mid).dt.days.abs() > 75
    df.loc[far, "qc_flag"] = (df.loc[far, "qc_flag"] + " date_far_from_campaign").str.strip()
    for _, r in df[far].iterrows():
        log.add(path.name, 3, r["page"], f"{r['reservoir_raw']} date={r['date'].date()}",
                "sample date more than 75 days from campaign month")
    return df
