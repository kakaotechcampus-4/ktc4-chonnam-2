# ADR-CASE-001: orchestration 진입점(`service.py`) 분리 + `ModuleAdapter` Protocol 도입

> 상태: **ACCEPTED**
>
> 결정일: `2026-09-16`
>
> Decider / Owner: 유소연 (`case` Owner · orchestration 담당)
>
> Consulted: 없음 — `case` 내부 실행 구조에 대한 결정이며 다른 모듈의 계약·경계를 바꾸지 않는다(§4 범위 참고)
>
> 적용 범위: `src/daesingo/case/adapters.py`, `src/daesingo/case/service.py`(신설), Mock→Real 교체(W5) 착수 준비
>
> 근거 목록: `docs/modules/case/tech-spec.md` §1(case가 하는 일 — "자연어 단서 구조화" 등) · `docs/modules/case/ui-tests/01_yu-soyeon_web-manual-ui-check_2026-09-16.md`(직전 UI 점검) · `src/daesingo/case/tests/test_scenario_*_smoke.py`(기존 실행 경로)

## 1. 목적

W5(Mock → Real 교체) 착수 전, "어댑터만 바꾸면 나머지는 그대로 동작한다"는 전제가 실제로 성립하는지 확인하고, 성립하지 않는 부분을 메운다.

## 2. 배경

`case`는 지금까지 `MockFixtureAdapter` 하나만 갖고 있었고, 그 도크스트링은 "case의 domain/view 코드는 이 인터페이스에만 의존한다"고 적어뒀다. 그런데 실제로 `MockFixtureAdapter`를 인스턴스화하는 곳은 `src/daesingo/case/tests/test_scenario_*_smoke.py` 뿐이었다 — "adapter로 데이터 가져오기 → 도메인 메서드 호출 → 결과 반영"이라는 orchestration 흐름 자체가 테스트 코드 안에만 손으로 짜여 있었고, `case`의 실행 코드(`domain.py`/`jobs.py`/`view.py`)에는 이 흐름을 재사용할 자리가 없었다.

이 상태로 Real 어댑터를 아무리 잘 만들어도, "그 어댑터를 실제로 호출하는 코드"가 테스트 바깥에 없으므로 Mock→Real 교체가 실행 가능한 형태로 존재하지 않는다.

## 3. 결정

| ID | 항목 | 상태 |
| --- | --- | --- |
| D1 | `adapters.py`에 `ModuleAdapter`(`typing.Protocol`)를 신설해 어댑터 인터페이스를 formalize한다 | **ACCEPTED** |
| D2 | `adapters.py`에 `RealAdapter` 골격을 추가한다 — 메서드별로 `NotImplementedError`, 모듈별로 하나씩 채운다 | **ACCEPTED** |
| D3 | `service.py`를 신설해 스모크 테스트의 adapter↔domain 연결 중 재사용 가능한 부분(`receive_search_candidates`, `fetch_case_view_inputs`, `build_view_from_adapter`)을 뽑아낸다 | **ACCEPTED** |
| D4 | `service.py`는 시나리오 분기(언제 재시도·정정을 받을지)를 대신 결정하지 않는다 — 그 판단은 계속 호출자(테스트, 앞으로의 worker) 책임으로 남긴다 | **ACCEPTED** |

### 3.1 D2 — `RealAdapter`를 지금 "완성"하지 않는 이유

recording/search/readout/evidence 중 case가 실제로 호출할 수 있는 엔드포인트를 내놓은 모듈이 아직 없다. `RealAdapter`를 지금 억지로 채우면 추측으로 만든 호출 코드가 생기고, 나중에 각 모듈 Owner가 실제 계약을 내놓았을 때 다시 갈아엎어야 한다. 대신 메서드 시그니처와 실패 방식(`NotImplementedError`, "이 case_id에 대해 이 모듈은 아직 Mock 유지" 메시지)만 확정해서, 모듈별로 준비되는 순서대로 하나씩 채울 수 있게 했다 — W5 원칙 "Mock retained for not-yet-ready modules"를 코드 수준에서 그대로 표현한다.

