# 서어진 (`search`) — 1차 완료 체크리스트

> **목적:** 공용 Mock Dataset과 Final Data Contract를 기준으로, 1차 Mock E2E 통합 전에 `search`가 어디까지 준비되면 **"통합 가능한 상태"**인지 정의한다. 내부 구현 방식(프롬프트·모델·chunk·알고리즘)은 정의하지 않는다.
> **기준 시점:** W4/W5 초기 Mock 통합. 최종 성능·모든 edge case·challenger 구현은 범위 밖.
> **근거 자료:** `product-spec.md` · `module-architecture.md` v4 §4-모듈2 · `ownership.md` §3(서어진) · `contract-analysis-scope.md` · `contract-analysis-run-candidate-event.md` · `contract-visual-evidence.md` · `docs/mock/01~04` · `data/mock/search/*`

---

## 회의에서 먼저 볼 핵심 (3~5)

1. `scenario_happy_001`의 `AnalysisScope`(scope_h001)를 입력받아 **`AnalysisRun`(SUCCEEDED) + `CandidateEvent`(rank1) + `VisualEvidence`(OBSERVED)**를 계약 형식대로 출력할 수 있다.
2. `scenario_partial_001`에서 **`AnalysisRun.outcome=PARTIAL` + `issues[]`(1건) + target `AMBIGUOUS`인 `VisualEvidence`**를 만들어, 일부 실패에도 usable candidate가 살아있음을 보인다.
3. `run_id` / `candidate_id`가 case·eval fixture와 **동일한 ID로 물린다** (`cand_h001.run_id == run_h001_search`).
4. `visual_event_type`이 **v4 baseline 4종 enum**만 쓰고 옛 이름(`LANE_CHANGE`)이 없다.
5. Consumer(case·eval)가 바로 읽을 수 있는 **정상/부분 출력 JSON**을 제시한다.

---

## 담당 범위

- **Owner:** 서어진
- **주 담당 Module:** `search`
- **보조 담당 Module:** 없음
- **Producer로 책임지는 Contract:** `AnalysisRun` + `CandidateEvent` (`analysis-run-candidate-event/v1`) · `VisualEvidence` (`visual-evidence/v1.0`)
- **Consumer로 사용하는 Contract:** `AnalysisScope` (`analysis-scope/1.0.0` — 입력) · recording 자산 참조(`timeline_id` / `input_ref` / `thumbnail_ref` = opaque id)
  - `AnalysisScope`는 **초안을 case(유소연)와 공동 작성**하지만 런타임 Producer는 case, `search`는 Consumer다.
- **1차 통합에서 내 출력의 주요 Consumer:** `case`(유소연 — candidate 선택·display) · `eval`(김대원 — Recall/span/비용 채점) · `evidence`(김준영)·`readout`(신유민)은 `VisualEvidence` projection 소비
- **1차 통합에서 내가 의존하는 주요 Producer:** `case`(`AnalysisScope`) · `recording`(정철원 — `timeline_id`·frame/input ref)

---

## 1차 완료 정의

> `scenario_happy_001`·`scenario_partial_001` 기준으로 `AnalysisScope` 입력을 계약 형식대로 받아 Candidate 탐색과 Fine 관찰을 수행하고, Final Data Contract에 맞는 **불변 `AnalysisRun` + 순위화된 `CandidateEvent[]` + `VisualEvidence`** 출력을 생성할 수 있으며, `PARTIAL`(issues 보존)·target `AMBIGUOUS`·`SUCCEEDED+candidates=[]` 같은 부분 성공/불확실 상태를 계약대로 구분해 보존하고, Merge 회의에서 case·eval이 같은 `run_id`/`candidate_id`로 바로 연결할 수 있는 출력 JSON과 contract test 결과를 제시할 수 있으면 1차 완료로 본다. (실제 AI 정확도·비용 최적화·challenger는 범위 밖.)

---

## 구현 체크리스트

> **셀프체크 (2026-09-07):** 근거 표기 — `self-check`=`python tests/test_search_stub.py`가 assert · `stub`=구조상 자명 · `경계`=`check_boundaries.py` PASS · `[ ] 후속`=실제 로직/fixture 필요.

### A. Input

