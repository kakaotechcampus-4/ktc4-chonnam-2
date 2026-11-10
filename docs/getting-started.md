# 개발 환경과 실행

[프로젝트 소개로 돌아가기](../README.md)


로컬 Compose/API/Worker 구성은 [Runtime/Ops·Recording 실행환경](../docs/runtime/local-runtime-environment.md)을 먼저 읽고
[`.env.example`](../.env.example)의 빈 필수값을 보호된 파일에 채운다. 현재 지원 toolchain, migration 순서,
Search/Intent 모델 구분, production Paddle cache, encoding 설정과 handler 등록 확인 방법을 한곳에서 안내한다.

Node.js 20 이상. npm workspace라서 **레포 루트에서 한 번만** 설치한다(`apps/*` 안에서 하지 않는다).

```bash
npm install            # 루트에서 한 번
npm run dev:prototype  # Vite가 출력하는 URL 열기 (기본 http://localhost:5173)
```

```bash
npm run build              # build 스크립트가 있는 workspace 전부
npm run preview:prototype  # 프로토타입 프로덕션 빌드 서빙
npm run dev:web            # apps/web 개발 서버 — / 는 실제 흐름(API 서버 :8000 필요), 시연은 /?demo
npm run preview:web        # apps/web 프로덕션 빌드 서빙
npm run test:web           # apps/web 테스트 (vitest)
```

