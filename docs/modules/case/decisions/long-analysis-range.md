# 긴 분석 범위 — MVP에서는 나누지 않고, 상한을 넘으면 변환 전에 구분되게 실패한다

> 2026-10-29 · 결정 추적 [#452](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452) Case 확인 요청 3 · 4 · 관련 `timeout-fallback.md` · `case-wait-timeout.md` §4 · `start-analysis.md` 알고 가는 한계 2 · #168 (c)

## 1. 문제

case는 업로드된 전체 범위를 scope 하나 · `COARSE_SEARCH` 하나(`max_latency_sec=150`)로 발주한다. 클립 분할은 구현되지 않았다(`timeout-fallback.md` 「남은 것」).

#452에서 MP4 22개(총 1,166.13초)를 한 case로 올렸을 때 두 가지가 드러났다.

- **저장 상한이 먼저 걸린다.** Recording이 분석 영상(234,566,319 bytes)을 만드는 데 약 285초가 걸렸고, 그 뒤 DB 저장 상한(`max_allowed_packet` 64 MiB)을 넘어 저장 단계에서 실패했다. 실패는 원인을 구분할 수 없는 `RUNTIME_HANDLER_ERROR`로 끝난다.
- **준비 시간이 case 대기 마감에 들어간다.** 마감은 `requested_at + 150 + 30초`(`case-wait-timeout.md` §3-2)라 큐와 Recording 준비 시간을 포함한다. Search의 실행 시계(`RunDeadline`)는 Search 호출부터 센다. 그래서 이 입력은 Search가 시작되기 전에 화면 대기가 끝난다.

## 2. 결정

1. **MVP에서는 분석 범위를 나눠 발주하지 않는다.** 분할 발주는 #168에 overlap 길이 · 중복 제거 호출 지점이 남아 있고, 분할 크기에 Search inline 상한과 Recording 저장 상한이 함께 들어가야 해서 Case · Search · Recording이 같이 바뀐다. #168 (c)에 남긴다.
2. **범위 상한의 수치는 case가 갖지 않는다.** 저장 상한(Recording)과 inline 상한(Search)은 각 Owner의 값이다. case가 「몇 분까지」를 따로 계산하면 같은 값이 두 곳에 생기고, 한쪽만 바뀌면 어긋난다.
3. **상한을 넘는 범위는 Recording이 변환 전에 거르고, 원인을 구분할 수 있는 실패로 돌려준다**(#452 Recording 확인 요청 1). 4분 변환 뒤 일반화된 오류로 끝나지 않게 하는 것이 목적이다. Recording 답(#452, 2026-10-29): (1) 별도로 확정한 지원 길이를 넘는 요청은 변환 전에 거부하고, (2) 변환 중에도 누적 결과가 저장 한도를 넘으면 DB write 전에 중단한다. code는 Recording `ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED` · Runtime terminal `RECORDING_ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED`다. 지원 길이 수치는 Runtime profile 측정 뒤 Recording이 정한다(「약 5분」은 추정).
4. **case는 그 실패를 탐색 실패와 다른 notice로 옮긴다.** `search.candidate_search_failed`(다시 찾기)와 구분해 「분석 범위가 너무 김」을 알린다. 같은 입력으로 다시 찾아도 결과가 같으므로 `RETRY_SEARCH`를 싣지 않는다 — 「실행 경로가 없는 action은 싣지 않는다」(CaseView 계약 B§7)와 같은 원칙이다.
5. **150초 잠정값은 유지한다.** 이 값은 Search 실행 상한(`AnalysisScope.budget.max_latency_sec`)이고 Recording 준비 시간과 별개다.
6. **case 대기 마감의 기산점은 지금 바꾸지 않는다.** Search 시작부터 세려면 Runtime · Recording이 「준비 끝 · Search 시작」을 case에 알려야 한다(cross-module). 결정 3대로 긴 범위가 변환 전에 거부되면, 마감에 걸리는 것은 상한 안의 범위뿐이다.

## 3. 확정 조건 · 재측정

- `timeout-fallback.md` 잠정값의 확정 조건 「Runtime 머신 재측정」에 **Recording 준비 · 큐 대기 · Search를 나눠 잰다**를 더한다. #452 측정은 셋을 합친 경과만 대기 마감과 비교할 수 있었다.
- 재측정에서 상한 안의 범위가 마감(180초)을 넘으면 그때 여유 30초 또는 기산점을 다시 정한다.
- 참고 추정(측정 아님): #452 입력의 비율(1,166초 → 준비 240.8~285.2초)을 그대로 적용하면 5분 범위의 준비 시간은 약 62~73초다. 영상 내용 · 머신에 따라 달라진다.

## 4. 지금 한 것 · 남은 것

- **한 것:** 이 문서 · `timeout-fallback.md` 「남은 것」 · `case-wait-timeout.md` §4 갱신. 코드 변경 없음.
- **남은 것 — 「분석 범위가 너무 김」 notice 등재 · 구현.** Recording code는 정해졌고(결정 3), Recording · Runtime 구현 뒤 한다. 발동 조건은 마지막 탐색 job의 실패 code가 `RECORDING_ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED`인 경우다. 할 일: notice code · `message_key` · CaseView 계약 B§7 등재 · web 문구(@uminshin). 담당은 10/30~11/3 Case 인수자(서어진).
- **남은 것 — 접수 단계 안내.** web이 업로드 단계에서 미리 안내할지는 web 판단이다. 안내에 수치를 넣으면 그 출처는 Recording 값이어야 한다(결정 2).

## 5. 고르지 않은 것

| 안 | 고르지 않은 이유 |
| --- | --- |
| case가 분석 범위 길이 상한(예: 5분)을 두고 `START_ANALYSIS`에서 거부 | 바이트 상한을 길이로 바꾸는 비율이 영상마다 다르다. 같은 값이 case와 Recording 두 곳에 생긴다(결정 2) |
| MVP 안에 클립 분할 발주 구현 | #168 미결과 3개 모듈 변경. 분할 크기도 저장 상한을 반영해야 해서 Recording 결정이 먼저다(결정 1) |
| case 대기 마감을 Search 시작부터 계산 | Runtime · Recording의 새 신호가 필요하다. 상한 안의 범위가 실제로 마감을 넘는지 재측정 전에는 근거가 없다(결정 6) |
