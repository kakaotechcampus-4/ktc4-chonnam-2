# 유형이 판별되면 신고 상황 응답 없이 신고용 영상을 발주한다 (#597 B안)

> **상태: 결정 · Case 쪽 구현(발주 조건 · 응답 대기 notice · `report_draft` 투영, case-view/v1.13) · Evidence [#618](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/618)과 통합 · Web 변경 전** · 2026-11-07 · 제품 결정 김준영([#597](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/597) 2026-11-07) · 담당 유소연(`case`, 구현 리드) · 관련 `core-user-flow.md` §10 · §15(Evidence 소유, 갱신 예정), `contract-job-record-case-view.md` B절 `notices[]`, #171 B-2 · C-2, #351, #545

## 1. 문제

후보 · 번호판 · 시각 · 위치를 다 준비한 뒤 결과 화면에서 「신고 상황」 응답(맞아요 / 잘 모르겠어요)을 한 번 더 받아야 신고문 · 신고용 영상 · 묶음이 만들어졌다. 사용자에게는 「다 찾아 놓고 또 확인을 받는 단계」로 보였다(#597 피드백). PM이 B안 — 유형을 판별했으면 상황 확인 없이 초안을 보여 주고 영상 · 묶음 준비를 시작 — 으로 정했다.

## 2. 결정 (Case 쪽)

1. **신고용 영상 · 번호판 이미지 자동 발주의 조건에서 「상황 응답 완료」를 뺀다.** 조건은 「EvidenceRecord가 조립됨(`evidence.record_id` non-null)」이다(`exports.issue_missing_exports`, `service.report_video_missing`). 나머지 조건(선택 후보 하나, FINAL 요건에 `package.asset.report_video.exists`가 있음)은 그대로다.
   - Fine `OBSERVED`는 응답 전에도 EvidenceRecord가 조립된다(`real_e2e.assemble_evidence_bundle`) — 바로 발주된다.
   - Fine `UNCERTAIN`은 「잘 모르겠어요」(`USER_UNSURE`) 전에는 조립되지 않는다(evidence `classify_visual_evidence` → `AWAIT_SITUATION_RESPONSE`, `record_id` null). 응답 조건을 따로 두지 않아도 지금처럼 응답을 기다린다. 이것이 「유형을 판별하기 어려운 경우에는 상황을 확인」이다.
   - 영상 · 번호판 이미지는 상황 응답 값에 따라 달라지지 않는다(clip + 사후 각인, best_frame 크롭). 응답 뒤 다시 만들 일이 없다.
2. **`case.situation_response_pending`은 조립 전 부분 투영(`record_id` null)에만 붙인다.** 조립된 evidence(Fine `OBSERVED`)에는 붙이지 않는다 — 응답을 기다리지 않으므로 「준비 전」 이유가 아니다.
3. **상황 응답 상태는 `NOT_ASKED`로 둔다.** 무응답을 시스템이 응답으로 바꾸지 않는다(#171 B-2는 그대로). `RECORD_SITUATION_RESPONSE` command는 그대로 받는다 — 유형 정정 경로(#545)에서 쓸 수 있다.
4. **`case.report_video_not_generated`는 응답 전에도 붙는다.** 조건이 같으므로 영상이 아직 없으면 「신고용 영상이 아직 만들어지지 않았습니다」(INFO)가 생성 중에 보인다. 실행 중에는 버튼을 싣지 않는 규칙(#351 [R-2])은 그대로다.

## 3. 다른 모듈에 남은 것 (이 결정만으로는 묶음이 나가지 않는다)

- **Evidence(김준영, #618):** `OBSERVED + NOT_ASKED`만 응답 없이 특정형 신고문 · 묶음 요건을 통과한다(요건 정책 v7). `OBSERVED + USER_UNSURE`는 계속 막는다. 정본은 `docs/modules/evidence/decisions/observed-report-draft.md`.
- **CaseView 초안(이 PR):** 최상위 `report_draft: {title, description} | null` — 현재 선택의 조립된 EvidenceRecord를 evidence `render_report_draft()`에 넘긴 결과를 그대로 싣는다(`view.py`, case-view/v1.13). 조립 전 · 렌더 불가면 `null`. 최종 신고문은 `package.report` 그대로다.
- **유형 정정(#545):** 기존 `RECORD_SITUATION_RESPONSE {CORRECTED, visual_event_type}`로 정정 기록과 `CORRECTED` 응답을 함께 남긴다(김준영 #597 2026-11-07). 발생시각 정정으로 사후 각인 입력이 바뀌면 현재 입력과 같은 export만 결과로 세고(`stored_observation`), 영상이 없어진 것으로 보아 새 입력으로 다시 발주한다 — 코드 경로 확인, 통합 E2E에서 실제 확인한다.
- **Web(신유민):** `selectScreen.ts`는 EVIDENCE_REVIEW에서 job이 돌고 응답 대기 notice가 없으면 진행 화면이다. 이 결정 뒤에는 `OBSERVED`일 때 영상 생성 중 진행 화면이 보인다 — 「생성 중에도 초안 표시」를 위해 web이 바꾼다.
- **mock 시나리오:** `data/mock/case/`의 응답 전 스냅샷(happy · correction_rerun · plate_reread)은 web 데모 · 테스트도 쓰므로 이전 흐름 그대로 두었다. web과 함께 B안 흐름으로 바꾼다. 그때까지 Case 테스트는 바뀐 두 code(`case.situation_response_pending`, `case.report_video_not_generated`)만 fixture와 대조하지 않는다(`B597_FIXTURE_LAG`).

## 4. 고르지 않은 것

- **`OBSERVED`면 시스템이 `CONFIRMED`를 대신 기록한다** — 무응답을 응답으로 바꾸는 것이라 #171 B-2와 부딪히고, 사용자가 보지 않은 판정을 확인한 것처럼 남긴다. PM 결정도 `NOT_ASKED` 유지다.
- **발주 조건에 Fine 판정(`OBSERVED`)을 직접 넣는다** — 조립 여부는 evidence `classify_visual_evidence`가 이미 정한다. Case가 같은 판단을 다시 하면 두 곳이 어긋날 수 있다.
