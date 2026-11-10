# 대신고 (Daesingo)

**블랙박스 영상에서 교통위반 신고 자료를 준비해 주는 제품.**

위험한 위반을 목격했지만 정확한 시각과 장소를 기록하지 못한 운전자를 돕는다. 기억나는 시간·차량·상황·장소를 입력하면 장시간 블랙박스 영상에서 사건 후보와 전후 근거를 찾아 신고자료를 준비하는 것이 제품 목표다. 현재 공개 체험에서 사용할 수 있는 영상은 아래 범위로 제한된다.

목표는 신고할 마음이 없던 사람을 유도하는 게 아니라, **이미 생긴 신고 의향이 준비 과정의 마찰 때문에 사라지지 않게 하는 것**이다.

## 공개 체험

[공식 샘플 체험 열기](https://daesingo-ktc4.duckdns.org/). 별도로 제공받은 공식 3분 또는 10분 ZIP의 압축을 풀고, 같은 묶음에 속한 MP4를 하나 이상 올린다. 한 번에 합계 10분까지 이용할 수 있다. 서버는 공식 파일의 크기와 SHA-256을 확인하며 임의 사용자 영상은 받지 않는다. 로그인 없이 분석하고 체험을 시작한 브라우저 세션에서 결과를 조회·다운로드할 수 있다.

2026-11-10 최종 공개 배포는 `61d9b7ea3ed706fc90a995a1d1e1c8ba213eba6a`다. 제한 AWS 검수에서 공식 10분 묶음 업로드부터 신고영상 자동 생성·다운로드까지 확인했다. 후보 영상은 한 번에 하나씩 재생할 수 있다. 체험 시작 24시간 후부터 서버 자동 정리 대상이 되므로 필요한 신고영상은 미리 다운로드한다. [최종 AWS 공개 운영 인계](docs/runtime/a1-public-readiness.md#2026-11-10-최종-aws-공개-배포)

> **현재 Runtime 실행환경 (2026-10-30 갱신):** 로컬 Compose는 API·Worker·migration·MySQL을 구성한다. 기본 Worker는 Search·Recording·production PaddleOCR·export를 조립하며, Analysis/Incident encoding 설정에 따라 등록 가능한 handler가 달라진다. 실제 env·버전·cache·실행 순서와 미결 항목은 [Runtime/Ops·Recording 실행환경](docs/runtime/local-runtime-environment.md), 검증 이력과 남은 위험은 [Runtime Implementation Log](docs/runtime/runtime-implementation-log.md)를 확인한다.

## 무엇을 하고, 무엇을 하지 않는가

제품이 약속하는 것과 명시적으로 하지 않는 것은 **[`docs/product/product-spec.md`](docs/product/product-spec.md) §5**가 소유한다. 요약하면:

**한다** — 자연어 기억 단서를 시간·차량·상황 정보로 구조화 · 1차 탐색(Coarse)으로 상위 후보 생성 후 정밀 검증 · Top-3 구조화 카드와 사용자 보정 · 사건 전후 증거 구간 구성(**영상 파일 경계에 걸친 사건 포함**) · 번호판 best frame과 OCR · 시각을 **출처와 함께**(화면 표시 / 파일명 / 메타데이터 / 사용자 / Unknown) 관리 · GPS가 있으면 위치 보강, 없으면 사용자 단서 유지 · 신고요건 점검과 안전신문고 handoff

**하지 않는다** — AI가 법적 위반 여부를 최종 확정 · 안전신문고 자동 제출 · 신뢰 가능한 출처 없는 시각을 임의 생성 · 안전신문고 최종 신고 위치의 자동 확정 · 모든 도로교통법 위반 유형 지원

### 초기 지원 사건 4종

신호위반 · 중앙선 침범 · 진로변경(백색 실선 침범) · 이륜차 안전모 미착용

4종으로 좁힌 이유는 시간 순서 판단(신호 → 정지선 → 통과)과 객체 속성 판단(안전모)처럼 **서로 다른 인식 능력을 함께 검증**할 수 있기 때문이다. 자세한 근거는 product-spec §6.

### 넘지 않는 선

[`product-spec.md`](docs/product/product-spec.md) **§7**이 제품 수준 불변 경계를 소유한다. 그중 셋만 옮기면:

- **원본 영상을 덮어쓰지 않는다.**
- 번호판·시각·위치가 불확실하면 **값을 만들어내지 않고** 출처와 `확인 필요`/`UNKNOWN` 상태를 보여준다.
- **실제 안전신문고 제출은 사용자가 직접 한다.**

## 사용자 흐름

공식 MP4 등록 → 기억나는 상황 입력 → 분석 시작 → 후보와 결과 확인 → 필요한 값 수정, 다른 후보 선택 또는 다시 탐색 → 신고자료 복사·다운로드 → 안전신문고에서 직접 첨부·제출.

단서 구조화와 탐색 범위 계산은 분석 중에 자동으로 진행한다. 결과 화면에서 위치 텍스트를 고치거나, 보조 지도가 활성화된 경우 핀으로 주변을 살펴볼 수 있다. 최종 신고 위치는 안전신문고에서 사용자가 선택한다.

화면 단위 흐름과 **실패했을 때 무엇을 보여주는지**는 [`docs/product/core-user-flow.md`](docs/product/core-user-flow.md)가 소유한다. 채팅 인터페이스가 아니라 **단계형 화면**이고, 자연어 입력은 단서 입력 한 곳에만 있다.

## 구조

모듈 7개로 나눈다. 기준은 팀원 수가 아니라 **서로 다른 변경 이유**다 — 무엇이 바뀌면 어디를 고치게 되는가.

| 모듈 | 다루는 사실 |
| --- | --- |
| `recording` | 블랙박스 파일·stream이라는 현실. Source가 말해주는 것과 픽셀 접근 경계 |
| `search` | 넓은 영상 범위의 픽셀이 말해주는 것 — 사건 구간 후보 탐색 |
| `readout` | 좁은 화면 영역의 값 — 번호판·화면 시각이 어떻게 보이는지 |
| `evidence` | 확정 Evidence + 신고 규정 + Package 정책 |
| `case` | 진행 상태·사용자 선택·부분 재실행·작업 발주 의도 |
| `web` | 도메인 상태를 갖지 않고 `CaseView`를 표현하는 작업공간 |
| `eval` | 제품 런타임과 분리된 채점 도구 |

두 가지가 이 구조의 핵심이다. **관찰(`search`·`readout`)과 확정(`evidence`)을 분리한다** — "AI가 그렇게 봤다"와 "이 값이 맞다"는 다른 사실이다. 그리고 **`eval`은 제품 런타임이 아니다** — `search`와 `readout`은 `eval`의 존재를 모른다.

경계·계약·각 모듈이 **알면 안 되는 것**은 [`docs/architecture/module-architecture.md`](docs/architecture/module-architecture.md)가 소유한다. 1,900줄이므로 전체를 읽지 않는다 — §1 → §2 → 자기 모듈 §4 → §5 순서로 읽는다.

### 기술 스택 (확정)

Python · FastAPI · **Modular Monolith**(API 1 + Worker 1) · MySQL 8.4 · DB Queue · ffmpeg/ffprobe · AWS · React 19/Vite 6 웹 앱(선택형 주행 게임에 Three.js 0.160.1) · Desktop Web 우선(모바일 반응형은 MVP 제외). 안전신문고 자동 제출 API는 연동하지 않는다.

## 레포 구성

`apps/`에 웹 앱과 프로토타입, `src/daesingo/`에 제품 서버, `eval/`에 평가 코드, `docs/`에 설계·운영 문서가 있다. 각 영역의 구현과 검증은 해당 README에서 확인한다.

| 경로 | 내용 |
| --- | --- |
| `apps/prototype/` | 흐름 프로토타입 (React 19 + Vite 6, 목데이터). **제품 코드 아님** |
| `apps/web/` | 실제 웹 앱(React 19 · Vite 6). 공식 공개 주소의 `/`와 기존 `/?sample` 링크는 같은 공개 체험에 연결된다. 개발 환경의 목데이터 시연은 `/?demo`를 사용한다. [웹 앱 실행·CI](apps/web/README.md) |
| `src/daesingo/` | Python 모듈형 모놀리스. [API](src/daesingo/api/README.md)는 Case·업로드·자산 조회를 제공하고, [Worker](src/daesingo/worker/README.md)는 큐에서 분석·OCR·영상 및 이미지 생성 작업을 실행한다. |
| `eval/` | 오프라인 채점 도구 — `datasets` / `manifests` / `runners` / `scorers` / `predictions` / `results`, 실제로 동작한다 |
| `data/` | 테스트 · 데모용 고정 데이터 — `mock/`(모듈별 계약 fixture · 시나리오), `real/`(실제 영상 E2E 산출 JSON) |
| `examples/` | `recording` · `search` 공개 함수 사용 예제 스크립트 |
| `scripts/` | 경계·계약 검사 등 팀 스크립트 (`check_boundaries.py` 등) |
| `Dockerfile` · `compose.yaml` · `docker/` | RT-13(a) local api/worker/migrate/mysql 구성·실행 어댑터. 설정과 전용 smoke는 [RT-13(a) Notes](docs/runtime/rt13a-docker-compose.md) 참조 |
| `deploy/` | RT-14 수동 배포·복구 도구. GitHub Actions에서 OIDC로 AWS에 인증하고 ECR 이미지와 SSM을 사용한다. 배포 버전에 연결된 Web·Caddy와 외부 기본 동작을 확인한다. [실행·복구 계약](docs/runtime/rt14-public-deployment.md) |
| `tests/` | 모듈별 pytest 테스트. 루트 `pyproject.toml`(`pythonpath=["src"]`, `testpaths=["tests"]`) 기준으로 수집하며, CI는 비-MySQL 회귀와 실제 MySQL·report gate를 분리한다 ([실행 구조](docs/runtime/ci-test-partitions.md)) |
| `docs/product/` | 타깃·문제·제품 약속·지원 범위·사용자 흐름·검증 계획 |
| `docs/architecture/` | 모듈 경계(v4)와 계약 원칙 |
| `docs/runtime/` | 공통 실행 인프라의 Runtime Tech Spec · Ops Spec. `common/runtime`은 도메인 모듈이 아님 |
| `docs/modules/` | 모듈별 조사·실험·결정·계약 |
| `docs/management/` | 역할 배정·운영 계획·cross-cutting 결정·보안 검수 |
| `docs/design/` | 디자인 시스템·1단계 목업·프로토타입 스펙 |
| `docs/archive/` | 지난 제출물과 종료된 안건 — **현재 문서가 아니다** |

Local logical backup/restore와 실제 복원 acceptance 실행은 [RT-13(b) Notes](docs/runtime/rt13b-backup-restore.md)를 따른다. DB backup은 shared media volume 자체를 포함하지 않는다.

문서는 한국어로 쓰고 폴더·파일 이름은 영어로 쓴다.

## 문서를 읽는 순서

**전체를 읽지 않는다.** 자기 작업에 해당하는 것만 연다.

| 하려는 일 | 읽을 것 |
| --- | --- |
| 제품 약속과 지원 범위 | [Product Spec](docs/product/product-spec.md) §3·§5·§7 |
| 화면 흐름 · 실패 UX | [Core User Flow](docs/product/core-user-flow.md) |
| 내 모듈의 경계 · 계약 · 금지사항 | `docs/architecture/module-architecture.md` §1 → §2 → §4 내 모듈 → §5 |
| 내 모듈의 조사 · 실험 · 결정 | `docs/modules/<module>/` |
| DB Queue · retry · lease/heartbeat · Worker 실행 기반 | `docs/runtime/runtime-tech-spec.md` |
| 운영 정책과 실제 공개 검증 | [Ops Spec](docs/runtime/ops-spec.md) · [최종 AWS 인계](docs/runtime/a1-public-readiness.md#2026-11-10-최종-aws-공개-배포) |
| RC 수용 결정과 평가·CI 결과 읽기 | [11/5 RC 결정](docs/management/rc-scope-2026-11-05.md) · [Eval 결과와 한계](docs/modules/eval/evaluation-results-2026-11-01.md#7-해석할-때-지켜야-할-것) · [CI 실행 구조](docs/runtime/ci-test-partitions.md) |
| 누가 무엇을 맡는지 | `docs/management/ownership.md` |
| 운영 결정(승인 경로 · 리뷰 담당) | `docs/management/cross-cutting-decisions.md` |
| 문서 폴더 규칙 · 문서가 서로 다른 말을 할 때 | `docs/README.md` |

문서가 충돌하면 우선순위는 **제품 약속 = `product-spec.md`** → **모듈 경계·계약 = `module-architecture.md`(v4)** → **화면 흐름 = `core-user-flow.md`** 이고, 셋이 어긋나면 혼자 고치지 않고 주간 회의 안건으로 올린다. 자세한 규칙은 [`docs/README.md`](docs/README.md).

정책의 우선순위와 실제 적용 여부는 구분한다. 적용 범위와 검증 결과는 해당 코드·테스트 및 배포 기록에서 확인한다.

## 실행

로컬 Compose/API/Worker 구성은 [Runtime/Ops·Recording 실행환경](docs/runtime/local-runtime-environment.md)을 먼저 읽고
[`.env.example`](.env.example)의 빈 필수값을 보호된 파일에 채운다. 현재 지원 toolchain, migration 순서,
Search/Intent 모델 구분, production Paddle cache, encoding 미결 항목과 8종 등록 확인 방법을 한곳에서 안내한다.

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

`apps/web` 결과 화면의 위치 지도는 선택적 build 설정 `VITE_KAKAO_MAP_KEY`를 읽는다. 로컬 공급 위치(`apps/web/.env.local`)와 배포 이미지 공급 경로는 [환경·배포 설정 명세 §2.4](docs/management/environment-and-deployment-config.md#24-web-선택적-build-설정)를 따르며, API/Worker runtime 설정만으로 활성화되지 않는다. 키가 없으면 지도 칸만 숨고 나머지 흐름은 그대로 동작한다.

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
대상 경로·허용/금지 방향은 [ownership §6](docs/management/ownership.md),
정적 분석 한계·검증 기록은 [RT-15(b) Notes](docs/runtime/rt15b-import-boundaries.md)를 따른다.
`--only=boundaries`로 경계만 실행할 수 있고, 회귀 fixture는
`uv run --no-sync pytest tests/test_import_boundaries.py`로 확인한다.

Runtime lint/type gate는 네 소유 경로만 검사한다. `uv sync --locked --extra quality`
후 로컬과 CI에서 `uv run --no-sync python scripts/check_runtime_quality.py`를 실행한다.
Ruff·mypy 버전, 규칙, 타입 예외와 검증 기록은 [RT-15(a) Notes](docs/runtime/rt15a-runtime-quality.md)에 있다.

배포 전 secret 검사는 `python scripts/check_secrets.py install --tool-dir .codex-scratch/rt15c/tool` 후 `python scripts/check_secrets.py scan --repo . --tool-dir .codex-scratch/rt15c/tool`로 실행한다. 고정 Gitleaks와 전체 HEAD 이력이 필요하며 원문 없이 rule ID·익명 예외 ID·건수만 출력한다. 합성 검증은 `python scripts/secret_scan_controls.py --tool-dir .codex-scratch/rt15c/tool`이다. A01·A02는 정확한 위치·좌표·값/패턴 지문만 허용하며, 같은 위치의 새 credential은 실패한다. 별도 `secret-scan.yml`은 develop 수동 실행 및 배포 workflow 선행 검사이며 일반 PR gate에는 편입하지 않았다. 예외 근거·비노출 사고와 보강·실패 정책·검사 한계는 [RT-15(c) Notes](docs/runtime/rt15c-secret-scan.md)를 따른다.

MySQL integration은 `DAESINGO_MYSQL_URL`로 지정한 폐기 가능한 MySQL 8.4 테스트 DB에서 실행한다. 공용 harness는 테스트별 schema를 생성·삭제하므로 해당 권한이 필요하며, 기존 Case fixture는 지정 DB의 Case table을 초기화한다. 권한 실패 시나리오까지 포함한 전체 검증은 테스트 사용자 생성·SELECT 권한 부여·사용자 삭제 권한도 필요하다. CI의 `python-tests.yml`은 비-MySQL `regression`과 MySQL 8.4 service를 쓰는 `mysql`을 병렬 실행하고 `quality`도 독립 실행하며 기존 `test`가 quality·regression·mysql 세 성공을 요구한다. 전체 MySQL gate는 `uv run python -m tests.ci_orchestration mysql .codex-scratch/mysql-evidence`로 실행한다. 실제 inventory 1회 → 같은 실행의 JSON/JUnit strict → catalog·실제 report mutation 순서이며 skip/xfail 0을 요구한다. 검증 wrapper를 단독 또는 bare pytest로 실행하면 현재 실행의 evidence가 없어 실패하므로 전체 gate 진입점을 사용한다. URL 없는 개별 DB 테스트의 기존 opt-in skip은 유지된다. partition·실행 환경·제약은 [CI 실행 구조](docs/runtime/ci-test-partitions.md)를 따른다.

Migration은 `uv run python -m daesingo.common.db.migrate --database-url-stdin`으로 실행한다. 호출자가 URL 한 개를 비대화형 stdin에 명시적으로 전달하며 credential을 argv·로그에 넣지 않는다. runner는 URL 환경변수·`.env`·RuntimeConfig를 읽지 않는다. 소스 checkout의 env를 frozen registry `case → runtime → recording` 순서로 `head`까지 적용하며, 새 env는 registry와 필수 테스트에 등록해야 한다. 기존 MySQL gate는 RT-02(a)·Case 실행 목록과 migration·Recording 필수 check를 함께 검사한다.

Migration은 단일 실행 전제다. process 내부 중복 호출만 거부하며 cross-process 동시 실행 안전성을 보장하지 않는다. 첫 실패에서 중단하고 retry·stamp·downgrade·resume/startup migration은 제공하지 않는다. MySQL DDL의 부분 적용은 전체 rollback되지 않으므로 실패 후 상태 검사·복구가 필요하다. 11/10 최종 공개 배포 `61d9b7ea`의 스키마는 Case `case_0001`, Recording `recording_0002`, Runtime `runtime_0008`이다. 작업 실행과 사용량 기록의 구현·검증 이력은 [Runtime Implementation Log](docs/runtime/runtime-implementation-log.md)를 확인한다.

API는 `uv run --no-sync python -m daesingo.api --revision <revision> --host 127.0.0.1 --port 8000`으로 실행한다. Case 생성·조회·명령, 원본·공식 샘플 등록, 프레임·파생 자산·후보 영상 조회를 제공한다. 로컬 실행 조건과 경로별 지원 범위는 [API README](src/daesingo/api/README.md), 운영 모드별 경계는 [A-1 운영 인계](docs/runtime/a1-public-readiness.md#http-연결-계약)를 확인한다.

### 프로토타입에 대해

`apps/prototype`은 **흐름 프로토타입**이다. 목데이터로 도는 10화면이고 백엔드·영상 파이프라인·AI 호출이 없다. 결과 없음 · 탐색 실패 · 범위 확장처럼 **실패 상태로 바로 점프하는 `ScenarioBar` 데모 컨트롤**이 들어 있다. 제품 코드가 아니므로 손대지 않는다.

후보 비교 영상 미리보기는 현재 세대 rank 1~3을 대상으로 첫 요청 때 구간 MP4를 준비한다. 재생은 후보 선택과 분리되며 `GET /cases/{case_id}/candidate-videos/{clip_ref}`의 inline·Range 응답을 사용한다. 구현 범위·상태·검증 한계는 [후보 영상 미리보기 결정](docs/modules/case/decisions/candidate-video-preview.md)을 확인한다.

실제 웹 앱의 화면 구조, 프로토타입과의 관계, 공개 체험·목데이터 시연의 실행 범위와 검사는 [웹 앱 README](apps/web/README.md)와 [Web 문서](docs/modules/web/README.md)를 따른다.

## 라이선스

[MIT](LICENSE).


### 기본 Worker OCR

`python -m daesingo.worker`의 production OCR 초기화와 검증은 [Issue #468 구현 기록](docs/runtime/issue468-production-readout.md)을 확인한다.
