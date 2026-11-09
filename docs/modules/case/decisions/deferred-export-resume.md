# 보류된 자동 내보내기는 반영 커밋 직후 한 번 더 발주한다 (#674 B안)

> **상태: 결정 · 구현(이 PR) · Runtime 리뷰 대기** · 2026-11-09 · 담당 유소연(`case`, 발주) · 연결부 리뷰 @cheol1203(JobExecution) · @flosure23(Runtime 정책) · 관련 [#674](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/674), #351, #664, `report-video-export.md`, `result-reflection.md`

## 1. 문제

공개 A1에서 마지막 번호판 · 시각 판독(OCR) 결과를 반영하면 Case가 신고용 영상 · 번호판 이미지 내보내기를 자동 발주한다. 그런데 이 발주는 매번 `LOCAL_CONCURRENT`로 보류됐고, 사용자가 「신고용 영상 만들기」를 누르기 전에는 영상도 복사 버튼도 나오지 않았다.

원인은 반영 중인 OCR이 자기 슬롯을 차지한 상태에서 판정되기 때문이다. 반영 T2 안에서는 그 OCR의 `case_applied_at`이 아직 비어 있다. 그래서 `refresh_active`가 케이스를 「사용 중」으로 보고 그 케이스의 로컬 admission을 모두 `active`로 남긴다. 그 합에 내보내기 2건을 더하면 로컬 동시 한도를 넘는다. 보류된 발주는 `local_work_state`(안내 문구용)에만 남고, 다시 발주하는 경로가 없었다.

## 2. 결정

1. **반영 T2가 커밋된 직후, 같은 Worker가 별도 transaction에서 보류분을 한 번 더 발주한다.** 연결 지점은 `worker/composition.py`의 직접 반영(`reflect`)이고, 결과가 `APPLIED`일 때만 실행한다. 이때는 OCR이 이미 반영돼 슬롯이 풀려 있다.
2. **발주 판단은 Case가 반영 · command와 같은 gate로 한다.** `reflection.resume_auto_exports(case_id, store, admit_auto_exports)`가 `_auto_export_gate`(`issue_missing_exports` + READY gate)를 다시 부른다.
   - `EVIDENCE_REVIEW`가 아니면(후보를 다시 고르는 중이거나 이미 READY) 아무것도 하지 않는다.
   - 현재 선택 후보와 현재 내보내기 요청 기준이다. 후보가 바뀌었으면 이전 후보의 보류분이 아니라 지금 후보 것을 발주한다.
   - 같은 입력은 fingerprint로 건너뛴다. 다시 불러도 중복 발주가 없다.
   - 자동 발주이므로 `case_rev`를 올리지 않는다(반영 경로와 같음). 바뀐 것이 없으면 저장하지 않는다.
3. **재시도는 `LOCAL_CONCURRENT` 보류에만 한다.** `LOCAL_LIMIT` · `JOBS_STOPPED` · `STOPPED` 등은 일시적인 자리 부족이 아니다. 지금처럼 안내와 수동 버튼을 남긴다.
4. **admission은 기존 `admit_local`을 그대로 쓴다.** 요청 키는 `auto-export-resume:<execution_id>`다. 성공하면 `admit_local`이 `local_work_state`를 지워 보류 안내가 사라진다. 다시 거절되면 아무것도 바꾸지 않는다(보류 안내 · 수동 버튼 유지).
5. **재시도 실패는 반영 결과를 바꾸지 않는다.** T2는 이미 커밋됐다. 예외는 삼키고, 사용자에게는 이전과 같은 보류 안내와 수동 버튼이 남는다.

## 3. 알려진 한계

- **다른 케이스가 슬롯을 차지한 경우:** 커밋 직후에도 자리가 없으면 다시 보류된다. 그 케이스에서 다음 반영이 일어나지 않으면 수동 버튼이 필요하다. 이번 이슈의 실제 원인(자기 점유)은 아니라서 이번 범위에서 다루지 않는다.
- **재전달 경로:** `common/jobs/redelivery.py`의 재전달 반영에는 연결하지 않았다. 재전달은 Worker 장애 복구 경로라 드물다. Runtime 공통 코드에 hook을 추가하는 일이라 Runtime 담당과 따로 정한다.
- **관측:** 재시도 실패를 로그로 남기지 않는다. 로그 이벤트를 추가하려면 Runtime 소유인 `common/logging/catalog.py`를 바꿔야 한다. `[미결 유지]` — Runtime 담당 판단.

## 4. 고르지 않은 것

- **웹이 보류 안내를 보면 자동으로 재요청한다** — 다른 케이스와 겹치는 경우까지 풀리지만 탭이 열려 있을 때만 동작한다. Web 모듈 수정도 필요하다.
- **Worker 주기 스캐너가 보류 케이스를 훑는다** — 모든 경우가 풀리지만 새 백그라운드 루프라 Runtime 변경이 가장 크다. 위 한계가 실제로 문제가 되면 다시 본다.
- **`reflect_terminal` 안(T2 안)에서 재시도한다** — T2 안에서는 반영 중인 job이 여전히 슬롯을 차지하므로 같은 이유로 거절된다. 또 옛 결과를 다시 전달해도 새로 발주되지 않는다는 기존 보장(`test_export_t2_deferral`)과 부딪힌다.
- **동시 실행 집계에서 반영 중인 job을 뺀다(A안)** — Runtime 정책 · 계약 영역이다. #674에 선택지로 제안했고 이 결정과 독립적이다.
