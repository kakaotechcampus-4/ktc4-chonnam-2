# command가 「이번에 append한 JobRecord」를 응답 밖으로 돌려주는 방식

> **상태: 결정 · 구현** · 결정일 2026-10-05 · 담당 유소연(`case`) · 근거 W7(7주차) 설계 고도화 목록 8순위 8-7(`../design-refinement-w7-baseline.md`), #245 D-2, #247 H-3, HTTP API Contract Draft §5.3(#265)
> case 공개 함수의 반환 모양이라 case 단독 결정 범위다. 규칙 원문은 `../contracts/contract-case-command.md` §4이고, 이 문서는 이유와 고르지 않은 안만 둔다.

## 배경

api composition root는 한 transaction 안에서 ① case command 처리 · 저장 ② **case가 돌려준 「이번 command로 append된 JobRecord 목록」**마다 Runtime enqueue ③ commit을 한다(runtime-tech-spec §12.1, #245 D-2). HTTP 층은 같은 목록으로 200(0건) / 202(1건 이상)를 정한다(#247 H-3). HTTP API Contract §5.3은 두 가지를 못 박았다.

- HTTP 층은 `kind`를 보고 200 / 202를 추론하지 않는다 — 같은 `kind`라도 발주 여부가 다를 수 있다.
- 이 목록은 **응답 body에 싣지 않는다** — case-command 응답은 `ok` · `error` · `case_view`뿐이다.

지금 `handle_command()`는 응답 dict만 돌려줘서 composition root가 이 목록을 얻을 길이 없다.

## A-1 후속 명확화 (2026-11-08 로컬 구현, #629)

A-1은 공개 배포 준비 작업 묶음(#629 「공개 API 보호와 공유 예산·삭제 연결」)의 항목 번호다. 코드는 `src/daesingo/case/command.py` `execute_command(admit_auto_exports=…)`.


성공한 정정과 자동 export 발주를 구분한다. `admit_auto_exports`가 거부하면 handler 뒤 snapshot은 보존하고
자동 export 후보만 폐기한다. 따라서 성공 응답에도 appended_job_records가 비어 있을 수 있다.
기존 JobRecord/export input은 변경·삭제하지 않으며 명시 job의 최종 거부는 호출자 transaction 전체를 rollback한다.
첫 자동 발주가 보류된 현재 입력은 화면의 기존 GENERATE_REPORT_VIDEO action으로 명시 발주할 수 있다.
기존 같은 입력 재시도와 달리 prior가 없으면 현재 adapter request의 첫 JobRecord를 만든다.
새 명시 export intent마다 case_rev를 한 번 올려 같은 payload 재전송과 실패 후 새 재시도를 구분한다.
다른 kind의 notice 재시도와 기존 force_rerun 값은 유지한다.
기존 command payload/HTTP 응답 필드와 append-only 조건을 바꾸지 않는다.

## 결정

1. **새 함수 `execute_command()`가 `CommandResult(response, appended_job_records)`를 돌려준다.** `handle_command()`는 `execute_command(...).response`만 돌려주는 얇은 함수로 남긴다.
2. **목록은 handler 전후의 `job_records` 길이 차이로 잘라 낸다.** JobRecord는 append-only라 이것이 정확하다. 복사본으로 돌려준다 — 호출자가 고쳐도 case 상태가 바뀌지 않는다.
3. **실패한 command는 늘 빈 목록이다.** handler는 거부할 때 상태를 바꾸기 전에 거부한다(§6 「실패하면 아무 상태도 바꾸지 않는다」).

지금 JobRecord를 append하는 command는 `RUN_NOTICE_ACTION`(1건)뿐이다. 분석 시작(`START_ANALYSIS`, Draft §11) 등이 생기면 같은 장치로 따라온다. (2026-11-08 현재: `START_ANALYSIS` · `EDIT_HINT` · `REQUEST_CANDIDATE_VIDEO_PREVIEW` · 후보 재선택도 JobRecord를 append하고, 성공 뒤 자동 export 발주(`exports.issue_missing_exports()`)도 같은 목록에 든다. 장치는 그대로다.)

## 고르지 않은 안

| 안 | 고르지 않은 이유 |
| --- | --- |
| `handle_command()` 반환을 `(response, appended)` 튜플이나 `CommandResult`로 바꾼다 | 기존 호출부(테스트 · orchestration 러너 #234)를 모두 고쳐야 한다. 더 중요하게는, body와 목록이 한 값으로 다니면 transport가 실수로 목록을 body에 실을 수 있다 — 함수를 나누면 「transport는 `response`만, composition root는 둘 다」가 모양으로 드러난다 |
| 응답 body에 `appended_job_ids` 같은 필드를 더한다 | HTTP API Contract §5.3이 금지한다. web은 진행을 `case_view.running_jobs[]`로 보고 job 식별자를 따로 받지 않는다 |
| composition root가 command 전후 `job_records`를 직접 비교한다 | composition root가 case 내부 상태(aggregate)를 알게 된다. case가 계산해 넘기는 쪽이 경계에 맞다 |
| `kind`별로 발주 여부를 표로 둔다 | §5.3이 금지한 「`kind`로 추론」과 같다. `RUN_NOTICE_ACTION`도 action에 따라 발주가 다르다 |

## 남은 것

- **202의 `case_view.running_jobs`에 이번 job이 들어 있어야 한다**(§5.3 다른 절반) — CaseView 투영 쪽이라 8-11에서 한다. 8-7만으로는 202 직후 polling 조건을 아직 채우지 못한다.
- 8-6(CaseStore MySQL, #267) 구현 때 `execute_command()` 안에서 성공한 command만 `save()`한다.

> (2026-11-08 현재: 두 항목 모두 끝났다. `running_jobs`는 `running-jobs-derivation.md`(8-11)대로 JobRecord 정산 기록에서 계산한다. `execute_command()`는 성공한 command만 `store.save()`한다.)
