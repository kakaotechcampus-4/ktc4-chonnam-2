<a id="rt-11a-source-upload"></a>

# RT-11(a) 소스 업로드

**RT-11 IN_PROGRESS · Refs #298 (RT-11(a)) · PR #382 · merge SHA 대기.**

구현 참고 사항이며 Contract/Decision/Baseline과 다른 모듈 인터페이스는 기존
권한을 유지한다. 증거: 무시된 `.codex-scratch/rt11a-20261020/`.

<a id="sources-and-starting-point"></a>

## 출처와 시작점

유지한 checkout/브랜치는 `codex/rt11a-source-upload`다. HEAD, origin/develop 및
실제 원격 develop은 `85da60b63e784efcbbfb00369244a133b470688e`였으며, 작업 트리는
깨끗하고 staging은 비어 있었다. GitHub PR #381은 해당 SHA로 MERGED였고, 원격
boundary-check/python-tests는 SUCCESS였다. Issue #302는 CLOSED였다. Issue #298은
OPEN이었으며 최신 본문을 직접 읽었고 comments0이었다. 이 검사는 이번 diff가
아니라 REC-1에 속한다.

Plan RT-11/§12, Tech §13, HTTP §3.5/§5.2/§7-6–9, Baseline B-U1/3/4/§2.6,
REC-1(a–c), Implementation Log, 현재 API/storage/errors/logging, CaseStore 및
record_source_registered, Recording capability/repository, gate와 workflow를
대조했다. 요청한 runtime-ops-workflow §4-2 포인터는 라우터를 통해
**ops-spec.md §4-2**로 연결된다. workflow 자체에는 업로드 정책이 없다.

<a id="implementation-choices"></a>

## 구현 선택

POST /cases/{case_id}/sources는 비어 있지 않은 filename을 갖는 file part 정확히
하나만 허용하며 추가 part는 허용하지 않는다. Part Content-Type/extension으로
media를 분류하지 않는다. MIME quoted-string decoding은 원래 filename을 불투명한
메타데이터로 보존하며, 생성할 저장 이름을 선택하는 데 절대 사용하지 않는다.
성공 시 case_id, source_asset_ref, case_view만 노출한다. HTTP §5.2는 Location
header를 정의하지 않는다.

