# `worker` — Worker composition root

**Owner:** 김준영 (공통 기반/운영) · **경계:** `docs/architecture/module-architecture.md` §1-5 · §6-2 · §8-2

- 배포 단위 「Worker 1」. `common/jobs`에서 row를 claim → RUNNING + heartbeat → 도메인 모듈의 **public capability**를 dispatch → 결과 ref + usage 기록.
- `STALE`은 실행 중 Worker가 살아 있지 않다고 Runtime이 판정한 terminal 실행 상태다. `case`가 현재 context에 유효하지 않다고 판단해 반영하지 않는 늦은 결과(중단된 job 등)와는 다른 개념이다 — 그런 실행은 `SUCCEEDED`를 유지하고, `case`가 그 `produced`를 domain state에 반영하지 않아 현재 `CaseView`를 덮지 않는다 (`docs/architecture/contracts/contract-job-execution.md` §6 · §9-8).
- Background로 가는 것(§8-1): 큰 source/proxy 준비 · RemoteCopy upload · Coarse/Fine 외부 AI · 장시간 OCR · Incident Clip / Report Video export.

## 상태

RT-01의 `bootstrap.py`를 구현했다. `bootstrap(revision=...)`은 `DAESINGO_ENV_FILE`(미지정 시 cwd `.env`)을 명시적으로 읽어 불변 Worker RuntimeConfig를 만들고, Search의 기존 `GeminiSearchConfig.from_dotenv(mapping)` 및 추가 등록 모듈의 factory/validator를 startup에서 호출한다. 실패 시 설정 key 이름만 기록하고 `SystemExit(1)`로 종료한다. `revision`은 호출자가 전달하는 commit SHA 등 안전한 식별자다.

필수 파일 key는 `DAESINGO_RUNTIME_DB_URL` · `DAESINGO_RUNTIME_MEDIA_ROOT` · `DAESINGO_RUNTIME_WORKER_TEMP_ROOT`와 현재 Search가 사용하는 `GEMINI_API_KEY`다. Search key rename/alias 의미는 바꾸지 않는다. pricing/FX는 필수값으로 강제하지 않는다. 반환된 `Startup.modules["search"]`는 마스킹된 credential과 검증된 Search config를 보관한다.

DB engine · claim loop · handler dispatch · heartbeat/sweep 실행은 아직 없다. 실제 provider 호출도 하지 않는다. thread에 correlation을 전달할 때는 `common.logging.copy_context_call`로 제출 시점의 context를 캡처한다. queue column을 통한 process 간 trace 전달은 RT-03 이후다. 세부 선택과 검증 결과는 [Implementation Log](../../../docs/runtime/runtime-implementation-log.md)에 기록한다.
