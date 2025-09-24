"""데이터베이스 설정 및 세션 관리 모듈."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

DATABASE_URL = os.getenv("REPCB_DATABASE_URL", "sqlite:///./repdb.sqlite3")

# SQLite의 경우 동일한 스레드에서만 연결을 허용하므로 check_same_thread 옵션을 비활성화한다.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    future=True,
)

SessionLocal = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
)


@contextmanager
def session_scope() -> Generator:
    """세션 컨텍스트 관리자를 제공하여 커밋/롤백을 자동으로 처리한다."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Generator:
    """FastAPI Depends 용 세션 생성기."""
    with session_scope() as session:
        yield session


def init_db(base) -> None:
    """모든 테이블을 생성한다. 실제 서비스에서는 Alembic을 권장한다."""
    base.metadata.create_all(bind=engine)
