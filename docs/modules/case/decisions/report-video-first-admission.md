# 신고영상과 번호판 이미지가 함께 거절되면 신고영상만 다시 받는다 (#675 결정 항목 2)

> **상태: 결정 · 구현(이 PR)** · 2026-11-10 · PM 확인으로 이번 배포 범위에 포함 · 담당 유소연(`case`) · 관련 [#675](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/675)([검토 코멘트](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/675#issuecomment-6743322783)), `deferred-export-resume.md`(#674), `report-video-export.md`, #676

## 1. 문제

공개 A1에서 자동 발주는 신고영상(`REPORT_VIDEO_EXPORT`)과 번호판 이미지(`PLATE_IMAGE_EXPORT`)를 한 묶음으로 admission한다. 그래서 로컬 작업 자리가 하나만 남으면 둘 다 보류되고, 사용자가 수동으로 만들기 전에는 READY가 되지 않았다.

번호판 이미지는 READY 조건이 아니다. 묶음(ReportPackage)에는 생성돼 있을 때만 들어간다(`evidence/requirements.py`). 선택 항목 때문에 필수 항목이 막히고 있었다.

## 2. 결정

1. **묶음이 거절되면 번호판 이미지를 빼고 신고영상만 한 번 더 묻는다.** `exports.gate_auto_exports`가 반영 · 보류분 재발주 · command 세 경로의 자동 발주를 모두 맡는다.
   - 둘 다 받아들여지면 지금과 같다.
   - 신고영상만 받아들여지면 신고영상만 발주한다. 번호판 이미지는 발주하지 않고 기록(JobRecord · export 입력)도 남기지 않는다.
   - 신고영상까지 거절되면 아무것도 발주하지 않는다. 선택 항목에 마지막 자리를 쓰지 않는다.
   - 신고영상이 이미 있고 번호판 이미지만 빠졌으면 번호판 이미지만 한 번 묻는다.
2. **선택 항목은 `OPTIONAL_EXPORT_KINDS = {PLATE_IMAGE_EXPORT}`로 둔다.** `issue_missing_exports(skip=...)`로 그 kind만 이번 발주에서 뺀다. 발주 조건(#351 · #597)은 바꾸지 않는다.
3. **admission 키는 바꾸지 않는다.** 거절된 admission은 호출자 savepoint로 되돌아가 행이 남지 않는다. 그래서 같은 키(반영 `auto-export:<execution_id>`, 재발주 `auto-export-resume:<execution_id>`, command는 payload 해시)로 다시 물어도 새 요청으로 처리된다. command는 API가 결과를 같은 키로 한 번 더 admission하는데, 그때 받는 목록(신고영상만)이 Case가 받아낸 목록과 같아서 충돌하지 않는다. Runtime · API 코드는 바꾸지 않는다.
4. **번호판 이미지만 보류돼도 보류 상태(`local_work_state`)는 남는다.** 무엇이 보류됐는지 사용자가 알아야 하기 때문이다. 보류 사유가 `LOCAL_CONCURRENT`면 #674의 반영 직후 재발주가 번호판 이미지만 다시 시도한다. 안내 문구를 어떻게 구분할지는 #676(Web) 범위다.

## 3. 고르지 않은 것

- **번호판 이미지를 먼저 · 따로 묻는다** — 자리가 하나뿐일 때 선택 항목이 먼저 가져갈 수 있다.
- **kind마다 admission 키를 나눈다** — Runtime(`public_reflection.py`)과 API(`composition.py`) 키 규칙을 바꿔야 한다. 위 3처럼 키를 그대로 써도 되므로 고르지 않았다. #675 검토 코멘트에서는 이 방법을 적었는데, 구현하면서 필요 없다는 것을 확인했다.
- **번호판 이미지를 admission 없이 발주한다** — 로컬 작업 한도를 우회한다. 한도 정책은 Runtime 소유다.
