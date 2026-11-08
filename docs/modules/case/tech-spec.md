# `case` Tech Spec — Workflow / Orchestration (Owner: 유소연)

> **먼저 읽기 (2026-11-08).** 이 문서는 **2026-09 1차 구현 기준** tech spec이다. 본문은 그 시점 기록이고, 아래에서 사실과 어긋난 줄만 고쳤다.
> 지금 구조는 이 문서 대신 아래를 본다.
> - 모듈 한눈에 보기 · 테스트 방법: [`docs/modules/case/README.md`](README.md)
> - CaseView · JobRecord 모양: [`contract-job-record-case-view.md`](../../architecture/contracts/contract-job-record-case-view.md)
> - 사용자 command: [`contracts/contract-case-command.md`](contracts/contract-case-command.md)
> - 그 뒤 결정들: [`decisions/README.md`](decisions/README.md)
>
> **용어.** `§4-모듈5` = `module-architecture.md` §4의 「모듈 5. `case`」 절. `W5`/`W6`/`W7` = 프로젝트 5·6·7주차. `Mock Pack` = `data/mock/` 아래 시나리오별 가짜 데이터(JSON) 묶음(`docs/mock/01_mock_dataset_overview.md`). `ERD 리뷰 항목 ①/③` = `codex/erd` 브랜치의 ERD(DB 표 관계도) 초안을 리뷰할 때 나온 항목 번호(각 결정 문서 머리말).