- [x] `AnalysisScope`를 계약 형식(`scope_id`·`time_ranges`≥1·`target_event_types`≥1·`hint`·`budget`)대로 받을 수 있다. — self-check
- [x] `target_event_types`가 **복수값일 수 있음**을 전제로 처리한다(단일값 가정 금지 — ADR-003 결정3). — stub이 `target_event_types`를 소비하지 않아 개수 가정 자체가 없음
- [x] `hint.vehicle`/`hint.free_text`가 `null`이어도 정상 동작한다. — stub이 hint 미소비, happy fixture `free_text=null`로 통과
- [ ] `budget`을 scope **전체 총합**으로 해석한다(per-time_range 분배는 search 내부 책임). — 후속: 실제 탐색 로직 필요(stub은 budget 미해석)
- [x] `case_id`·`selection_rev`·위치·파일/asset 참조가 입력에 **없음을 전제**한다(있다고 가정하는 코드가 없다). — stub은 `scope_id`만 읽음
- [x] happy/partial 두 `AnalysisScope` fixture를 로딩(또는 동일 효과)해 실행 진입점에 넣을 수 있다. — self-check가 두 scope로 호출

### B. Core Flow

- [x] Candidate 탐색(Coarse)이 `AnalysisScope` → `CandidateEvent[]`를 만든다. — self-check(`search_candidates`)
- [x] Fine/Classification 관찰이 `VisualEvidence`를 만든다(candidate 연결 또는 candidate-independent 모두 가능). — self-check(`verify_visual`)
- [x] 한 번의 public capability 호출 = 하나의 `AnalysisRun`으로 기록한다. — 호출당 run 1개 반환

### C. Output Contract

**`AnalysisRun`**
- [x] `run_id`·`operation`·`input_ref{kind,ref}`·`implementation`·`outcome`·`started_at`·`completed_at`·`issues[]`·`usage_refs[]`·`usage_summary`·`contract_version` 필수 필드를 모두 생성한다. — self-check(`RUN_REQUIRED`)
- [x] `operation`은 `CANDIDATE_SEARCH | VISUAL_VERIFY`만 쓴다(내부 COARSE/FINE 노출 금지). — self-check
- [x] `completed_at >= started_at`. — self-check(datetime 비교)
- [x] `usage_summary.token_usage.total_tokens == input + output`. — self-check
- [x] `contract_version == "analysis-run-candidate-event/v1"`. — self-check

**`CandidateEvent`**
- [x] `candidate_id`·`run_id`·`span{timeline_id,start_ms,end_ms,representative_ms}`·`rank` 필수 필드를 생성한다. — self-check(`CAND_REQUIRED`)
- [x] `candidate.run_id == 자신을 만든 AnalysisRun.run_id`. — self-check
- [x] span 불변조건: `start_ms >= 0`, `start_ms < end_ms`, `start_ms <= representative_ms <= end_ms`. — self-check
- [x] `rank`는 1부터 시작하고 한 Run 안에서 중복이 없다. — self-check
- [x] `event_type_hint`는 있으면 4종 enum이며, **법적 신고 유형으로 쓰지 않는다**. — self-check(4종 enum 검사)

**`VisualEvidence`**
- [x] `schema_version`·`visual_evidence_id`·`run_id`·`input_ref`·`verification`·`primitives[]`·`temporal_facts[]`·`uncertainties[]`·`legal_status` 필수 필드를 모두 생성한다. — self-check(`VE_REQUIRED`)
- [x] `visual_event_type`은 `OBSERVED`일 때만 non-null, 값은 **`SIGNAL`/`CENTER_LINE_CROSSING`/`SOLID_LINE_LANE_CHANGE`/`MOTORCYCLE_HELMET_NON_USE`** 중 하나다. — self-check
- [x] `legal_status`는 항상 존재하고 항상 `null`이다. — self-check
- [x] `primitives`/`temporal_facts`/`uncertainties`는 `null`이 아니라 배열이다(빈 배열 허용). — self-check
- [x] top-level `confidence`를 만들지 않는다(component confidence만). — self-check(`"confidence" not in ve`)

### D. Failure / Uncertainty

- [x] `SUCCEEDED / PARTIAL / FAILED`를 구분한다. — self-check(happy=SUCCEEDED, partial=PARTIAL; FAILED는 fixture 후속)
- [x] `PARTIAL`이면 `issues.length >= 1`이고, 영향 범위를 `scope_ref`로 남긴다. — self-check(issues≥1); `scope_ref`는 partial fixture 충족
- [ ] `FAILED`이면 usable Candidate를 반환하지 않는다. — 후속: `FAILED` fixture 없음
- [ ] `SUCCEEDED + candidates=[]`(정상 탐색했으나 후보 0개)를 **오류가 아닌 정상**으로 표현한다. — 후속: 빈 결과 fixture 없음(범위 밖)
- [ ] `VisualEvidence.verification`의 `OBSERVED / NOT_OBSERVED / UNCERTAIN`을 구분한다(실행 실패를 `UNCERTAIN`으로 위장하지 않는다). — 후속: `NOT_OBSERVED`/`UNCERTAIN` fixture 없음(현재 둘 다 OBSERVED)
- [x] target 미확정을 `association_status=AMBIGUOUS`로 표현하고, 확보된 primitive/temporal_fact는 유지한다. — self-check(partial)

