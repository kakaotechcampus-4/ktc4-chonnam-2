# RT-08(b) Implementation Plan

**Goal:** 승인된 Case interface로 POST /cases와 GET /cases/{case_id}/view를 연결한다. Refs #295 (RT-08(b)).

**Spec:** Runtime Implementation Plan §6 RT-08 · §12, HTTP API Contract §3 · §5.1 · §5.4, Case jobexecution-read-port 결정 및 PR #342 합의. HEAD/최신 develop: `d436de08f8e16a11a99a322ce7fd1de36e80c05a`(PR #366).

**Architecture:** API composition이 caller transaction을 소유한다. 요청별 CaseStore에 MySQLCaseRepository와 Runtime read_executions를 주입한다. 생성 commit 뒤 별도 read transaction으로 get_view를 호출한다. 생성 후 조회 실패는 반영 여부를 보존해 500으로 처리한다. Case 내부·Contract·Decision·Baseline은 변경하지 않는다.

## 선택

- composition의 공개 함수 호출: API에서 aggregate/SQL로 재구현하는 대안은 Case 경계를 침범하므로 제외.
- 생성 commit 뒤 공개 조회: commit 전 응답 조립 대안은 Plan/요청 순서와 다르므로 제외.
- 생성 후 조회 실패 500: 이미 생성됐을 수 있으므로 미반영을 뜻하는 503으로 반환하지 않는다.
- 동기 DB 경로에 logger를 넘기지 않는다. 기존 bounded ApiEvents만 사용한다.

## Review Focus

- body를 읽거나 client identity를 신뢰하지 않는 생성, 정확한 201/body/Location.
- commit 후 조회 실패 및 COMMIT ACK 유실에서 503을 잘못 반환하지 않는가.
- Case share lock 뒤 동일 Connection으로 Runtime read, scope/대표 상태는 Case가 결정하는가.
- 입력·SQL·예외·경로·secret·Runtime private column이 응답/로그에 새지 않는가.
- JSON/JUnit 필수 evidence의 family 및 개별 parameter/layer 누락을 거부하는가.

## Tasks

- [x] `tests/api/test_cases_view_mysql.py`: 실제 migration/HTTP 생성·조회·404·body 무시·read projection·caller rollback·Case lock 순서·pool/1205/1213/disconnect/COMMIT ACK loss·postcommit read failure·privacy/correlation RED.
- [x] `tests/common/db/test_mysql_gate.py`, nested migration gate: 신규 acceptance inventory 및 부분 누락 RED.
- [x] `api/composition.py`, `routes_cases.py`, `routes_view.py`, `app.py`: 공개 호출/tx/오류 최소 구현 후 GREEN. 기존 API unpublished route 회귀의 /cases 기대는 405로 갱신.
- [x] `scripts/check_mysql_test_report.py`: 독립 필수 acceptance identity 추가 후 GREEN. nested 900초/CI 20분 유지.
- [x] targeted → 전체 pytest(require MySQL) → JSON/JUnit gate·누락 mutation → boundary·Contract fixture·workflow·diff 실행. 최초 전체 Worker 2 FAIL, 별도 MySQL 8.4 전체 nested timeout/진단 관측기 충돌 2 FAIL을 구분해 기록했다. 전체 GREEN·병합 가능 판정은 보류한다.
- [x] README/Implementation Log/Implementation Notes에 결과·대안·한계·PR #366 merge SHA 기록. RT-08 IN_PROGRESS 유지. staging/commit/push/PR 생성 없음.

## 2026-10-17 통합 후속

위 기준 SHA·CI 20분·실패 수치는 구현 당시 snapshot이다. 현재 재적용 기준은 #371 merge `4f383c9412593fb8e415598dfa7481fb447a1b2c`이며 #372 merge `a5d61cc7d1fc9d02c229deca87bd0c2a7aec2ed1`를 포함한다. workflow 30분·nested 900초, timestamp35와 API21 필수 evidence를 함께 유지한다. 직접 검증과 원본 감사는 Implementation Log의 통합 후속에서 구분한다. **IN_PROGRESS · Refs #295 (RT-08(b)) · PR/SHA pending**. 원본 checkout 보존, 커밋·스테이징·푸시·PR 생성 없음.
