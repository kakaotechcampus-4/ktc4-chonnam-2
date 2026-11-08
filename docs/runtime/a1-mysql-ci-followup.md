# #629 MySQL 관측 범위 수정과 제출 구분

2026-11-08 로컬 후속. 기준 HEAD는 `117bf0efae64e3590acf301d83ee70d0966926ff`,
A-1 도입 전 고정 parent는 `5004f652b6d115546e44987c926930016ab93409`다.
이 문서는 이전 [Web 인계](a1-public-web-handoff.md)의 MySQL 미해결 판정을 갱신한다.
원격 결과를 로컬 수정본의 결과로 바꾸지 않는다. 운영 미적용 / 공개 NO-GO다.

## 원인과 최소 수정

- A-1은 dispatch 전에 binding 조회, terminal 처리 전에 Case tag 조회 transaction을 추가했다.
  internal Worker도 public Case를 우회 처리하지 않도록 이 조회는 유지한다.
- 취소 시험은 checkpoint 뒤 **첫 commit**에 실제 COMMIT OK 관측을 연결했다. 이제 먼저 실행되는
  tag 조회 commit을 terminal commit으로 오인했다. `finish()`에 진입한 실제 transaction 객체에만
  관측을 연결한다. COMMIT 응답 유실 뒤 UPDATE 없이 durable row를 확인하는 replay도 포함한다.
- T1/T2 sink 시험은 composition의 모든 transaction 결과를 terminal 결과 목록에 넣었다.
  시험 fixture의 `job_execution`/`rt04b_case` 접근을 `before_execute`에서 구분해, DB kill보다 먼저
  해당 시도를 포착한다. 다른 조회도 같은 고장 observer에 전달하고 별도 정확한 횟수로 검증한다.
- 제품 Worker·공유 admission·예약·취소 metric 구현은 수정하지 않았다. 기존 durable 상태,
  writes/retry/실제 connection kill 횟수, COMMIT 응답 유실, 30ms 허용치와 380ms 하한,
  timeout·skip·canonical/strict gate를 유지한다. helper는 해당 fixture 전용이며 범용 SQL 분류기가 아니다.

## 변경 전후 근거

원격 #629 base `f068c9de5d73ac83c483d291e99612889c2d144c`에서 확인한 Worker composition,
WorkerLoop와 세 실패 시험 파일의 Git blob은 위 고정 parent와 모두 동일하다.
전체 원격 base source를 실행한 것으로 표현하지 않는다.
동일한 로컬 Python 의존성·캐시된 MySQL 8.4.13·packet 64MiB에서 순차 실행했다.
DB는 전용 tmpfs, memory/swap 각각 1GiB, CPU 2, pids 256이며 기존 volume은 연결하지 않았다.

| 실행 | 결과 | 판정 |
| --- | --- | --- |
| 원격 run 42405787097, HEAD 117bf0ef | MySQL 1,310 PASS / 23 FAIL; 신규 A-1 19 PASS | 원래 CI 실패 유지. strict·실제 보고서 변조 NOT_RUN |
| 고정 parent 원래 23건 | 23 PASS | 비교 기준 |
| 현재 HEAD 원래 23건 | 18 FAIL / 5 PASS | 14개 observer 실패와 취소 4개 실패 재현. 나머지 취소 5개는 이 환경에서 기존 30ms 안에 통과했으나 관측 대상은 동일하게 잘못됨 |
| 수정 초안 | 22 PASS / 1 FAIL | 응답 유실 뒤 read-only replay 관측 누락 발견. 최종 수정에 반영 |
| replay 보완 단독 | 1 PASS | unknown_commit |
| 최종 세 Worker 파일 전체 | 90 PASS | 원래 실패 대상 23개 각각 포함. terminal 상태·retry·metrics 관련 회귀에서 Worker 동작 회귀 증거 없음 |
| 같은 실행의 A-1 19건 | 19 setup ERROR | Windows 공용 pytest 임시 경로 WinError 5. 전체 invocation은 90 PASS / 19 ERROR이며 GREEN 아님 |
| 새 소유 basetemp에서 A-1만 재검증 | 18 PASS / 1 FAIL | 마지막 controller 복구 시험은 Windows symlink 권한 WinError 1314, AUTH_REQUIRED. 기존 helper·assertion을 우회하거나 skip하지 않음 |

