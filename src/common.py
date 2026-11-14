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
ABBREVIATIONS = {"sto": "santo", "sta": "santa", "anto": "antonio"}

# Spelling differences between tables, checked by hand against Table 2 of the same report.
TYPOS = {"gerninal": "germinal"}


def normalize_name(name: str) -> str:
    """Strip accents, lower-case, expand abbreviations so names join across tables and campaigns."""
    if name is None:
        return ""
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("\n", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    tokens = [ABBREVIATIONS.get(t, t) for t in s.split()]
    tokens = ["maria" if t == "ma" and i > 0 and tokens[i - 1] == "santa" else t for i, t in enumerate(tokens)]
    s = " ".join(tokens)
    return TYPOS.get(s, s)
