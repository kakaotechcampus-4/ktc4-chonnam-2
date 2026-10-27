# RT-13(a) Docker Compose Implementation Plan

> Execution: `superpowers:executing-plans`, TDD, one fresh read-only reviewer after direct verification. User instructions override skill defaults: no worktree, commit, staging, push, PR, or intermediate reviewer.

**Goal:** 승인된 M4 local Compose 경계를 구현한다. `IN_PROGRESS · Refs #300 (RT-13(a))`를 유지한다.

**Architecture:** Python 3.12 단일 image, command를 나눈 api/worker와 one-shot migrate, MySQL 8.4. 별도 named data/media volumes와 보호된 host file의 read-only mount를 쓴다. migration runner에는 파일에서 읽은 URL을 stdin으로만 전달한다.

**Tech Stack:** Python 3.12, locked uv, ffmpeg, Docker Compose, 기존 pytest/MySQL evidence gate. Compose 파일은 추가 YAML dependency 없이 검사할 수 있는 YAML의 JSON subset으로 작성한다.

**Spec:** [#300 Owner 승인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/300#issuecomment-6433879506), Runtime Plan RT-13/§12, Ops §4–5, Tech §4.4/§15.2, Baseline B-W1/W4/O1/H3/§2.6, RD-12.

## Global Constraints

- 시작 branch `codex/rt13a-docker-compose`, HEAD/remote develop `ef5806aec92307fa89fdc489b61f9fab9a1702bc`, clean index/worktree 확인.
- api ready: interval 10s, timeout 5s (> B-H3 3s), retries 3, start_period 10s. Worker stop grace 30s.
- api/worker numeric UID/GID 일치, non-root. Secret 값은 argv/image/Config.Env에 넣지 않는다.
- media/staging/temp/spool non-tmpfs. B-O1 20m × 5; application INFO 유지.
- 승인 댓글이 Plan의 이전 PR 경계/NOT_BASELINED보다 새 Accepted Owner Decision이다. 승인값 반영이며 새 숫자/production 정책 선택이 아니다.
- Docker 미설치 및 MySQL 미설정은 성공 증거로 대체하지 않는다.

## Review Focus

1. 파일 credential 권한: UID 10001이 실제로 읽고 다른 사용자 접근을 넓히지 않는지.
2. fresh named volume seed의 디렉터리 소유권과 재생성 보존.
3. migrate 실패 시 dependency가 fail closed인지, runner의 부분 DDL 실패 의미 보존.
4. secret-bearing 예외/child output이 stdout/argv/env로 새지 않는지.
5. smoke 전용 project/volume만 정리하고 기존 자원을 건드리지 않는지.

### Task 1: Image / Compose와 failure-mode verifier

Files: `Dockerfile`, `.dockerignore`, `compose.yaml`, `docker/runtime.py`, `scripts/check_compose.py`, `tests/deploy/test_compose.py`, `tests/deploy/test_runtime.py`.

- [x] 요구된 잘못된 image/dependency/secret/volume/UID/path/tmpfs/health/grace/rotation 구성을 거부하는 테스트를 먼저 작성하고 RED 증거를 저장한다.
- [x] 단일 image, read-only env-file, stdin migration bridge, ready caller 및 Compose verifier를 최소 구현한다.
- [x] 실제 bundle과 mutation/negative controls를 GREEN으로 검증한다.

Interfaces: verifier `validate(config: dict, dockerfile: str, dockerignore: str) -> list[str]`; runtime `main(argv=None) -> int`. 기존 CLI `python -m daesingo.common.db.migrate --database-url-stdin`를 재사용한다.

### Task 2: 전용 local smoke와 운영 기록

Files: `scripts/smoke_compose.py`, `tests/deploy/compose_probe.py`, `tests/deploy/test_smoke_compose.py`, `.env.example`, `docs/runtime/rt13a-docker-compose.md`, Baseline, Implementation Log, root README 사실 절.

- [x] smoke의 project/cleanup safety와 secret inspection negative control을 RED→GREEN으로 작성한다.
- [x] config/build/up → migration/ready → HTTP command/view/upload → worker byte read → killed claim/STALE/attempt2 → recreate persistence → inspect → finally cleanup 경로를 구현한다.
- [x] RT-13(b) logical backup/restore smoke 및 필요시 후속 검증 확장, RD-12f/h production 및 RT-14 경계를 문서화한다.
- [x] 승인값의 근거/Evidence/지표/Trigger, 구현 Notes와 Log를 남긴다.

### Task 3: 검증과 fresh reviewer

- [x] 관련 회귀, 전체 pytest 1회(JSON/JUnit), mandatory MySQL gate와 strict validator, boundary/Contract/workflow/diff 검증을 수행한다. 긴 실행 원본과 재실행 증거를 분리한다.
- [x] Docker 실행 가능 시 전용 smoke 수행. 불가능하면 실행 전 차단/미검증 항목을 정확히 기록한다.
- [x] `fork_turns=none` reviewer 1회. P1/P2는 같은 세션에서 RED→GREEN 수정 후 같은 reviewer 재리뷰.
- [x] 미커밋/미스테이징, 최종 branch/HEAD/index, 변경 파일과 제외 파일/자원 정리를 보고한다.

## Execution result

구현 및 동일 fresh reviewer 재리뷰 완료. 수행 체크는 acceptance PASS를 뜻하지 않는다. 최종 deploy79개는 implementer/reviewer 각각 통과했다. 실제 Docker는 preflight에서 차단, 전체 pytest3실패와 mandatory strict gate FAIL을 보존한다. RT-13은 IN_PROGRESS이며 최종 기록은 docs/runtime/rt13a-docker-compose.md를 따른다.

## Docker 설치 후 재개 계획

- [x] 기존17개 SHA-256과 branch/HEAD/index 무결성을 확인한다.
- [x] 실제 Docker acceptance를 전용 project/새 volumes로 수행하고 실패 상태를 먼저 수집한다.
- [x] 이전 API2건/nested900초를 원본·재현·develop과 대조한다. RT-13 원인일 때만 TDD 최소 수정한다.
- [x] 최종 실제 MySQL 포함 전체 pytest1회와 그 JSON/JUnit strict gate1회를 수행한다(별도 중복 전체/MySQL suite를 만들지 않는다).
- [x] 문서/수정 delta를 같은 fresh reviewer에게 읽기 전용 후속 검토시킨다.
- [x] 전용 자원만 정확히 정리하고 미커밋·미스테이징으로 결과를 보고한다.

위 초기 결과는 보존 이력이며 설치 후 새로운 증거로 소급해 고치지 않는다.

실제 Docker9단계/cleanupPASS. 최종full12678pass/3fail/33skip/xfail0, MySQL1045pass/skip-xfail0/strictPASS. 새3fail은 검증사본Git문맥/PATH누락으로 대조확인했고 소스불변 상태의 targeted 보완환경에서후보/develop각3pass다. 전체공식3fail은유지하고전체/strict재실행없음이다. exact자원정리/독립audit완료이며최종리뷰와보고를남긴다.

동일freshreviewer최종후속:새P1/P2없음·추가수정요청없음,실행증거읽기전용대조(테스트/strict/Docker재실행없음). 미커밋intermediate후보이며공식전체3FAIL/원격CI미확인한계유지. 최종결과기록만추가하고실행code/tests불변·17후보·HEAD/index보존상태로보고한다.

