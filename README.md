# RePCB

RePCB는 다양한 PCB 연관 파일(BOM/Placement/자삽/Gerber)을 업로드하면 서버에서 자동으로 판별·정규화하여 DB에 저장하고, 웹에서는 Web Worker + OffscreenCanvas 기반의 대용량 PCB 뷰어를 제공하는 참조 구현이다.

## 구성

- **backend/**: FastAPI 기반 API 서버
  - 업로드 판별(`detectors.py`), 저장(`storage.py`), 파서(`parsers/`), 임포트 파이프라인(`pipeline.py`), REST 라우터(`routers/`)
- **web/**: Drag&Drop 업로드 UI 및 Worker 기반 렌더러
- **tools/**: Gerber → pcb.json 변환 스크립트

## 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .  # pyproject.toml 기반
```

또는 단순히 필요한 패키지 설치:

```bash
pip install fastapi uvicorn[standard] sqlalchemy pandas python-multipart openpyxl
```

## 실행

1. 서버 실행

```bash
uvicorn backend.app:app --reload
```

2. 정적 웹 파일은 `web/` 디렉터리를 Nginx/VSCode Live Server 등으로 서빙하거나, 간단히 Python HTTP 서버 사용:

```bash
cd web
python -m http.server 8000
```

3. 브라우저에서 `http://localhost:8000/index.html` 접속 후, 업로드 패널에 파일을 드롭한다. 서버는 `/uploads` → `/imports/run` 순으로 호출되며 DB와 오브젝트 스토리지(`./storage/`)에 데이터가 저장된다.

## API 개요

| Method | Path | 설명 |
| --- | --- | --- |
| `POST` | `/projects/` | 프로젝트 생성 |
| `GET` | `/projects/` | 프로젝트 목록 |
| `POST` | `/uploads/?project_id=1` | 파일 업로드 (다중) |
| `GET` | `/uploads/project/{id}` | 업로드 이력 |
| `POST` | `/imports/run` | 업로드 파일 파싱/DB 반영 |
| `GET` | `/imports/status/{project_id}` | 최근 임포트 상태 |
| `GET` | `/query/bom/{project_id}` | BOM 데이터 |
| `GET` | `/query/placements/{project_id}` | Placement 데이터 |
| `GET` | `/query/gerber/{project_id}` | Gerber 레이어 목록 |
| `GET` | `/query/gerber/layer/{layer_id}` | 레이어 상세(세그먼트/플래시 JSON 포함) |

## 주요 동작 흐름

1. 브라우저에서 Drag&Drop으로 여러 파일을 업로드.
2. `/uploads` 엔드포인트는 SHA-256을 계산하여 중복 파일을 차단하고, 확장자 기반으로 kind를 설정.
3. `/imports/run` 호출 시 `ImportPipeline`이 파일 종류에 따라 적절한 파서를 실행하고 DB에 저장.
4. Gerber 결과는 JSON으로 변환되어 워커/메인에서 재사용 가능.
5. Web Worker는 OffscreenCanvas를 우선 사용하여 파싱/렌더 루프를 메인 스레드로부터 분리. 미지원 브라우저는 메인 스레드 렌더러로 폴백.
6. Viewer는 팬/줌, Fit, 레이어 토글, Single Color, 중앙 10% 미리보기를 지원한다.

## 테스트 / 검증

- `tools/merge_gerber_to_json.py`로 로컬 Gerber를 하나의 `pcb.json`으로 변환해 워커에 직접 로드.
- 대용량 처리 및 LOD는 `geometry.js` 및 `renderer2d.js`에 확장 가능한 훅(TODO)으로 표시.

## 수락 테스트 가이드

1. **업로드-임포트**: BOM/Placement/Gerber ZIP 등 3개 이상의 파일을 `/web` UI에서 드롭 → `/imports/run` 결과 확인 → DB(`repdb.sqlite3`)에서 테이블 데이터 확인.
2. **웹 뷰어**: 레이어 목록 토글, Single Color, Fit 버튼, 마우스 팬/줌, 중앙 10% 토글 동작 확인.
3. **로컬 파일 표시**: `pcb.json` 또는 복수 `.gbr` 파일을 직접 드롭하면 서버를 거치지 않고 워커에서 즉시 렌더.
4. **진행률 이벤트**: 업로드 이후 `progress` 메시지가 UI에 표시되는지 확인.
5. **중복 업로드 방지**: 동일 파일 재업로드 시 `/uploads` 응답이 기존 업로드 ID를 재사용함을 확인.

## 데이터 저장 구조

- 데이터베이스: `sqlite:///repdb.sqlite3`
- 원본 파일 스토리지: `./storage/uploads/<sha256>`
- Gerber JSON: `./storage/gerber_json/layer_<id>.json`

## 기타

- 실제 서비스에서는 Alembic 마이그레이션, 오브젝트 스토리지(S3 등), 인증/권한 처리가 필요하다.
- WebGL2, WASM 파서 교체를 위한 인터페이스는 `renderer2d.js`, `geometry.js`, `worker.js` 모듈로 분리되어 있다.
