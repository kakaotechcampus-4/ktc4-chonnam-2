# web 화면 캡처 3장 — 2026-09-14

> 대상: `apps/web` @ 화면 정리분 · 입력 `data/mock/case/*.json`(Mock Pack v5)
> 재현: `npm run dev:web` → 상단 스냅샷 바에서 해당 항목 클릭
> 「1차 완료 체크리스트」 Merge 전 셀프 체크 증빙 — web 몫.

| 파일 | 스냅샷 | 보여주는 것 |
| --- | --- | --- |
| `01-ready-happy-rev4.png` | `case_h001` rev4 · `stage=READY` | **정상.** 신고자료 화면이 `report_field_states`로 렌더된다. 위치만 「확인 필요」(출처: 사용자가 말한 위치)이고 신고유형·위반내용은 「AI 추정」 — `stage=READY`·`user_reviewed=true`에서도 미확정 표시가 남는다 |
| `02-progress-happy-rev1.png` | `case_h001` rev1 · `stage=SEARCHING` | **처리 중.** 값 상태가 아니라 진행 상태 화면이 나온다(`evidence=null`). 「진행 중인 작업」에 `job_h001_search`가 뜬다 |
| `03-blocked-infra-failure-rev2.png` | `case_x001` rev2 · `stage=EVIDENCE_REVIEW` | **차단.** `blocking=true` notice(`readout.plate_read_failed`)가 빨간 「진행할 수 없음·ERROR」로, non-blocking(`readout.overlay_presence_undetermined`)은 파란 「안내」로 갈린다. `RETRY_PLATE_READ` 버튼이 등재값이라 렌더된다 |

## 화면에 보이는 것 중 제품에 안 들어가는 것

**한 화면 = 한 단계**로 맞췄다(`core-user-flow.md` §4-1). 다른 단계의 패널을 증빙으로 봐야 할 때는 맨 아래 점선 접힘(`증빙용 — …`)에 들어 있고, 접힌 상태가 제품 흐름과 같은 모양이다.

캡처 상단의 **스냅샷 바 16개 버튼**과 **「스냅샷 16건 파싱 OK」 배지**, notice 아래 **code 문자열**은 개발·증빙용이다. 실제 앱에서 사용자는 자기 사건 하나만 보고, 이 세 가지는 빠진다. 목업 화면 설계(10종 레이아웃)도 아직 입히지 않은 상태다 — 지금 증빙해야 하는 것이 「`CaseView`만 읽어 화면 상태가 갈리는가」이기 때문이다.
