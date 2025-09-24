"""부품 좌표(Placement) 파서."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Mapping

import pandas as pd

HEADER_ALIASES = {
    "refdes": {"refdes", "ref", "designator", "reference"},
    "x": {"x", "x(mm)", "x (mm)", "pos x", "center-x"},
    "y": {"y", "y(mm)", "y (mm)", "pos y", "center-y"},
    "rotation": {"rotation", "rot", "theta"},
    "side": {"side", "layer", "side name"},
    "package": {"package", "footprint"},
}


def normalize(header: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", header.lower()).strip()


def map_columns(columns: Iterable[str]) -> Mapping[str, str]:
    mapping = {}
    for col in columns:
        norm = normalize(col)
        for key, aliases in HEADER_ALIASES.items():
            if norm in aliases:
                mapping[key] = col
                break
    return mapping


def load_dataframe(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def parse_placements(path: Path) -> List[dict]:
    df = load_dataframe(path)
    mapping = map_columns(df.columns)
    required = {"refdes", "x", "y"}
    if not required.issubset(mapping):
        missing = required - mapping.keys()
        raise ValueError(f"Placement 파일에 필수 컬럼이 없음: {missing}")
    results = []
    for _, row in df.iterrows():
        refdes = str(row[mapping["refdes"]]).strip()
        if not refdes:
            continue
        def to_float(value):
            try:
                return float(value)
            except Exception:
                return 0.0
        results.append(
            {
                "refdes": refdes,
                "x": to_float(row[mapping["x"]]),
                "y": to_float(row[mapping["y"]]),
                "rotation": to_float(row[mapping.get("rotation", 0)]),
                "side": str(row[mapping.get("side", "top")] or "top").strip(),
                "layer_hint": None,
                "package": str(row[mapping.get("package", "")] or "").strip() or None,
            }
        )
    return results
