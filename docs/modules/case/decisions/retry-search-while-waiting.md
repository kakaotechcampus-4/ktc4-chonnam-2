# 「다시 찾기」 — 결과 없음에서는 `SEARCHING`으로 돌아가고, 탐색을 기다리는 동안에는 다시 받지 않는다

> 2026-10-29 · 결정 추적 [#426](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/426) Case 확인 요청 1 · 3 · web 수정 PR #434(병합) · 관련 `edit-hint.md` · `report-video-export.md` [R-2] · `stop-analysis.md`

## 1. 문제

결과 없음(`CANDIDATE_REVIEW` · 후보 0개)에서 「다시 찾기」(`RETRY_SEARCH`)를 누르면 새 `COARSE_SEARCH`가 발주된다. 그런데 세 가지가 어긋났다.

- **진행 표시:** stage가 `CANDIDATE_REVIEW`에 머물러 진행 단계가 `coarse_search=DONE` · `candidate_review=RUNNING`이었다. 탐색 실패 뒤에 다시 찾으면 `coarse_search=FAILED`가 남았다. web은 `running_jobs`로 진행 화면을 띄우지만(#434) 단계 표시가 틀렸다.
- **중복 발주:** 탐색을 기다리는 동안에도 notice에 `RETRY_SEARCH`가 실려, 누를 때마다 같은 입력의 job이 새로 생겼다(#426에서 9회 추가 → 실제 실행 10건).
- **결과 반영 불가(이번에 찾음):** 탐색 결과 반영(`CaseAggregate.receive_candidates`)은 `SEARCHING → CANDIDATE_REVIEW` 전이만 받는다. 결과 없음에서 다시 찾은 결과는 stage가 `CANDIDATE_REVIEW`라 `InvalidTransition`으로 반영되지 못했다. Worker 결과 반영(`reflection._apply_coarse_search`)도 같은 함수를 쓴다.

## 2. 결정

1. **결과 없음에서 다시 찾으면 `SEARCHING`으로 돌아간다.** `RUN_NOTICE_ACTION`의 `RETRY_SEARCH`가 `CANDIDATE_REVIEW`에서 오면 `regress_to_searching()` 뒤에 발주한다 — 「설명 고쳐 다시 찾기」(`EDIT_HINT`)와 같은 역행이다. 후보는 원래 0개라 버리는 것이 없다. 새 결과는 기존 반영 경로 그대로 `CANDIDATE_REVIEW`로 전진한다.
2. **탐색을 기다리는 동안에는 어떤 notice에도 `RETRY_SEARCH`를 싣지 않는다.** 기다리는 탐색 job은 `running_jobs`의 `HINT_EXTRACT` · `COARSE_SEARCH`다. 허용 = 화면의 버튼이라(case-command 계약 §5) command도 함께 막힌다(`case.command.unknown_target`). `GENERATE_REPORT_VIDEO`의 실행 중 규칙(#351 [R-2])과 같다.
3. **실패 뒤 다시 찾는 동안 `coarse_search`는 `FAILED`가 아니다.** 기다리는 탐색 job이 있으면 이전 실패를 보이지 않는다(`CaseAggregate.search_awaited`). 그래서 `search.candidate_search_failed`도 그동안 붙지 않는다. 새 결과가 실패면 다시 `FAILED`다.
4. **정상 종료 · 실패 뒤의 다시 찾기 경로는 그대로다.** 막는 것은 기다리는 동안의 추가 발주뿐이다. 반복 횟수 · 비용 상한(#311)은 두지 않는다.

## 3. 구현

- `domain.CaseAggregate.search_awaited` — 기다리는 탐색 job이 있는가(저장하지 않고 정산 기록에서 계산).
- `command._run_notice_action` — `COARSE_SEARCH` 발주가 `CANDIDATE_REVIEW`에서 오면 `regress_to_searching()`.
- `view._build_progress` — `candidate_search_failed and not search_awaited`일 때만 `FAILED`.
- `service.derive_notices` — `running_jobs`에 탐색 job이 있으면 모든 notice에서 `RETRY_SEARCH`를 뺀다.
- 테스트 `tests/case/test_retry_search_while_waiting.py` — 결과 없음 → 다시 찾기(`SEARCHING` · `RUNNING` · 결과 없음 notice 없음) → 두 번째 다시 찾기 거부 · 추가 job 없음 → 결과 반영 뒤 `CANDIDATE_REVIEW` · 버튼 복귀, 실패 뒤 다시 찾기 중 `RUNNING`, notice 공통 규칙.

## 4. 남은 것

- Worker 경로(`reflection._apply_coarse_search`)로 결과 없음 → 다시 찾기 → 결과 반영을 끝까지 돌리는 테스트는 없다. 반영 함수가 같아 이 수정으로 함께 풀리지만, 실제 경로로는 확인하지 않았다.
