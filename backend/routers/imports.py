"""임포트 파이프라인 라우터."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import ImportStatus, Project, Upload
from ..pipeline import ImportPipeline, PipelineError

router = APIRouter()


class ImportRequest(BaseModel):
    project_id: int
    upload_ids: List[int]


class ImportResult(BaseModel):
    upload_id: int
    status: str
    message: str | None = None


@router.post("/run", response_model=List[ImportResult])
def run_import(payload: ImportRequest, session: Session = Depends(get_session)):
    project = session.get(Project, payload.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    pipeline = ImportPipeline(session)
    results: List[ImportResult] = []
    for upload_id in payload.upload_ids:
        upload = session.get(Upload, upload_id)
        if not upload:
            results.append(ImportResult(upload_id=upload_id, status="error", message="Upload not found"))
            continue
        if upload.project_id != payload.project_id:
            results.append(ImportResult(upload_id=upload_id, status="error", message="Upload not in project"))
            continue
        try:
            pipeline.run_for_upload(upload)
            results.append(ImportResult(upload_id=upload_id, status="ok"))
        except PipelineError as exc:
            upload.status = "error"
            session.add(upload)
            results.append(ImportResult(upload_id=upload_id, status="error", message=str(exc)))
    summary = {"results": [r.dict() for r in results]}
    status = (
        session.query(ImportStatus)
        .filter(ImportStatus.project_id == payload.project_id)
        .first()
    )
    if not status:
        status = ImportStatus(project_id=payload.project_id, payload=summary)
        session.add(status)
    else:
        status.payload = summary
    session.commit()
    return results


@router.get("/status/{project_id}")
def get_status(project_id: int, session: Session = Depends(get_session)):
    status = (
        session.query(ImportStatus)
        .filter(ImportStatus.project_id == project_id)
        .order_by(ImportStatus.updated_at.desc())
        .first()
    )
    if not status:
        return {"project_id": project_id, "status": "unknown"}
    return status.payload
