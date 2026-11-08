# `case` — Workflow / Orchestration — 유일한 지휘자

**Owner:** 유소연 (`docs/management/ownership.md`) · **경계:** `docs/architecture/module-architecture.md` §4-모듈5 · **문서 작업공간:** `docs/modules/case/`

## 이 폴더가 하는 일 (요약 — 원문은 §4-모듈5)

자연어 단서 구조화·상태 기계·Candidate selection·**`JobIntent` 생성**·rerun_policy·`EvidenceNeeds` → JobIntent·stale 결과 적용 여부·`CaseView` projection·`USER_REVIEWED`·correction 로그 export

## 이 폴더가 알면 안 되는 것 (§4-모듈5 「알면 안 되는 것」)

130MB 등 규정 숫자 / OCR threshold / prompt 내용 / Overlay가 왜 우선인지 같은 evidence 정책 / codec·ffmpeg / Worker lifecycle 구현(그건 `common/`)

## 공개 진입점

다른 모듈(API · Worker)은 아래만 부른다. `daesingo.case`가 앞의 다섯 개를 다시 내보낸다(`__init__.py`).

| 진입점 | 하는 일 | 부르는 곳 |
| --- | --- | --- |
| `service.create_case` | 빈 case를 만든다 | API `POST /cases` |
| `service.record_source_registered` | 업로드된 영상을 case에 등록한다 | API 업로드 |
| `command.execute_command` | 사용자 command 하나를 처리한다(분석 시작 · 후보 선택 · 상황 응답 · 정정 · 직접 입력 등). 종류와 규칙은 `docs/modules/case/contracts/contract-case-command.md` | API `POST /cases/{id}/commands` |
| `service.get_view` | 화면용 `CaseView`를 만든다. 모양은 `docs/architecture/contracts/contract-job-record-case-view.md`(현재 `view.CONTRACT_VERSION`) | API `GET /cases/{id}/view` |
| `store.CaseStore` | case 읽기 · 저장, 관찰 job 고정 입력 조회(`observation_input`) | API · Worker |
| `reflection.reflect_execution` | 끝난 Worker 작업 결과를 case에 반영하고 다음 작업을 자동 발주한다 | Worker |
| `stored_observation.stored_adapter_factory` | 저장된 관찰 결과를 읽는 adapter를 만든다 | API · Worker composition |
| `store_mysql.MySQLCaseRepository` | case 저장소의 MySQL 구현(표 정의는 `migrations/case/`) | API · Worker composition |

안쪽 모듈은 다음과 같다.
- `domain.CaseAggregate`: 진행 단계(상태 기계)와 후보 선택.
- `jobs`: 작업 발주 기록(JobRecord). kind 목록은 `jobs.JOB_KINDS`.
- `analysis_start`: 분석 시작과 첫 탐색 범위 · 예산.
- `exports`: 신고 영상 · 번호판 이미지 내보내기 발주.
- `correction`: 사용자 정정 기록.
- `view`: CaseView 조립.

`adapters.MockFixtureAdapter`는 테스트와 데모용이고, 공개 API가 아니다.

## 상태

2026-11-08 기준으로 공개 RC에 쓰이는 실제 경로가 구현돼 있다.
- API · Worker 배선, MySQL 저장, 역행 전이(재탐색 · 다른 후보 · READY에서 되돌아가기), 실패 · timeout 분기가 들어 있다.
- 테스트는 `tests/case/`에 있다. 실행 방법은 `docs/modules/case/README.md` 「한눈에 보기」를 본다.
- 결정 기록은 `docs/modules/case/decisions/README.md`에 있다.
- `docs/modules/case/tech-spec.md`는 2026-09 1차 구현 시점의 기록이다.
