"""업로드 라우터."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_session
from ..detectors import DetectionError, detect_file_kind
from ..models import Project, Upload
from ..storage import store_stream

router = APIRouter()


class UploadOut(BaseModel):
    id: int
    project_id: int
    filename: str
    kind: str
    status: str

    class Config:
        orm_mode = True


@router.post("/", response_model=List[UploadOut])
async def upload_files(
    project_id: int,
    files: List[UploadFile] = File(...),
    session: Session = Depends(get_session),
):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    results = []
    for file in files:
        file.file.seek(0)
        stored = store_stream(file.file, subdir="uploads", filename=file.filename)
        file.file.seek(0)
        try:
            kind = detect_file_kind(file.filename)
        except DetectionError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        existing = (
            session.query(Upload)
            .filter(Upload.project_id == project_id, Upload.sha256 == stored.sha256)
            .first()
        )
        if existing:
            results.append(existing)
            continue
        upload = Upload(
            project_id=project_id,
            filename=file.filename,
            sha256=stored.sha256,
            size=stored.size,
            kind=kind,
            stored_path=str(stored.path),
            status="stored",
        )
        session.add(upload)
        session.flush()
        results.append(upload)
    session.commit()
    return results


@router.get("/project/{project_id}", response_model=List[UploadOut])
def list_uploads(project_id: int, session: Session = Depends(get_session)):
    return (
        session.query(Upload)
        .filter(Upload.project_id == project_id)
        .order_by(Upload.created_at.desc())
        .all()
    )
