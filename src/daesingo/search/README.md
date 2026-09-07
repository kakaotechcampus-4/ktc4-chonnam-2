# `search` — 사건 탐색

**Owner:** 서어진 (`docs/management/ownership.md`) · **경계:** `docs/architecture/module-architecture.md` §4-모듈2 · **문서 작업공간:** `docs/modules/search/`

## 이 폴더가 하는 일 (요약 — 원문은 §4-모듈2)

Coarse 후보 구간 생성·Fine/Classification visual verification·4종 event routing·`AnalysisRun` 실행 기록·실패 taxonomy 기록·`providers/`(외부 AI API 호출은 여기서만)

## 이 폴더가 알면 안 되는 것 (§4-모듈2 「알면 안 되는 것」)

신고 규정·Report Type / case stage / 확정 Evidence / 사용자 개인정보 / eval의 존재 / 신고용 mp4 생성 / `if eval_mode`

## 공개 함수

다른 모듈은 **공개 함수만** 호출한다. `from daesingo.search import ...`로 쓴다.

| 함수 | 입력 (Contract) | 출력 (Contract) |
| --- | --- | --- |
| `search_candidates(scope)` | `AnalysisScope` (`contract-analysis-scope.md`) | `{"analysis_run": AnalysisRun, "candidates": CandidateEvent[]}` (`contract-analysis-run-candidate-event.md` §2) |
| `verify_visual(input_ref, target_hint=None)` | `input_ref` (opaque str) + optional `target_hint` | `VisualEvidence` (`contract-visual-evidence.md` §2) |

## 상태

**fixture 기반 stub만 있다** (`stub.py`) — 1차 Mock E2E 통합용. 값은 `data/mock/search/`의 fixture가 소유하고, 함수는 입력에 맞는 fixture를 찾아 반환한다. 실제 Coarse/Fine 로직·`providers/`는 아직 없다. self-check: `python tests/test_search_stub.py`.

실제 구현이 생기면 `stub.py`를 대체하되 `__init__`이 노출하는 공개 함수 이름·시그니처는 유지한다(Consumer는 내부가 fixture인지 실제 구현인지 몰라야 한다).
