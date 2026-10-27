# 새 후보 준비 중 재선택 금지 — 「준비 중」을 case가 판단한다 (6.6순위 조건 1)

> **상태: case 결정 · 구현 · web(신유민) 확인 대기** · 결정일 2026-10-24 · 담당 유소연(`case`) · 근거 `core-user-flow.md` §8-1 「새 후보를 준비하는 동안에는 다시 후보를 바꾸는 동작을 제공하지 않는다. 준비가 끝난 뒤 결과 화면에서 다음 후보를 고를 수 있다」 · #173 E-4 조건 1([case 댓글](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/173#issuecomment-5865032697)) · `design-refinement-w7-baseline.md` 6.6순위 · `incident-clip-observation-input.md` §4-1
> 무엇을 「준비 중」으로 보고 재선택을 거부하는지는 case 결정 범위다. 진행 화면에서 버튼을 주지 않는 것은 web 규칙이고(§8-1), 이 문서는 그 규칙과 같은 판단을 case가 command에서도 지키게 한다.

## 1. 목표 · 범위

지금은 진행 화면이 재선택 버튼을 주지 않는 web 규칙에만 기댄다. case가 같은 판단을 하면 낡은 화면 · 다른 클라이언트에서 온 `SELECT_OTHER_CANDIDATE`도 막힌다. 2026-09-28에는 case domain에 「준비 완료」 신호가 없어 미뤘다 — 추측으로 막으면 상황 응답 대기와 구분하지 못했다(#173 댓글). #396으로 관찰 job마다 후보 · 세대 입력이 고정되어 이제 신호가 있다.

**범위 밖:** 진행 화면 표시 · 버튼(web) · 「초안 준비 중」 중단(product 미결, 8-1 · 8-9) · 재선택 뒤 관찰 재사용(`incident-clip-observation-input.md` §4-6).

## 2. 결정

1. **「준비 중」 = 선택 후보 · 현재 세대로 입력이 고정된 관찰 job 중 case가 아직 결과를 기다리는 것이 있다.** 관찰 job은 `FINE_VERIFY` · `INCIDENT_CLIP_BUILD` · `PLATE_READ` · `OVERLAY_TIME_READ`이고, 「기다린다」는 `running_jobs`와 같은 정의(정산되지 않은 JobRecord, `running-jobs-derivation.md`)다. `JobExecution` 상태가 아니라 case 정산 기록으로 본다 — 실행이 끝났어도 T2 반영 전이면 아직 준비 중이다.
2. **준비 중이면 `check_reselect()`가 거부한다** → command는 `case.command.not_allowed`이고 아무 상태도 바꾸지 않는다(CorrectionRecord · `case_rev` 그대로, #166과 같은 원칙). `CaseAggregate.preparing_selected_candidate()`가 판단한다.
3. **다음은 막지 않는다.**
   - 상황 응답 대기(`AWAIT_SITUATION_RESPONSE`) — 판독까지 정산돼 기다리는 job이 없다. 2026-09-28에 구분할 수 없던 경우가 이것이다.
   - Fine 실패 · `NOT_OBSERVED` — job이 정산됐다. 출구가 「다른 후보 보기」다(8-14, `core-user-flow.md` §8-1).
   - 이전 세대의 관찰 job — 재탐색 뒤 남은 job은 새 후보 목록의 준비가 아니다.
   - 입력 없이 발주된 관찰 job(동기 · 데모 경로) — 어느 후보의 것인지 모른다.
4. **결과 화면의 재판독 · 다시 시도도 준비 중으로 본다.** 같은 입력으로 다시 발주된 판독(`jobs.issue_same_input`)은 선택 후보의 관찰 job이라 기다리는 동안 재선택을 막는다. 끝나면 바로 풀린다.

## 3. 알려진 한계

- 비동기 경로의 첫 선택(Coarse T2 자동 선택)은 composition 주입과 함께 열렸다(2026-10-26, `incident-clip-observation-input.md` §9 3단계). 자동 선택 뒤 첫 Fine을 기다리는 동안이 이 규칙이 막는 「준비 중」이다.

## 4. 미결 (채우지 않는다)

- §2-4 — 결과 화면에서 재판독 · 다시 시도가 도는 동안 web이 다른 후보 선택 버튼을 그대로 두는지. 두면 사용자가 누를 때 `not_allowed`가 난다 — web(신유민) 확인.

## 5. 고르지 않은 안

| 안 | 고르지 않은 이유 |
| --- | --- |
| `JobExecution` terminal 여부로 판단(#173 댓글의 원래 계획) | T1과 T2 사이에 실행은 끝났지만 case 반영 전인 구간이 「준비 끝」으로 보인다. case가 기다리는 job은 `running_jobs`와 같은 기준이라 화면과 어긋나지 않는다 |
| CaseView 값(`EVIDENCE_REVIEW` + `evidence=null`)으로 판단 | 상황 응답 대기 · Fine 실패도 `evidence=null`이라 구분하지 못한다(2026-09-28에 미룬 이유 그대로) |
| 재판독 · 다시 시도는 제외 | `force_rerun`이 다시 시도(`RUN_NOTICE_ACTION`)에는 없어 kind 정보만으로 가를 수 없고, 화면 규칙을 web과 정하기 전에 case가 예외를 먼저 만들지 않는다(§4) |

## 6. 구현

- `domain.CaseAggregate.current_generation_job_id()` · `preparing_selected_candidate()` · `check_reselect()`. `observation.current_generation_job_id()`는 이 메서드를 부른다.
- 테스트 `tests/case/test_reselect_while_preparing.py` — Fine · 뒤 단계 대기 중 거부, 거부 시 무변경, 체인 정산 · Fine 실패 뒤 허용, 이전 세대 job · 입력 없는 job은 막지 않음.
