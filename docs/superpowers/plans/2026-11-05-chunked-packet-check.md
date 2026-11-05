# Writer-aware deploy-packet Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline; request one independent whole-change review. Commit/push/publish/dispatch/deploy are forbidden for this task.

**Goal:** 실제 이미지 writer 형식에 맞춰 packet 기동 검사를 수행한다.

**Architecture:** 기존 `mysql_repository.add_prepared_media`의 budget/chunk 계산을 `prepared_command_limits(packet, *, write_format, command_budget=None)`로 추출하고 writer와 runtime이 함께 사용한다. runtime은 설치된 module의 `PREPARED_WRITE_FORMAT`만 읽는다. legacy는 기존 `check_packet(MAX_BYTES,P,margin)`, chunked는 공통 함수의 양수 chunk와 `check_packet(command_budget,P,margin)`를 사용한다.

**Tech Stack:** Python / SQLAlchemy / PyMySQL / pytest, offline only.

**Spec:** [기존 최소 수정안](../../runtime/rt14-packet-compatibility-review.md)과 이번 사용자 지시. 제어 workflow나 host/env format toggle은 추가하지 않는다.

## Global Constraints

- 현재 branch/base `codex/rt14-chunked-packet-check` / `d7aca292a2431e639ed3838c564c7c306d03581d` 유지. 시작 미커밋 변경 없음.
- B `ce0750d5a3317ad1c810783d67f8a05ba88bce08`는 변경하지 않는다. 새 C′ SHA/image/digest는 향후 CI·publish 단계에서 새로 고정한다.
- MAX_BYTES 양수, Recording 업무 한도, metadata·무결성·escaping·SAVEPOINT·RR 동작을 유지한다. Coarse 600초/종료 후150초 복귀와 #583 분리 유지.
- 실제 DB/이미지 검증은 NOT_RUN. Docker 재구축·대규모 복제·AWS·서버 변경·배포·commit·push·게시 금지. 기존 증거/volume/원본 보존.

## Review Focus

- 전체 MAX_BYTES>P인 chunked가 통과하되 legacy는 거부한다.
- budget+margin==P, 너무 작은 packet, 잘못된 양수 타입/형식을 거부한다.
- env 위장 입력은 선택된 이미지 형식을 바꾸지 못한다.
- shared 계산을 실제 writer도 호출하고, 실제 렌더 SQL escaping guard를 우회하지 않는다.
- 설정 검증·실패의 engine dispose·비밀 비출력 계약을 유지한다.

## Task: 공통 계산과 runtime 분기

Files: `src/daesingo/recording/mysql_repository.py`, `docker/runtime.py`, 새 `tests/deploy/test_packet_compatibility.py`; runtime packet 조사 문서 정합화.

- [x] 실제 runtime main에 fake DB 경계만 연결한 packet/형식/양수/정책 경계 테스트를 작성하고 전체 M>P 성공 사례의 RED를 확인했다.
- [x] shared 계산 테스트와 실제 PyMySQL escaping guard의 offline 부정 대조를 작성했다.
- [x] 기존 계산을 공통 함수로 추출하고 실제 writer 호출을 연결했다. runtime 분기만 수정했다.
- [x] GREEN, 관련 offline 배포/Recording 회귀410개, Ruff·경계·diff를 확인했다. 전체/실제 DB·image는 NOT_RUN으로 구분했다.
- [x] 독립 리뷰 및 보강 재검토에서 잔여 확정 P1/P2 없음. 문서/검증 기록·파일 SHA256·Draft PR 본문을 `.codex-scratch/chunked-packet-check/`에 준비한다. staging/commit/push하지 않는다.

Ruling: 사용자가 기존 문서의 최소 수정안을 명시적으로 구현하도록 승인했으므로 설계 재승인을 요청하지 않는다. 기존 SQL 식을 그대로 공유하며 추가 packet/memory/시간 보장을 주장하지 않는다.

## 실행 근거

`red-confirmed.xml`:23 failed/22 passed → `green-workspace-temp.xml`:72 passed → `regression-final.xml`:410 passed. 최초 잘못된 PyMySQL positive fixture 및 Windows 기본 temp 권한 오류는 숨기지 않고 별도 초기 XML에 보존했다. 리뷰의 optional 사각지대는 실제 기본 format 일치/shared policy의 DML 이전 거부 전파 테스트로 보강하고 재확인했다. checkbox가 아닌 XML·AST/bytes 대조·파일 hash를 근거로 사용한다.
