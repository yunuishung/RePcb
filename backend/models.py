"""SQLAlchemy 모델 정의."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    uploads = relationship("Upload", back_populates="project", cascade="all,delete-orphan")


class Upload(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    size = Column(Integer, nullable=False)
    kind = Column(String(32), nullable=False)
    status = Column(String(32), default="pending", nullable=False)
    stored_path = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    project = relationship("Project", back_populates="uploads")


class BomItem(Base):
    __tablename__ = "bom_items"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    refdes = Column(String(64), nullable=False)
    mpn = Column(String(128))
    value = Column(String(128))
    footprint = Column(String(128))
    qty = Column(Integer, default=1)
    vendor = Column(String(128))


class Placement(Base):
    __tablename__ = "placements"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    refdes = Column(String(64), nullable=False)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    rotation = Column(Float, default=0.0)
    side = Column(String(32), default="top")
    layer_hint = Column(String(64))
    package = Column(String(128))


class InsertOp(Base):
    __tablename__ = "insert_ops"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    refdes = Column(String(64), nullable=False)
    op_code = Column(String(64), nullable=False)
    nozzle = Column(String(64))
    feeder = Column(String(64))
    speed = Column(Float)
    notes = Column(Text)


class GerberLayer(Base):
    __tablename__ = "gerber_layers"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(128), nullable=False)
    color = Column(String(16), default="#00ff00")
    bbox_minx = Column(Float)
    bbox_miny = Column(Float)
    bbox_maxx = Column(Float)
    bbox_maxy = Column(Float)
    raw_path = Column(Text, nullable=False)
    json_path = Column(Text)
    tiles_ready = Column(Boolean, default=False)


class GerberSegment(Base):
    __tablename__ = "gerber_segments"

    id = Column(Integer, primary_key=True)
    layer_id = Column(Integer, ForeignKey("gerber_layers.id"), nullable=False)
    x0 = Column(Float, nullable=False)
    y0 = Column(Float, nullable=False)
    x1 = Column(Float, nullable=False)
    y1 = Column(Float, nullable=False)
    width = Column(Float)


class GerberFlash(Base):
    __tablename__ = "gerber_flashes"

    id = Column(Integer, primary_key=True)
    layer_id = Column(Integer, ForeignKey("gerber_layers.id"), nullable=False)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    shape = Column(String(8), nullable=False)
    p1 = Column(Float)
    p2 = Column(Float)
    p3 = Column(Float)
    p4 = Column(Float)


# JSON 필드가 필요한 경우를 대비해 여유롭게 정의
class ImportStatus(Base):
    __tablename__ = "import_status"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
