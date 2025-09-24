"""FastAPI 애플리케이션 부트스트랩."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .models import Base
from .routers import imports, projects, query, uploads

app = FastAPI(title="RePCB API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 테이블 초기화 (개발 환경)
init_db(Base)

app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
app.include_router(imports.router, prefix="/imports", tags=["imports"])
app.include_router(query.router, prefix="/query", tags=["query"])


@app.get("/")
def root() -> dict:
    return {"message": "RePCB API"}