Starlette RequestBodyLimitMiddleware는 Content-Length 없이도 overhead를 포함한
원시 바이트를 센다. receiver는 HTTP413이 AnyIO ExceptionGroup으로 감싸지지 않도록
access receive proxy 안에 둔다. 기존 lock의 Starlette 1.8.0을 명시적으로
고정하고(Baseline ≥1.6), 누락된 python-multipart0.0.32만 추가한다.
[upstream changelog](https://github.com/Kludex/python-multipart/blob/master/CHANGELOG.md)에는
header 경계와 CR/LF boundary scanning 수정이 기록돼 있다. 기존 의존성을
업그레이드하지 않는다. Callback parsing은 threadpool에서 chunk를 공유 staging에
직접 쓰며 form()/UploadFile/전체 요청 buffer 또는 spool을 사용하지 않는다.
최종 multipart 완료를 확인한다. Parser 진단은 인스턴스 소유 null logger를
사용하며 공유 logger는 바꾸지 않는다.

기존 UploadSettings는 idle60s, duration1800s 및 raw1GiB를 제공한다. 빈 메시지는
idle byte clock을 갱신하지 않는다. 기본 Uvicorn은 응답 없는 return/exception/cancel에
500을 반환하며, [ASGI HTTP messages](https://asgi.readthedocs.io/en/stable/specs/www.html)에는
HTTP close send event가 없다. API 소유 H11Protocol adapter는 현재 request cycle을
캡처하는 private callback으로 이미 확정된 no-status abort 정책을 구현한다.
disconnected를 표시하고 keepalive를 비활성화하며 cycle을 깨우고 transport를
닫는다. 신뢰된 abort 상태는 잘못된 failed/completed500 이벤트 없이 access
logging을 정리할 수 있게 한다. 지원 호출은 이 adapter를 명시적으로 선택하는
python -m daesingo.api로 유지한다. 일반 ASGI hosting은 이 capability를 제공해야
하며 기본 Uvicorn만으로는 부족하다. 새 boundary reviewer가 제품 코드 작성 전에
이 경로를 독립적으로 입증했다. 이는 Plan §12.3 구현 세부사항이며 새로운
timeout 정책/Owner 의무가 아니다.

공유 staging → flush/file fsync → close → st_dev 확인 → 생성한 source locator로
원자적 os.replace는 모두 DB checkout 전에 수행한다. POSIX는 추가로 등록 전에
final, staging 및 root 디렉터리에 fsync한다. Windows에는 동등한 directory fsync
primitive가 없으므로 해당 테스트는 전원 장애 시 디렉터리 내구성을 입증하지
않는다. 이후 호출자 트랜잭션 하나에서 기존 CaseStore.load_for_update로 INTAKE를
확인하고, 그 Connection에 Recording MySQL adapter를 생성한 뒤 source를 등록하고
변경 없는 record_source_registered를 호출한다. 두 번째 Case lock은 이미 같은
트랜잭션이 소유한다. COMMIT ACK 이후에만 별도 공개 case.get_view가 201을 만든다.
Recording repository는 스스로 commit/rollback하지 않는다.

새 구현 리뷰는 첫 버전이 여전히 트랜잭션 안에서 전체 소스를 hash/probe한다는
점을 발견했다. 실제 MySQL RED 테스트 두 개와 독립 reviewer의 실제 AVI/기본
ffprobe RED가 이를 재현했다. 기존 공개 FfprobeMediaProbe 및
RecordingService(media_probe=...) 연결 지점은 이제 checkout 전에 media를 준비한다.
요청 로컬 adapter는 준비 전후와 등록 시 dev/ino/size/mtime_ns/ctime_ns 신원을
확인하여, Case lock 안에서 hash/tool 없이 준비된 결과를 반환한다. 타입이 지정된
준비 오류는 missing404/non-INTAKE409 우선순위를 유지하도록 등록까지 미룬다.
변경이 생기면 행 없이 TEMPORARY_FAILURE를 반환한다. Recording 공개 인터페이스
변경이나 추가 Owner 의무는 필요하지 않다. 서버 소유 publish 파일은 기존 공유
파일시스템 신뢰 경계의 적용을 계속 받는다.

Recording 코드만 사용하여 UNSUPPORTED_MEDIA→422, TEMPORARY_FAILURE→503,
예상 밖 오류→안전한 500으로 처리한다. Source 전용 HTTP 예외는 관련 없는 기존
오류 매핑을 보존한다. 기존 precommit DB503/unknown COMMIT500 의미는 유지한다.
commit 후 view 실패는 500이며, 미적용을 보장하지 않는다. 응답 유실 시
file_count N+1이 남으며, 재시도는 revision 의미가 동일한 새 등록이다.

실패 후 행 없는 staging/final 파일이 남을 수 있다. 정리는 RT-12가 담당하며
frames/assets/Range/retention/purge/Object Storage/capacity/concurrency/Worker/Web/
auth 정책을 도입하지 않는다.

<a id="verification-progress"></a>

## 검증 진행

- 초기 RED: HTTP/ASGI/subprocess29 FAIL, 실제 MySQL4 FAIL. 초기 두 파일 연결과
  가정한 Recording getter는 테스트 실수였고 나중에 수정했다. 첫 실패는 수정된
  assertion의 증거가 아니다.
- 첫 GREEN 시도:49 PASS/4 FAIL 및 MySQL3 PASS/1 getter test FAIL. Streaming
  HTTP413 grouping, 지나치게 넓은 422 매핑, Windows connection-aborted 처리와
  fixture 오류를 진단하고 수정했으며 실패는 계속 보존한다.
- 집중 raw1GiB 정확한 크기/+1/Content-Length 있음/없음, storage/fsync/device,
  streaming/timeouts/process 및 기존 API 회귀:59 PASS. GiB fixture는 전체 body
  할당 없이 assertion 후 명시적으로 제거한다.
- 확장 MySQL registration/rollback/filename/concurrency/checkout/abort/COMMIT
  ACK/응답 유실은 최종 inventory 전에 20 PASS. 첫 process-kill 실행은 3 PASS/
  1 전체 transaction-audit FAIL. 감사는 이제 자신을 제외하고 AUTOCOMMIT과 정확한
  스키마 소유권을 사용한다. 아래 최종 실제 strict 실행은 네 가지를 모두 포함한다.
- 새 gate family RED12 FAIL→GREEN12 PASS. 초기 독립 inventory의
  36 obligations/12 families는 리뷰 후 38로 늘었으며 기존 전체 inventory에
  추가된다. 최종 strict JSON/JUnit/parameter/metadata/family 결과는 아래에 기록한다.
- 경계 PASS, Contract62 구조/26 JSON/104 의미 PASS. 초기 Windows cp949 출력은
  em dash를 출력하다 실패했으며 명시적 UTF-8 재실행은 통과했다.

후속: source-only413은 이제 Connection:close를 포함하므로, 거부된 미완료 요청이
Uvicorn의 body draining/keepalive 재개를 일으킬 수 없다. RED2 FAIL/2 PASS는
GREEN4 PASS가 됐으며, reviewer는 실제 declared 및 chunked CLI packet,
Contract413 및 EOF를 독립적으로 확인했다. prepared-probe 수정은 현재
12 families의 MySQL 업로드 의무 **38**개를 모두 통과한다(65.08s, wrapper
exit0/source drift0). reviewer는 직접 AVI를 생성하고 checkout0 및 별도 Case
NOWAIT lock 상태에서 실제 ffprobe를 실행한 뒤 201과 새 service 복원을 확인했다.
앞선 전체 suite 시도는 이 리뷰 수정을 위해 127.766s 후 의도적으로 중단했다.
exit1/drift0은 보존하며 PASS로 재분류하지 않는다. 최종 전체 suite 실패와
성공한 격리 strict 실행은 아래에 기록한다.

전체 회귀가 모두 green인 것은 아니다. 실패 두 건과 범위를 한정한 후속 조치,
새 리뷰, 보존 및 리소스 감사는 아래에 기록한다. 현재 diff의 원격 CI는 대기
중이다. staging/commit/push/PR은 수행하지 않았다.

<a id="complete-delivery-inventory"></a>

## 전체 전달 목록

| 영역 | 파일 |
| --- | --- |
| 루트 사실/의존성 | README.md; pyproject.toml; uv.lock |
| 구현 기록 | docs/runtime/runtime-implementation-log.md; docs/runtime/rt11a-source-upload.md |
| API composition | src/daesingo/api/__main__.py; src/daesingo/api/app.py; src/daesingo/api/composition.py; src/daesingo/api/errors.py |
| 업로드 구현 | src/daesingo/api/routes_sources.py; src/daesingo/api/upload.py; src/daesingo/api/upload_protocol.py |
| HTTP/ASGI/프로세스 테스트 | tests/api/test_sources.py; tests/api/test_sources_process.py; tests/api/source_process.py; tests/api/test_process_safety.py |
| MySQL 인수 | tests/api/test_sources_mysql.py; tests/api/test_sources_interruption_mysql.py; tests/upload_acceptance.py |
| Strict gate | scripts/check_mysql_test_report.py; tests/common/db/test_mysql_gate.py; tests/common/db/integration/test_migration_gate.py |

총 22개 파일이다. tests/api/test_process_safety.py는 기존 child에 예상한 정확한
http=cli.UploadH11Protocol dictionary entry만 추가하며 모든 signal/cleanup/logger
assertion을 보존한다. 정확한 바이트 치환과 동결 hash 증거는
signal-expectation-impact.json에 있다. Scratch/RAW/archive/pytest report/media/
임시 env 파일은 PR에서 제외하며, 기존 증거는 삭제하지 않고 보존한다.

<a id="whole-suite-result-and-current-source-follow-up"></a>

## 전체 suite 결과와 현재 소스 후속 조치

동결한 full-final은 2714.09s에 **9381 PASS /26 기존 opt-in SKIP /2 FAIL**로
완료됐다(wrapper2725.875s, exit1, source drift0). 실패 내용:

- 기존 signal child는 예전 Uvicorn kwargs의 정확한 형태를 기대해 새로 필요한
  HTTP protocol을 누락했다. 해당 AssertionError로 의도한 interrupt가 수행되지 않았다.
- 원래 필수 MySQL 함수의 중첩 subprocess가 900s를 초과했다. 완료된 child
  JSON/JUnit/mutation 증거는 없다. 원래 전체 strict gate는 이 실패 보고서를
  거부하며, 결과를 합치거나 조작하지 않고 보존한다.

격리 테스트 기대값 수정 후 process-safety + HTTP/ASGI/default1GiB + 실제
timeout + 기존 app 검사는 모두 통과한다. **104 PASS**,84.99s, wrapper
exit0/drift0. 전체 동결 이후 제품 코드는 바꾸지 않았다. reviewer는 실패한
전체 실행 결과를 유지하면서 이 격리 기대값 조정과 범위를 한정한 재실행을
명시적으로 수용했다.

정확히 새로 소유한 RAM MySQL 서버는 기본 계정 4개, 다른 client/transaction/data
lock 없음, timeout 후 방치된 harness UUID 스키마 하나를 갖고 있었다.
테이블과 연결이 없음을 기록한 다음 그 스키마만 제거했다.
InnoDB flush_log_at_trx_commit=1, sync_binlog=1 및 packet64MiB를 관측했다.
원래 필수 함수를 변경 없는 nested900s/outer1800s 아래 단독 재실행했으며,
완료 결과는 다음과 같다.

격리 재실행 child는 **806 tests /2418 passed phases**로 완료됐다.
JUnit870.196s, skip0/xfail0. Root가 변경 없는 strict JSON/JUnit CLI를 실행해
통과했다. 변경 없는 900s deadline에 대해 이 로컬 실행은 29.804s만 남는다.
현재 diff의 원격 CI는 계속 대기 중이다.

<a id="final-local-evidence-and-independent-review"></a>

## 최종 로컬 증거와 독립 리뷰

원래 필수 함수는 **1 PASS in1235.87s**, wrapper1238.296s,
exit0, source drift0으로 완료됐다. 정확한 parameter omission inventory는
**5633 =5139 기존 +494 업로드**(38 upload identities ×13 layers)이며 모두
거부했다. 업로드 metadata omission152와 family omission12를 합해 추가로
164개 사례를 거부했다. reviewer는 git HEAD와 대조해 추가 38개/12 families를
독립적으로 도출하고 정확한 Counters, 중복 identity 없음, 모두 거부됨 및 XML
artifact를 확인했다. 기존 필수 inventory 전체, checker 함수 AST,
nested900s, workflow30min 및 엄격한 selected-test skip0/xfail0을 보존한다.
전체 suite의 외부 opt-in skip26개는 strict 선택 밖이며 소스 바이트는 HEAD와 같다.

새 reviewer는 HTTP/app 검사 55개, 실제 CLI timeout 검사 2개,
checkout0 및 독립적으로 사용 가능한 Case NOWAIT lock 상태의 실제
AVI/기본 ffprobe/MySQL 성공과 원시 CLI413/EOF probe 2개를 직접 실행했다.
P2 지적 두 개(413 keepalive 및 트랜잭션 안의 probe)를 모두 수정하고 독립적으로
재확인했다. reviewer는 strict806 JSON/JUnit CLI, 경계/Contract/diff 검사도
직접 실행하고 mutation/보존/현재 소스 증거를 확인했다. 남은 제품 P1/P2나
새 Owner 정책 결정은 확인되지 않았다.

Root 직접 결과는 현재 HTTP/ASGI/default1GiB/process/app 검사 104개,
업로드 MySQL 의무 38개, 원래 필수 함수+모든 누락 mutation 및 실패한
9409-case 전체 실행을 포함한다. 이는 reviewer 직접 실행 및 과거 원격 CI와
구분한다. 합친 보고서로 실패한 전체 결과를 바꾸지 않는다.

보존: REC-1(c) 증거 파일 16228개와 REC-1(a)/(b) 증거 파일 150/148개는
기록된 hash와 일치한다. 원래 Implementation Log 바이트는 정확한 prefix로
유지하며 추가 내용은 시간순이다. 동결 source/config 파일 557개는 리뷰한 signal
기대값 항목만 다르며 정확한 역바이트 치환으로 입증했다. product, gate 및
config drift0. Workflow 바이트와 동결 migration은 바꾸지 않았다.
경계 PASS; Contract62 구조/26 JSON/104 의미 PASS; diff 검사 PASS.
python-multipart0.0.32만 추가했으며 기존 lock version은 모두 같고
uv lock --check --offline은 통과한다. Native POSIX 운영 publish 함수 probe는
같은 device에서 file fsync→replace→directory fsync 세 번을 관측했다.
이는 전체 Linux HTTP/MySQL 또는 전원 장애 테스트가 아니다.

<a id="owned-resources-remaining-limits-and-handoff"></a>

## 소유 리소스, 남은 한계 및 인계

종료 전 MySQL8.4.7에는 기본 계정 네 개, system schema와 소유한 base schema만
있었고 다른 clients0/transactions0/data locks0이었다. 전체 실행 timeout으로
방치된 소유 UUID 스키마는 성공한 격리 재실행 전에 기록하고 제거했으며,
관계없는 스키마나 계정은 바꾸지 않았다. 종료 시 소유한 mysqld, RAM datadir 및
socket을 제거했다. 소유 업로드 파일 416개는 제거 전에 hash를 기록했고,
소유 테스트 링크 세 개는 링크 자체만 제거했다. 소유 테스트 Python 프로세스는
남지 않았다. 테스트별 API process/listener 정리와 orphan 조건은 원시 증거에 남긴다.

**정리 한계:** 원래 helper 종료는 exit1이었다. 관계없는 port58501도 소유한
공유 wslrelay.exe PID25236에서 Windows port62501이 계속 열려 있기 때문이다.
WSL ss에는 Linux62501 listener가 없고 MySQL backend도 남지 않았다.
공유 relay/WSL은 중지하지 않았다. 완전한 listener 정리를 주장하지 않으며,
reviewer는 이를 비차단 OS 잔여물로 분류했다. 수집한 MySQL 로그, 최종
DB/process/listener 감사, 파일별 hash 및 원래 helper 실패는
`.codex-scratch/rt11a-20261020/` 아래 보존한다.

비차단 위험: private close adapter는 고정한 Uvicorn 내부 구현에 의존한다.
지원 API CLI는 이를 제공하지만 일반 기본 ASGI hosting은 제공하지 않는다.
Windows에는 여기서 사용하는 directory fsync primitive가 없으며 RAM 테스트는
전원 장애 내구성을 입증하지 않는다. 준비한 stat 신원은 기존 storage 신뢰 경계를
유지한다. Native 파일시스템 정체는 receive deadline으로 완전히 제한되지 않는다.
로컬 MySQL child870.196/900s의 시간 여유는 작으며, Windows 전체 실행45m14s는
변경 없는 Linux CI30min workflow 아래의 성공을 입증하지 않는다.

로컬 변경은 리뷰 가능하며 이 결과를 공개하면 commit/중간 PR에 기술적으로
준비된 상태다. 원격 CI와 merge 준비 여부는 입증되지 않았다. 사용자는
staging/commit/push/PR 전에 중단하도록 요청했으며 모두 수행하지 않았다.
남은 제품 P1/P2: 새 리뷰에서 발견되지 않음. Owner 결정: 새로 도입한 것 없음.
현재 PR 번호/merge SHA: 대기. **RT-11 IN_PROGRESS**;
**Refs #298 (RT-11(a))**. FrameRef/DerivedAsset 및 다른 모든 제외 범위는
후속 작업으로 남는다. Scratch/RAW/archive/pytest output/media/temp env 및 증거
로그는 22개 파일 전달에서 제외하며 기존의 관계없는 파일은 보존했다.

<a id="pr-382-ci-duration-fixture-correction-uncommitted-follow-up"></a>

## PR #382 CI duration fixture 수정 (미커밋 후속 조치)

위 섹션은 원래 구현 증거를 보존한다. 이 후속 조치는 현재 HEAD
`fd0595def4026605530cc4f31c6613481e2a9746`에서 시작하며 브랜치는 같고 작업 트리는
깨끗하며 staging은 비어 있다. PR #382는 열려 있다. 원격 run39418471074,
job118613193000은 1538.27s에 9381 PASS/27 SKIP/1 FAIL을 보고했다.
`test_receive_abort_sends_no_status_and_never_registers[duration]`만 실패했고,
ASGI 메시지 세 개가 400 `http.malformed_request`를 구성했다.
Boundary-check는 통과했으나 이후 **MySQL execution gate는 SKIPPED**였으며
성공이 아니다. 원래 job 로그, job/run/PR JSON 및 SHA256 manifest는 새로 무시된
`.codex-scratch/rt11a-ci382-20261020/`에 보존한다. 원격 재실행은 요청하지 않았다.

원래 fixture는 설정 지연20ms, idle40ms, total70ms 및 multipart
`boundary=boundary`로 `b'-'` chunk 열 개를 전송한다. 세 번째 바이트는
잘못된 형식인 `b'---'`를 만든다. 정확한 원래 테스트는 Ubuntu24.04.1,
Python3.12.3, uv0.11.15 및 동일한 lock 의존성에서 400/메시지 세 개를 재현했다.
CI는 Python3.12.15를 사용했으며 이 patch-version 차이는 공개한다.
고정한 uv에는 로컬 managed3.12.15 다운로드 항목이 없어 정확한 버전 설정의
실패 시도를 보존한다. 초기 로컬 pytest의 missing-basetemp-parent 오류는
설정 증거이며 이후 실제 테스트 RED와 다르다.

별도 계측으로 정확한 chunk/설정 및 receive/parser/abort 이벤트를 보존했다.
잘못된 세 번째 바이트는 70ms deadline 전인 업로드 경과66.931ms에 parser에
도달했으며 registration0과 함께 400을 반환했다. 동일한 실제 지연/설정에서
payload만 유효한 열린 multipart part로 바꾸면 `duration` abort,
ASGI 메시지 없음 및 registration0이 나왔다. 실제 CI의 chunk별 경과 시간은
기록되지 않았다. 설정 시간은 알려져 있고 측정 시간은 로컬 재현에 속한다.
이 관측은 시간에 따라 달라지는 잘못된 테스트 입력을 식별하며, 운영 코드가
앞선 parser 오류를 억제해야 한다는 증거가 아니다.

테스트 소스만 바꾼다. duration 입력은 유효한 열린 part 뒤에 data byte를 붙이며,
테스트 로컬 receiver clock은 바이트가 도착할 때마다 20ms 진행한다.
payload 수정 전에 이전 잘못된 입력으로 통제된 RED를 확인했다. GREEN은
메시지/등록 없음, 정확한 `duration` close reason, 소비한 chunk 네 개,
staging payload 세 바이트 및 final 파일 없음을 검증한다. Idle/disconnect
assertion은 유지하며 실제 CLI timeout 테스트는 mock 없는 경과 시간 취소와
transport 종료를 계속 검증한다. 임의 sleep 증가, timeout 완화, 제품,
Contract/Baseline, 의존성, workflow, DB 또는 strict-gate 변경은 없다.

ASGI 테스트 helper의 선택적 arrival callback 기본값은 None이다. close observer는
이제 이미 설정된 신뢰 scope abort reason을 기록한다. MySQL helper consumer는
close entry를 무시하며 receive 경로는 같다. 독립 리뷰는 이 테스트 fixture만을
위해 새 로컬 DB/전체 pytest 재실행이 필요하지 않다고 판단했다. 새 HEAD의
원격 전체 회귀와 strict MySQL gate는 여전히 필수다.

집중 Linux3 PASS 및 Windows3 PASS. 새 reviewer는 HTTP/실제 CLI timeout 검사
33개를 독립 실행했고(GiB 사례2개 deselected), 메모리 음성 대조군 세 개는
duration 강제, transport close 또는 올바른 abort reason을 제거했을 때 예상대로
실패했다. reviewer는 product/tests/docs/git을 편집하지 않았다.

첫 광범위 Linux 실행은 94 PASS/10 FAIL,149.52s를 보존했다. 실패는 짧은
CLI-child startup/communication 제한과 관련됐다. import 전용 benchmark는
`/mnt/c`에서 5.545s, SHA가 같은 파일192개의 native source snapshot에서
1.936s를 측정했다. 이 단일 benchmark는 import 지연을 뒷받침하지만 모든
timeout의 원인을 입증하지 않는다. Git checkout/worktree는 만들지 않았다.
이후 동일한 104개 테스트는 child import에 native source를 사용하고 timeout을
바꾸지 않은 상태에서 통과했다. **104 PASS/skip0,86.34s**,
wrapper89.734s/exit0/source 변경 없음. 첫94/10 실패 결과는 별도로 보존하며
PASS로 재분류하지 않는다.

경계, Contract fixture 및 diff 검사는 통과한다. 제품 source192개와
gate/harness/inventory/workflow/dependency 파일을 HEAD와 비교했다.
총198개 파일이며 변경은 없다. reviewer는 native source 복사본192개를 독립적으로
다시 hash해 정확한 일치를 확인했다. 이번 수정에서는 이 테스트와 Runtime 기록
문서 두 개만 바뀐다. 원래 Log 바이트는 정확한 prefix로 유지하며 이전
scratch/RAW/archive/pytest 증거는 편집하거나 삭제하지 않았다.

Root 정리는 새 소유 Linux 업로드 파일67개와 Windows3개를 제거하기 전에
파일별 hash를 보존했다. 소유 Linux 테스트 Python 프로세스는 남지 않았고
Windows 프로세스 감사에서도 없었다. native 실행에서 테스트별 실제 API
listener/child 정리 assertion이 통과했다. 새 MySQL server, schema 또는 account는
생성하지 않았다. 새 비활성 Linux env/cache/source snapshot 및 원시 보고서는
계속 제외된 테스트 도구로 남기며, pytest 링크는 따라가지 않고 기록했다.
공유 WSL relay는 중지하지 않았다.

Reviewer 전용 fixture 정리에는 별도 감사 한계가 있다. 정리 스크립트는 생성한
업로드 파일을 제거한 다음, 메모리의 파일별 hash/count를 쓰기 전에 느린
metadata 검사 중 중단됐다. 해당 count/hash 기록은 복구하거나 주장할 수 없다.
최종 읽기 전용 검사에서 정확한 reviewer 루트 네 곳에 생성 업로드 파일이
남지 않았음을 기록하며 원시 로그/XML은 보존한다. 이것은 Root의 보존된67/3
기록이나 어떤 테스트 결과도 대체하지 않는다.

이번 수정은 사용자가 요청한 첫 보고 중단 지점에 있다. staging, commit,
push 또는 CI 재실행은 없다. 현재 수정의 원격 CI/MySQL gate 성공과 merge 준비는
입증되지 않았다. RT-11 IN_PROGRESS; Refs #298 (RT-11(a)).
