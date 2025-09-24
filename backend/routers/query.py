"""데이터 조회 API."""
from __future__ import annotations

from typing import List
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import BomItem, GerberLayer, Placement

router = APIRouter()


@router.get("/bom/{project_id}")
def get_bom(project_id: int, session: Session = Depends(get_session)):
    items = (
        session.query(BomItem)
        .filter(BomItem.project_id == project_id)
        .order_by(BomItem.refdes)
        .all()
    )
    return [
        {
            "refdes": item.refdes,
            "mpn": item.mpn,
            "value": item.value,
            "footprint": item.footprint,
            "qty": item.qty,
            "vendor": item.vendor,
        }
        for item in items
    ]


@router.get("/placements/{project_id}")
def get_placements(project_id: int, session: Session = Depends(get_session)):
    items = (
        session.query(Placement)
        .filter(Placement.project_id == project_id)
        .order_by(Placement.refdes)
        .all()
    )
    return [
        {
            "refdes": item.refdes,
            "x": item.x,
            "y": item.y,
            "rotation": item.rotation,
            "side": item.side,
            "layer_hint": item.layer_hint,
            "package": item.package,
        }
        for item in items
    ]


@router.get("/gerber/{project_id}")
def list_layers(project_id: int, session: Session = Depends(get_session)):
    layers = (
        session.query(GerberLayer)
        .filter(GerberLayer.project_id == project_id)
        .order_by(GerberLayer.id)
        .all()
    )
    return [
        {
            "id": layer.id,
            "name": layer.name,
            "color": layer.color,
            "bbox": {
                "minx": layer.bbox_minx,
                "miny": layer.bbox_miny,
                "maxx": layer.bbox_maxx,
                "maxy": layer.bbox_maxy,
            },
            "json_path": layer.json_path,
        }
        for layer in layers
    ]


@router.get("/gerber/layer/{layer_id}")
def get_layer_detail(layer_id: int, session: Session = Depends(get_session)):
    layer = session.get(GerberLayer, layer_id)
    if not layer:
        raise HTTPException(status_code=404, detail="Layer not found")
    data = {}
    if layer.json_path:
        import json
        try:
            data = json.loads(Path(layer.json_path).read_text())
        except Exception:
            data = {}
    return {
        "id": layer.id,
        "name": layer.name,
        "color": layer.color,
        "bbox": {
            "minx": layer.bbox_minx,
            "miny": layer.bbox_miny,
            "maxx": layer.bbox_maxx,
            "maxy": layer.bbox_maxy,
        },
        "json_path": layer.json_path,
        "data": data,
    }
