# `case` Tech Spec — Workflow / Orchestration (Owner: 유소연)

> **작성일 2026-09-13 · 작성 담당 유소연(`case`) · 문서 성격: 1차 구현 실제 코드의 상세 설계 기록.**
> 이 문서는 `docs/modules/case/checklists/phase1-completion-checklist.md`(1차 완료 정의·범위)와
> `src/daesingo/case/README.md`(공개 함수 요약)의 상세판이다. 팀 공지된 "1차 구현" 기준
> ("각자 Architecture + Canonical Contract + Mock + 1차 완료 체크리스트를 기준으로 자기
> Tech Spec과 구현을 진행한다")에 따라 작성했다.
> 근거: `docs/architecture/module-architecture.md` §4-모듈5 · `docs/architecture/contracts/contract-job-record-case-view.md` ·
> `docs/architecture/contracts/contract-job-execution.md` · `docs/architecture/contracts/contract-correction-record.md` ·
> `docs/modules/case/decisions/*.md` · `docs/modules/case/checklists/phase1-completion-checklist.md`.

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
  명시하지만, **1차 구현 범위에서는 만들지 않는다** — happy path(`scenario_happy_001`)에 필요한
  전진 전이 + 빈 후보 배열 처리만 구현했다(§6 참고).
- `case_rev`는 상태 전이마다 증가시키되, `INTAKE → SEARCHING` 전이만 예외다: `scenario_happy_001`의
  `case_views[0]`(stage=SEARCHING)과 `job_h001_search`(COARSE_SEARCH)가 둘 다 `case_rev:1`로 남아있는
  것을 근거로, 이 전이는 "요청 시점 리비전"이 아직 바뀔 내용이 없어 `case_rev`를 올리지 않는다
  (`domain.py::CaseAggregate.start_search()` 주석 참고 — fixture 역산 결정이며, 향후 §7 원문과
  재대조가 필요하면 이 문서를 갱신한다).
- 빈 후보 배열(`candidates=[]`)은 실패가 아니다 — `SEARCHING`에 머물고 전이하지 않는다
  (`scenario_empty_001` 원칙). 비차단 INFO notice로 재검색을 유도하는 표시 규칙은 1차 제외 범위.

### 내부 데이터 모델 (코드 수준 — DB 스키마 아님)

영속성 계층이 아직 없으므로 아래는 순수 Python 객체(`dataclass`)이지, DB 테이블 설계가 아니다.

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

지원하는 `JobRecord.kind`: `COARSE_SEARCH` · `PLATE_READ` · `OVERLAY_TIME_READ` · `FINE_VERIFY` ·
`REPORT_VIDEO_EXPORT`. `JobRecord`는 발주 의도만 담고 실행 상태(`JobExecution`)는 담지 않는다
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
  immutable snapshot으로 갖고 `supersedes_id` 체인으로 추적 가능한 기존 구조로 충분히 커버된다 —
  그래서 새 이력 구조를 만들지 않았다.

`correction.py::apply_correction()`은 correction 시점의 `case.selection_rev`를 그대로 스냅샷하고,
correction 자체는 `selection_rev`를 증가시키지 않는다(그 버그가 실제로 났던 지점 — 이슈 #39
Required-3, `scenario_correction_rerun_001` v4 노트 참고). 같은 `target_field`의 최신
`CorrectionRecord`를 `supersedes_id`로 체이닝한다.

---

## 5. `CaseView` projection

`build_case_view()`가 web의 유일한 read dependency(`case-view/v1.3`)를 만든다. 원칙(§4-모듈5 ⑥):
evidence/readout 값을 **복사해서 그대로 소유하지 않는다** — 매번 다시 조립한다. 신고 요건 판정
(readiness/checks)이나 번호판 OCR 같은 evidence/readout의 판단 자체는 여기서 재계산하지 않고 그대로
옮겨 담기만 한다.

내부 흐름: `CaseAggregate` 상태 + (아직 코드 없는 recording/search/readout/evidence의 산출물을 대신
읽는) `MockFixtureAdapter` 결과를 조합 → `progress[]` / `candidates[]` / `evidence` /
`requirements_evidence` / `requirements_package` / `package` 조립.

`info_state` 파생 규칙(`observability_to_info_state()`, `resolution_status_to_info_state()`,
`labels.py`)은 **happy-path fixture 하나에서 관찰된 패턴을 재현한 것**이지 B절 §7 원문 전체를
옮긴 것이 아니다 — 특히 `location_display`를 항상 `INFO_NEEDS_REVIEW`로 고정하는 규칙은 다른
시나리오(GPS로 확정된 위치 등)로 확장하기 전에 원문과 재대조가 필요하다고 `labels.py`/`view.py`
docstring에 명시해뒀다.

---

## 6. 1차 구현이 실제로 재현하는 것 / 재현하지 않는 것

### 재현한다 (코드 + 테스트로 검증됨)

1. `CaseView` 상태 기계의 **전진 전이** 전부(`INTAKE → SEARCHING → CANDIDATE_REVIEW →
   EVIDENCE_REVIEW → READY`) + 빈 후보 배열 처리.
2. `JobRecord` 발주 규칙(신규 Intent = 항상 새 `job_id`, kind별 wrapper 7종).
3. `CaseView` projection이 evidence/readout/recording 값을 복사 소유하지 않고 안전하게 가공해
   내보내는 것 — `scenario_happy_001`의 `case_views[-1]`(READY 스냅샷)과 `evidence`/
   `requirements_evidence`/`requirements_package`/`package.*` 필드가 **바이트 단위로 일치**함을
   `tests/test_scenario_happy_smoke.py`가 검증한다.
4. `CorrectionRecord` 생성(`selection_rev` 스냅샷 + `supersedes_id` 체인).

### 재현하지 않는다 (§11 1차 완료 제외 범위 — 체크리스트와 동일)

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

| 파일 | 함수/메서드 | 시그니처 | 설명 |
| --- | --- | --- | --- |
| `domain.py` | `CaseAggregate.intake` | `(case_id: str, hints: dict, manifest_summary: dict) -> CaseAggregate` | Case 생성 |
| `domain.py` | `.start_search` | `() -> None` | INTAKE → SEARCHING (`case_rev` 미증가) |
| `domain.py` | `.receive_candidates` | `(candidates: list[Candidate]) -> None` | 후보 있으면 CANDIDATE_REVIEW로 전진 |
| `domain.py` | `.select_candidate` | `(candidate_id: str) -> None` | CANDIDATE_REVIEW → EVIDENCE_REVIEW, `selection_rev` +1 |
| `domain.py` | `.mark_ready` | `() -> None` | EVIDENCE_REVIEW → READY |
| `domain.py` | `.next_job_id` | `(kind: str) -> str` | 항상 새 job_id |
| `jobs.py` | `issue_coarse_search` | `(case, *, scope_ref, input_fingerprint) -> JobRecord` | |
| `jobs.py` | `issue_plate_read` | `(case, *, input_fingerprint, force_rerun=False) -> JobRecord` | |
| `jobs.py` | `issue_overlay_time_read` | `(case, *, input_fingerprint) -> JobRecord` | |
| `jobs.py` | `issue_fine_verify` | `(case, *, input_fingerprint) -> JobRecord` | |
| `jobs.py` | `issue_report_video_export` | `(case, *, input_fingerprint) -> JobRecord` | |
| `jobs.py` | `issue_resume_search` | `(case, *, scope_ref, input_fingerprint) -> JobRecord` | "이어서 찾기", 새 job_id + `force_rerun=True` |
| `jobs.py` | `issue_plate_reread` | `(case, *, input_fingerprint) -> JobRecord` | `EvidenceNeeds`의 `PLATE_REREAD` 자동 발주 |
| `correction.py` | `apply_correction` | `(case, *, kind, target_field, previous_value, new_value) -> CorrectionRecord` | `selection_rev` 스냅샷 + supersede |
| `view.py` | `build_case_view` | `(case, *, evidence_record=None, requirement_report_evidence=None, requirement_report_package=None, report_package=None, running_jobs=None, notices=None) -> dict` | `CaseView`(`case-view/v1.3`) |
| `adapters.py` | `MockFixtureAdapter` | `(mock_root: Path, scenario_id: str)` + `get_candidate_events/get_evidence_record/get_requirement_report/get_report_package` | **공개 API 아님** — 실제 모듈 구현 시 같은 시그니처의 실제 호출 어댑터로 교체 |

---

## 8. 검증 현황

- `pytest src/daesingo/case/tests/ -v` → **12 passed** (도메인 6 + jobs 4 + happy-path smoke 2).
- `python3 scripts/check_boundaries.py --only=boundary` → **PASS — 경계·계약 정합성 위반 0건.**
- `tests/test_scenario_happy_smoke.py`가 `data/mock/case/scenario_happy_001.json`의
  `case_views[0]`(SEARCHING)과 `case_views[-1]`(READY)을 실제 코드 실행 결과와 대조 — READY 스냅샷은
  `evidence`/`requirements_evidence`/`requirements_package`/`package.*` 필드가 완전 일치함을 확인했다.
  (`case_rev`처럼 그 fixture 고유의 누적 이력값은 의도적으로 비교 대상에서 제외했다 — 코드 주석 참고.)

`src/`에 아직 `pyproject.toml`이 없어 `tests/conftest.py`가 `sys.path`에 `src/`를 얹는 임시 조치를
쓴다 — 팀이 repo root 공용 패키징을 도입하면 걷어낼 항목이다(§9).

---

## 9. 다음 단계 (이번 라운드 이후)

- FastAPI 엔드포인트로 `domain`/`jobs`/`correction`/`view` 함수들을 감싸는 배선.
- 영속성 계층(MySQL) — 현재는 순수 메모리 객체.
- 역행 전이(`TIME_HINT_EDIT`, major `TIMELINE_REBASE`) 구현.
- happy path 외 6개 시나리오의 `CaseView` 표시 규칙.
- `selection_rev` 관련 실제 재사용(§4) 검증, "이어서 찾기" 데모 fixture.
- repo root 공용 `pyproject.toml` 도입 시 `tests/conftest.py`의 `sys.path` 임시 조치 제거.