### 3.2 D3 — `service.py`가 "전체 자동 진행"을 하지 않는 이유

happy path 하나만 보면 처음부터 끝까지 자동으로 진행시키는 함수 하나를 만들고 싶어지지만, 실제 시나리오는 unknown/abstain, infra_failure(재시도), correction_rerun처럼 분기가 다르다. 그 분기를 `service.py`가 대신 추측해서 결정하면, 나중에 실제 worker loop를 설계할 때 이 파일이 오히려 제약이 된다. 그래서 이번 결정은 "adapter 값을 domain에 반영하는" 기계적인 부분만 재사용 가능하게 뽑아내는 데 그친다.

## 4. 영향

- `docs/modules/case/checklists/phase1-completion-checklist.md` 74번 항목("사용자 자연어 단서 구조화")과는 별개다 — 그 항목은 실제 AI 모델 호출이 필요해 Mock 1차 범위 밖으로 명시적으로 뺀 것이고, 이 ADR은 이미 존재하는 case 내부 상태(candidates/evidence/package)를 어댑터로부터 가져오는 배관 문제를 다룬다.
- 다른 모듈의 계약이나 경계를 바꾸지 않는다 — `scripts/check_boundaries.py`/`scripts/check_contract_fixtures.py` 통과 확인함.
- 기존 `test_scenario_*_smoke.py`는 그대로 둔다 — "case가 계약을 재현하는가"를 검증하는 책임은 계속 그 파일들에 있고, 새 `test_service.py`는 "service.py로 뽑아낸 함수가 그 연결을 그대로 재현하는가"만 확인한다.

## 5. 남은 일

- recording/search가 먼저 준비되면 `RealAdapter.get_candidate_events()`/`get_analysis_scopes()`부터 채운다.
- 실제 worker loop(또는 그에 준하는 진입점) 설계는 이 ADR의 범위 밖이다 — `service.py`의 함수들을 어떤 순서/조건으로 호출할지는 각 모듈이 Real로 바뀌는 시점에 별도로 결정한다.

## 6. 후속 — 2026-09-18: search만 real로 교체

D2 작성 시점(2026-09-16)에는 "case가 실제로 호출할 수 있는 엔드포인트를 내놓은 모듈이 아직 없다"고 판단했다. 이틀 뒤 다시 확인한 결과는 달랐다 — `tests/{search,evidence,readout,recording,common}` 216개 테스트(+ 68 subtests)가 전부 통과하는, 이미 merge된 실제 코드가 있었다.

다만 모듈별로 사정이 다르다는 것도 같이 확인됐다:

| 모듈 | 실측 결과 | `RealAdapter` 처리 |
| --- | --- | --- |
| `search` | `search_candidates(scope)`가 `AnalysisScope` 하나만 받는 순수 함수라 그대로 연결 가능 | **`get_candidate_events()`를 real로 교체.** `search_scope` 생성자 인자 추가, `search.AnalysisScope.model_validate()`로 변환 후 호출. `test_real_adapter_get_candidate_events_matches_fixture`로 mock 경로와 같은 후보가 나오는지 검증 |
| `search` (scope 자체) | `get_analysis_scopes()`는 case가 `AnalysisScope`의 Producer라 애초에 "가져오는" 대상이 아님(Mock에서도 `test_scope.py` 정답지 용도일 뿐) | real 대응 없음 — `NotImplementedError` 유지, 영구히 |
| `evidence` | `assemble_evidence()` 등 함수 자체는 완성돼 있음. 하지만 입력으로 요구하는 `plate_readout`(readout)·`incident_clip`(recording)을 가져올 경로가 `ModuleAdapter`에 없음 | `NotImplementedError` 유지 — evidence를 더 기다리는 게 아니라 **case가 readout/recording까지 엮는 별도 설계**가 선행돼야 함(이 ADR 범위 밖) |
| `common/runtime` | `InMemoryJobExecutionStore`는 호출 가능한 서비스가 아니라 Worker 프로세스가 채우는 저장소. `worker/`가 비어 있어 채울 대상 자체가 없음 | `NotImplementedError` 유지 — Worker 인프라가 먼저 나와야 함 |