### E. State / Lifecycle

- [x] 완료된 `AnalysisRun`/`VisualEvidence`를 수정하지 않는다(immutable). — stub은 fixture 읽기 전용, 수정 경로 없음
- [ ] 재실행은 기존 결과를 덮지 않고 **새 `run_id`와 새 result**를 만든다. — 후속: 새 run_id 생성은 실제 구현 몫(stub은 결정적으로 같은 fixture 반환)
- [x] `QUEUED/RUNNING/STALE`을 `AnalysisRun`에 넣지 않는다(그건 `JobExecution` 책임). — fixture/출력에 해당 값 없음
- [x] `usage_summary`를 사후 가격 변경으로 재계산해 덮지 않는다. — stub은 재계산 로직 없음

### F. Integration

- [x] case가 `candidate_id`/`rank`로, eval이 `rank`/span으로 내 출력을 실제로 읽을 수 있다. — self-check(해당 필드 존재 확인)
- [x] 정답 하드코딩 **가짜 구현(stub)**으로 위 출력을 낼 수 있다(실제 provider 없이 case·eval이 병행 출발 가능). — `stub.py`
- [x] 내 출력이 **계약 밖 내부 객체**(raw provider payload 등)에 의존하지 않는다. — 출력은 순수 JSON dict(fixture)
- [x] `eval`의 존재·내부를 참조하지 않는다(`if eval_mode` 없음, `import eval` 없음). — 경계(`check_boundaries.py` PASS)

### G. Test / Evaluation

- [x] happy/partial 각각에 대해 출력이 계약 불변조건을 만족하는지 확인하는 최소 contract test가 있다. — `test_search_stub.py`
- [x] `scenario_happy_001`·`scenario_partial_001` fixture와 동일 ID/구조로 출력이 나온다. — self-check(`ve == ve_expected` round-trip)
- [x] eval이 채점에 쓰는 값(`rank`, span, `usage_summary`)을 제공한다. — 출력에 존재
- [x] 실패 case(`PARTIAL` issues, `AMBIGUOUS`)가 테스트로 검증된다. — `test_partial`

### H. Operational (1차 통합에 필요한 최소)

- [x] `usage_summary`에 cost/token/latency를 남긴다(측정 불가 시 `null` 키 유지). — 출력 `usage_summary`에 존재
- [x] `issues[].kind`를 실패 분류 이름으로 기록한다(자유 텍스트 대체 금지). — partial 출력 `issues[].kind=INFRA`. → **taxonomy 확정은 아래 통합 대기 참조.**

---

## Contract별 완료 조건

### `AnalysisRun` + `CandidateEvent` (`analysis-run-candidate-event/v1`)

- [x] `SUCCEEDED`(happy)·`PARTIAL`(partial) 정상 Artifact 생성 가능 — self-check
- [x] Invariant 만족: run immutable · `completed_at>=started_at` · candidate span 3조건 · rank 1-based 무중복 · `PARTIAL⇒issues≥1` — self-check (단 `FAILED⇒candidate 없음`은 FAILED fixture 없어 미재현)
- [ ] `SUCCEEDED+candidates=[]` 표현 가능(현재 fixture엔 없음 — v1 확장 시 대상) — 후속
- [x] Consumer(case·eval)가 `run_id`/`candidate_id`/`rank`로 실제로 읽음 — self-check(필드 존재)
- [x] 예시 fixture(`analysis_run.*`/`candidate_events.*`)와 실제 출력 구조 동일 — self-check(fixture 그대로 반환)

### `VisualEvidence` (`visual-evidence/v1.0`)

- [x] `OBSERVED/MATCHED`(happy)·`OBSERVED/AMBIGUOUS`(partial) Artifact 생성 가능 — self-check
- [x] Invariant 만족: `OBSERVED⇔visual_event_type non-null` · `legal_status==null` · 3개 collection은 배열 · top-level confidence 없음 — self-check
- [ ] `NOT_OBSERVED`/`UNCERTAIN` 표현 가능(현재 fixture엔 없음 — v1 확장 시 대상) — 후속
- [x] Consumer(evidence·readout)가 `visual_event_type`/`target`/`input_ref`를 projection으로 읽음 — self-check(필드 존재)
- [x] 예시 fixture(`visual_evidence.*`)와 실제 출력 구조 동일 — self-check(`ve == ve_expected` round-trip)