처음 base 실행에서 비교용 archive의 migration 복사를 빠뜨려 생긴 23 setup ERROR도 별도 보존했다.
동일 base migration을 포함한 후의 23 PASS와 구분한다.
원격의 23 FAIL과 로컬의 18 FAIL을 같다고 쓰지 않는다. 잘못된 commit anchor는 DB 왕복 속도에 따라
허용치 안에 들어갈 수 있다. 최종 수정은 실제 terminal COMMIT OK와 원래 허용치로 비교한다.

이 결과는 시험 관측 범위가 원인이라는 근거다. 전체 제품 회귀 부재나 최종 canonical 성공을 뜻하지 않는다.
현재 수정본 원격 CI, 로컬 canonical 전체·후속 strict/실제 보고서 변조, 실제 이미지·host 복구는 **NOT_RUN**이다.
Windows symlink 권한이 없는 1건은 권한 있는 Linux/CI에서 같은 시험으로 재검증한다.

추가 부정 대조에서는 scratch 전용 주입으로 terminal receipt 시각을 400ms 앞당겼다.
수정된 시험은 원래 30ms assertion에서 약 21ms와 421ms의 불일치를 거부했다.
따라서 실제 terminal timing 오류까지 통과시키도록 관측을 무력화한 것은 아니다.
최초 부정 대조 wrapper의 signature 누락으로 다른 assertion에서 먼저 실패한 기록도 보존하며,
signature를 보존한 후 위 metric assertion에 도달한 결과와 구분한다. 제품 파일에는 주입하지 않았다.

기존 assertion 전체와 wait/result/sleep/approx/skip, parametrization/mandatory marker의 AST 대조는 통과했다.
새 helper Ruff는 통과했다. 세 기존 시험 파일의 Ruff 16개 지적은 고정 base와 현재의 code/message/해당 줄이
동일하며 새 지적은 없다. 기존 fixture import 등의 지적을 이번 작업에 섞어 고치지 않았다.
최종 snapshot secret scan은 2,621개 파일, 탐지 0건, 기존 정밀 예외 2건이다. history/배포 scan을 대신하지 않는다.
독립 리뷰에서 검토 범위의 수정할 결함은 발견하지 못했다.

모든 시험 후 소유 schema가 0개임을 확인하고 이번 tmpfs container/network만 제거했다.
다른 container 0개를 확인한 뒤 이번에 시작한 Docker Desktop을 정상 종료했다.
기존 image/volume·Windows MySQL·원본 입력·샘플·보호 증거는 보존한다.

## 제출 대상 구분

기존 #629의 89개 파일은 HEAD 117bf0ef에 이미 커밋되어 있다. 재추가할 미커밋 파일과 구분한다.
추가 변경은 다음 두 묶음이며 실제 staging/commit/push는 하지 않았다.

**첫 커밋: 시험 수정 — 5개**

```text
tests/api/test_sources_process.py
tests/worker/test_cancel_checkpoint_mysql.py
tests/worker/test_reflection_mysql.py
tests/worker/test_worker_mysql.py
tests/worker/terminal_observation.py
```

제안 커밋 메시지: `fix(runtime-tests): scope MySQL probes to terminal transactions`

업로드 timeout 시험의 `PUBLIC_MODE=internal` 한 줄 보완도 이 묶음에 포함한다.
이전 RED 403 두 건 → 원래 timeout 두 건과 공개 거부 네 건의 6 PASS 근거를 유지한다.
이번 작업에서 그 코드·시험을 다시 바꾸거나 이유 없이 반복 실행하지 않았다.

**둘째 커밋: Web 후속 연결과 인계 — 10개**

```text
apps/web/src/App.tsx
apps/web/src/__tests__/app.test.tsx
apps/web/src/__tests__/officialSampleEntry.test.tsx
apps/web/src/__tests__/officialSampleSafety.test.tsx
apps/web/src/api/publicSamples.ts
apps/web/src/screens/ApiFlow.tsx
apps/web/src/screens/OfficialSampleEntry.tsx
apps/web/vite.config.ts
docs/runtime/a1-public-web-handoff.md
docs/runtime/a1-mysql-ci-followup.md
```