> **작성일 2026-09-13 · 작성 담당 유소연(`case`) · 문서 성격: 1차 구현 실제 코드의 상세 설계 기록.**
> 이 문서는 `docs/modules/case/checklists/phase1-completion-checklist.md`(1차 완료 정의·범위)와
> `src/daesingo/case/README.md`(공개 함수 요약)의 상세판이다. 팀 공지된 "1차 구현" 기준
> ("각자 Architecture + Canonical Contract + Mock + 1차 완료 체크리스트를 기준으로 자기
> Tech Spec과 구현을 진행한다")에 따라 작성했다.
> 근거: `docs/architecture/module-architecture.md` §4-모듈5 · `docs/architecture/contracts/contract-job-record-case-view.md` ·
> `docs/architecture/contracts/contract-job-execution.md` · `docs/architecture/contracts/contract-correction-record.md` ·
> `docs/modules/case/decisions/*.md` · `docs/modules/case/checklists/phase1-completion-checklist.md`.

> **2026-09-19 갱신 — W5/W6 Real E2E 이후.** 아래 §6·§7·§8·§9는 2026-09-13(1차 구현) 시점 기준으로 남아있다. 2026-09-18 이후 `RealAdapter` 실제 호출 배선, `service.py::get_view(case_id, *, store)`, `store.py::CaseStore`가 추가됐다.
>
> 다음 우선순위/미결 항목은 §9를 반복 갱신하는 대신 `docs/modules/case/design-refinement-w7-baseline.md`로 이관한다.

---

## 1. 이 모듈이 하는 일 (§4-모듈5 요약)

**사용자 의도와 현재 진행 상태를 소유하고, 어떤 작업을 언제 발주하고 무엇만 다시 실행할지 결정하는
유일한 지휘자다.**

- 자연어 단서 구조화 + 사용자 수정
- 상태 기계
- Candidate selection
- **Job Intent 생성**
- rerun_policy
- `EvidenceNeeds` → Job Intent mapping
- stale result의 domain 적용 여부 판단
- `CaseView` projection
- `USER_REVIEWED` 상태
- correction learning log export

### 알면 안 되는 것 (§4-모듈5 ⑦, 코드에도 그대로 적용)

업로드 규정 수치 / OCR threshold / prompt 내용 / Overlay가 왜 우선인지 같은 evidence 정책 로직 /
codec·ffmpeg 세부 / Worker lease·heartbeat 구현. 이 목록의 리터럴 문자열은 `scripts/check_boundaries.py`가
소유하며 이 문서나 코드에 복제하지 않는다(복제하면 CI 자체가 걸린다).

### 소유 데이터 (§4-모듈5 ⑤)

| 데이터 | Owner |
| --- | --- |
| `Case`(상태 기계, hints, manifest_summary) | case |
| `Selection`(candidate 선택 + `selection_rev`) | case |
| `CorrectionRecord` | case |
| workflow stage / `USER_REVIEWED` | case |
| Job 발주 의도 / rerun policy (`JobRecord`) | case |
| Job execution lifecycle (`JobExecution`) | common/runtime — 구현은 recording |
| Evidence 값 | evidence — case는 복사해 소유하지 않는다 |

---

## 2. 상태 기계

```
INTAKE → SEARCHING → CANDIDATE_REVIEW → EVIDENCE_REVIEW → READY
```

- `TIME_HINT_EDIT`, major `TIMELINE_REBASE`, candidate 변경 등에 의한 역행 전이는 §4-모듈5 ②가
  명시하지만, **1차 구현 범위에서는 만들지 않았다**(이후 추가됨 — `domain.py`의 `regress_to_searching()` · `leave_ready()`) — happy path(`scenario_happy_001`)에 필요한
  전진 전이 + 빈 후보 배열 처리만 구현했다(§6 참고).
- `case_rev`는 상태 전이마다 증가시키되, `INTAKE → SEARCHING` 전이만 예외다: `scenario_happy_001`의
  `case_views[0]`(stage=SEARCHING)과 `job_h001_search`(COARSE_SEARCH)가 둘 다 `case_rev:1`로 남아있는
  것을 근거로, 이 전이는 "요청 시점 리비전"이 아직 바뀔 내용이 없어 `case_rev`를 올리지 않는다
  (`domain.py::CaseAggregate.start_search()` 주석 참고 — fixture 역산 결정이며, 향후 §7 원문과
  재대조가 필요하면 이 문서를 갱신한다).
- 빈 후보 배열(`candidates=[]`)은 실패가 아니다(`scenario_empty_001` 원칙). **지금 코드는 `CANDIDATE_REVIEW`로 전진하고**
  `search.no_candidates`(비차단 INFO) notice를 붙인다(`domain.py::receive_candidates()` docstring). 1차 구현 당시 이 줄은
  「`SEARCHING`에 머문다」로 적혀 있었으나 코드와 반대였다.

### 내부 데이터 모델 (코드 수준 — DB 스키마 아님)

아래는 **1차 구현 시점 예시**다. 그때는 영속성 계층이 없어 순수 Python 객체(`dataclass`)였다. 지금은 필드가 더 많고
MySQL 저장(`store_mysql.py::MySQLCaseRepository`, `migrations/case/`)도 있다 — 현재 필드는 `domain.py`의 `Candidate` · `CaseAggregate`를 본다.

```python
@dataclass
class Candidate:
    candidate_id: str
    at: str | None
    at_provenance: str | None
    observed: str
    thumb_ref: str | None
    selected: bool = False
    timeline_revision: int = 1
    stale_revision: bool = False
    stale_revision_label_key: str | None = None
    situation_confirmation: str = "NOT_ASKED"

@dataclass
class CaseAggregate:
    case_id: str
    case_rev: int = 1
    stage: str = "INTAKE"
    user_reviewed: bool = False
    hints: dict[str, Any]
    manifest_summary: dict[str, Any]
    selection_rev: int = 0          # 단일 현재값 — 아래 §4 참고
    candidates: list[Candidate]
    job_records: list[dict[str, Any]]        # JobRecord, append-only
    correction_records: list[dict[str, Any]] # CorrectionRecord, append-only
```

`CaseView`는 이 상태 + 다른 모듈 산출물의 projection이다(§4-모듈5 ⑥) — `CaseAggregate` 자체를 밖으로
노출하지 않는다.

---

## 3. Job Intent — `JobRecord` 발주 규칙

핵심 규칙(`contract-job-execution.md` 2026-09-13 명확화 그대로): **사용자의 새 Intent는 항상 새
`job_id`로 발주한다.** `RETRY_PLATE_READ`/`RETRY_SEARCH`/재개("이어서 찾기")도 전부 새 `job_id`다.
같은 `job_id` + `attempt` 증가는 자동 인프라 재시도(`STALE`)뿐이며, 그건 `common/runtime`의 책임이라
이 모듈 코드에는 그 분기가 아예 없다(`CaseAggregate.next_job_id()`가 매번 `uuid4` 기반 새 id만 생성).

재개 시 새 `job_id`를 쓰기로 한 근거는
`docs/modules/case/decisions/job-resume-identity-policy.md`(2026-09-13, ERD 리뷰 항목 ③에서 확정)에
있다 — 요약: `JobRecord`는 "작업 1건당 하나의 Intent 기록"이라 재요청 자체가 새 Intent이고, 기존
`actions[] → 발주` 컨벤션과의 일관성을 위해서다. 아직 실제 데모 fixture는 없다(비차단 항목, 차기
라운드 반영 예정).

지원하는 `JobRecord.kind`(1차 구현 때 5종, 지금 9종 — `jobs.py::JOB_KINDS`): `COARSE_SEARCH` · `PLATE_READ` · `OVERLAY_TIME_READ` · `FINE_VERIFY` ·
`REPORT_VIDEO_EXPORT` · `PLATE_IMAGE_EXPORT` · `HINT_EXTRACT` · `INCIDENT_CLIP_BUILD` · `CANDIDATE_VIDEO_PREVIEW`. `JobRecord`는 발주 의도만 담고 실행 상태(`JobExecution`)는 담지 않는다
(append-only).

---

## 4. `selection_rev` — 단일 현재값, 이력 테이블 없음

`docs/modules/case/decisions/case-selection-revision-persistence.md`(2026-09-13, ERD 리뷰 항목 ①에서
확정)에 따라 `selection_rev`는 `Case` aggregate 내부의 **단일 현재값**이다. 별도 "선택 이력" 테이블은
만들지 않는다.

- `case_rev`와 별개 카운터로, 후보 선택(`select_candidate()`) 시점에만 증가한다.
- **`CaseView`에는 절대 노출하지 않는다** — 지금까지 web·eval 어느 쪽도 외부 노출을 요청한 적이
  없고, `case-view` 스키마도 이 필드를 포함하지 않는다.
- 과거 선택 맥락이 필요하면 `CorrectionRecord`/`EvidenceRecord`가 생성 시점 `selection_rev`를
  immutable snapshot으로 갖고 `supersedes_ref` 체인으로 추적 가능한 기존 구조로 충분히 커버된다 —
  그래서 새 이력 구조를 만들지 않았다.

`correction.py::apply_correction()`은 correction 시점의 `case.selection_rev`를 그대로 스냅샷하고,
correction 자체는 `selection_rev`를 증가시키지 않는다(그 버그가 실제로 났던 지점 — 이슈 #39
Required-3, `scenario_correction_rerun_001` v4 노트 참고). 같은 `target_field`의 최신
`CorrectionRecord`를 `supersedes_ref`로 체이닝한다(`correction.py`, correction-record/v1.1 §3).

---

## 5. `CaseView` projection

`build_case_view()`가 web의 유일한 read dependency(작성 당시 `case-view/v1.3`, 지금은 `view.py::CONTRACT_VERSION` = `case-view/v1.12`)를 만든다. 원칙(§4-모듈5 ⑥):
evidence/readout 값을 **복사해서 그대로 소유하지 않는다** — 매번 다시 조립한다. 신고 요건 판정
(readiness/checks)이나 번호판 OCR 같은 evidence/readout의 판단 자체는 여기서 재계산하지 않고 그대로
옮겨 담기만 한다.

내부 흐름: `CaseAggregate` 상태 + (아직 코드 없는 recording/search/readout/evidence의 산출물을 대신
읽는) `MockFixtureAdapter` 결과를 조합 → `progress[]` / `candidates[]` / `evidence` /
`requirements_evidence` / `requirements_package` / `package` 조립. (2026-11-08 현재: 실제 모듈을 부르는 `adapters.py`의 `RealAdapter` · 저장 관찰을 읽는 `stored_observation.py`가 있고, `service.build_view_from_adapter()`가 조립한다.)

`info_state` 파생 규칙(`labels.py` — 예: `observability_to_info_state()`는 observability 값을 `info_state`로 바꾸고 모르는 값은
`INFO_UNKNOWN`으로 둔다. 이전에 적혀 있던 `resolution_status_to_info_state()`는 코드에 없다)은 **happy-path fixture 하나에서 관찰된 패턴을 재현한 것**이지 B절 §7 원문 전체를
옮긴 것이 아니다 — 특히 `location_display`를 항상 `INFO_NEEDS_REVIEW`로 고정하는 규칙은 다른
시나리오(GPS로 확정된 위치 등)로 확장하기 전에 원문과 재대조가 필요하다고 `labels.py`/`view.py`
docstring에 명시해뒀다. (2026-11-08 현재: 2026-09-14에 CaseView 계약 B절 §7(「Enum / State」 절의 `info_state` 파생 규칙) 원문대로 다시 구현했다 — `labels.py` docstring. 위치는 대표값이 `user_hint`일 때만 `INFO_NEEDS_REVIEW`다.)

---

## 6. 1차 구현이 실제로 재현하는 것 / 재현하지 않는 것

### 재현한다 (코드 + 테스트로 검증됨)

1. `CaseView` 상태 기계의 **전진 전이** 전부(`INTAKE → SEARCHING → CANDIDATE_REVIEW →
   EVIDENCE_REVIEW → READY`) + 빈 후보 배열 처리.
2. `JobRecord` 발주 규칙(신규 Intent = 항상 새 `job_id`, kind별 wrapper 7종 — 지금은 `issue_overlay_time_reread`까지 8종).
3. `CaseView` projection이 evidence/readout/recording 값을 복사 소유하지 않고 안전하게 가공해
   내보내는 것 — `scenario_happy_001`의 `case_views[-1]`(READY 스냅샷)과 `evidence`/
   `requirements_evidence`/`requirements_package`/`package.*` 필드가 **바이트 단위로 일치**함을
   `tests/case/test_scenario_happy_smoke.py`가 검증한다.
4. `CorrectionRecord` 생성(`selection_rev` 스냅샷 + `supersedes_ref` 체인).

### 재현하지 않는다 (§11 1차 완료 제외 범위 — 체크리스트와 동일)

> 1차 구현 시점 목록이다. 역행 전이(`regress_to_searching()` · `leave_ready()`), MySQL 저장(`store_mysql.py`),
> FastAPI 라우트(`src/daesingo/api/routes_*.py`)는 그 뒤 생겼다.

- 역행 전이(`TIME_HINT_EDIT`, major `TIMELINE_REBASE` 등).
- FastAPI 엔드포인트 배선 / 영속성(MySQL) — 지금은 순수 Python 객체로만 존재.
- `selection_rev` 이력 테이블, "이어서 찾기" 실제 fixture(방향은 확정, 데모 fixture는 없음).
- happy path 외 6개 시나리오(후보 0개 / low confidence / GPS 없음 / Timestamp conflict / Plate
  abstain / Timeout·partial result)의 표시 규칙.
- 실제 AI/OCR/Search 성능 — Mock Pack 자체의 목적이 아니다.
- Worker lease/heartbeat 등 실행 lifecycle 구현 — `common/runtime` 담당.
- 신고 요건 계산 로직, 시각 출처 우선순위 로직 — `evidence` 담당, case는 결과만 read-through.

---

## 7. 공개 함수 시그니처

`src/daesingo/case/README.md` "공개 함수" 절의 요약과 동일한 확정본이며, 이 문서가 상세 근거를
담는다. §4-모듈5 「Public Capability」의 함수 이름은 설계 시점 placeholder였고 아래가 그걸 대체한다.
다른 모듈은 **이 함수들만** 호출한다 — `MockFixtureAdapter`는 예외(1차 구현 한정 내부 stand-in).

`service.py::get_view(case_id, *, store, notices=None, now=None)`가 web이 실제로 부를 단일 진입점으로 추가됐다. 아래 표의 개별 함수 목록도 여전히 유효하다.

| 파일 | 함수/메서드 | 시그니처 | 설명 |
| --- | --- | --- | --- |
| `domain.py` | `CaseAggregate.intake` | `(case_id: str, hints: dict, manifest_summary: dict) -> CaseAggregate` | Case 생성 |
| `domain.py` | `.start_search` | `() -> None` | INTAKE → SEARCHING (`case_rev` 미증가) |
| `domain.py` | `.receive_candidates` | `(candidates: list[Candidate], *, job_id: str \| None = None) -> bool` | 빈 배열이어도 CANDIDATE_REVIEW로 전진. 기다리지 않는 job의 결과면 `False` |
| `domain.py` | `.select_candidate` | `(candidate_id: str) -> None` | CANDIDATE_REVIEW → EVIDENCE_REVIEW, `selection_rev` +1 |
| `domain.py` | `.mark_ready` | `(*, report_package: dict \| None) -> None` | EVIDENCE_REVIEW → READY. ReportPackage가 없으면 거부 |
| `domain.py` | `.next_job_id` | `(kind: str) -> str` | 항상 새 job_id |
| `jobs.py` | `issue_coarse_search` | `(case, *, scope_ref, input_fingerprint, scope=None) -> JobRecord` | `scope`를 주면 case에 남긴다 — 1차 구현 뒤 추가 |
| `jobs.py` | `issue_plate_read` | `(case, *, input_fingerprint, force_rerun=False) -> JobRecord` | |
| `jobs.py` | `issue_overlay_time_read` | `(case, *, input_fingerprint) -> JobRecord` | |
| `jobs.py` | `issue_fine_verify` | `(case, *, input_fingerprint) -> JobRecord` | |
| `jobs.py` | `issue_report_video_export` | `(case, *, input_fingerprint) -> JobRecord` | |
| `jobs.py` | `issue_resume_search` | `(case, *, scope_ref, input_fingerprint) -> JobRecord` | "이어서 찾기", 새 job_id + `force_rerun=True` |
| `jobs.py` | `issue_plate_reread` | `(case, *, input_fingerprint) -> JobRecord` | `EvidenceNeeds`의 `PLATE_REREAD` 자동 발주 |
| `jobs.py` | `issue_overlay_time_reread` | `(case, *, input_fingerprint) -> JobRecord` | `EvidenceNeeds`가 `OVERLAY_TIME_OCR`를 요청할 때 자동 발주(`force_rerun=True`) — 1차 구현 뒤 추가 |
| `correction.py` | `apply_correction` | `(case, *, kind, target_field, previous_value, new_value) -> CorrectionRecord` | `selection_rev` 스냅샷 + supersede |
| `view.py` | `build_case_view` | `(case, *, evidence_record=None, requirement_report_evidence=None, requirement_report_package=None, report_package=None, job_executions=None, notices=None, plate_read_status=None, overlay_time_read_status=None, current_timeline_revision=None, plate_readouts=None, visual_evidence_decision=None, visual_verify_status=None, independent_facts=None) -> dict` | `CaseView`(작성 당시 `case-view/v1.3`, 지금 `CONTRACT_VERSION` = `case-view/v1.12`) |
| `adapters.py` | `MockFixtureAdapter` | `(mock_root: Path, scenario_id: str)` + `get_candidate_events/get_evidence_record/get_requirement_report/get_report_package` | **공개 API 아님** — 실제 모듈 구현 시 같은 시그니처의 실제 호출 어댑터로 교체(→ 지금 `adapters.py::RealAdapter`) |

---

## 8. 검증 현황

- `pytest tests/case` → **54 passed**(2026-09-19 당시 기록 — 1차 구현 시점 12건에서 시나리오 스모크 테스트 등이 늘어남. 지금 건수와 다르다). Real E2E 병합 후에는 `pytest tests/case/` 기준으로도 검증 범위가 확장됐다. 지금 실행 방법은 `python -m pytest tests/case -q`(모듈 README 「한눈에 보기」).
- `python3 scripts/check_boundaries.py --only=boundaries`(당시 문서엔 `--only=boundary`로 적혔으나 키 이름은 `boundaries`) → **PASS — 경계·계약 정합성 위반 0건.**(2026-09-19 재확인)
- `tests/case/test_scenario_happy_smoke.py`가 `data/mock/case/scenario_happy_001.json`의
  `case_views[0]`(SEARCHING)과 `case_views[-1]`(READY)을 실제 코드 실행 결과와 대조 — READY 스냅샷은
  `evidence`/`requirements_evidence`/`requirements_package`/`package.*` 필드가 완전 일치함을 확인했다.
  (`case_rev`처럼 그 fixture 고유의 누적 이력값은 의도적으로 비교 대상에서 제외했다 — 코드 주석 참고.)

~~`src/`에 아직 `pyproject.toml`이 없어 `tests/conftest.py`가 `sys.path`에 `src/`를 얹는 임시 조치를
쓴다~~ → 지금은 루트 `pyproject.toml`에 `pythonpath = ["src"]` · `testpaths = ["tests"]`가 있다. 루트 `conftest.py`도
아직 `src/` · `tests/`를 `sys.path`에 올린다(그 파일 docstring에 「한시적」이라고 적혀 있다).

---

## 9. 다음 단계 (2026-09-13 시점 기록 — 최신 우선순위는 `design-refinement-w7-baseline.md` 참고)

⚠️ 이 목록은 1차 구현 직후 기록이다. Real E2E 이후 재우선순위화된 최신 목록은 `docs/modules/case/design-refinement-w7-baseline.md`를 따른다.

- ~~FastAPI 엔드포인트로 `domain`/`jobs`/`correction`/`view` 함수들을 감싸는 배선.~~ → 생김(`src/daesingo/api/routes_*.py`).
- ~~영속성 계층(MySQL) — 현재는 순수 메모리 객체.~~ → 생김(`store_mysql.py`, `migrations/case/`).
- 역행 전이(`TIME_HINT_EDIT`, major `TIMELINE_REBASE`) 구현. → `regress_to_searching()`(`TIME_HINT_EDIT` 등 → `SEARCHING`) · `leave_ready()`(`READY`에서 값 정정 · 상황 응답 → `EVIDENCE_REVIEW`)로 생김. major `TIMELINE_REBASE`는 아직 구현하지 않았다(`domain.py` 모듈 docstring).
- happy path 외 6개 시나리오의 `CaseView` 표시 규칙.
- `selection_rev` 관련 실제 재사용(§4) 검증, "이어서 찾기" 데모 fixture.
- ~~repo root 공용 `pyproject.toml` 도입 시 `tests/conftest.py`의 `sys.path` 임시 조치 제거.~~ → `pyproject.toml`은 생김(`pythonpath = ["src"]`). 루트 `conftest.py`의 `sys.path` 조치는 아직 남아 있다.