> `AnalysisScope`는 Consumer 계약이므로 여기 완료 조건에 넣지 않는다(입력 처리 항목은 A절). 단 **초안 공동 작성 책임**(유소연과)은 유지.

---

## Scenario별 완료 조건

| Scenario | 내 입력 | 내가 할 처리 | 기대 출력 | 완료 기준 |
| --- | --- | --- | --- | --- |
| `scenario_happy_001` | `AnalysisScope`(scope_h001), target `SOLID_LINE_LANE_CHANGE`, hint 흰색 SUV | Candidate 탐색 + Fine 관찰 | `AnalysisRun`(run_h001_search, SUCCEEDED) · `CandidateEvent`(cand_h001, rank1) · `VisualEvidence`(ve_h001, OBSERVED/MATCHED) | 3개 출력이 계약대로 생성, `candidate.run_id`·`ve.run_id`가 run과 일치, `visual_event_type=SOLID_LINE_LANE_CHANGE` |
| `scenario_partial_001` | `AnalysisScope`(scope_p001), target `SIGNAL`, hint 없음 | 일부 범위 실패 하 탐색 + Fine 관찰 | `AnalysisRun`(run_p001_search, **PARTIAL**, issue 1건) · `CandidateEvent`(cand_p001, rank1, score↓) · `VisualEvidence`(ve_p001, OBSERVED/**AMBIGUOUS**) | `outcome=PARTIAL`+`issues≥1`, target `AMBIGUOUS`인데 primitive/temporal_fact 유지, Case가 실패로 죽지 않음 |

> B(결과 없음=`SUCCEEDED+candidates=[]`)·NOT_OBSERVED·FAILED는 이번 Seed에 대표 fixture가 없다(`04_mock_validation_report.md`). 코드는 표현 가능해야 하되 통합 증빙은 happy/partial 두 개로 한다.

---

## Merge 전 셀프 체크 증빙

- [x] 정상 입력 예시 (`AnalysisScope` happy/partial JSON) — `data/mock/search/analysis_scope.{happy,partial}_001.json`
- [x] 정상 출력 JSON (`AnalysisRun` SUCCEEDED + `CandidateEvent` + `VisualEvidence` OBSERVED) — `search_candidates(happy)` + `verify_visual(happy)` 출력 = 해당 fixture
- [x] 부분/불확실 출력 JSON (`AnalysisRun` PARTIAL + issues + `VisualEvidence` AMBIGUOUS) — partial 출력 = 해당 fixture
- [x] contract test 실행 결과 (불변조건 통과 로그) — `python tests/test_search_stub.py` → `PASS`
- [x] ID 정합 확인 결과 (`candidate.run_id == run.run_id`, ve와 candidate가 같은 run) — self-check
- [x] `usage_summary` 값 예시 (token/cost/latency) — `analysis_run.*` 내 존재

> "구현했습니다"는 증빙이 아니다. 위 JSON·테스트 결과로 보인다.

---

## Merge 전 확인 질문 (스스로 답할 수 있어야 함)

1. `scenario_happy_001` 입력이 들어오면 어떤 `AnalysisRun`/`CandidateEvent`/`VisualEvidence`가 나오는지 설명할 수 있는가?
2. case는 내 출력 중 어떤 필드를 쓰는가? (`candidate_id`·`rank`·`span` / `visual_event_type`·`target`)
3. eval은 내 출력 중 무엇으로 채점하는가? (`rank`·span·`usage_summary`)
4. `PARTIAL`일 때 `issues[]`와 `SUCCEEDED+candidates=[]`를 서로 다르게 표현하는가?
5. `visual_event_type`에 옛 이름(`LANE_CHANGE`)이나 신고 유형이 섞이지 않는가?
6. 실제 provider가 없는 지금, 어떤 stub이 출력을 대신 만들고 있는가?
7. 내 코드가 다른 모듈 내부나 `eval`을 import하지 않는가?

---

## 접합부 확인 (Merge에서 상대와 같이 볼 것)

| 접합 상대 | Contract | 내 역할 | 상대 역할 | Merge에서 확인할 것 |
| --- | --- | --- | --- | --- |
| `case`(유소연) | `AnalysisScope` | Consumer | Producer | scope에 case 내부값(id/위치/파일) 안 섞임, target_event_types 복수 처리 |
| `case`(유소연) | `AnalysisRun`+`CandidateEvent` | Producer | Consumer | 같은 `candidate_id`/`rank`, `PARTIAL` 시 coverage notice용 `issues` 읽힘 |
| `eval`(김대원) | `AnalysisRun`+`CandidateEvent` | Producer | Consumer | `rank` 기준 Recall, span error, `usage_summary`로 efficiency |
| `evidence`(김준영)·`readout`(신유민) | `VisualEvidence` | Producer | Consumer(projection) | `visual_event_type`을 관찰값으로만 해석, `track_ref` 없어도 readout 동작 |
| `recording`(정철원) | `timeline_id`·frame/input ref | Consumer | Producer | span의 `timeline_id`가 recording timeline을 가리킴, ref 형식 합의 |

---

## 부분 완료 / 통합 대기 (내 실패로 세지 않음)

| 항목 | 현재 어디까지 됨 | 무엇을 기다리는가 | 상대 담당 | Mock 대체 가능 |
| --- | --- | --- | --- | --- |
| **B08** 상대 timeline ↔ ISO8601 AnalysisScope 접합 | scope는 ISO8601-only로 소비 | search 입력에 timeline 참조를 어디로 싣는지 결정(CALL-11) | 정철원·유소연 | 가능(happy는 절대시각 있음) |
| **B09** Candidate/Run의 timeline revision 추적 | `span.timeline_id`만 있음 | `AnalysisRun`에 `timeline_ref{id,revision}` 추가 여부 결정(CALL-11) | 정철원·유소연 | 가능(single revision 가정) |
| **B07(항목3)** verify_visual Fine input 표면 | `input_ref` opaque 소비 | `FrameRef`/Fine input/selector 계약 확정 | 정철원·PM | 가능(opaque id) |
| recording 자산 계약 2건 미작성 | `timeline_id`/`thumbnail_ref`/`input_ref`를 opaque id로 소비 | `SourceAsset`/`MediaStream`/`FrameRef` 계약 파일 | 정철원 | 가능(opaque id) |
| 실패 분류(`issues[].kind`) 확정 | `failure-taxonomy.md` 초안 존재, fixture는 `INFRA` 사용 | **Owner(나) 확정** + eval과 이름 병합 상의 | 서어진(+김대원) | 가능(현재 INFRA) |
| Candidate 0개 / NOT_OBSERVED / FAILED fixture | 코드 표현은 목표, fixture 없음 | v1 Scenario 확장 | 서어진 | 해당 없음(1차 제외) |

---

## 1차 완료에서 제외하는 것

- 실제 AI/Search 정확도·Recall 성능 증명 (Mock은 성능 자료 아님)
- 비용·지연 최적화, 실제 provider 호출
- challenger 구현 (baseline만 — `challenger-policy.md`)
- 모든 실패 taxonomy 분기와 edge case
- `SUCCEEDED+candidates=[]`·`NOT_OBSERVED`·`FAILED` 대표 시나리오(v1)

---

## Merge 중단 기준 (하나라도 걸리면 진행 금지)

- `visual_event_type`에 4종 밖 값 또는 옛 이름(`LANE_CHANGE`) 사용
- `run_id`/`candidate_id` 중복, 또는 `candidate.run_id != AnalysisRun.run_id`
- `outcome=PARTIAL`인데 `issues=[]`, 또는 `FAILED`인데 candidate 반환
- `legal_status`가 non-null, 또는 `OBSERVED`인데 `visual_event_type=null`(및 그 반대)
- `rank` 중복 / 0-based / 누락
- `AnalysisScope`에서 `case_id`·위치·파일 참조를 읽어 동작 (경계 위반)
- Happy Path 자체가 계약 출력을 못 만듦
- 계약 밖 내부 객체 의존, 또는 `eval` import/`if eval_mode`

---

## 검증 명령 / 실행 방법

`[구현 후 작성]` — `src/daesingo/search`에 아직 코드가 없다(README만). 구현 시작 후 실제 실행 명령을 기입한다.

- Mock 파일 정합성은 기존 `python scripts/validate_mock_pack.py`로 확인 가능(참고).

---

## 회의에서 말할 한 줄 요약

> `search`는 `case`가 준 `AnalysisScope`를 입력으로 받아 Candidate 탐색과 Fine 관찰을 수행하고, 불변 `AnalysisRun` + 순위화된 `CandidateEvent` + `VisualEvidence`(관찰만, 법적 판단 없음) 형태로 결과를 반환합니다. Happy Path와 Partial(PARTIAL/AMBIGUOUS) Scenario까지 Mock 기준으로 검증했고, timeline revision·상대시각 접합(B08/B09)은 CALL-11 결정을 기다리는 통합 대기 항목입니다.
