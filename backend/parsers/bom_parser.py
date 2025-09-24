"""BOM 파일 파싱 및 정규화."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Mapping

import pandas as pd

# 헤더 매핑 룰: 다양한 명칭을 통합한다.
HEADER_ALIASES = {
    "refdes": {"refdes", "ref", "designator", "reference"},
    "mpn": {"mpn", "manufacturer part", "mfr part", "mfg part"},
    "value": {"value", "val"},
    "footprint": {"footprint", "package"},
    "qty": {"qty", "quantity"},
    "vendor": {"vendor", "supplier", "dist"},
}


def normalize_header(header: str) -> str:
    header = re.sub(r"[^a-z0-9]+", " ", header.lower()).strip()
    return header


def map_columns(columns: Iterable[str]) -> Mapping[str, str]:
    mapping = {}
    for col in columns:
        norm = normalize_header(col)
        for key, aliases in HEADER_ALIASES.items():
            if norm in aliases:
                mapping[key] = col
                break
    return mapping


def load_dataframe(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def parse_bom(path: Path) -> List[dict]:
    df = load_dataframe(path)
    mapping = map_columns(df.columns)
    if "refdes" not in mapping:
        raise ValueError("BOM 파일에서 참조디자인ator(refdes) 컬럼을 찾을 수 없음")
    result = []
    for _, row in df.iterrows():
        refdes = str(row[mapping["refdes"]]).strip()
        if not refdes:
            continue
        item = {
            "refdes": refdes,
            "mpn": str(row[mapping.get("mpn", "")] or "").strip() or None,
            "value": str(row[mapping.get("value", "")] or "").strip() or None,
            "footprint": str(row[mapping.get("footprint", "")] or "").strip() or None,
            "qty": int(row[mapping.get("qty", "")] or 1),
            "vendor": str(row[mapping.get("vendor", "")] or "").strip() or None,
        }
        result.append(item)
    return result