제안 커밋 메시지: `feat(web): connect A-1 official sample entry to protected API`

기존 Web 코드 8개·업로드 수정·MySQL 시험 수정 4개의 검증된 hash를 보존했다.
두 문서는 서로 링크하므로 둘째 커밋에 함께 넣는다. 앞선 6/9 분할 준비안은 이 5/10 순서로 대체한다.
첫 커밋은 새 terminal_observation helper를 모든 사용 시험과 함께 포함하며 Web 파일을 요구하지 않는다.
Web 코드는 HEAD 117bf0ef에 이미 있는 공개 API를 사용하고 새 Python 시험 수정에 의존하지 않는다.
따라서 코드 검증은 각각 가능하다. 문서만 두 묶음의 결과를 함께 설명하므로 둘째에 둔다.
기존 Web 362 PASS/build PASS는 해당 보존 snapshot의 결과이며 외부 브라우저 완주를 대신하지 않는다.
scratch/로그/DB 비밀 설정/샘플 영상과 시험 잔여 `.runtime-cleanup-*.lock` 3개는 제출 대상에서 제외한다.

## CI와 공개 조건

기존 `python-tests.yml` → `tests.ci_orchestration mysql`의 canonical 전체 → strict JSON/JUnit →
동일 invocation/SHA/token/hash 봉인 → 실제 보고서 변조 → 원본 재대조 순서는 변경하지 않았다.
부분 focused 보고서를 canonical checker에 넣어 통과 근거로 쓰지 않는다.
사용자가 commit/push한 다음 **그 통합 SHA**의 새 원격 전체 gate 결과를 확인해야 한다.

Windows 미통과 node는 아래와 같다. 로컬 AUTH_REQUIRED 판정은 유지한다.

```text
tests/recording/test_public_recovery_mysql.py::test_existing_controller_can_restart_current_guarded_tuple_without_schema_or_ledger_rollback
```

기존 run 42405787097의 MySQL job 128503060684 원문에는 2026-11-07T19:40:30Z에 이 node의
`PASSED [60%]`가 한 번 있다. 이는 HEAD 117bf0ef의 과거 Linux 실행이며 수정본을 통과시킨 근거가 아니다.
새 통합 SHA의 python-tests / mysql(ubuntu-24.04)에서 node의 실제 PASSED 로그가 정확히 한 번이며
동일 node FAILED/ERROR/SKIPPED/XFAIL/XPASS가 없는지 확인한다. job 성공만으로 node 실행을 추정하지 않는다.
이어 canonical-mysql·strict·actual-report-mutations 세 stage success와 required test success를 각각 확인한다.
현재 workflow에는 MySQL JSON/JUnit 별도 artifact 업로드가 없다. 보존하지 않은 보고서를 다운로드했다고
표현하지 않으며, 기존 `-vv` job 원문 로그와 stage 기록을 확보한다. 이번 새 CI 확인은 NOT_RUN이다.

공식 샘플은 조사한 1min 10개 / 합계 600,000ms / 244,829,133B 그대로다. short는 제외한다.
공개·외부 AI 처리 권한과 실제 예산 승인은 미확정이다. authorization_ref를 채우거나 서버에 등록하지 않았다.
Coarse 600초 유지, 26분 E2E 제외. bb29/b915는 세션 보호를 우회하므로 공개 rollback 대상으로 부적합하다.
guarded current 재기동은 로컬 source/DB/controller 시험이며 실제 이미지·host 복구는 NOT_RUN이다.
공식 샘플·예산 승인, Web 통합·외부 완주, 운영 보호 mount·복구 증거 전까지 공개 NO-GO다.

상세 로그/XML/JSON·소스 및 제출 목록 hash는 로컬
`.codex-scratch/a1-mysql23-20261108/`에 보존한다. 운영/유료 호출/commit/push/외부 게시는 하지 않았다.
