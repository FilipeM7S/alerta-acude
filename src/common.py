"""Shared paths and helpers for Alerta Açude."""
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"

CYANO_THRESHOLD = 20_000  # cells/mL, Portaria GM/MS 888/2021, Annex XX art. 43


# Abbreviations used in COGERH Table 3 ("Sto Antº de Russas", "Sta Mª de Aracatiaçu").
# NFKD turns "º" into "o" and "ª" into "a", so "Antº" -> "anto" and "Mª" -> "ma".
# 2024/2025 reports add "Santo Ant.", "Santa M.", "S. Pedro Timb.", "Mons. Tabosa".
ABBREVIATIONS = {"sto": "santo", "sta": "santa", "anto": "antonio", "ant": "antonio",
                 "mons": "monsenhor", "timb": "timbauba"}

# A lone "S." means São, Santo or Santa depending on the next word.
S_PREFIX = {"antonio": "santo", "maria": "santa", "pedro": "sao"}

# Whole-name differences, each checked by hand against the other table of the same report.
ALIASES = {"gerninal": "germinal",          # typo in Table 3 (2016-2021)
           "osterne": "thomas osterne",     # Table 2, Feb/2024
           "volta": "varzea da volta",      # Table 2, Feb/2024
           "do batalhao": "barragem do batalhao"}  # Feb/2024; never in the same campaign as the full name


def normalize_name(name: str) -> str:
    """Strip accents, lower-case, expand abbreviations so names join across tables and campaigns."""
    if name is None:
        return ""
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("\n", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    tokens = [ABBREVIATIONS.get(t, t) for t in s.split()]
    out = []
    for i, t in enumerate(tokens):
        prev = out[-1] if out else None
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if t in ("ma", "m") and prev == "santa":
            t = "maria"
        elif t == "p" and prev == "sao":
            t = "pedro"
        elif t == "s" and nxt in S_PREFIX:
            t = S_PREFIX[nxt]
        out.append(t)
    s = " ".join(out)
    return ALIASES.get(s, s)
