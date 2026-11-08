# case 대기 timeout — 타이머 없이 마감을 계산하고, 늦은 결과는 반영하지 않는다

> **상태: 결정 · 구현(탐색 `COARSE_SEARCH`만)** · 결정일 2026-10-13 · 준비 여유 추가 2026-11-04(#452, §3-8 · 계수 2.0 · 상한 60분 PM 잠정 승인) · 탐색 예산 E2E 한정 예외 2026-11-05(#452, §3-9) → 공개 RC 동안 600초 유지 2026-11-07(§3-10) · 갱신 2026-10-26(web · Runtime 확인 반영) · 담당 유소연(`case`) · 근거 W7(7주차) 설계 고도화 목록 8순위 8-9(`../design-refinement-w7-baseline.md`), `timeout-fallback.md`(잠정값 · 「진행 중인 Job은 강제 취소하지 않는다」), `stop-analysis.md`(같은 guard), `running-jobs-derivation.md`(정산 사유 `STOPPED_WAITING`), Runtime Tech Spec §12.2 · Provisional Baseline §3.2(RD-04b), #291(`runtime.retry.after_case_stopped_count` 의미)
> 「얼마나 기다린 뒤 부분 결과로 넘어가는가」와 「그때 어떤 job을 유지 · 취소하는가」는 case 소유다(`timeout-fallback.md`). 실행 상한 값(`AnalysisScope.budget.max_latency_sec`)은 그 문서와 #149 A안이 정했고 여기서 다시 정하지 않는다.

## 1. 목표 · 범위

탐색 job이 끝나지 않으면(Worker 사망 뒤 재시도도 소진 · 큐 적체) 사용자가 「분석 진행」에서 끝없이 기다리지 않게 한다. 마감이 지나면 case가 기다리기를 멈추고(`running_jobs`에서 빠짐), 화면은 중단과 같은 결과로 넘어간다(`core-user-flow.md` 「분석 중단·timeout·인프라 실패」 — 보존된 결과와 다시 탐색하는 출구 — 버튼은 기존 `RETRY_SEARCH`의 「다시 찾기」).

**범위:** `COARSE_SEARCH`만.
**범위 밖:** 단서 구조화(`HINT_EXTRACT`, §5) · 판독 · Fine · export 대기(값과 화면이 없다, §5) · Runtime 실행 취소(하지 않는다).

## 2. 흐름

```
마감 = JobRecord.requested_at + min(scope.budget.max_latency_sec + 30초 + 분석 범위 길이 × 2, 60분)
      (실행 상한 + 30초보다 짧아지지 않는다 — §3-8)

[get_view]        마감이 지난 job은 기다리지 않는 것으로 계산 — 저장하지 않음
[command]         case 잠금 → 마감 지난 job을 STOPPED_WAITING 정산 → 검사 · 처리 → 성공하면 함께 저장
[Worker T2]       case 잠금 → (같은 execution이면 ALREADY_APPLIED) → 마감 지난 job 정산
                  → 이번 job이 그중 하나면 NOT_APPLIED(STOPPED_WAITING), 정산은 저장
```

## 3. 결정

1. **타이머를 두지 않는다. case 행을 읽는 쪽이 마감을 계산한다.** CaseView 조립은 읽기라 저장하지 않고, case 행을 잠그는 command · T2 반영이 `STOPPED_WAITING`을 남긴다. Runtime에 새 주기 작업이나 port를 요청하지 않는다. T2가 끝내 오지 않아도(재시도가 끝난 `STALE`은 case에 전달되지 않는다 — Runtime worker README) 화면은 매 조회마다 같은 계산으로 멈춘 상태를 보인다.
2. **마감 = 발주 시각 + 실행 상한 + 큐 대기 여유 30초.** 실행 상한은 그 job의 AnalysisScope `budget.max_latency_sec`(공개 RC 동안 600초 — §3-9 · §3-10. 이전 일반 운영값은 150초)이다. 여유 30초는 단서 구조화 대기(`start-analysis.md` §3-5)와 같다. scope를 모르는 job에는 마감을 지어내지 않는다. 기준 시각은 `requested_at`이라 큐 대기도 마감에 든다 — 큐가 밀려 탐색이 시작되지 못하는 것도 사용자에게는 같은 기다림이다.
3. **마감 뒤 도착한 결과는 반영하지 않는다**(`NOT_APPLIED(STOPPED_WAITING)`). 정산된 job의 결과는 받지 않는다는 기존 guard(`stop-analysis.md` §3-7) 그대로다. #291에서 합의한 `runtime.retry.after_case_stopped_count`(attempt ≥ 2 ∧ `NOT_APPLIED(STOPPED_WAITING)`)가 이 경로를 센다. timeout 화면에서 결과가 저절로 바뀌지 않고, 사용자는 「다시 찾기」로 다시 시작한다.
4. **실행은 취소하지 않는다.** `CommandResult.cancelled_job_ids`에 넣지 않는다 — `timeout-fallback.md` 「진행 중인 Job은 강제 취소하지 않고, case가 기다리는 것만 멈춘다」. 사용자 요청이 아니라 `case_rev`도 올리지 않는다(정산 기록은 `case_rev`와 무관, `running-jobs-derivation.md`).
5. **화면은 중단과 같은 모양이다.** stage는 `SEARCHING`, `coarse_search`는 `PARTIAL`(B§10 불변조건 5 「사용자 중단 · case timeout처럼 case가 기다리기를 멈춘 job」). 상태는 저장하지 않고 계산한다(`CaseAggregate.analysis_timed_out` — 가장 나중 탐색 job의 정산 사유가 `STOPPED_WAITING`).
6. **notice는 `case.analysis_timed_out`을 새로 둔다**(INFO · non-blocking · `actions:[RETRY_SEARCH]`, `message_key: notice.analysis_timed_out`). 출구는 중단과 같지만 원인이 사용자가 아니라 code를 나눈다 — 같은 code면 web이 「중단했습니다」라고 말하게 된다. 둘 중 하나만 붙고, 마지막 탐색 job의 정산 사유를 따른다. 규칙 원문은 CaseView 계약 B§7 `notices[].code` 행. 문구와 버튼은 web이 확인했다(2026-10-24 신유민, [#358 코멘트](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/358)) — 버튼은 새 라벨 없이 기존 `RETRY_SEARCH`의 「다시 찾기」다. 영상 전체를 다시 보는 동작이라 「이어서 찾기」보다 사실에 맞다(`core-user-flow.md` §7 현재 범위).
7. **command는 잠근 직후 정산한다.** 사용자가 본 timeout 화면의 「다시 찾기」(`RUN_NOTICE_ACTION`)가 같은 기준으로 검사되고, 성공하면 그 정산도 저장된다. 마감이 지난 뒤 `STOP_ANALYSIS`는 기다리는 탐색 job이 없어 `not_allowed`다.

8. **긴 입력은 준비 여유를 더 기다린다(2026-11-04, [#452](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452)).** 마감 기산점이 발주 시각이라 Recording 분석 영상 준비도 마감 안에 든다(§4). EC2에서 120초 입력의 준비만 177.61초였고(#561), 26분 입력은 Search가 시작되기 전에 마감이 지난다. 그래서 마감에 **분석 범위 길이(그 job AnalysisScope의 `TIMELINE_RELATIVE` 범위 합) × 2**를 더하고, 전체 대기는 **60분**을 넘지 않게 한다(`domain.SEARCH_WAIT_PREP_FACTOR` · `SEARCH_WAIT_MAX_SEC`).
   - **준비 여유는 Search 실행 상한(`budget.max_latency_sec`)을 올리지 않는다**(값 자체는 §3-9 · §3-10). 이 값은 Search `RunDeadline`도 정한다(#149 A안). 늘어난 시간은 Search가 아니라 준비 시간이라 case 대기에만 더한다.
   - **잠정값.** 계수 2.0은 EC2 1회 측정(약 1.5배)에 여유를 둔 값, 60분은 26분 입력(약 1560 × 2 + 180 ≈ 55분)이 들어가는 값이다. PM이 11/5 E2E용으로 잠정 승인했다([#564 코멘트](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/564)). 일반 운영값으로 둘지는 미정이다. 배포 머신 26분 실측이 나오면 다시 본다.
   - 짧은 입력은 거의 같다(10초 입력 180 → 200초). 상한에 걸려도 지금처럼 `case.analysis_timed_out`으로 끝난다 — 무한 대기는 없다.

9. **11/5 26분 E2E 동안만 첫 탐색 예산을 600초로 둔다(2026-11-05, [#452](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452)). 일시 예외다.** EC2에서 15개 영상(1,584초)의 Coarse 준비만 173.77초가 걸려 Search `RunDeadline` 150초로는 완주할 수 없다. PM이 「통제된 E2E 검증에 한해 Search 실행 상한을 유한하게 늘린다」를 잠정 승인했고, Search가 600초(준비 220 + provider 약 170 + 재시도 1회 약 175초)를 제안했다.
   - **값을 두는 곳:** `analysis_start.InitialSearchBudget.max_latency_sec` 기본값. 이 값은 첫 탐색 · 「다시 찾기」 · 단서 수정 재탐색의 `COARSE_SEARCH` scope에만 들어간다. Fine은 `observation.FINE_MAX_LATENCY_SEC`(70초)를 따로 써서 바뀌지 않는다.
   - **설정값으로 열지 않는다.** 주입하려면 Runtime 소유 composition root(API · Worker)와 설정 키를 같이 바꿔야 하고, 두 경로가 같은 값을 읽는지도 따로 검증해야 한다. 일시 예외에 쓰기에는 범위가 크다.
   - **그 revision에서는 짧은 입력도 600초다.** 길이에 따라 주지 않는다. Search가 끝나면 바로 반영되므로 실제로 늘어나는 것은 실패할 때의 최대 대기뿐이다. 통제된 E2E 환경이라 받아들인다.
   - **60분 상한과의 관계:** 26분 입력은 `600 + 30 + 1,584 × 2`가 상한 3,600초에 걸린다. 발주 → Search 진입(Recording 준비 + 큐)이 **2,970초 안**이어야 Search 600초를 다 쓴다. EC2 하네스의 같은 구간은 2,448초였다(시험용 검증 포함, 제품 값 아님).
   - **늦은 결과 · 재실행:** §3-3 그대로 반영하지 않는다. Runtime STALE 재실행은 Recording부터 다시 할 수 있어 60분 안에 끝난다는 근거가 없다 — 그 경우 `case.analysis_timed_out`으로 끝나고, 이것을 성공 경로로 세지 않는다.
   - ~~**되돌리기:** E2E 결과가 나오면 150초로 되돌린다.~~ → §3-10에서 공개 RC 동안 600초 유지로 바뀌었다. 당시 결정 이력으로 남긴다.
10. **공개 RC 동안 첫 탐색 예산 600초를 유지한다(2026-11-06 대면 회의, [#452](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452) 정철원 · 김준영 댓글 2026-11-06 · 07).** §3-9의 「E2E 뒤 150초로 되돌린다」를 이번 RC에서는 하지 않는다. 코드 값은 바꾸지 않는다.
   - **이유:** 150초로 되돌리면 긴 입력은 Search 준비만으로 상한을 넘겨 다시 완주할 수 없다(§3-9의 173.77초 실측). 공개 RC가 받는 입력 길이를 검증 전에 줄이게 된다.
   - **검증 근거:** 26분(15개) 검증은 끝나지 않고 보류됐다. 대신 20개 · 20분 입력이 600초로 READY · 신고영상 다운로드까지 갔다(Coarse job 418초 — `docs/runtime/experiments/2026-11-07-ec2-20file-product-e2e-result.md`). 20분 입력의 case 마감은 `600 + 30 + 1,200 × 2 = 3,030초`로 60분 상한 안이다.
   - **그대로 남는 것:** 짧은 입력도 600초다(§3-9). 그래서 Search가 실패하면 짧은 입력도 최대 약 10분을 기다린 뒤에야 시간 초과 안내를 본다. 성공하면 바로 반영되므로 정상 경로 시간은 늘지 않는다.
   - **다시 볼 때:** RC 이후 입력 길이별 처리시간과 `case.analysis_timed_out` 기록을 보고 PM · Search와 다시 정한다. 하나의 값을 되돌리는 대신 범위 길이에 따라 정하는 방식도 그때 본다. 공개 업로드 허용 길이는 별도로 정한다[미정].

## 4. 알려진 한계

- **시계.** 마감은 `requested_at`(발주한 process의 시계)과 판정하는 process의 시계를 비교한다. API · Worker container 시계가 어긋나면 그만큼 마감이 밀리거나 당겨진다. lease처럼 DB `NOW(6)`(Runtime B-L6)를 쓰지 않는다 — case 행에 그 시각이 없다. 수 초 차이는 30초 여유 안에 든다.
- **재시도와의 관계.** Worker가 죽으면 attempt 2는 마지막 heartbeat 뒤 최대 ~82초에 시작한다(Baseline §3.2). 탐색이 길면 attempt 2는 마감 뒤에 끝나 반영되지 않는다. Runtime이 이미 case 확인을 받은 관계다(RD-04b).
- ~~**Recording 준비 시간이 마감에 들어간다**(2026-10-29, #452).~~ → 2026-11-04 준비 여유로 대응(§3-8). 아래는 당시 기록이다. 마감 기산점이 `requested_at`이라 큐 대기와 Recording 분석 영상 준비가 모두 150 + 30초 안에 든다. Search 실행 시계(`RunDeadline`)는 Search 호출부터 센다. 19분 26초 입력은 준비에만 240.8~285.2초가 걸려 Search 시작 전에 마감이 지났다. 기산점은 지금 바꾸지 않고 재측정 뒤 다시 본다 — `long-analysis-range.md` §2-6 · §3.
- **클립 분할 전 값.** 지금 탐색은 클립 1개다. 분할하면 `timeout-fallback.md`의 「150초 × 클립 수」를 scope 예산으로 넘기는 방식에 따라 이 계산도 바뀐다.

## 5. 미결 (채우지 않는다)

- **단서 구조화(`HINT_EXTRACT`) 90초**(`start-analysis.md` §3-5)는 이번에 하지 않는다. 마감 뒤 「빈 단서로 첫 탐색 발주」에는 발주(쓰기)가 필요한데 타이머가 없으면 그 시점이 없다. Runtime은 `APPLIED`일 때만 후속 job을 enqueue한다. 또 90초는 재시도 시작 ~82초와 같은 자릿수라 살아날 분석까지 끊는다. 그래서 Search 함수의 전체 상한 60초와 Runtime 재시도에 맡기고 계속 기다린다. **한계:** 재시도까지 `STALE`로 끝나면 T2가 오지 않아 `SEARCHING`에 머문다. Runtime 확인(2026-10-24 정철원, [#358 코멘트](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/358)): 지금 공개 경계에서는 재시도가 끝난 `STALE`을 T2로 넘기지 않고, 기존 T2를 조용히 넓히지도 않는다. 넘기려면 ① 소진을 알리는 별도 terminal 알림인지 ② T2 확장이면 `produced` 없음 · 중복 전달 · `case_applied_at` receipt 의미 ③ case가 그 job을 어떤 사유로 정산하고 무엇을 다시 발주할지를 Runtime · Case가 먼저 정해야 한다. 이 PR의 탐색 timeout에는 Runtime 변경이 필요 없다. 결정 추적은 [#405](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/405). → **2026-10-27 닫음:** ①별도 terminal 알림으로 정했고, case는 `EXHAUSTED`로 정산한 뒤 빈 단서로 첫 탐색을 발주한다. 단서 구조화에는 case 대기 timeout을 두지 않는다(소진 알림 + 사용자 중단). → `hint-exhaustion.md`
- 판독 · Fine · export 대기 — 값(Fine 70초만 있음)과 timeout 화면이 정해지지 않았다. Fine timeout을 `search.visual_verify_failed`와 같게 보일지는 web과 정한다.

## 6. 고르지 않은 안

| 안 | 고르지 않은 이유 |
| --- | --- |
| Runtime 주기 sweep이 case timeout 함수를 부른다 | Runtime에 새 Task · 합의가 필요하다. 탐색 timeout은 발주가 필요 없어 읽을 때 계산으로 충분하다 |
| 마감 뒤라도 선택 context가 맞으면 반영 | 화면이 timeout 상태에서 저절로 바뀌고, `STOPPED_WAITING` 이름 · #291 지표 의미와 어긋난다 |
| `get_view`가 정산을 저장 | 읽기 경로가 쓰기 transaction을 갖게 된다. 계산이 같으므로 저장은 다음 쓰기에 맡겨도 화면이 같다 |
| `case.analysis_stopped`를 그대로 쓴다 | 사용자가 누르지 않았는데 「중단했다」고 말하게 된다 |
| timeout 때 Runtime 중단 요청 | `timeout-fallback.md`가 이미 하지 않기로 했다 — 비용이 나간 호출을 버리지 않는다 |
| 긴 입력에 탐색 예산(`max_latency_sec`)을 늘린다(#452) | Search 실행 상한까지 같이 늘어난다(#149 A안 단일 권위). 늘어난 시간은 준비 시간이라 Search 합의 없이 바꿀 이유가 없다. 11/5 E2E는 Search 준비 자체가 150초를 넘어 PM · Search 합의로 일시 예외를 두었고(§3-9), 공개 RC 동안 유지한다(§3-10) |
| 마감을 설정값(env)으로 열어 배포가 넣는다(#452) | 값의 소유가 흐려지고, 짧은 입력도 같은 시간을 기다리게 된다 |
| 마감 기준을 실행 시작 시각으로 | Runtime 실행 기록이 있어야 하고, 시작조차 못 한 job(큐 적체 · Worker 부재)은 끝없이 기다린다 |

## 7. 테스트

- `tests/case/test_case_wait_timeout.py` — 마감 계산(scope 예산 · 여유, 단서 구조화 · scope 모름은 마감 없음), view(마감 전 대기 · 마감 뒤 `PARTIAL` · notice · 저장 안 함), T2(마감 전 `APPLIED` · 뒤 `NOT_APPLIED(STOPPED_WAITING)` 정산 저장 · 다른 job T2에서도 정산), command(「다시 찾기」 · 취소 없음 · 중단 `not_allowed`).

## 8. 남은 것

- 위 §5 미결(단서 구조화 항목은 2026-10-27 `hint-exhaustion.md`로 닫음).
- 잠정값 확정 뒤(runtime 머신 재측정, `timeout-fallback.md`) 여유 30초도 다시 본다.
