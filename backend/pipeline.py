"""업로드된 파일을 파싱하여 DB에 저장하는 파이프라인."""
from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Callable, Iterable, List

from sqlalchemy.orm import Session

from . import models
from .parsers.bom_parser import parse_bom
from .parsers.gerber_parser import parse_gerber
from .parsers.insert_parser import parse_insert_ops
from .parsers.placement_parser import parse_placements
from .storage import STORAGE_ROOT

ZIP_SIZE_LIMIT = 500 * 1024 * 1024  # 500MB 안전장치
ZIP_ENTRY_LIMIT = 2000
ZIP_COMPRESSION_RATIO_LIMIT = 100


class PipelineError(Exception):
    pass


class ImportPipeline:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- 공용 유틸 ---------------------------------------------------------
    def _store_bom(self, project_id: int, items: List[dict]) -> None:
        for item in items:
            self.session.add(models.BomItem(project_id=project_id, **item))

    def _store_placements(self, project_id: int, placements: List[dict]) -> None:
        for item in placements:
            self.session.add(models.Placement(project_id=project_id, **item))

    def _store_insert_ops(self, project_id: int, ops: List[dict]) -> None:
        for item in ops:
            self.session.add(models.InsertOp(project_id=project_id, **item))

    def _store_gerber_layer(self, project_id: int, name: str, meta: dict, segments: List[dict], flashes: List[dict], raw_path: Path) -> None:
        layer = models.GerberLayer(
            project_id=project_id,
            name=name,
            color="#00ff00",
            bbox_minx=meta["bbox"]["minx"],
            bbox_miny=meta["bbox"]["miny"],
            bbox_maxx=meta["bbox"]["maxx"],
            bbox_maxy=meta["bbox"]["maxy"],
            raw_path=str(raw_path),
        )
        self.session.add(layer)
        self.session.flush()  # layer.id 확보
        json_path = STORAGE_ROOT / "gerber_json" / f"layer_{layer.id}.json"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as fp:
            json.dump(
                {
                    "units": meta.get("units", "IN"),
                    "bbox": meta["bbox"],
                    "segments": segments,
                    "flashes": flashes,
                },
                fp,
            )
        layer.json_path = str(json_path)
        for seg in segments:
            self.session.add(
                models.GerberSegment(
                    layer_id=layer.id,
                    x0=seg["x0"],
                    y0=seg["y0"],
                    x1=seg["x1"],
                    y1=seg["y1"],
                    width=seg.get("width"),
                )
            )
        for fl in flashes:
            params = fl.get("params", {})
            self.session.add(
                models.GerberFlash(
                    layer_id=layer.id,
                    x=fl["x"],
                    y=fl["y"],
                    shape=fl["shape"],
                    p1=params.get("diameter"),
                    p2=params.get("height"),
                )
            )

    # --- ZIP 처리 ----------------------------------------------------------
    def _extract_zip(self, path: Path) -> List[Path]:
        with zipfile.ZipFile(path) as zf:
            if len(zf.namelist()) > ZIP_ENTRY_LIMIT:
                raise PipelineError("ZIP 엔트리 개수 제한 초과")
            extracted = []
            with tempfile.TemporaryDirectory() as tmpdir:
                total_uncompressed = 0
                for member in zf.infolist():
                    if member.is_dir():
                        continue
                    total_uncompressed += member.file_size
                    if total_uncompressed > ZIP_SIZE_LIMIT:
                        raise PipelineError("ZIP 해제 크기 제한 초과")
                    if member.compress_size == 0:
                        ratio = 1
                    else:
                        ratio = member.file_size / member.compress_size
                    if ratio > ZIP_COMPRESSION_RATIO_LIMIT:
                        raise PipelineError("ZIP Bomb 가능성 감지")
                    target = Path(tmpdir) / Path(member.filename).name
                    with zf.open(member) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    extracted.append(Path(target))
                final_paths = []
                storage_dir = STORAGE_ROOT / "gerber_zip_extract"
                storage_dir.mkdir(parents=True, exist_ok=True)
                for file_path in extracted:
                    final = storage_dir / file_path.name
                    shutil.copy(file_path, final)
                    final_paths.append(final)
            return final_paths

    # --- 파이프라인 실행 ----------------------------------------------------
    def run_for_upload(self, upload: models.Upload) -> None:
        kind = upload.kind
        path = Path(upload.stored_path)
        if not path.exists():
            raise PipelineError(f"파일이 존재하지 않습니다: {path}")
        if kind == "text_table" or kind == "spreadsheet":
            # BOM -> Placement -> Insert 순으로 시도한다.
            try:
                items = parse_bom(path)
            except Exception:
                items = None
            if items:
                self._store_bom(upload.project_id, items)
                upload.kind = "bom"
            else:
                try:
                    placements = parse_placements(path)
                except Exception:
                    placements = None
                if placements:
                    self._store_placements(upload.project_id, placements)
                    upload.kind = "placement"
                else:
                    try:
                        inserts = parse_insert_ops(path)
                    except Exception:
                        inserts = None
                    if inserts:
                        self._store_insert_ops(upload.project_id, inserts)
                        upload.kind = "insert"
                    else:
                        raise PipelineError("테이블 파일에서 지원되는 형식을 찾지 못했습니다")
        elif kind == "gerber_file":
            meta, segments, flashes = parse_gerber(path)
            self._store_gerber_layer(upload.project_id, path.name, meta, segments, flashes, path)
            upload.kind = "gerber_file"
        elif kind == "gerber_zip":
            extracted = self._extract_zip(path)
            for file_path in extracted:
                if file_path.suffix.lower() not in {".gbr", ".ger", ".pho", ".gtl", ".gbl", ".gts", ".gbs", ".gm1", ".gm2", ".gto", ".gbo"}:
                    continue
                meta, segments, flashes = parse_gerber(file_path)
                self._store_gerber_layer(upload.project_id, file_path.name, meta, segments, flashes, file_path)
        elif kind == "pcb_json":
            data = json.loads(path.read_text())
            layers = data.get("layers", [])
            for layer in layers:
                meta = {"units": data.get("units", "IN"), "bbox": layer.get("bbox", data.get("bbox", {}))}
                segments = layer.get("segments", [])
                flashes = layer.get("flashes", [])
                dummy_path = STORAGE_ROOT / "pcb_json" / layer.get("name", "layer.json")
                dummy_path.parent.mkdir(parents=True, exist_ok=True)
                dummy_path.write_text(json.dumps(layer))
                self._store_gerber_layer(upload.project_id, layer.get("name", "layer"), meta, segments, flashes, dummy_path)
        else:
            raise PipelineError(f"알 수 없는 kind: {kind}")
        upload.status = "imported"
        self.session.add(upload)
