<a id="rt-11b-stored-frame-read-http"></a>

# RT-11(b) 저장 Frame 읽기 HTTP

RT-11 IN_PROGRESS · Refs #298 (RT-11(b)) · PR pending · merge SHA pending.

현재 구현은 아래 「후속 독립 재리뷰 P1 수정」을 반영한다. 최초 실행·실패·과거 판정은
해당 snapshot의 이력으로 보존하며 현재 검증과 구분한다.

## 승인과 구현 계획

현재 checkout `codex/rt11b-frame-read`의 기준은
`c491a95b8726377c2eca2ac3dad6bcc6ce416670`이다. Git branch/HEAD/clean
working tree/빈 staging 및 최신 원격 develop 일치를 직접 확인했다.
루트 CLAUDE.md, 사용자 제공 AGENTS 지침, Runtime Plan RT-11/REC-1/§12,
HTTP §3.5/§5.5/§7, SourceAsset Final Contract §5/§6.6, Ops RD-17/§4-2와
logging/privacy, Tech Spec §13, Baseline B-F1/B-F2, REC-1(c) 공개 capability와
Implementation Log를 구현 입력으로 사용한다. 저장소에는 별도 AGENTS.md가 없다.

Issue #298 본문과 전체 댓글 2개를 직접 확인했다.
[제안](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/298#issuecomment-6292559346)과
[Runtime/HTTP Owner 승인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/298#issuecomment-6306955258)은
stored bytes 복원을 위한 짧은 DB 구간을 허용한다. 원래 Plan/B-F2 문구는
고치지 않고 승인된 해석을 여기와 Log에 기록한다. 새 Decision Gate는 없다.

- [x] API·Recording RED 보존 → 최소 구현 GREEN.
- [x] independent frame inventory 누락을 기존 checker가 허용하는 RED 보존.
- [x] 실제 MySQL frame acceptance, caller transaction/connection/process 복원.
- [x] 전체 필수 MySQL 원본 nested900 실행·strict JSON/JUnit·누락 mutation.
- [x] API/Recording 및 gate 회귀, static/workflow 검증(실패 이력과 제한은 아래).
- [x] 소유 DB 자원 정리·감사(공유 Windows relay 잔여와 helper exit1은 아래).

<a id="implementation-notes"></a>

## 구현 기록

### 구현 결과

`GET /cases/{case_id}/frames/{frame_ref}`는 app-local asyncio semaphore를
DB checkout 전에 획득한다. 기본 한도는 기존 FrameSettings의 2이며, 초과
요청은 상한 없는 대기를 한다. 대기 task는 DB를 열지 않는다. 획득한 작업은
context를 보존하는 threadpool에서 기존 RT-02 caller transaction을 실행한다.
기존 CaseStore 공개 `get_case`로 case 존재를 확인한 뒤, Recording의 새 최소
공개 `read_owned_frame_image`가 기존 소유 관계와 저장 이미지 capability를
조합한다. API는 Recording schema/table/private API를 읽지 않는다.

Recording의 caller Connection 소유·commit/rollback 규칙은 유지한다. 같은
transaction 안에서 ownership을 먼저 확인하므로 foreign frame의 availability는
응답에 영향을 주지 않는다. 결과는 frozen `FrameImage`의 bytes와 형식뿐이다.
connection 반환이 끝난 뒤 route가 HTTP Response를 만들고 bytes를 전송한다.
provider/ffprobe/decoder/frame regeneration/원본 읽기는 실행하지 않는다.

성공은 실제 저장 이미지 형식 `Content-Type`, 정확한 `Content-Length`,
`Cache-Control: private, max-age=3600`이다. 기존 config를 소비하고 새 값은
만들지 않는다. Range/206 구현은 포함하지 않는다. 같은 ref의 bytes를 바꾸거나
HTTP/server frame cache를 추가하지 않는다.

없는 case/ref와 cross-case는 같은 `404 http.not_found` envelope다.
`FRAME_NOT_FOUND`/`STREAM_UNAVAILABLE`/`OUT_OF_RANGE`는 typed
`404 http.ref_unavailable`, `TEMPORARY_FAILURE`는503이다. 기존 RT-02의
precommit DB/pool503·commit 결과 불명500·예상 밖500 정책을 유지한다.
문자열·파일 내용으로 taxonomy를 추론하지 않고 raw 예외/header를 반환하지 않는다.

### Plan 대비 변경

원래 소유 확인→반환→read_frame을 Owner 승인대로
대기→짧은 ownership+stored-image load→반환→응답으로 구체화했다.
DB 점유는 이 짧은 구간에만 허용하며 semaphore 대기와 응답 전송은 checkout0다.
Case mediation/association/callback, schema, upload, asset, RT-10 변경은 없다.

### 새로 고정된 implementation detail

async route + sync DB threadpool을 사용한다. HTTP task가 취소돼도 shielded
read task가 DB 정리를 마칠 때까지 permit을 보유한다. 순수 ASGI middleware가
기존 access/BaseHTTPMiddleware 바깥에서 실제 body/final send를 감싸며, 정상 전송
완료·disconnect·취소·전송 예외로 HTTP 수명이 끝난 후 정확히 한 번 반환한다.
HTTP가 먼저 취소된 경우에도 DB thread 정리가 끝나기 전에는 반환하지 않는다.
대기 취소·typed failure·unexpected failure는 permit을 누수하지 않는다.
완료 callback은 취소된 HTTP의 남은 read 예외를 소비하되 출력하지 않는다.
semaphore는 DB checkout 전부터 실제 ASGI 전송 종료까지 유지한다. DB connection은
stored read 후 즉시 반환하므로 느린 client와 대기는 connection을 보유하지 않는다.
이미지 크기 자체의 byte 상한은 추가하지 않는다. 기존 DB timeout과 process
shutdown 정책을 유지한다. 최초 구현의 “느린 client 전송에 permit을 묶지 않음”은
독립 재리뷰에서 재현된 P2-1이며 현재 설계로 수정했다.

관측은 기존 bounded ApiEvents/allowlist logger다. `api.frame.request_rate`는
진입당 count1 이벤트(시간 구간별 집계 입력), wait_ms는 semaphore 획득 또는
대기 취소까지, latency_ms는 대기를 포함한 실제 ASGI 전송 종료 또는 실패/취소까지의
duration_ms다. 응답 준비만으로200을 기록하지 않는다. 완료 status는 실제 HTTP
response.start에서 얻어 typed404가FAILED로 기록되던 P3도 수정했다. send 예외는
FAILED, task 취소/미완료는 CANCELLED다. ASGI send 반환은 client의 전체 수신/ACK
증명이 아니며 transport가 disconnect를 조용히 수락하는 경우를 새 정책으로 분류하지
않는다. raw case/ref/path/query,
파일명·bytes·secret·예외를 event에 넣지 않는다. trace context는 유지한다.
포화·sink 장애의 best-effort 유실 특성은 기존과 같다.

### Contract / Decision / Baseline 영향

Owner가 승인한 stored-read 배치 해석을 적용한다. Final Contract schema/status,
Accepted Decision, Baseline 값의 추가 변경은 없다. Recording 최소 capability
추가는 사용자가 이번 작업 범위로 승인했다.

### Owner 확인 포인트

승인된 짧은 DB 점유/전송 중 connection 반환과 semaphore2를 테스트로 고정한다.
저장 형식 식별은 기존 Recording PNG adapter 범위이며 전체 decode 검증이 아니다.
읽기 중 case/ref 상태가 바뀌는 retention 정책은 이번 범위에서 정하지 않는다.

<a id="verification--진행-기록"></a>

### 검증 — 진행 기록

- initial sandbox RED: API fixture temp 생성 오류13 ERROR/Recording3 FAIL.
- explicit basetemp sandbox 시도는 출력 없이 진행이 멈춰 소유 pytest를 종료했다.
  같은 테스트를 unsandboxed 실행했을 때 정상 진행했다. 정확한 sandbox 정지
  원인은 확정하지 않는다. 실패/중단 결과를 제품 RED나 PASS로 재분류하지 않는다.
- valid RED:13 FAIL/3 PASS → minimal GREEN:16 PASS.
- gate RED: api_frame family 누락6건이 거부되지 않음 → checker inventory 보강.
- first MySQL:13 PASS/4 FAIL. SecretStr를 subprocess env 문자열로 전달하지 않은
  fixture 오류1건과, 다른 정상 DB read가 진행 중인데 전역 checkout0를 요구한
  동기화 오류3건이다. bytes 복원 완료2건을 확인한 뒤 대기 경계를 측정하도록 수정.
- corrected MySQL:17 PASS/skip0/xfail0/source drift0. 두 fresh interpreter 복원,
  actual disconnect/pool saturation, 동시 실행2/대기1, wait/active 취소, 느린
  ASGI send 중 connection0/Case lock 해제를 포함한다.
- 최초 MySQL 실행 중 checker inventory 파일만 갱신된 source drift는 별도 기록한다.
  최종17건의 직접 재검증에는 source drift가 없다.

### 선행 원격 증거 (이번 변경 검증과 분리)

PR #382 develop merge SHA `596e8a162b71949e7b3189e994921bb6247aac4b`,
boundary-check/python-tests SUCCESS, MySQL gate811/skip0/xfail0를 직접 확인했다.
PR #385 develop merge SHA `c491a95b8726377c2eca2ac3dad6bcc6ce416670`,
boundary-check/python-tests SUCCESS, MySQL gate839/skip0/xfail0를 직접 확인했다.
이 원격 결과를 현재 변경의 local/remote PASS로 사용하지 않는다.

### 미실행·위험·전달 상태

전체 pytest는 실행하지 않았다. 현재 source의 전체 필수 MySQL은 API/Case/Worker/
Recording persistence/공용 DB·jobs·usage·migration을 포함하고, 추가로 전체
API/Recording 비MySQL 및 strict gate unit을 실행했다. bare pytest는 이 MySQL과
nested 실행을 반복하고 이번 변경이 없는 Search/readout/evidence/domain unit까지
포함하므로 중복 실행을 줄였다. 미실행 suite의 회귀 위험과 현재 diff 원격CI는
남아 있다. 과거 PR CI가 이를 대체하지 않는다. 독립 재리뷰는 사용자 요청대로
별도 대화에서 수행하며 이 대화는 reviewer/subagent를 호출하지 않았다.
staging/commit/push/PR 생성은 하지 않았다.

## 최초 구현의 직접 검증과 제한 (P2 수정 전 snapshot)

| 실행 | 직접 관측 결과 |
| --- | --- |
| API/Recording 초기 TDD | valid RED13 FAIL/3 PASS → GREEN16 PASS |
| 실제 frame MySQL | 17 PASS/skip0/xfail0, source drift0 |
| strict gate unit | 6,483 PASS/484.86초, source drift0 |
| 원본 필수 MySQL child | 851 PASS/2,553 phases/484.666초, skip·xfail·JUnit failure/error0 |
| 원본 mandatory parent | 1 PASS/892.62초, wrapper exit0/source drift0; nested900 유지 |
| strict CLI | child의 원본 JSON/JUnit으로 PASS851 |
| parameter mutation | 전체6,218건 모두 거부; 신규 frame17×13=221건 포함 |
| 신규 metadata/family | frame metadata68 + family6 =74건 모두 거부 |
| API/Recording 비MySQL 전체 | 779 PASS/기존 외부 미디어15 SKIP/1 FAIL/201 deselected, source drift0 |
| 실패 node 단독 확인 | 1 PASS/3.19초, 원본5초 제한·source 불변; broad 실패를 소급하지 않음 |
| static | boundary 위반0, Contract62구조/26JSON/104의미 PASS, actionlint 관련 workflow2개 PASS, diff-check PASS |
| 정책 보존 | checker 함수AST 불변, 기존 inventory 포함, 신규6 scenarios/17 parameters만 추가, migration16개·workflow byte 불변, nested900·workflow30분 유지 |

관련 회귀의 유일한 실패는
`tests/api/test_process_safety.py::test_composition_failure_exits_within_five_seconds_after_ready_trigger`다.
보존된 phase는 GO 전 `setup_import_watchdog_5s`를 가리킨다. 4.5초 stack은
기존 `search/coarse.py` import의 `importlib.get_data`였고 새 frame route import에
도달하기 전이다. 이후 imports_done/ready가 늦게 관측됐다. 이 사실은 실패 위치를
구분하며 지연의 정확한 환경 원인을 확정하지 않는다. 모든 무거운 검증 종료 뒤
같은 node를 단독 실행해 원래 deadline으로 PASS했다. 전체780 PASS라는 합성 결과를
만들지 않으며, 초기779/1과 단독1을 각각 보존한다. 5초 startup watchdog 재발은
비차단 위험으로 공개하고 현재 CI/독립 재리뷰에서 평가해야 한다.

로그/오류 비노출은 실제 API/Recording 경계에서 검사했다. 로컬 RAW pytest 출력은
진단 자료이며 원격 게시/PR에 넣지 않는다. MySQL은 소유 WSL8.4.7 RAM datadir와
전용 CA TLS를 사용했다. flush 설정1/fsync로 논리 transaction/connection 경계를
검증하며 host/power-loss 디스크 내구성을 증명하지 않는다. PNG 식별과 큰 stored
bytes의 MySQL packet/RSS 용량 한계는 기존 Recording 설계 범위다.

## 최초 구현의 자원 감사와 정리 (P2 수정 전 snapshot)

전용 서버의 마지막 감사는 system schema4+owned base1, 기본 account4개,
다른 client0, InnoDB transaction0/data lock0이었다. init/server 로그를 보존했다.
첫 감사는 감사 자신의 비AUTOCOMMIT transaction을1개 관측해 실패했다. 같은
connection ID6689가 `innodb_trx`의 ID6689임을 직접 확인하고 helper만 AUTOCOMMIT으로
보정했다. 최초 실패 JSON을 별도로 보존하고 후속 감사0과 구분한다.

정상 SHUTDOWN 뒤 소유 mysqld·Linux listener·datadir와 Windows Python helper는
없다. **서버 helper는 최종 port assertion에서 exit1**이었다. Windows의 공유
`wslrelay.exe` PID2736이 localhost62840을 계속 listen했으며 Linux에는 같은
listener가 없었다. 공유 WSL/relay를 kill/restart하지 않았다. 이 OS 포워딩 잔여는
소유 DB/process/data 정리와 구분하며 자원 정리 전체 PASS/잔여0을 주장하지 않는다.
후속 상태가 달라지면 원본을 수정하지 않고 별도 기록한다.

**최종 후속 검사:** 동일한 원본 `assert_port_closed`를62840에 재실행해 PASS했다.
Linux listener0, MySQL handshake 없음, 이 작업 소유 Windows Python process0이다.
공유 relay/WSL은 변경하지 않았다. 따라서 마지막 검사 시 포트 잔여는 해소됐으며,
정확한 제거 시점/원인은 단정하지 않는다. 초기 helper exit1과 당시 listener JSON은
그대로 유지하고 `poststop-status.json`의 후속 closed=true와 구분한다.

## 변경 파일 전체 목록

| 파일 | 역할 |
| --- | --- |
| `README.md` | 현재 Frame HTTP 공개 동작 사실2곳 |
| `src/daesingo/api/README.md` | HTTP/connection 경계 |
| `src/daesingo/api/app.py` | route·outer middleware 순서·trace 연결 |
| `src/daesingo/api/composition.py` | 짧은 caller transaction |
| `src/daesingo/api/errors.py` | typed frame unavailable |
| `src/daesingo/api/routes_frames.py` (신규) | shield로 보호한 저장 데이터 조회/HTTP header |
| `src/daesingo/api/frame_lifetime.py` (신규) | outer ASGI permit/실제 전송 관측 |
| `src/daesingo/recording/README.md` | 신규 최소 capability 설명 |
| `src/daesingo/recording/service.py` | owned stored image 공개 read |
| `src/daesingo/recording/repository.py` | in-memory에서 scope 확인 후 복원 |
| `src/daesingo/recording/mysql_repository.py` | 단일 ownership-scoped statement |
| `tests/api/test_frames.py` (신규) | HTTP·취소·실패·관측 단위 검증 |
| `tests/api/test_frames_mysql.py` (신규) | 실제 MySQL71개 필수 acceptance |
| `tests/api/frame_process.py` (신규) | fresh interpreter 복원 소비자 |
| `tests/api/test_frames_network_mysql.py` (신규) | 실제 TCP backpressure/disconnect |
| `tests/recording/test_owned_frame_image.py` (신규) | 소유·가용성 구분 |
| `tests/frame_acceptance.py` (신규) | 독립 필수 evidence inventory |
| `scripts/check_mysql_test_report.py` | checker의 추가 필수 inventory |
| `tests/common/db/test_mysql_gate.py` | 누락 거부 단위 검증 |
| `tests/common/db/integration/test_migration_gate.py` | 실제 전체 report 누락 mutation |
| `docs/runtime/runtime-implementation-log.md` | 기존 이력 보존 후속 기록/색인 |
| `docs/runtime/rt11b-frame-read.md` (신규) | 승인·Implementation Notes·검증·제한 |

`.codex-scratch/**`, RAW, JSON/JUnit 원본, runner, 임시 DB/datadir, media와
진단 자료는 전부 PR 제외다. 새 제품/Owner 의미 판단 blocker는 발견하지 않았다.
현재 diff 원격CI와 사용자 주도의 별도 독립 재리뷰는 미실행이다. 공개한 회귀 실패
및 OS 잔여를 포함해 독립 재리뷰 가능한 미커밋·미스테이징 상태로 전달한다.

## 독립 재리뷰 P2 수정 — 현재 구현

사용자가 제공한 독립 보고서·재현 코드를 읽고 scratch 복사본으로 직접 실행했다.
P2-1은 설정2에 body send3/조기 latency200 세 건, P2-2는 corrupt foreign503과
unknown404로 재현됐다. 원본 리뷰의 P2-2는 live MySQL이 아닌 row transport 주입
재현이다. 이번 수정에서는 실제 MySQL 손상 row도 직접 검사한다. 원본 보고서와
이전 scratch는 수정하지 않으며 새 자료는 `.codex-scratch/rt11b-p2-20261021/`다.

### P2-1: Response 객체를 넘어 실제 ASGI send 수명

`FrameLifetimeMiddleware`는 access/BaseHTTPMiddleware 바깥에서 admission부터
실제 payload/final body send까지 감싼다. Response.__call__을 inner middleware
안에서 감싸는 방식은 outer send를 보호하지 못하므로 사용하지 않았다.
permit은 DB checkout 전에 획득하고, 정상 전송 완료·client disconnect·request
취소·send OSError/예상 밖 예외에서 finally로 정확히 한 번 반환한다. HTTP가
먼저 취소되면 shielded read task의 완료 callback으로 반환을 미뤄 native DB
thread 정리 전 새 조회가 들어가지 않는다. connection은 기존 caller transaction
종료 때 반환되어 느린 전송과 대기에는 넘어가지 않는다.

RED는 body/final × 정상·cancel·disconnect·OSError·예상 밖 예외10건과 HTTP404
metric 불일치 등4건의14 FAIL/9 PASS였다. 동일 테스트는 수정 후23 PASS다.
두 send를 정지시킨 상태에서 세 번째 loader/checkout을 막고, 한 종료로 하나만
입장시켜 double release를 탐지한다. 후속 정상 요청으로 누수도 검사한다.

실제 MySQL의 같은10개 전송 경계와 실제 TCP backpressure/disconnect를 추가했다.
TCP는 실제 Uvicorn과 client socket을 사용하고 provider/decoder/regeneration을
호출하지 않는다. 초기 두 TCP 시도에서는 단일 큰 write가 만들어내는 blocked send를
관측하지 못했다. 두 번째 실패의 관측값은 active send0/load2였다. 이 fixture
실패를 제품 RED나 PASS로 바꾸지 않는다. handshake 전 receive window를 제한하고
실제 Uvicorn send를 합법적인 ASGI chunk로 분할하는 서버 adapter로 drain을 관측했다.
인위적인 send 대기 gate나 제품 테스트 분기는 없고3초/5초 deadline도 유지했다.
보정 TCP 테스트는1 PASS다. ASGI send 종료와 client 수신 ACK는 구분한다.

### P2-2: ownership scope 뒤 metadata 복원

`read_owned_frame_image`의 공개 서명은 바꾸지 않았다. 내부 repository의
`get_owned_frame`은 frame→stream→source→case_asset을 요청 case로 제한하는 단일
SELECT로 payload/bytes를 가져온 뒤에만 모델을 복원한다. identity 비교는 binary며
ref 문자열의 구조를 해석하지 않는다. 따라서 foreign ref의 손상 metadata/bytes는
unknown과 같은404/body/metric status를 갖는다. 소유를 증명한 row만 기존
TEMPORARY_FAILURE503 또는 FRAME_NOT_FOUND404(ref_unavailable)로 분류한다.
관계 식별 필드가 손상돼 소유를 증명할 수 없으면 UNKNOWN_REF로 fail-closed한다.
실제 DB 장애를404로 덮거나 exception 문자열을 파싱하지 않는다.

단일 statement는 READ COMMITTED의 같은 statement snapshot에서 관계·metadata·bytes를
읽어 이전 여러 SELECT의 check/read 간격을 제거한다. 새로운 row lock·관계 변경
정책·retention 의미는 추가하지 않았다. 실제 테스트에서 writer의 미커밋 관계 삭제는
reader에 보이지 않고 commit 뒤 다음 statement는 UNKNOWN_REF였으며, 각 read는
SELECT1개이고 caller transaction은 계속 열려 있었다. service/repository가 스스로
commit/rollback/Connection close를 호출하지 않는다. standalone owns_frame/read_frame
등의 기존 의미와 API의 공개 Recording capability 경계는 유지한다.

실제 MySQL RED3 FAIL/2 PASS → GREEN5 PASS와 공개 read 회귀3 PASS를 보존했다.
frame/stream/source의 비관계 metadata·bytes·관계 식별 필드 손상을 검사했다.
foreign/unknown의 event 종류와 HTTP status는 같고 raw ref/손상 원문은 로그에 없다.
성능 duration의 수치까지 같다는 constant-time 보장은 추가하지 않는다.

### P3와 검증 범위

기존 request/wait/latency event와 logging privacy 경계를 유지한다. P2-1의 실제
전송 수명에 latency를 통합하고 response.start의 실제 status를 사용하여 완료 전200과
typed404의FAILED 오표기를 수정했다. 새 metric/config/Owner 정책은 만들지 않는다.
transport가 disconnect를 send 반환으로 조용히 처리할 수 있으므로 client 전달 성공
ACK를 기록한다고 주장하지 않는다.

두 수정의 직접 frame/API/Recording 실행은59 PASS, TCP 보정은1 PASS다. 신규17개를
더해 frame34 parameters/8families로 inventory를 보강했고 신규 family 누락 RED2도
보존했다. checker 함수 AST·기존 inventory·migration16개·workflow bytes·30분/900초는
그대로다. DB 경로와 inventory가 바뀌어 전체 원본 mandatory MySQL/strict/mutation 및
gate unit을 현재 source로 다시 실행 중이다. 과거851/6483을 현재 PASS로 재사용하지
않는다. 완료 결과와 관련 회귀/자원 감사는 아래 후속 기록으로 추가한다.

이 수정에서도 reviewer/subagent·staging·commit·push·PR 생성은 하지 않는다.
과거 import watchdog 실패는 원인 미확정 위험으로 유지하고 단독 PASS로 소급하지 않는다.

### P2 수정 후 직접 검증 완료 기록

아래는 `.codex-scratch/rt11b-p2-20261021/`의 현재 source 직접 실행 결과다.
최초 구현의851/6483·779/1 및 독립 reviewer 실행을 현재 결과로 재사용하지 않는다.

| 실행 | 직접 결과 / 원본 |
| --- | --- |
| P2-1 ASGI 수명·metric TDD | `p2-1-red`14 FAIL/9 PASS → `p2-1-green`23 PASS |
| P2-2 live MySQL 손상 scope TDD | `p2-2-red`3 FAIL/2 PASS → `p2-2-green`8 PASS(같은5개+Recording3개) |
| frame/API/Recording 직접 묶음 | `frame-green`59 PASS, source drift0 |
| 실제 TCP backpressure/disconnect | fixture2 FAIL 보존 → `network-fragment`1 PASS/2.79초 |
| 전체 필수 MySQL child | `mandatory-p2-tmp/test_actual_report_rejects_eac0/mysql.json`/`mysql.xml`:868 PASS/2604 phases/621.982초; skip·xfail·failure·error0 |
| 원본 strict JSON/JUnit checker CLI | `strict-cli.txt`: PASS868 |
| 전체 parameter 누락 mutation | `parameter-mutations.json`:6439건 모두 거부; frame34×13=442 포함 |
| frame metadata/family 누락 mutation | `frame-omissions.json`:144건 모두 거부(metadata136+family8) |
| mandatory parent | `mandatory-p2`:1 PASS/1216.33초; wrapper1218.719초/exit0/source drift0 |
| gate unit 전체 | `gate-unit-p2`:6672 PASS/766.81초; wrapper772.938초/exit0/source drift0 |
| API·Recording 비MySQL 전체/process 회귀 | `related-unit-p2`:790 PASS/기존 외부 미디어15 SKIP/218 deselected/262.11초; wrapper270.329초/exit0/source drift0 |
| boundary·Contract·workflow | boundary0; Contract62구조/26JSON/104의미; 두 workflow actionlint PASS |
| 보존 정책 | checker 함수AST·기존 inventory·migration16개·workflow bytes 불변, nested900/워크플로30분 유지; strict gate skip/xfail0 |

현재 비MySQL broad 실행은 과거 watchdog 실패 node도 포함해 PASS했다. 이전 broad
779 PASS/1 FAIL과 단독1 PASS는 별도 원본이며 이 결과로 소급 재분류하지 않는다.
정확한 import 지연 원인과 재발 가능성은 여전히 미확정이다. TCP 초기 두 시도와
DB helper 종료 실패도 삭제·PASS 변환하지 않는다.

bare 전체 pytest는 실행하지 않았다. 수정된 DB 조회와 evidence inventory 때문에
전체 필수 MySQL·mutation·gate unit은 다시 실행했고, 관련 API/Recording/process
비MySQL도 따로 실행했다. 이 범위와 겹치는 nested/full 재실행은 반복하지 않았다.
미변경 도메인의 비MySQL 전체 회귀와 현재 diff 원격CI는 미실행이다. 원격CI는
로컬 결과로 대체하지 않으며 PR#382/#385의 CI는 선행 상태 증거로만 유지한다.

### P2 수정 후 자원 감사와 전달 상태

종료 전 실제 MySQL8.4.7 감사는 system4+owned base1 schema/기본계정4/다른
client0/transaction0/data lock0/commit flush1/fsync였다. init/server 로그를 보존하고
SHUTDOWN 및 생성한 UUID datadir 정리를 수행했다. Linux 소유 mysqld·listener·
datadir와 Windows 소유 Python runner/server 잔여는 없다. 실제 TCP 테스트의 client·
Uvicorn thread·listener도 finally에서 닫고 종료를 확인했다.

helper의 최종 port assertion은 exit1이었다. 첫 후속 관측에서 Windows52571은
공유 wslrelay PID30640의 listener였고 Linux listener는0이었다. 원본 실패와
`poststop-status.json`을 보존한다. 공유 WSL/relay를 강제 종료하지 않았으며
후속 상태는 아래 추가 기록으로 구분한다.

후속 `poststop-direct-status.json`에서는 원본 assert_port_closed가 PASS했고 Windows
listener/소유 Python0, Linux listener/소유 mysqld0 및 생성 datadir 부재를 직접
확인했다. 초기 shell 인자 전달에 기대지 않고 WSL `test ! -e`에 경로를 직접 전달해
부재를 검사했다. helper exit1·최초 relay 관측을 보존하며 해소 시점·원인은
단정하지 않는다. 공유 WSL/relay 변경 없이 현재 소유 테스트 자원 잔여는 없다.

재현된 두 제품 P2는 수정·직접 검증했다. 현재 알려진 미해결 제품 병합 차단 finding은
없으며 별도 독립 재리뷰와 현재 diff의 원격CI는 남아 있다. 비차단 위험은 과거
import watchdog 원인 미확정/재발 가능성, OS forwarding 종료 지연, 큰 bytes의
packet/RSS, 기존 PNG 식별 범위, RAM DB의 전원장애 내구성 미검증이다.
새 Contract·Owner 판단이나 공개 surface 확장은 없다.

22개 PR 후보 파일 목록은 위 표에 있으며 scratch·RAW·JSON/JUnit 원본·runner·
임시 DB/datadir·media·진단 자료와 외부 독립 리뷰 보고서는 제외한다. 기존 증거를
삭제하지 않았다. **RT-11 IN_PROGRESS · Refs #298 (RT-11(b))**를 유지하며
미커밋·미스테이징 상태로 별도 독립 재리뷰에 전달한다.

## 후속 독립 재리뷰 P1 수정 — exact identity

상태는 **RT-11 IN_PROGRESS · Refs #298 (RT-11(b))**다. 사용자 지정 후속
review 보고서와 `run_mysql_review.py`를 읽고 원본을 보존했다. 재현부 복사본을
전용 실제 MySQL8.4.7에서 직접 실행하여 `PAD_ATTRIBUTE=PAD SPACE`, trailing
space 비교1, 기존 owns_frame=False/new capability foreign PNG68bytes/HTTP200,
unknown404를 확인했다. 이전 P2 수정 후 제품 blocker가 없다는 기록은 그때의
snapshot이며 이 후속 P1 발견을 반영한 승인으로 재해석하지 않는다.

### 원인과 선택한 SQL

실제 schema는 `recording_entry.kind VARCHAR(32) ascii_bin`, `entry_key VARCHAR(64)
ascii_bin`, JSON payload와 LONGBLOB content다. `utf8mb4_bin`은 byte sequence의
binary collation과 달리 PAD SPACE이므로 Python에서 다른 유효 문자열인
`ms_padding`/`ms_padding `를 JSON join에서 같은 값으로 취급했다. 기존 stream
조회는 JSON 직렬화 identity의 SHA256 key를 사용하여 둘을 구분했다.
[MySQL8.4 문서](https://dev.mysql.com/doc/refman/8.4/en/charset-binary-collations.html)의
PAD SPACE 설명과 실제 서버 관측을 대조했다.

길이 없는 `CAST(left AS BINARY) = CAST(right AS BINARY)`를 선택했다. 실제 서버에서
trailing/leading/multiple space, 대소문자, 비ASCII/결합문자, 300자 넘는 값은 서로
불일치하고 self는 일치했다. `utf8mb4_0900_bin`도 해당 probe에서 구분했지만 schema
collation을 바꿀 필요가 없는 binary cast를 사용한다. BINARY(N)의 padding/truncation,
trim/정규화/새 ref 형식 제한은 도입하지 않는다.

신규 query의 frame→stream, stream→source, link→source, case_id, asset_ref.kind
JSON 비교에 양쪽 cast를 적용했다. JSON identity는 STRING 타입일 때만 비교에
참여하며 그렇지 않으면 SQL NULL로 fail-closed한다. 네 table-kind predicate는
기존 index 후보 비교에 exact residual을 더했다. frame entry_key는 기존 고정64자
SHA256 후보 조건을 유지하고, 복원한 FrameRef identity의 기존 validation도 유지한다.
실제 EXPLAIN에서 frame은 `uq_recording_entry_identity(kind, entry_key)` const/1row였고
나머지는 kind index 후보를 사용했다. 대규모 성능 보장을 뜻하지는 않는다.

단일 ownership-scoped statement 안에서만 관계를 제한하고, 그 뒤 metadata/bytes를
복원한다. API schema 직접 접근, Python 사후 ownership filtering, 전체 관계 목록
로딩, migration, 모델 축소, 새 공개 surface/Case callback은 없다. READ COMMITTED
statement snapshot과 caller Connection/transaction 소유권은 유지한다.

### P1 TDD와 기존 경계

새 fixture는 canonical 모델을 validate하고 기존 repository 저장 메서드로 두 case의
source/stream/frame과 서로 다른 유효 PNG를 등록한다. stream/source/frame identity의
6종 문자열 차이 × capability/HTTP를 각각 검사하며 양방향 foreign404, self의 정확한
bytes200, unknown과 같은404, 손상 foreign metadata/bytes404, owned metadata503/
bytes404 unavailable을 검증한다. case-scope trailing alias도 별도 parameter다.

첫 capability RED6 FAIL/12 PASS, 독립 HTTP RED6 FAIL/12 PASS, case-scope RED1 FAIL을
보존했다. source padding에서는 정상 own read도 ambiguous join으로 MultipleResultsFound가
될 수 있었다. 최초 P1 GREEN37 PASS 뒤 owned FrameRef metadata의 기존 dependency 의미를
별도로 검사해 후보의 과한 frame-payload predicate를 제거했다(RED1 FAIL 보존).
최종 query의 직접 frame/API/Recording/TCP 묶음은98 PASS/80.98초다. 기존 P2의
payload/final send 수명10개, MySQL 수명10개, 실제 TCP, 손상 scope와 transaction 경계를
포함한다. 원본 gate 신규 family 누락RED1도 보존했다. 잘못된 첫 gate 선택식의0건
실행은 RED로 집계하지 않는다.

필수 inventory는 frame72 parameters/9families다(이전34/8에38 parameters/1family 추가).
DB query와 보안 evidence가 바뀌었으므로 현재 source의 전체 필수 MySQL·strict 원본
JSON/JUnit·누락 mutation과 gate unit/관련 process 회귀를 다시 검증한다. 과거868/
6672/790은 보존 증거이며 현재 결과로 재사용하지 않는다. 결과·자원·미실행 검증은
후속 기록에 추가한다. 새 증거는 `.codex-scratch/rt11b-p1-20261021/`에 보존한다.

### 기존 경로 추가 관측 — 이번 수정 범위 밖

같은 서버에서 기존 `get_case_assets`의 JSON case_id 비교도 공백 alias를 허용하는
것을 별도로 확인했다. 정확히 존재하는 Case row가 없는 `case_id + ' '`에 기존
`owns_frame`은 True였다. 신규 query는 수정 후 UNKNOWN_REF이며 새 HTTP parameter는
404를 검사한다. 두 실제 case의 유효 stream/source/frame 경계에서는 기존 소유 판정과
신규 capability가 일치했다. 기존 경로의 alias 수용은 이번에 고치거나 정상 정책으로
고정하지 않으며 별도 Owner/보안 검토 항목으로 보고한다. 이 probe만으로 기존 전체
surface의 다른 실제 case bytes 노출까지 검증했다고 주장하지 않는다.

과거 import watchdog 실패는 원인 미확정 위험으로 유지한다. reviewer/subagent·
staging·commit·push·PR 생성은 하지 않으며 기존 리뷰·RAW·실패 원본은 수정하지 않는다.

### 2026-10-22 사용한도 중단 후 재개 · 보존 결과 대조

재개 때 branch/HEAD/22개 후보 파일/staging0을 다시 확인했다. 중단 전에
`mandatory-p1`이 완료됐으며 현재 source/config와의 실행 중 drift는0이었다.
child 원본 JSON/JUnit은906 PASS/2718 phases/761.840초, skip·xfail·failure·error0이다.
재개 후 현재 strict CLI도 동일 원본을 PASS906으로 판정했다. parameter mutation6933건
모두 거부(frame936 포함), frame metadata288/family9 누락297건 모두 거부했다.

parent는1 PASS/3453.90초(wrapper3453.063초/exit0)였다. 실행 구간에 Windows System의
절전·복귀 이벤트(21:47:50/22:23:01)가 있었다. 이 관측을 `power-events.json`으로
보존하며 긴 wall time의 정확한 기여도를 단정하거나 임의로 빼지 않는다. child900/
wrapper1800 설정은 바꾸지 않았고, 이 parent wall time을 workflow30분 충족 증거로
쓰지 않는다. 현재 원격CI의 실제30분 budget 충족은 미검증이다.

재개 시 원래 Windows helper와 MySQL listener/RAM datadir는 보이지 않았다. 해당
server의 명시적인 SHUTDOWN/prestop 감사·로그 회수는 완료했다고 주장하지 않는다.
첫 `gate-unit-p1`은 끊긴 DB 때문에 preflight exit4로 종료했으며 삭제·제품 실패로
재분류하지 않는다. 새 UUID 전용 server/CA를 `resume-20261022/`에 만들고 같은
source와900초 runner 제한으로 남은 gate/회귀를 진행한다. 완료된 전체 MySQL을
동일하게 반복하지 않는다. 이전 server URL/CA/원본도 덮어쓰지 않았다.

보존 검사는 HEAD 대비 frame72 parameters/9families, P2 snapshot 대비38 parameters/
1family 추가와 기존 inventory 전부 유지, checker 함수AST 불변을 확인했다. 전체
tracked migration17개와 workflow5개 bytes는 HEAD와 같다(기존 code 필터16개와
집계 범위를 구분한다). boundary0/Contract62구조·26JSON·104의미 및 두 workflow
actionlint PASS다. 현재 round 변경은 기존22개 중6개이며 새 PR 후보 파일은 없다.

### P1 최종 직접 검증과 남은 검증 차단

| 직접 실행 | 결과 |
| --- | --- |
| P1/이전 P2 frame 묶음 | 최종 query98 PASS/80.98초(현재 inventory 반영 전 snapshot; 이후 전체 child가 현재 inventory를 검증) |
| 현재 전체 필수 MySQL/strict |906 PASS/2718 phases/761.840초, strict CLI PASS906, source drift0 |
| 현재 전체 parameter 누락 mutation |6933건 모두 거부; frame72×13=936 포함 |
| 현재 frame metadata/family 누락 |297건 모두 거부(metadata288+family9) |
| 전체 gate unit |`gate-unit-p1-resumed`:7091 PASS/447.73초, wrapper452.5초/exit0/source drift0 |
| API·Recording 전체 비MySQL/process |`related-unit-p1-resumed`:788 PASS/15 SKIP/**2 FAIL**/256 deselected/330.81초, wrapper337.11초/exit1/source drift0 |
| 실패 node 분리 확인 |`regression-isolated`:**1 FAIL/1 PASS**/7.64초, source/deadline/assertion 불변 |

두 broad 실패 node는 다음과 같으며 원본을 소급 PASS로 바꾸지 않는다.

- `test_actual_server_cleanup_failure_exit_and_listener_release`: 원래5초 child가 stdout/
  stderr 없이 timeout됐다. 원래 node의 분리 실행에서도 같은5초 timeout이었다.
- `test_receive_abort_sends_no_status_and_never_registers[disconnect]`: expected close[]와
  달리['idle']이었다. 원래40ms idle 설정을 유지한 분리 실행은 PASS했다.

재실행 전에 source/call 경계를 조사하고 별도 진단을 보존했다. cleanup은 frame read를
요청하지 않는 실제 Uvicorn startup/shutdown 테스트다. 별도 phase 계측 child는 import
이후 server 반환·listener 검사·assertions를 끝냈다(phase3.906초, launch 포함 wall5.407초,
communicate timeout 인자5초). 이것을 원래 node의 deadline PASS로 쓰지 않는다. upload
timing plugin은 clock/40ms/기존 assertion을 바꾸지 않았고 실제 request→disconnect를
16ms에 관측했다. 이 진단과 별도 PASS로 원본 timeout/idle의 정확한 원인이나 해결을
확정하지 않는다. 제품/fixture/환경 원인은 미확정이며 이 둘은 현재 검증 차단 항목이다.
scope 밖 upload 동작이나 process deadline을 바꿔 GREEN을 만들지 않았다.

이번 SQL P1의 양방향 case 격리 재현은 해소됐고 이전 P2 targeted는 통과했다. 다만
관련 broad 회귀를 전체 PASS라고 할 수 없고, 기존 case-id alias 관측도 별도 Owner/
보안 검토가 남는다. 현재 원격CI와 별도 독립 재리뷰가 필요하며 병합 준비 완료를
선언하지 않는다. 과거 import watchdog 실패도 별도의 원인 미확정 위험으로 유지한다.

전체 필수 MySQL은 보안 query/inventory 변경 때문에 직접 다시 실행했다. bare 전체
pytest는 미실행이다. 현재 SQL 경로/필수 evidence 전체, 관련 API/Recording/process와
gate를 검사했고 이미 재현된 관련 실패가 있어, 겹치는 full/nested 반복으로 PASS를
만들지 않았다. 미변경 도메인 비MySQL 전체와 현재 diff 원격CI는 미검증이다. 원격CI의
30분 budget이나 성공을 로컬 결과·과거 PR CI로 대체하지 않는다.

### P1 자원 정리와 독립 재리뷰 전달

재개 후 server의 종료 전 감사는 MySQL8.4.7/system4+owned base1 schema/기본계정4/
다른client0/transaction0/data lock0/commit flush1/fsync였다. init/server 로그를 보존하고
정상 SHUTDOWN 및 생성한 UUID datadir 정리를 완료했다(helper exit0). 최종 소유 자원
상태와 파일/source 해시는 scratch의 후속 감사에 기록한다. 중단 전 server의 종료
전 감사가 없다는 제한은 이 새 server의 성공으로 덮지 않는다.

전체 후보22개 중 이번 round 변경은 다음6개다: mysql_repository.py, test_frames_mysql.py,
frame_acceptance.py, check_mysql_test_report.py, runtime-implementation-log.md,
rt11b-frame-read.md. 전체22개 경로는 위 목록과 같다. scratch·RAW·원본 JSON/JUnit·
mutation·runner·DB URL/CA·임시 DB/datadir/media·진단·외부 리뷰 자료는 PR 제외다.
미커밋·미스테이징으로 **검증 차단 사항을 포함하여 독립 재리뷰 가능한 상태**에 전달한다.
reviewer/subagent·staging·commit·push·PR 생성 없이
**RT-11 IN_PROGRESS · Refs #298 (RT-11(b))**를 유지한다.

최종 `resume-20261022/poststop-direct-status.json`은 port closed/datadir absent,
Windows 소유Python·listener0/Linux 소유mysqld·listener0을 확인했다. 공유 WSL/relay는
변경하지 않았다. `final-audit.json`에는 현재22파일 SHA256/이번6파일 차이, 실행 당시
source/config 일치, staging0, 기존 Log 전체 prefix 보존, 원본2 FAIL과 단독1 FAIL,
현재/이전 server 자원 상태를 함께 보존했다. 검증 실패를 포함하는 감사 결과이며
전체 회귀PASS를 뜻하지 않는다.

## 2026-10-22 두 회귀 실패 systematic investigation 후속 기록

사용자 요청대로 원인 확정 전에 제품·테스트를 수정하지 않았다. 신규 scratch는
`.codex-scratch/rt11b-regression-20261022/`이며 이전 실패/리뷰/RAW를 그대로 유지한다.
현재22개 후보의 byte snapshot과 index hash를 보존하고, HEAD/develop
`c491a95b8726377c2eca2ac3dad6bcc6ce416670`을 일반 archive directory로 추출했다.
새 branch/worktree가 아니며 dirty checkout을 reset/stash하지 않았다.

### Cleanup phase와 기준 비교

원래 node는 Popen을 생성한 **뒤** communicate(timeout=5)를 호출한다. 별도 GO
handshake가 없고 child import/setup부터 main/shutdown/atexit/pipe EOF가 이 예산에
들어간다. Popen 생성 자체는 communicate 예산 밖이다. 과거 실패 stack은 parent의
stdout reader join/EOF 대기를 보여주지만, 당시 child stack이 없어 child의 정확한
phase/근본 원인은 복원할 수 없다. 다른 GO 기반 composition watchdog과 구분한다.

두 test 함수 AST는 기준/current에서 동일하다. 원래5초/원래 assertion을 유지하고
marker/stack/원본 stdout·stderr/native PID tree/TCP/thread/task/pool을 분리 계측했다.
current checkout3.141초, baseline archive4.547초에 expected exit1로 반환했다.
baseline4.2초 stack은 main 반환 뒤 socket probe였고4.344초 native snapshot의
launcher/runtime에는 TCP가 없었다. 이를5초 실패 재현으로 부르지 않는다.

checkout에는 유효 source pyc122개, archive에는0개여서 양쪽 모두 cache 없는
snapshot으로 한 번 대조했다(current3.094초/base2.500초). Import/launch 시간 차이는
관측했으나 과거 timeout 원인이라고 단정하지 않는다. 현재 broad 계측 node는
communicate425873.125→425875.609, main 반환1.969초/last atexit2.282초였다.
종료 후 tasks0/checkout0/frame permit2/waiter0/child tree·TCP0이며 handler 복원
assertion도 통과했다. 실제 signal을 전송한 테스트는 아니다.

### Disconnect predecessor 조사

원래 순서의 선행160개에서 직전 idle/duration+target3 PASS, 앞80+target81 PASS,
뒤80+target81 PASS, 전체160+target161 PASS였다. 기준에 존재하는 같은 선행 묶음도
138 PASS다. 오염을 일으키는 최소 predecessor는 찾지 못했다. Target 전후 MainThread만
있고 loop None/child·TCP0, signal/env hash 복원, fixture-local app/composition을 확인했다.
실제 request→disconnect/consumed[0,1]/sent0/closed[]/등록0, checkout0/permit2/waiter0였다.
Threadpool staging/write 실행과 receive를 실제 clock/perf-counter로 기록했다.
Python3.12.14의 native monotonic 해상도15.625ms는40ms 판정의 민감 조건이지만 원인
확정 증거는 아니다. Clock freeze/timeout/sleep 증가·재시도·assertion 완화는 없다.

### 현재 직접 검증과 보존 증거

| 이번 직접 실행 | 결과 |
| --- | --- |
| 원래 API/Recording broad + 외부 phase/timing 계측 |790 PASS/기존15 SKIP/256 deselected/184.38초, source drift0 |
| frame/API/Recording/실제 TCP |98 PASS/51.55초; 실제 MySQL72개/216 phases/skip·xfail0 |
| 현재 checker + 보존된 전체906 JSON/JUnit |strict PASS906/2718 phases(전체 MySQL 새 실행과 구분) |
| 현재 독립 frame 누락 mutation |parameter936/metadata288/family9,1233건 모두 거부 |
| frame gate unit만 |801 PASS/6290 deselected/24.63초(전체7091 재실행 아님) |
| static |boundary0/Contract62·26·104/두 workflow actionlint PASS |

계측 broad는 production 호출·원래 assertion·deadline을 유지하지만 child trace prefix와
관측 wrapper가 있는 실행임을 공개한다. 무계측 새 broad라고 표현하지 않는다.
전체 선행161개/current 및138개/baseline의 cleanup child는 원래대로 실행했다.
과거2 FAIL/단독1 FAIL과 별도 import watchdog 실패는 그대로다. 현재 broad GREEN을
근본 원인 해결/안정적 반복GREEN으로 소급하지 않는다. 기준 PASS만으로 과거 실패가
RT-11(b)와 무관하다고 입증됐다고도 하지 않는다. 추측성 fix/RED→GREEN은 없다.

제품/테스트/config가 그대로여서 전체 pytest·전체MySQL·전체gate 반복은 하지 않았다.
새 관련 broad·실제frame·801 gate·독립 mutation을 실행하고 source가 일치하는 기존
전체906/6933 mutation/7091 gate는 보존 증거로 구분한다. 현재 원격CI는 미실행이며
30분/900초/strict inventory·skip/xfail 정책을 유지한다.

현재 관련 직접 회귀는 GREEN이다. 독립 재리뷰에서는 이 관측과 남은 원인 미확정/
재발 위험을 함께 검토할 수 있으며, 역사적 실패의 해소나 최종 병합 승인을 뜻하지
않는다. 기존 alias의 별도 보안 영향/Issue 후보는 PR 제외 scratch 자료로 분리했다.
그 기존 제품 경로는 이번 RT-11(b)에서 수정하지 않았다.

이번 round는 이 note와 Implementation Log만 추가 기록한다. 현재22개 후보 전체목록은
위 표와 같으며 새 제품/테스트 파일은 없다. Scratch·archive·native/stack/process 원본·
JSON/JUnit·runner·DB/CA·media·별도 보안 후속자료는 PR 제외다.
**RT-11 IN_PROGRESS · Refs #298 (RT-11(b))**를 유지한다.

이번 조사 server의 종료 전 감사는 MySQL8.4.7/system4+owned base1/기본계정4/
다른client0/transaction0/data lock0였다. 로그 보존 후 SHUTDOWN/helper exit0,
생성UUID datadir 부재·port closed·Windows 소유Python/listener0·Linux mysqld/listener0을
확인했다. 추가 Windows process 관측도 matching Python0이다. 공유 WSL/relay는
변경하지 않았다. 새 `final-audit.json`은 이번 변경이 note/Log2개뿐이고 제품/test/config
불변, 기존 index byte 동일/staging0, 현재 계측 broad GREEN/과거 원인 미확정을 함께
기록한다. Fresh72개 부분 report만으로 전체 gate를 통과시킬 수 없다는 거부도 확인했다.
