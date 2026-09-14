# CaseView 16 스냅샷 렌더 결과 — 2026-09-14

> 대상: `apps/web` @ 첫 커밋 · 입력 `data/mock/case/*.json`(Mock Pack v5, 7 시나리오 16 스냅샷)
> 재현: `npm run dev:web` → 화면 상단 스냅샷 바에서 각 항목 클릭. 아래 표는 렌더된 DOM에서 배지·버튼·notice를 그대로 수집한 것이다.
> 「1차 완료 체크리스트」의 `web` 항목 증빙.

## 결과 — 16건 전부 렌더, 파싱 위반 0건

| 스냅샷 | 고른 화면 | 값 상태 배지 | 렌더된 버튼 | notice (B=차단) |
| --- | --- | --- | --- | --- |
| happy #1 | PROGRESS · `stage=SEARCHING` | — | — | — |
| happy #2 | HANDOFF · `READY` rev3 | 출처 확인됨 · 확인 필요 · AI 추정 | 자료 내려받기 · 항목 복사 · 안전신문고 열기 | — |
| happy #3 | HANDOFF · `READY` rev4 | 출처 확인됨 · 확인 필요 · AI 추정 | 자료 내려받기 · 항목 복사 · 안전신문고 열기 | — |
| correction_rerun #1 | EVIDENCE rev2 | 출처 확인됨 · 확인 필요 · 알 수 없음 · AI 추정 | 시각 직접 입력 | I:`evidence.time_needs_user_confirmation` · I:`readout.overlay_not_present` |
| correction_rerun #2 | EVIDENCE rev3 | 출처 확인됨 · **사용자 확인됨** · 알 수 없음 · AI 추정 | 신고용 영상 만들기 | I:`evidence.time_post_stamp_required` · I:`readout.overlay_not_present` |
| plate_reread #1 | EVIDENCE rev3 | 알 수 없음 · 출처 확인됨 · AI 추정 | 번호판 직접 입력 | I:`evidence.plate_abstained` |
| plate_reread #2 | EVIDENCE rev4 | 출처 확인됨 · 알 수 없음 · AI 추정 | 신고용 영상 만들기 | I:`case.report_video_not_generated` |
| unknown_abstain_partial #1 | EVIDENCE rev3 | 출처 확인됨 · 확인 필요 · 알 수 없음 · AI 추정 | 시각 확인하기 | I × 4 (`time_conflict_needs_notice`·`overlay_not_present`·`visual_event_unconfirmed`·`time_post_stamp_required`) |
| unknown_abstain_partial #2 | HANDOFF · `READY` rev4 | 확인 필요 · 알 수 없음 · 출처 확인됨 · AI 추정 | 시각 확인하기 · 자료 내려받기 · 항목 복사 · 안전신문고 열기 | I × 4 (위와 같음) |
| infra_failure #1 | PROGRESS · evidence 조립 전 | — | — | I:`readout.overlay_presence_undetermined` |
| infra_failure #2 | PROGRESS · evidence 조립 전 | — | 번호판 다시 읽기 | **B:`readout.plate_read_failed`** · I:`readout.overlay_presence_undetermined` |
| infra_failure #3 | PROGRESS · evidence 조립 전 | — | 번호판 다시 읽기 | I:`case.plate_read_cancelled` · I:`readout.overlay_presence_undetermined` |
| infra_failure #4 | PROGRESS · evidence 조립 전 | — | 번호판 다시 읽기 | I:`case.plate_read_cancelled` · I:`readout.overlay_ocr_failed` |
| empty #1 | NO_RESULT · 후보 0건 | — | 설명 고치기 · 다시 찾기 | I:`search.no_candidates` |
| relative_rebase #1 | CANDIDATES · 후보 1건 | — | — | — |
| relative_rebase #2 | CANDIDATES · 후보 1건 | **이전 기준으로 찾은 장면** | — | — |

## 이 표가 증빙하는 것

- **`info_state` 5종 전부 화면에 떴다** — 출처 확인됨 · 사용자 확인됨(correction_rerun #2, fixture 통틀어 1건) · AI 추정 · 확인 필요 · 알 수 없음
- **등재 `actions[]` 7종 전부 렌더 경로가 있다** — `EDIT_EVENT_TIME`(시각 직접 입력) · `GENERATE_REPORT_VIDEO` · `MANUAL_PLATE_INPUT` · `RETRY_PLATE_READ` · `REVIEW_TIME` · `EDIT_HINT` · `RETRY_SEARCH`
- **`notices[].code` 12종 전부 문구가 매핑됐다** — fallback으로 빠진 건 없다
- **blocking과 non-blocking이 갈린다** — 전체에서 blocking은 `readout.plate_read_failed` 1건이고 나머지는 안내로 렌더된다
- **`evidence=null`(6건)·`candidates=[]`(1건)·`package=null`을 실패로 그리지 않는다** — 진행 상태 화면과 빈 결과 화면이 따로 있다
- **WARN에서도 제출 경로가 열린다** — `unknown_abstain_partial #2`는 `requirements_package.readiness=WARN`인데 capabilities 3종 버튼이 그대로 뜬다(값 상태 표시 규칙 §3-7)
- **`stale_revision_label_key`로 문구를 고른다** — `relative_rebase #2`에서만 뜨고 boolean으로 문구를 만들지 않는다

## 아직 증빙하지 못한 것

- **같은 `job_id`의 attempt 대표 선택** — `representativeJobs()`로 구현했으나 **v5 fixture에 중복 `job_id`도 `attempt` 필드도 없어** 목데이터로 눌러볼 수 없다. 코드만 있고 화면 증빙이 없는 상태다.
- **`at_provenance` 출처 문구** — `case-view/v1.4`의 `at_provenance_label_key` 확정 대기. 지금은 raw 값을 mono로 그대로 보여준다.
- **위치 미확보 notice 문구**(이슈 #48 Q3) — 값 등재 후 매핑 추가.
- **PNG 화면 캡처 3장** — 회의 자료용으로 별도 확보 필요.

## 부수 발견 — fixture 불일치 1건

`notices[].code`는 12종인데 `message_key`는 13종이다. `evidence.time_post_stamp_required` 하나가 두 키로 내려온다 — `notice.post_stamp_required`(correction_rerun #2)와 `notice.time_post_stamp_required`(unknown_abstain_partial #1·#2). 같은 뜻이라 web은 같은 문구를 매핑해 두었으나, 한쪽으로 통일하는 편이 맞다(fixture 반영: 유소연).
