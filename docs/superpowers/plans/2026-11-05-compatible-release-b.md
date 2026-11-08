# 호환 중간 release B 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 사용자 요청에 따라 commit/push/게시/운영 작업은 하지 않는다.

**Goal:** e50이 읽는 신규 쓰기를 유지하면서 최종 후보의 청크·metadata envelope를 읽고 exact replay하는 B를 만든다.

**Architecture:** 현재 전용 브랜치의 reader·Case/Worker 동작은 유지한다. Recording repository에 명시적 저장 정책을 두고 B의 기본을 legacy로 설정한다. 기존 ref는 잠금 아래 저장 표현을 보존하고 metadata/descriptor/content를 검증한다. 최종 후보는 기준 SHA `ceb6f5fa010f1f541179e9d3ab95aecd5a82d3cb`, e50은 `e50b2976ef4edc3a030cfc5b03a5206340dd917b`의 실제 source snapshot으로 대조한다.

**Tech Stack:** Python 3.12, SQLAlchemy/PyMySQL, MySQL 8.4, pytest.

**Spec:** 이 대화의 2026-11-05 사용자 구현 요청과 직전 전이 조사. 이 문서는 실행 승인이나 release SHA/image 승인 파일이 아니다.

## Global Constraints

- 현재 `codex/issue452-compatible-release`에서 작업한다. 원본·보호 증거·기존 volume 보존.
- AWS·운영 DB·publish·서비스 중단·배포·commit·push·외부 게시 금지.
- controller와 migration 의미, Coarse 600초 및 종료 후 150초 후속 release 조건 유지.
- e50→B와 C→B를 검증한다. C 이후 e50 직접 rollback은 승인하지 않는다.
- DB 검증은 새 소유 격리 DB만 사용한다. resource와 정확한 소유 대조 후 소유 시험 자원만 정리한다.

## Review Focus

- metadata-only가 envelope로 새로 저장되는 누락.
- 기존 C ref의 B replay가 payload/BLOB/청크를 덮어쓰는 경우.
- legacy JSON 저장이 float를 바꿔도 exact guard를 통과하는 경우.
- SQL packet 초과·case link 실패를 caller가 잡고 commit했을 때 부분 상태 잔존.
- Case unknown fields·600 scope·T1/T2 replay의 단순 load 성공을 처리 호환성으로 확대하는 경우.

## Task 1 — B 저장 정책과 원자적 재사용

Files: `src/daesingo/recording/mysql_repository.py`, 필요 시 Recording 소유 helper; `tests/recording/test_compatible_release*.py`.

- [x] 신규 metadata-only/native/BLOB 기대값의 실패 테스트를 먼저 실행한다.
- [x] B 기본 legacy, 명시 chunked 테스트 정책, 두 표현 reader 유지. 신규 native JSON은 재조회 exact mismatch면 savepoint를 rollback한다.
- [x] existing ref는 metadata exact·descriptor·서버 bytes integrity 검증 후 표현을 그대로 재사용한다. 불일치·오류의 case link는 남기지 않는다.
- [x] chunk writer의 기존 검증은 명시 chunked 정책으로 계속 실행하고 B default 소비도 검증한다.

## Task 2 — 실제 revision 전이 검증

Files: `tests/recording/test_compatible_release_mysql.py`, test-only revision runner/utilities, 필요 시 필수 MySQL inventory.

- [x] git object에서 e50/C source를 별도 임시 경로에 읽기 복사하고 subprocess로 실행한다. checkout/생산 코드 monkeypatch로 다른 revision을 흉내내지 않는다.
- [x] 새 MySQL 8.4에서 e50 seed→B migration/read/write→C read/write→B read/replay를 확인한다. AnalysisSource/IncidentClip, metadata-only, native/envelope×legacy/chunk 조합, 원자성·caller rollback·새 연결을 검증한다.
- [x] 실제 Case 저장·scope/produced·T2 재전달을 비교하여 필요한 보완만 한다. controller의 C 이후 O 거부도 기존 실제 전이 테스트로 확인한다. 합성 job 프로토콜과 실제 handler 검증의 범위는 기록에서 구분한다.

## Task 3 — 검증·독립 리뷰·기록

Files: `docs/runtime/compatible-release-b.md` 및 관련 canonical 문서 최소 수정.

- [x] 관련 offline/실제 MySQL, 프로젝트 regression 선택, lint·boundary·contract·diff 검증을 실행하고 실패/skip/NOT_RUN을 분리한다. 초기 전체 regression10 실패와 MySQL strict gate NOT_RUN을 기록했다. 후속에서10건은 개별 재검증으로 정산했고 전체 MySQL은1276 passed/1 failed다. strict gate 통과로 표시하지 않는다.
- [x] fresh 독립 reviewer가 사용자 요구·diff·실행 근거를 읽고 검토했다. RR 후속 결함은 작성자가 세 형식 RED→GREEN으로 보완했다. 초기 종료 시 NOT_RUN이던 후속 독립 재리뷰는 아래 PR 준비 후속에서 수행했다.
- [x] B와 C source identity·배포물/하네스 차이·호환 승인/backup 조건·150 복귀·한계를 기록한다. release 승인·운영 실행은 NOT_RUN으로 유지한다.

