"""프로젝트 라우터."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Project

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str


class ProjectOut(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


@router.post("/", response_model=ProjectOut)
def create_project(payload: ProjectCreate, session: Session = Depends(get_session)):
    project = Project(name=payload.name)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.get("/", response_model=List[ProjectOut])
def list_projects(session: Session = Depends(get_session)):
    return session.query(Project).order_by(Project.created_at.desc()).all()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
