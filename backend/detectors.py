"""업로드 파일의 종류를 판별하는 헬퍼."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import BinaryIO

TEXT_EXTS = {".csv", ".tsv", ".txt"}
XLSX_EXTS = {".xlsx", ".xlsm"}
GERBER_EXTS = {".gbr", ".ger", ".pho", ".gtl", ".gbl", ".gts", ".gbs", ".gm1", ".gm2", ".gto", ".gbo"}


class DetectionError(Exception):
    """판별 실패시 발생."""


def detect_file_kind(filename: str, sample: bytes | None = None) -> str:
    """파일 확장자 및 샘플을 통해 kind를 판별한다."""
    ext = Path(filename).suffix.lower()
    if ext in {".zip"}:
        return "gerber_zip"
    if ext in TEXT_EXTS:
        # BOM/Placement/Insert 구분은 컬럼 기반으로 추후 파서가 재확인한다.
        return "text_table"
    if ext in XLSX_EXTS:
        return "spreadsheet"
    if ext in GERBER_EXTS:
        return "gerber_file"
    if ext == ".json":
        return "pcb_json"
    raise DetectionError(f"알 수 없는 확장자: {ext}")


def sniff_zip_kind(data: bytes) -> str:
    """ZIP 내부 파일명을 기반으로 Gerber ZIP인지 확인한다."""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        gerber_count = sum(1 for name in zf.namelist() if Path(name).suffix.lower() in GERBER_EXTS)
        if gerber_count == 0:
            raise DetectionError("Gerber 파일을 찾을 수 없는 ZIP")
    return "gerber_zip"
