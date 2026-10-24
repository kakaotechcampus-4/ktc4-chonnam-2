# `api` — FastAPI composition root

RT-12(a)는 lifespan startup에서 staging/temp 잔여 scan을 1회 수행하고 기존
CleanupSettings 주기로 반복하며 종료 때 소유 thread를 join한다. upload의
생성→publish까지 lease로 보호한다. `composition.media`는 기존 materializer의
명시적 temp_root 주입·활성 보호용 factory이며 현재 기본 Recording에는
materializer가 없다. [경계·검증](../../../docs/runtime/rt12a-cleanup.md)을 참조한다.

**Owner:** 김준영 (공통 기반/운영) · **경계:** `docs/architecture/module-architecture.md` §1-5 · §8-1 · §8-2

- 배포 단위 「API 1」. 긴 작업은 HTTP 요청 안에서 끝내지 않는다 — `case`가 만든 `JobRecord`를 queue에 넣고 `202 Accepted`를 반환한다.
- 즉시 처리하는 것(§8-1): `CaseView` 조회 · hint 수정 · candidate 선택 · pure evidence recompute · requirement recompute · 상태 전이.
- 인증은 MVP 최소 수준이며 방식은 미결(§1-7 A2).
- `web`이 읽는 상태는 `case.get_view()`를 노출하는 CaseView 하나다 (§4-모듈6 ③). 그 밖의 read는 CaseView가 가리키는 FrameRef · 신고용 artifact의 바이너리 조회뿐이다. HTTP surface 결정은 `docs/runtime/runtime-tech-spec.md` §13(RD-05, #247), 경로 · status · body는 HTTP API Contract `docs/architecture/contracts/contract-http-api.md`(`http-api/v1`, Final — Accepted)다. route 구현 전 선행 조건은 그 문서 §9.1이다.

## 상태

RT-01의 `bootstrap.py`를 구현했다. `bootstrap(revision=...)`은 `DAESINGO_ENV_FILE`(미지정 시 cwd `.env`)을 명시적으로 읽고, 불변 API RuntimeConfig와 등록된 모듈 factory/validator를 검증한 뒤 JSON line `process.started`를 기록한다. 실패 시 설정 key 이름만 기록하고 `SystemExit(1)`로 종료한다. `revision`은 호출자가 전달하는 commit SHA 등 안전한 식별자다.

필수 파일 key는 `DAESINGO_RUNTIME_DB_URL` · `DAESINGO_RUNTIME_MEDIA_ROOT` · `DAESINGO_RUNTIME_API_TEMP_ROOT`다. shell에서는 파일 경로만 읽는다. 세부 선택과 검증 결과는 [RT-01 Implementation Log](../../../docs/runtime/runtime-implementation-log.md#rt-01--runtime-config--composition-bootstrap--structured-log-기반)에 기록한다.

RT-08(a)는 `app.create_app` · `composition.compose_api` · API QueuePool / ready NullPool · `errors`의 HTTP envelope · `health`의 `/health/live`와 `/health/ready`를 구현한다. health 성공 body는 Contract §5.7의 `{status: ok}`, 준비 실패는 `{status: unavailable}`이다. 일반 오류는 Contract §3.3의 `ok/error/case_view`이며 프레임워크 `detail`·validation 입력·예외 header를 반환하지 않는다. docs/OpenAPI·slash redirect는 비활성이다.

```bash
uv run --no-sync python -m daesingo.api --revision <revision> --host 127.0.0.1 --port 8000
```

`--revision`은 필수다. port는 0~65535(0은 OS가 배정) 범위를 DB/composition 전에 검증하며 잘못된 argv는 stderr 없이 코드 1이다. 서버 일반 예외·의도적인 SystemExit/기타 BaseException은 코드 1, KeyboardInterrupt는 정상 graceful 코드 0이다. CLI는 lifespan 전 실패에도 resource를 정리하고 signal과 Uvicorn logger 상태를 복원한다. lifespan에서 삼켜진 cleanup 실패도 코드 1로 보존한다. 지원 실행 경계는 명시적 workers=1 · reload off이며 `WEB_CONCURRENCY`로 늘어나지 않는다(B-W4). 설정 검증/engine 조립 실패는 listener 전 안전한 상수 event와 종료 코드로 끝난다. startup에서 migration·DB 접속·provider HTTP는 실행하지 않는다.

ready는 media root의 존재·디렉터리·쓰기 권한과 Linux read-only mount flag를 파일 생성 없이 검사한다. DB는 공용 pool 대기 없이 전용 연결에서 SELECT 1을 실행한다. 두 검사의 제한/전체 budget은 기존 ReadySettings와 B-H1~B-H3를 소비하며, 각 probe는 하나의 in-flight 호출을 동시 요청이 공유한다. 제한을 넘은 native 호출은 강제 종료하지 못하지만 추가 probe를 누적하지 않는다. 늦게 반환한 DB connection은 정상 close된다. Windows에는 statvfs가 없어 디렉터리/access 검사만 적용하며 실제 RO mount acceptance는 Linux private namespace에서 검증한다.

request마다 서버가 발급한 trace_id를 thread/context 경계로 유지한다. request/ready event는 RT-01 allowlist logger를 쓰는 단일 daemon consumer와 유한 queue로 분리하며, sink 장애·지연·thread 시작 실패가 HTTP 응답을 바꾸지 않는다. 로그 포화 시 event를 버리고 shutdown은 유한 대기한다. API 소유 handler는 I/O lock과 stdlib cleanup lock을 분리하고 emission에서 flush하므로 shutdown은 sink I/O를 반복하지 않는다. 기본 stdout과 고정 오류 stderr는 unbuffered fd write로 Python buffered I/O 종료 lock을 잡지 않는다. 제3자 handler를 종료/제거하거나 logging 전역 registry를 수정하지 않는다. fatal sink 예외는 close에서 owner에게 전달하고 composition 실패 진단은 유한 drain 뒤 startup 코드 1보다 우선하지 않는다. raw uvicorn access/error/traceback 출력을 억제한다. 요청 URL·query·body·header·예외 문자열·DB URL·mount 경로는 event/응답에 넣지 않는다.

RT-08(b)는 `POST /cases`와 `GET /cases/{case_id}/view`를 구현한다. 생성은 body를 읽지 않고 공개 `case.create_case` → caller transaction commit → 별도 read transaction에서 공개 `case.get_view` → `201` + `Location` 순서다. 조회는 CaseStore에 같은 Connection과 Runtime `read_executions`를 주입한다(PR #342 합의). Case가 share lock·job scope·대표 attempt·CaseView를 소유하고 HTTP는 응답을 재조립하지 않는다. 없는 Case는 Contract 404 envelope다.

RT-02의 precommit DB 실패는 503, COMMIT 결과 불명은 500이며 자동 재시도하지 않는다. 생성 commit 뒤 응답 조회 실패는 생성이 이미 반영됐으므로 500이다. DB transaction helper에 동기 logger를 전달하지 않고 기존 ApiEvents로 요청 trace와 조회 시간·안전한 Case identity를 기록한다.

RT-08(c)는 `POST /cases/{case_id}/commands`를 연결한다. `application/json`·UTF-8과 B-U2 실제 수신 byte 한도를 검사하고 JSON 값은 Case의 공개 `execute_command`에 그대로 전달한다. Case 저장과 이번 `appended_job_records` batch enqueue는 한 Connection/transaction이며 commit 후에만 응답한다. status는 append 목록과 Case 응답 표로 정하고 body는 고치지 않는다. 요청 trace를 enqueue에 이어 주며 URL·header·payload·예외 원문은 로그에 넣지 않는다. `Content-Length`가 없거나 실제보다 작아도 수신 한도를 적용한다. 수신은 async, 동기 DB 작업은 context를 보존하는 threadpool에서 수행한다(Plan P-9 대비 구현 상세).

RT-08(d)는 Case의 `cancelled_job_ids`를 같은 Connection/transaction의 기존 Runtime `request_cancel`에 전달한다. Case가 먼저 잠기며, QUEUED는 같은 commit에서 CANCELLED, RUNNING은 최초 cancel marker만 기록한다. HTTP status와 body는 기존 append 목록·Case 응답 표 그대로다. 실패는 전체 rollback이고 API 재시도는 없으며, COMMIT 결과 불명은 기존 500이다. Worker의 협력적 checkpoint·ownership fence·늦은 결과 guard와 T2 redelivery 의미는 유지한다. `START_ANALYSIS`의 `CaseTimelineSource`와 실제 모듈 결과 adapter/reader 조립도 아직 없으며, 해당 dependency가 필요한 command의 동작 완료를 주장하지 않는다. 이 slice의 실제 발주 acceptance는 기존 `RUN_NOTICE_ACTION`과 영속 fixture Case로 검증한다. media HTTP는 RT-11, 실제 capability 조립은 해당 선행 Owner/후속 Task 범위다.

실제 MySQL acceptance는 기존 disposable 8.4 harness에 참여한다. SHUTDOWN 검사는 suite DB와 분리된 두 번째 서버를 사용한다. Linux CI는 서비스가 준비한 mysql:8.4 image를 Docker로 재사용하고 sudo/unshare/mount로 private RO tmpfs를 생성·해제한다. Windows 로컬 acceptance는 WSL Ubuntu 및 `DAESINGO_MYSQL_TEST_BASEDIR`/`DAESINGO_MYSQL_TEST_LIBDIR`의 테스트 전용 Linux 바이너리/라이브러리 위치가 필요하다. fixture는 기능 부재를 skip으로 대체하지 않는다.

RT-11(b)는 `GET /cases/{case_id}/frames/{frame_ref}`를 구현한다. 기본2의 frame semaphore를 DB checkout 전에 획득하고, 짧은 caller transaction에서 case 존재 및 Recording 공개 `read_owned_frame_image`로 소유·저장 이미지를 복원한다. Connection 반환 뒤 실제 Content-Type·정확한 Content-Length·`private, max-age=3600` header를 구성하고 bytes를 전송한다. unknown/cross-case는 같은 safe404, owned-but-unavailable은 typed404이며 provider/decoder/재생성은 호출하지 않는다. 대기·응답 전송 중에는 DB connection을 보유하지 않는다. 순수 ASGI middleware는 access/BaseHTTPMiddleware 바깥에서 실제 body 전송 완료·disconnect·취소·send 예외까지 permit을 유지한다. HTTP가 먼저 취소돼도 진행 중 DB read 정리가 끝나기 전에는 반환하지 않는다. frame latency는 실제 ASGI 전송 수명과 HTTP status를 기록하며 client 수신 ACK를 보장하는 값은 아니다. 승인 해석·관측 범위·검증은 [RT-11(b) note](../../../docs/runtime/rt11b-frame-read.md)에 기록한다.

RT-11(c)는 `GET /cases/{case_id}/assets/{asset_ref}`를 구현한다. 기존 Case ID 검증 및 존재 조회와 Recording 공개 `owns_asset`·`open_derived_asset`를 한 caller transaction에서 사용한다. 저장 stream은 transaction 안에서 닫고, commit·connection 반환 뒤 detached bytes로 응답한다. 실제 형식과 길이, 서버가 정한 ASCII attachment filename 및 `private, no-store`를 제공한다. unknown·foreign·종류 불일치는 같은 `404 http.not_found`, owned-but-unavailable은 `404 http.ref_unavailable`이며 기존 dependency·validation·unexpected 오류 매핑을 유지한다. frame semaphore를 사용하지 않으며 provider·재생성·Range·retention·새 생성 surface를 추가하지 않는다. [구현·검증 경계](../../../docs/runtime/rt11c-asset-read.md)를 참조한다.

Asset 전송 관측은 [Issue #298 Owner 승인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/298#issuecomment-6380891047)을 따른다. `api.asset.download_latency_ms.duration_ms`는 outer ASGI 진입부터 최종 body의 downstream send 반환 또는 예외·취소 종료까지 monotonic으로 측정한다. `api.asset.bytes.count`는 **successfully returned downstream send bytes, not client-received bytes**다. Content-Length를 집계하지 않으며, 부분 전송·오류 응답에서 정상 반환한 chunk는 포함하고 실패한 chunk는 제외한다. client 수신이나 TCP ACK를 보장하지 않는다. matched GET마다 종료 시 두 metric을 한 번씩 emit하며, 정상 전송은 실제 HTTP status 문자열, 예외는 `FAILED`, task cancel·final body 없는 종료는 `CANCELLED`다. `DISCONNECTED`는 추가하지 않는다. 원래 HTTP status를 바꾸거나 raw case/ref/filename/locator/예외 원문을 기록하지 않으며 공통 `api.request.completed`의 전역 의미도 유지한다. 기존 유한 ApiEvents queue의 best-effort 전달 정책을 사용한다.