## 실행 기록

- 시작 HEAD `ceb6f5fa`, 전용 브랜치 clean/index empty 확인. 새 worktree 대신 사용자가 준비한 전용 브랜치를 사용한다.
- Windows Docker Desktop pipe 없음. Ubuntu의 기존 별도 Docker daemon은 응답하며 실행 중 container 없음. 기존 volume은 사용하지 않는다.
- 계획/검증 로그는 `.codex-scratch/compatible-release-b/`에 보존한다. commit 금지이므로 기록을 삭제하지 않는다.
- Ruling: 제품 수정은 Recording repository 한 파일로 제한했다. 기존 C 기준 Case/Worker와 controller/migration을 유지하고, 구버전 대조와 실제 Worker 시험을 추가했다. 모든 handler의 revision 전이까지 승인한 것은 아니다.
- Ruling: 전체 회귀 실패는 B 외부 기능을 바꾸거나 assertion을 완화해서 없애지 않는다. 자원/도구를 보완한 개별 재검증 및 C baseline 대조와 함께 실패 원본을 보존한다.
- 최종 수치·리뷰 범위·NOT_RUN은 `docs/runtime/compatible-release-b.md`의 실제 실행 기록을 따른다. 체크박스는 작업을 수행하고 기록했다는 뜻이며 배포 gate 전체 PASS가 아니다.

## PR 준비 후속 — 2026-11-05

- 현재 브랜치·HEAD·변경12개와 empty index를 다시 확인했다. checkout·staging·commit·push·외부 게시를 하지 않는다.
- 사용자 명시 요청에 따라 RR 수정과 반례 테스트를 독립 재리뷰했다. 확정 P1/P2 없음. raw metadata/chunks·실제 MP4/MIME assertion 보강을 반영하고 그 diff도 독립 확인했다.
- 기존 실패10개 각각을 실제 후속 PASS JUnit에 연결했다. 도구가 갖춰진 Linux에서 미확인이던 diagnostic2개만 새로 실행했다. 기존 확인8개는 재사용하며 전체 regression 재통과로 바꾸지 않는다.
- canonical 필수 MySQL을 부분 검사와 분리해 실제 `tests.ci_orchestration mysql`로 실행한다. frozen 공개 소스 hash·uv.lock 고정 의존성·실제 MySQL8.4·전체 collection·strict·실제 보고서 변조·봉인 근거를 사용한다. assertion/skip/timeout은 바꾸지 않는다.
- B legacy writer와 B 병합 후 별도 C의 chunk/envelope writer 복귀를 PR 설명에 구분한다. 배포 image/backup/restore 검증은 NOT_RUN으로 남긴다.
- 실행 하네스는 `.codex-scratch/compatible-release-b/pr_*.py`이며 제품 코드나 배포물에 포함하지 않는다. WSL/Docker Desktop 경로·네트워크 차이로 선행 연결 검사가 실패한 기록과 도구 준비 실패를 보존한다. UUID로 소유 DB를 확인한 runner에서 gate를 실행한다.
- canonical gate 최종 결과와 PR 준비 판정은 후속 runtime 기록 및 로컬 PR 본문에 기재한다.
- 첫 완료된 전체 MySQL에서 기존 analysis-source 한도 검사의 청크 기본값 전제2건이 드러났다. 이 파일을 Bdefault/Cexplicit writer2×mode3으로 확장하고 기존 C assertion·한도/transaction/fingerprint를 유지했다. 독립 검토 후 집중6건 통과. 따라서 시작12파일에 이 검사1개가 추가되어 총13파일이며 별도 frozen source로 전체 gate를 다시 실행한다.
- 후속 canonical 전체 pytest는1276 passed/1 failed로 종료했다. Worker cancellation metric의 ±30ms 상한 실패는 인과관계 확인 필요이며 strict checker·실제 보고서 변조는 NOT_RUN이다. 필수 gate 통과/PR 준비 완료로 표시하지 않는다.
- baseline probe 준비 중 task image cache가 C: 공간을 소진해 Ubuntu emergency_ro/시작 오류가 발생했다. 사용자 허용 범위의 Ubuntu 재시작 및 미사용 task bind 정상 해제를 수행했으나 복구되지 않았다. 사용자가 추가 WSL/Docker Desktop 재시작을 거절하여 중단했다. 원본·보호 증거·기존 volume 삭제나 강제 fsck·VHD 수정은 하지 않았으며 내부 증거 무결성 확인은 미완료다.
- 최종 로컬 PR 초안·13파일 hash 목록·검증 결과는 준비하되 PR 상태는 BLOCKED다. 남은 Worker baseline 대조와 환경 복구·전체 canonical 후속 단계는 NOT_RUN으로 남긴다.
