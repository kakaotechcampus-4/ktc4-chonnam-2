# 발생시각 없음 — `evidence.event_time_missing` notice로 이유와 출구(`EDIT_EVENT_TIME`)를 보인다

> 2026-10-29 · 결정 추적 [#449](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/449) Case 확인 요청 2 · 관련 `input-commands.md` · case-command 계약 §12-3 「notice action 싣기」 · CaseView 계약 B§7 `notices[].code`

## 1. 문제

공개 영상처럼 메타데이터가 지워지고 파일명이 바뀐 입력은 발생시각 출처(사용자 정정 · 화면 시각 · 파일명 · 파일/제조사 메타데이터)가 모두 빈다. evidence는 발생시각 없이 Package를 만들지 않는다(`package.input.occurred_at_missing`). 그래서 그 case는 다른 단계가 모두 성공해도 `EVIDENCE_REVIEW`에 머문다.

입력형 command `EDIT_EVENT_TIME`(`input-commands.md`)이 출구지만, 막힌 이유를 알리는 notice가 없었다. case notice 중 시각 관련은 0개였다. 화면은 왜 묶음이 안 되는지, 무엇을 하면 되는지 말하지 않았다.

## 2. 결정

1. **`evidence.event_time_missing`을 등재한다.** 모양: `severity:WARN` · `blocking:true` · `actions:[EDIT_EVENT_TIME]` · `message_key: notice.event_time_missing`.
2. **`blocking:true`다.** 시각을 넣기 전에는 어떤 조작으로도 Package에 가지 못한다. 번호판 보류(`evidence.plate_abstained`)는 번호판 없이도 Package가 나가서 `blocking:false`인 것과 다르다.
3. **발동 조건: `evidence`가 non-null이고 `evidence.record_id`가 non-null이며 `event_time_display.value`가 null일 때.**
   - 응답 전 부분 투영(`record_id=null`)은 시각을 아직 정하지 않은 상태라 「없음」으로 보지 않는다.
   - 상황 응답 여부와는 무관하다. 응답 전에도 시각은 입력할 수 있고, 응답 전 이유는 `case.situation_response_pending`이 함께 나른다.
4. **사라지는 조건은 값이 생기는 것이다.** 사용자가 `EDIT_EVENT_TIME`으로 시각을 넣으면 `event_time_display.value`가 채워져 붙지 않는다. 따로 정산하지 않는다.
5. **재확인(`evidence.time_needs_user_confirmation`)과 code를 나눈다.** 그쪽은 시각은 있는데 확인이 필요한 상태이고, 이쪽은 시각이 없어 묶음이 막힌 상태다. 같은 code면 web이 「확인해 주세요」로 막힌 상태를 가볍게 말하게 된다.
6. **접두어는 evidence다.** 시각을 정하는 `TimeResolution`을 evidence가 만든다(B§7 `notices[].code` 규칙). case는 CaseView 값만 보고 붙인다.

## 3. 구현

- `service.EVENT_TIME_MISSING_NOTICE` · `service.derive_notices()`의 evidence 갈래.
- 테스트 `tests/case/test_event_time_missing_notice.py` — 모양, 발동 · 비발동(값 있음 · 부분 투영 · evidence 없음), `EDIT_EVENT_TIME` 입력 뒤 사라짐(`RealAdapter` mock 원본에서 `occurred_at`을 뺀 결과로 재현).
- 계약: CaseView B§7 `notices[].code` 등재, case-command 계약 §12-3 「notice action 싣기」.

## 4. 남은 것

- web 문구 `notice.event_time_missing`(신유민). 예: 「발생 시각을 찾지 못해 신고자료를 묶을 수 없어요. 시각을 직접 입력해 주세요.」 — 확정은 web.
- #449 검증 계획 「`EDIT_EVENT_TIME` 한 번으로 `requirements_package`가 PASS/WARN이 되고 `package`가 생긴다」는 실제 경로(같은 공개 영상 입력)로 아직 확인하지 않았다.
