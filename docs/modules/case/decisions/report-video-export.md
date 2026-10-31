# 신고용 영상 — 첫 발주 시점 · `case.report_video_not_generated` · 재시도 버튼

> **상태: 결정 · notice 구현 · 자동 발주 배선 보류** · 결정일 2026-10-13 · 담당 유소연(`case`) · 근거 [#351](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/351) [결정 코멘트](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/351#issuecomment-6143734339), #47 Q3, #280, `core-user-flow.md` 「신고자료 묶음 전」 · 「신고용 영상 생성」
> 발주와 notice는 case 소관이다(#351). 신고용 영상 생성 자체(C-07)는 recording, 요건 판정은 evidence 몫이다. 규칙 원문은 CaseView 계약 A§7(발주 시점 · `GENERATE_REPORT_VIDEO` 매핑) · B§7(`notices[].code`)로 옮겼다.

## 1. 문제

신고용 영상이 없는 real case는 신고 단계로 갈 길이 없었다(#351 §1).

- 영상을 만드는 `REPORT_VIDEO_EXPORT`를 발주하는 곳이 데모(`demo_happy_001.py`)뿐이다.
- 그 입구인 `case.report_video_not_generated` notice는 real 경로에서 만드는 코드가 없고, 계약에도 발동 조건이 없었다.
- notice가 없으면 web은 응답 대기가 아닐 때 영상 칸을 있는 것처럼 그린다(`ResultScreen.tsx`).
- notice가 붙어도 `RUN_NOTICE_ACTION`은 이전 `JobRecord`가 없으면 `not_allowed`다.

## 2. 결정

1. **[R-1] case가 자동 발주한다.** evidence가 있고, 선택 후보의 신고 상황 응답이 끝났고(`CONFIRMED` · `CORRECTED` · `USER_UNSURE`), 신고용 영상이 없고, 같은 입력의 `REPORT_VIDEO_EXPORT`가 아직 없을 때다.
   - 응답 전에는 만들지 않는다 — Flow 「신고자료 묶음 전」.
   - Package에 영상이 필요하므로 READY 전에 발주한다. #47 Q3의 「`mark_ready` 직전」을 바로잡는다. `PLATE_IMAGE_EXPORT`도 같은 시점을 따른다.
   - 입력은 선택 후보 IncidentClip과 사후 각인 여부 · 각인 값이다. 후보를 바꾸거나 시각을 고치면 입력이 달라져 다시 발주한다(Flow 「새 후보로 다시 만든다」).
2. **[R-2] notice는 영상이 없는 동안 계속 붙이고, 버튼만 상황에 따라 싣는다.** 조건은 `service.report_video_missing(view)` 하나로 두고 자동 발주도 같은 함수를 쓴다.
   - `evidence.record_id`가 있고(응답 전 부분 투영이 아니다), 선택 후보 응답이 끝났고, `requirements_package.checks`의 `package.asset.report_video.exists`가 `PASS`가 아닐 때.
   - 실행 중에도 붙인다 — 거두면 web이 없는 영상을 있는 것처럼 그린다.
   - `GENERATE_REPORT_VIDEO`는 이전 `REPORT_VIDEO_EXPORT` JobRecord가 있고 그 kind가 `running_jobs`에 없을 때만 싣는다.
3. **[R-3] `RUN_NOTICE_ACTION`은 이전 `JobRecord`를 계속 요구한다.** 첫 발주는 [R-1]이 하므로 버튼은 실패 뒤 재시도다. 계약 표의 「기존 `job_id` 없으면 새로 만든다」를 「직전 발주 입력으로 새 `job_id`」로 고쳤다.

## 3. 고르지 않은 것

| 안 | 고르지 않은 이유 |
| --- | --- |
| Package 오류 사유 `package.asset.report_video_missing`을 발동 조건으로(#351 본문 후보) | 발동하지 않는다. 영상이 없으면 `report_video.exists`가 `UNKNOWN`이고 overall이 PASS/WARN이 아니라 `build_report_package()`는 `package.requirement_not_ready`에서 먼저 멈춘다 |
| 「PASS/WARN이 아닌 check가 `report_video.exists` 하나뿐」(「영상만 남음」) | 성립하지 않는다. 영상이 없으면 첨부 규칙(`package.asset.*_count` · `total_size`, `attachment_policy_v1.json`)과 사후 각인(`package.time.post_stamp_applied`)도 함께 `UNKNOWN`이다 |
| 실행 중 notice를 거둠 | web이 응답 대기가 아닐 때 notice가 없으면 영상이 있는 것처럼 그린다 |

## 4. 지금 한 것 · 보류한 것

- **한 것:** `report_video_missing()` · notice(`derive_notices`) · 재시도 근거(`build_view_from_adapter`가 이전 `REPORT_VIDEO_EXPORT` JobRecord 유무를 넘김) · 계약 A§7 · B§7 · `scenario_plate_reread_001` rev4에서 notice 제거(응답 전이다 — 다음 행동은 `case.situation_response_pending`).
- **보류 — 자동 발주 배선([R-1]).** 지금은 영상을 만들 실행기가 없다 — recording `REPORT_VIDEO_EXPORT` capability(C-07)와 Worker handler 등록(RT-10 #297)이 없고, 동기 real 경로는 후보 선택 뒤 관찰을 JobRecord 없이 adapter가 돌린다. 실행기 없이 발주하면 정산되지 않는 job이 `running_jobs`에 남아 「신고용 영상 만드는 중」이 끝나지 않는다. 그동안 notice는 버튼 없이 「아직 없어요」만 보인다.
- **T2 반영기(2026-10-24):** `REPORT_VIDEO_EXPORT` · `PLATE_IMAGE_EXPORT` 결과는 정산 + READY gate로 반영한다(`result-reflection.md` §3-4). [R-3] 재시도로 발주한 job이 Worker에서 돌아와도 멈추지 않는다. 자동 발주([R-1])는 아래 재개 조건 그대로 보류다.
- **재개 조건:** recording export handler가 생기면 command 처리 뒤(`execute_command`의 READY gate 자리)와 T2 관찰 반영 뒤(`observation-storage.md` §4-5)에서 `report_video_missing()`과 「같은 입력의 발주 없음」으로 발주한다. 입력(IncidentClip · 사후 각인 값)과 fingerprint는 RT-10 「handler가 읽는 case 입력」(#297 Consult)에서 함께 정한다 — 지금 adapter는 TimeResolution · IncidentClip ref를 내보내지 않는다.

## 5. 미결 (채우지 않는다)

- ~~export 실패 code 매핑~~ → **닫힘(2026-10-29).** RT-10(b) #442가 `case/exports.py` `export_notices()`로 `recording.report_video_export_failed` · `recording.plate_image_export_failed`를 내리고, 같은 날 CaseView 계약 B§7에 그 모양 그대로 등재했다. 남은 것은 web 문구(`notice.report_video_export_failed` · `notice.plate_image_export_failed`, 신유민)다.
- `GENERATE_PLATE_IMAGE`의 notice 발동 조건 — 같은 모양이라 #351을 따르되(#351 범위 밖), 번호판 이미지는 선택 첨부라 Package를 막지 않는다(#280).

## 6. Runtime implementation checkpoint — 2026-10-29

The RT-10(b) Recording export implementation connects [R-1] at the existing
command and observation T2 READY-gate locations. It fixes each request in a
separate append-only Case input map, uses the #351 response/evidence gate and
deduplicates automatic orders by kind plus full-input fingerprint. Case relays
the existing Evidence policy limit injected by composition; no byte policy is
calculated here. Current successful/reflected produced refs select the generated
assets, and Case relays Recording's transform fact for post-stamp evaluation.

The plate input/failure wire choices use the user's explicit PM delegation and
remain #47 Owner deferred review. They do not replace the decision above or
claim additional Case Owner approval. The export failure notices now follow the
existing Contract mappings; limit exhaustion has no same-input plate retry.
Detailed verification, limitations and file manifest are in the
[Implementation Notes](../../../runtime/rt10b-recording-exports.md).
