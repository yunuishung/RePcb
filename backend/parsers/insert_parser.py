"""자삽(삽입) 데이터 파서."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Mapping

import pandas as pd

HEADER_ALIASES = {
    "refdes": {"refdes", "ref", "designator", "reference"},
    "op_code": {"op", "op code", "operation", "code"},
    "nozzle": {"nozzle", "head"},
    "feeder": {"feeder", "slot"},
    "speed": {"speed", "feed"},
    "notes": {"notes", "comment", "remark"},
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


def parse_insert_ops(path: Path) -> List[dict]:
    df = load_dataframe(path)
    mapping = map_columns(df.columns)
    if "refdes" not in mapping or "op_code" not in mapping:
        raise ValueError("Insert 데이터에 필수 컬럼(refdes/op_code)이 없음")
    results = []
    for _, row in df.iterrows():
        refdes = str(row[mapping["refdes"]]).strip()
        op = str(row[mapping["op_code"]]).strip()
        if not refdes or not op:
            continue
        def to_float(v):
            try:
                return float(v)
            except Exception:
                return None
        results.append(
            {
                "refdes": refdes,
                "op_code": op,
                "nozzle": str(row[mapping.get("nozzle", "")] or "").strip() or None,
                "feeder": str(row[mapping.get("feeder", "")] or "").strip() or None,
                "speed": to_float(row[mapping.get("speed", "")]),
                "notes": str(row[mapping.get("notes", "")] or "").strip() or None,
            }
        )
    return results
