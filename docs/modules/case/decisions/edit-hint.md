# 설명 고쳐 다시 찾기 — `EDIT_HINT{description}` 한 command로 원문을 다시 받아 구조화부터 다시 돈다

> 2026-10-27 · 결정 추적 [#410](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/410) · 관련 [#404](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/404) · [#405](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/405) · case-command 계약 §13 · CaseView 계약 B§7

## 1. 문제

- 결과 없음(`search.no_candidates`)은 `EDIT_HINT`를 싣고 있었지만 보낼 command가 없었다(case-command 계약 §12-5).
- CaseView 계약 B§7은 `EDIT_HINT`를 「새 Job 없음, 다음 `RETRY_SEARCH`의 입력을 바꾸는 동작」으로 정의했는데, 코드의 `RETRY_SEARCH`는 직전 탐색 입력을 그대로 다시 쓴다(`jobs.issue_same_input()`). 두 단계 구조가 성립하지 않았다.
- 설명을 잘 이해하지 못함(`search.hint_unclear`)은 「다시 적기」를 command 뒤로 미뤘다(`hint-unclear-notice.md` 2단계).
- 단서 구조화 중 중단하면 다시 낼 탐색이 없어 `case.analysis_stopped`의 `actions`가 비었다 — 출구가 「새 신고」뿐(#405 Known Issue).

## 2. 결정

1. **(A) 원문 다시 적기 + (가) 한 command.** 새 command `EDIT_HINT{description}`. web(신유민) 의견: 분석 시작 입력 UI를 다시 쓸 수 있고, 필드별 편집(B)은 화면을 새로 만들어야 한다. 「고치고 바로 찾기」가 화면상 자연스럽다.
2. **성공하면** `SEARCHING`으로 역행(후보 · 선택 폐기, `regress_to_searching()` — `TIME_HINT_EDIT`와 같은 역행) · 역행하면 기다리던 job을 `SUPERSEDED`로 정산(§4) · 원문 교체 · hints 4개 `null` · `hint_unclear` · `candidate_search_failed` 해제 · `case_rev` +1 · `HINT_EXTRACT` 1건. 설명이 비었으면 구조화 없이 바로 첫 탐색(분석 시작과 같다).
3. **결과 반영은 분석 시작과 같은 경로다** — `reflect_hint_extraction()` → `issue_initial_search()`, 소진 알림이면 `reflect_hint_exhaustion()`. 구조화 · scope 생성 경로를 하나로 유지한다.
4. **예산은 첫 탐색과 같다**(`InitialSearchBudget`). 같은 경로를 쓰는 것이 이 안을 고른 이유다.
5. **허용 조건 = 현재 CaseView notice가 `EDIT_HINT`를 싣고 있는가.** `RUN_NOTICE_ACTION`과 같은 근거다. 어느 화면에 출구를 둘지는 notice가 정하므로, 화면을 더할 때(위반 미관찰) command를 고치지 않고 notice만 고친다. 추가로 `SEARCHING`에서는 분석 job을 기다리는 중이면 받지 않는다(진행 중 덮어쓰기 방지).
6. **`EDIT_HINT`를 싣는 notice:** `search.no_candidates` · `search.hint_unclear` · `case.analysis_stopped`(다시 낼 탐색 근거가 없을 때). 탐색 근거가 있는 중단 · timeout은 지금처럼 `RETRY_SEARCH`만 — 이번에 바꾸지 않는다.
7. **CorrectionRecord를 남기지 않는다.** 설명 원문은 evidence 필드가 아니라 탐색 입력이고, CaseView `description`으로 보인다.

## 3. PM 확인 대기

- **위반 미관찰(`evidence.visual_event_not_observed`)에 싣기** — `core-user-flow.md` §6 · 표 변경이라 PM 확인 뒤(#404). 확인되면 `VISUAL_EVENT_NOT_OBSERVED_NOTICE.actions`에 `EDIT_HINT`를 넣기만 하면 된다. 「다음 후보를 자동으로 확인하지 않는다」(#168 [A])는 그대로다.

## 4. 알려진 한계

- **후보 선택 뒤 고치면 이전 후보 목록에 딸린 job은 `SUPERSEDED`로 정산한다(2026-10-27).** #412로 Coarse 반영 뒤 rank=1을 자동 선택해 Fine을 발주하므로, `search.hint_unclear` 화면은 보통 `EVIDENCE_REVIEW`이고 Fine · clip · 판독 job이 돌고 있다. 그대로 두면 역행 뒤 진행 화면 `running_jobs`에 이전 후보의 job이 결과가 올 때까지 남는다(결과는 선택이 없어 쓰이지 않는다). 그래서 역행할 때 기다리던 job을 모두 정산한다 — `running_jobs`에서 바로 빠지고, 늦은 결과는 기존 guard대로 `NOT_APPLIED(SUPERSEDED)`다. Runtime 실행은 취소하지 않는다(`cancelled_job_ids=[]`, timeout-fallback 원칙). `SUPERSEDED`의 뜻을 「같은 kind · `scope_ref`로 새 job을 발주했다」에서 「case가 그 job의 입력(후보 목록)을 새것으로 바꿨다」로 넓혀 쓴다(`running-jobs-derivation.md`). Runtime이 이미 받는 사유라 새 사유를 만들지 않았다. 역행하지 않는 경로(`SEARCHING`, 중단 · timeout 뒤)는 정산하지 않는다.
  - `TIME_HINT_EDIT` 역행(`correction.edit_time_hint()`)은 같은 정산을 하지 않는다 — 실행 경로(web 버튼)가 없어 이번 범위 밖이다.
- 같은 원문을 다시 보내도 거부하지 않는다 — 구조화를 다시 돌리는 의미가 있다(중단 뒤 재시작).

## 5. 고르지 않은 안

| 안 | 고르지 않은 이유 |
| --- | --- |
| (B) hints 필드별 patch(`TIME_HINT_EDIT`) | web이 화면을 새로 만들어야 하고, 분석 시작(원문)과 입력 방식이 달라진다 |
| (나) 고치기와 `RETRY_SEARCH` 두 단계 | 버튼이 하나 더 필요하고, `RETRY_SEARCH`를 현재 hints로 scope를 다시 만들게 바꾸면 실패 · 중단 뒤 「같은 조건으로 다시」와 뜻이 갈린다 |
| 허용 조건을 stage로 정하기 | 버튼이 없는 화면(후보가 있는 정상 결과)에서도 받게 된다. 화면을 더할 때마다 command 규칙을 고쳐야 한다 |
| CorrectionRecord(`TIME_HINT_EDIT`)로 남기기 | 원문 교체는 hints patch가 아니고, evidence가 읽는 값도 아니다 |
| 탐색용 예산을 따로 두기 | 근거 값이 없고, 첫 탐색과 다른 경로가 생긴다 |

## 6. 테스트

`tests/case/test_edit_hint_command.py` — 결과 없음에서 `HINT_EXTRACT` 재발주 · 역행 · 원문 · hints · `case_rev` · 세대, 반영 뒤 첫 탐색, 빈 설명 바로 탐색 · 예산, `hint_unclear` notice action과 해제, 단서 구조화 중 중단의 출구, 탐색 근거가 있는 중단은 `RETRY_SEARCH`만, 버튼 없는 화면 · 분석 진행 중 `not_allowed`, `invalid_payload` · `stale_revision`, 타임라인 실패 시 저장 안 함, 선택 뒤 역행(aggregate), `EVIDENCE_REVIEW`에서 고치면 기다리던 Fine을 `SUPERSEDED`로 정산 · 역행 없는 경로는 정산 안 함, `INTAKE` 거부.

## 7. 남은 것

- 위반 미관찰에 싣기(§3, PM).
- CaseView 계약 B§7 `EDIT_HINT` 행 개정 web 확인(#410).
- web: `actionIntent.ts`의 `EDIT_HINT`(지금 `LOCAL_INPUT`)를 이 command로 보내기 · `ApiFlow.tsx` 입력 화면(web 소유).