`apps/web` 결과 화면의 위치 지도는 선택적 build 설정 `VITE_KAKAO_MAP_KEY`를 읽는다. 로컬 공급 위치(`apps/web/.env.local`)와 배포 이미지 공급 경로는 [환경·배포 설정 명세 §2.4](../docs/management/environment-and-deployment-config.md#24-web-선택적-build-설정)를 따르며, API/Worker runtime 설정만으로 활성화되지 않는다. 키가 없으면 지도 칸만 숨고 나머지 흐름은 그대로 동작한다.

### Python (`src/daesingo`, `eval/`)

Python 3.12 이상. 레포 루트에 `pyproject.toml`이 있고 `src/` 레이아웃(`pythonpath=["src"]`)으로 잡혀 있다.

```bash
uv sync --locked --extra test --extra quality   # pytest와 quality negative control 도구도 잠금 버전으로 설치
# uv 없이: pip install -e ".[test,quality]" — 이 경우 아래 명령의 `uv run`은 빼고 실행한다
uv run python -m tests.ci_orchestration regression .codex-scratch/regression.xml  # 비-MySQL 회귀 (출력 폴더를 먼저 만든다)
uv run pytest tests/case/   # 모듈 하나만
uv run python scripts/check_boundaries.py  # 모듈 경계 위반 검사
```

경계 검사는 기존 문자열·계약 검사에 Runtime Python import 검사를 더한다.
대상 경로·허용/금지 방향은 [ownership §6](../docs/management/ownership.md),
정적 분석 한계·검증 기록은 [RT-15(b) Notes](../docs/runtime/rt15b-import-boundaries.md)를 따른다.
`--only=boundaries`로 경계만 실행할 수 있고, 회귀 fixture는
`uv run --no-sync pytest tests/test_import_boundaries.py`로 확인한다.

Runtime lint/type gate는 네 소유 경로만 검사한다. `uv sync --locked --extra quality`
후 로컬과 CI에서 `uv run --no-sync python scripts/check_runtime_quality.py`를 실행한다.
Ruff·mypy 버전, 규칙, 타입 예외와 검증 기록은 [RT-15(a) Notes](../docs/runtime/rt15a-runtime-quality.md)에 있다.

배포 전 secret 검사는 `python scripts/check_secrets.py install --tool-dir .codex-scratch/rt15c/tool` 후 `python scripts/check_secrets.py scan --repo . --tool-dir .codex-scratch/rt15c/tool`로 실행한다. 고정 Gitleaks와 전체 HEAD 이력이 필요하며 원문 없이 rule ID·익명 예외 ID·건수만 출력한다. 합성 검증은 `python scripts/secret_scan_controls.py --tool-dir .codex-scratch/rt15c/tool`이다. A01·A02는 정확한 위치·좌표·값/패턴 지문만 허용하며, 같은 위치의 새 credential은 실패한다. 별도 `secret-scan.yml`은 develop 수동 실행 및 배포 workflow 선행 검사이며 일반 PR gate에는 편입하지 않았다. 예외 근거·비노출 사고와 보강·실패 정책·검사 한계는 [RT-15(c) Notes](../docs/runtime/rt15c-secret-scan.md)를 따른다.

MySQL integration은 `DAESINGO_MYSQL_URL`로 지정한 폐기 가능한 MySQL 8.4 테스트 DB에서 실행한다. 공용 harness는 테스트별 schema를 생성·삭제하므로 해당 권한이 필요하며, 기존 Case fixture는 지정 DB의 Case table을 초기화한다. 권한 실패 시나리오까지 포함한 전체 검증은 테스트 사용자 생성·SELECT 권한 부여·사용자 삭제 권한도 필요하다. CI의 `python-tests.yml`은 비-MySQL `regression`과 MySQL 8.4 service를 쓰는 `mysql`을 병렬 실행하고 `quality`도 독립 실행하며 기존 `test`가 quality·regression·mysql 세 성공을 요구한다. 전체 MySQL gate는 `uv run python -m tests.ci_orchestration mysql .codex-scratch/mysql-evidence`로 실행한다. 실제 inventory 1회 → 같은 실행의 JSON/JUnit strict → catalog·실제 report mutation 순서이며 skip/xfail 0을 요구한다. 검증 wrapper를 단독 또는 bare pytest로 실행하면 현재 실행의 evidence가 없어 실패하므로 전체 gate 진입점을 사용한다. URL 없는 개별 DB 테스트의 기존 opt-in skip은 유지된다. partition·실행 환경·제약은 [CI 실행 구조](../docs/runtime/ci-test-partitions.md)를 따른다.

Migration은 `uv run python -m daesingo.common.db.migrate --database-url-stdin`으로 실행한다. 호출자가 URL 한 개를 비대화형 stdin에 명시적으로 전달하며 credential을 argv·로그에 넣지 않는다. runner는 URL 환경변수·`.env`·RuntimeConfig를 읽지 않는다. 소스 checkout의 env를 frozen registry `case → runtime → recording` 순서로 `head`까지 적용하며, 새 env는 registry와 필수 테스트에 등록해야 한다. 기존 MySQL gate는 RT-02(a)·Case 실행 목록과 migration·Recording 필수 check를 함께 검사한다.

Migration은 단일 실행 전제다. process 내부 중복 호출만 거부하며 cross-process 동시 실행 안전성을 보장하지 않는다. 첫 실패에서 중단하고 retry·stamp·downgrade·resume/startup migration은 제공하지 않는다. MySQL DDL의 부분 적용은 전체 rollback되지 않으므로 실패 후 상태 검사·복구가 필요하다. 11/10 최종 공개 배포 `61d9b7ea`의 스키마는 Case `case_0001`, Recording `recording_0002`, Runtime `runtime_0008`이다. 작업 실행과 사용량 기록의 구현·검증 이력은 [Runtime Implementation Log](../docs/runtime/runtime-implementation-log.md)를 확인한다.

API는 `uv run --no-sync python -m daesingo.api --revision <revision> --host 127.0.0.1 --port 8000`으로 실행한다. Case 생성·조회·명령, 원본·공식 샘플 등록, 프레임·파생 자산·후보 영상 조회를 제공한다. 로컬 실행 조건과 경로별 지원 범위는 [API README](../src/daesingo/api/README.md), 운영 모드별 경계는 [A-1 운영 인계](../docs/runtime/a1-public-readiness.md#http-연결-계약)를 확인한다.

### 프로토타입에 대해

`apps/prototype`은 **흐름 프로토타입**이다. 목데이터로 도는 10화면이고 백엔드·영상 파이프라인·AI 호출이 없다. 결과 없음 · 탐색 실패 · 범위 확장처럼 **실패 상태로 바로 점프하는 `ScenarioBar` 데모 컨트롤**이 들어 있다. 제품 코드가 아니므로 손대지 않는다.

후보 비교 영상 미리보기는 현재 세대 rank 1~3을 대상으로 첫 요청 때 구간 MP4를 준비한다. 재생은 후보 선택과 분리되며 `GET /cases/{case_id}/candidate-videos/{clip_ref}`의 inline·Range 응답을 사용한다. 구현 범위·상태·검증 한계는 [후보 영상 미리보기 결정](../docs/modules/case/decisions/candidate-video-preview.md)을 확인한다.

실제 웹 앱의 화면 구조와 프로토타입과의 관계는 [웹 앱 README](../apps/web/README.md)와 [Web 문서](../docs/modules/web/)에서 확인한다.