D2의 "모듈별로 준비되는 순서대로 하나씩 채운다"는 원칙은 그대로 유지한다 — 이번엔 그 순서가 `search` 하나였을 뿐이다. `scripts/check_boundaries.py`/`scripts/check_contract_fixtures.py`, 전체 테스트(`pytest src tests`, 450 passed) 재확인함.

**다음으로 준비되는 모듈이 있으면 이어서 채운다:**
- readout/recording이 `ModuleAdapter`에 메서드로 노출되면(설계 필요) evidence 연결 재시도
- Worker 진입점이 생기면 `common/runtime` 연결 재시도

## 7. 후속 — 2026-09-18(W6): evidence도 `scenario_happy_001` 대표 시나리오로 real 교체

PM 공지(W5 Baseline + W6 Real E2E, 2026-09-22 월 20:00 회의 데드라인 — "대표 실제 데이터 시나리오 1개가 전체 흐름을 실제로 통과하는지 회의에서 직접 실행 확인")에 맞춰 §6에서 "case가 readout/recording까지 엮는 별도 설계가 필요하다"고 미뤄뒀던 부분을 오늘 진행했다. 확인해보니 readout/recording도 search와 같은 상태였다 — `tests/readout/test_public_functions.py`가 "외부 의존 없음"이라고 명시하고, `tests/recording/test_first_integration_contract.py`가 `resolve_span → prepare_analysis_source → build_incident_clip` 흐름을 fixture만으로 완결시킨다. 즉 **case가 readout/recording을 "못 부르는" 게 아니라 "아직 안 불러본" 것**이었다.

### 7.1 새 모듈 `case/real_e2e.py`

`build_happy_001_evidence_bundle()` 하나로 recording→`search.verify_visual`→readout→evidence 체인을 실제 함수 호출로 잇는다. 순서는 evidence 자체 도구(`evidence/mock_integration.py`)가 mock 데이터로 검증해둔 순서(`resolve_time`→`assemble_evidence`→`calculate_evidence_needs`→`evaluate_requirements`×2→`build_report_package`)를 그대로 따르되, 입력 각각을 raw JSON이 아니라 real 함수 반환값으로 채운다.

### 7.2 알려진 단순화 2건 (정직하게 남김, W7 대상)

1. `time_source_candidates` — `RecordingFixture` pydantic 모델에 이 필드가 없다(recording의 1차 구현 범위 밖). 공개 함수로 노출된 적이 없으므로 이 한 값만 recording의 raw fixture JSON에서 읽는다.
2. `situation_response`/`observation_facts` — case에 이 값을 만드는 로직(intake UI)이 없어 `None`. 그 결과 `FINAL_PACKAGE` 판정이 PASS/WARN에 못 미쳐 `build_report_package()`가 `PackageNotReady`를 던질 수 있다 — 조용한 실패가 아니라 `EvidenceBundle.package_error`에 사유가 남고, `RealAdapter.get_report_package()`는 `None`을 돌려준다(CaseView의 partial 표현이 이미 이런 상태를 위해 있음, §5-12).

### 7.3 결과

`test_real_e2e.py`의 `test_real_e2e_happy_path_reaches_ready_caseview`가 recording→search→후보 선택→readout→evidence→`CaseView`까지 전부 real로 돌려서 `stage: READY`, `plate_display.value: "12가3456"`, `event_time_display.value: "2026-08-24T18:05:12+09:00"`, `requirements_evidence.readiness: WARN`(PASS는 아니지만 실제 평가 결과)을 확인했다. `package`는 7.2-2번 이유로 `None` — 이번 데드라인 기준("전체 흐름을 실제로 통과하는지")은 만족한다.

