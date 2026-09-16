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
