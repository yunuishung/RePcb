"""파일 저장소 관리. SHA-256 중복 방지와 경로 관리를 담당한다."""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable, Tuple

CHUNK_SIZE = 1024 * 1024
STORAGE_ROOT = Path(os.getenv("REPCB_STORAGE_ROOT", "./storage"))
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


@dataclass
class StoredFile:
    sha256: str
    size: int
    path: Path


def iter_chunks(stream: BinaryIO, chunk_size: int = CHUNK_SIZE) -> Iterable[bytes]:
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        yield chunk


def store_stream(stream: BinaryIO, *, subdir: str, filename: str) -> StoredFile:
    """스트림을 읽어 저장하고 SHA-256 해시를 반환한다."""
    digest = hashlib.sha256()
    size = 0
    temp_path = STORAGE_ROOT / "tmp"
    temp_path.mkdir(parents=True, exist_ok=True)
    temp_file = temp_path / f"{filename}.part"
    with open(temp_file, "wb") as f:
        for chunk in iter_chunks(stream):
            digest.update(chunk)
            size += len(chunk)
            f.write(chunk)
    sha_hex = digest.hexdigest()
    final_dir = STORAGE_ROOT / subdir / sha_hex[:2]
    final_dir.mkdir(parents=True, exist_ok=True)
    final_path = final_dir / filename
    if final_path.exists():
        temp_file.unlink(missing_ok=True)
        return StoredFile(sha256=sha_hex, size=size, path=final_path)
    os.replace(temp_file, final_path)
    return StoredFile(sha256=sha_hex, size=size, path=final_path)


def ensure_unique_path(sha256: str, filename: str, *, subdir: str) -> Path:
    """동일한 파일명이 중복되더라도 SHA-256을 기반으로 고유 경로를 반환."""
    final_dir = STORAGE_ROOT / subdir / sha256[:2]
    final_dir.mkdir(parents=True, exist_ok=True)
    return final_dir / filename