`get_job_executions()`(common/runtime)는 여전히 `NotImplementedError`다 — `service.py`의 `fetch_case_view_inputs()`가 이 메서드를 아예 안 부르므로 오늘 목표에 영향 없음.

전체 테스트(`pytest src tests`, 453 passed) 및 `scripts/check_boundaries.py`/`check_contract_fixtures.py` 재확인함.

## 8. 후속 — 2026-09-18(W6): `case.get_view(case_id)` 진입점 + `CaseStore`

§4/§5(원래 이 ADR의 "남은 일")가 지적했던 마지막 간극을 메웠다 — `module-architecture.md`가 적은 `web → case.get_view() → CaseView`를 실제로 만족하는 함수가 코드에 없었다. `build_view_from_adapter(case, adapter)`는 이미 만들어진 `case`/`adapter` 객체가 있어야 했는데, web이 실제로 쥐고 있는 건 `case_id` 문자열 하나뿐이다.

### 8.1 결정

| ID | 항목 | 상태 |
| --- | --- | --- |
| D5 | `case/store.py`에 `CaseStore`(case_id → `CaseAggregate` + `ModuleAdapter` 최소 in-memory 매핑) 신설 | **ACCEPTED** |
| D6 | `case/service.py`에 `get_view(case_id, *, store, running_jobs=None, notices=None)` 신설, `build_view_from_adapter()`에도 같은 두 파라미터 통과시킴 | **ACCEPTED** |
| D7 | `case/__init__.py`에서 `get_view`/`CaseStore`를 재노출해 `case.get_view(...)` 형태를 문자 그대로 만족시킴 | **ACCEPTED** |

### 8.2 D5 — `store`를 숨은 전역 상태로 두지 않는 이유

`get_view(case_id)`가 인자 하나로 끝나려면 프로세스 전체가 공유하는 전역 `CaseStore` 인스턴스를 어딘가 둬야 유혹이 생긴다. 그렇게 하지 않았다 — 테스트마다 상태가 새는 걸 막고, 나중에 FastAPI app state 같은 실제 배선 결정을 지금 미리 굳히지 않기 위해서다. 그래서 `store`는 항상 호출자가 명시적으로 넘긴다. `case.get_view(case_id, store=store)`가 "완전한 한 줄 호출"은 아니지만, `store` 자체는 호출자가 한 번만 만들어 재사용하면 되므로 실사용 부담은 크지 않다.

### 8.3 D5 — `CaseStore`가 `ModuleAdapter`도 같이 들고 있는 이유

어댑터를 매 조회마다 호출자가 다시 구성해서 넘기게 하면(예: `RealAdapter`의 `search_scope`/`mock_root`를 매번 다시 조립) `get_view(case_id)`가 사실상 여러 인자짜리 호출이 된다. 어떤 case가 Mock 시나리오 기반인지 Real 데이터 기반인지는 등록 시점에 정해지고 그 case 생애주기 동안 안 바뀐다는 게 지금까지의 실행 방식(스모크 테스트·`real_e2e.py`)과 일치해서, `register(case, adapter)`로 묶어 저장한다.

### 8.4 검증

`test_get_view_entrypoint.py`: 미등록 case_id 조회 시 명확히 실패, 중복 등록 거부, Mock/Real 어댑터 둘 다로 `case.get_view(case_id)` 한 호출에서 `CaseView`(Real 경로는 `stage: READY` + `plate_display.value: "12가3456"`까지)가 나오는지 확인. `src/daesingo/case` 67 passed, 전체 `pytest src tests` 458 passed, `check_boundaries.py`/`check_contract_fixtures.py` 재확인함.

### 8.5 남은 일

- 여러 요청에 걸쳐 `CaseStore`를 어디서 살려둘지(FastAPI app state 등)는 이 ADR 범위 밖 — 실제 배선 시점에 결정한다.
- 정식 DB 영속화·동시성 제어는 W5/W6 요청 문서가 이번 범위 밖으로 뺐다.
