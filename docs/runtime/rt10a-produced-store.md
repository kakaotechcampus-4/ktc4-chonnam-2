<a id="rt-10a-produced-object-storage-gate"></a>

# RT-10(a) produced object 저장 gate

**IN_PROGRESS · Refs #297 (RT-10(a)) · PR pending · merge SHA pending.**

<a id="implementation-notes"></a>

## 구현 기록

### 구현 결과

- `common/jobs/produced.py`: payload 의미를 해석하지 않는 JSON snapshot·append-only repository·기존 `ProducedReader(conn, kind, produced)` callable 구현. Search/readout/Case import가 없다.
- `runtime_0005`: 새 `produced_objects` InnoDB table. `(execution_id, ordinal)` primary key, case/job kind binding, opaque object kind/ref와 JSON payload. 이전 frozen migration은 수정하지 않는다.
- 내부 `HandlerResult.objects`는 optional이며 기존 참조만 있는 결과와 recording 외부 참조는 그대로 허용한다. Worker가 dispatch 결과를 detached JSON snapshot으로 검증하고 ref를 결합한다. T1 직접 record 진입도 같은 검증을 한다.
- owner 조건부 terminal UPDATE가 성공한 Connection에서 payload batch를 append한다. 같은 T1 transaction이 실패하면 terminal·produced·payload 모두 rollback한다. 실패 terminal의 진단 객체도 보존하지만 유효 결과 여부는 기존 Contract가 정한다. cancellation·stolen ownership에는 payload를 쓰지 않는다.
- COMMIT 불명 복구는 기존 owner/status/produced/failure receipt와 저장 객체 전체를 대조한다. 누락·변조 객체를 뒤늦게 채워 성공으로 바꾸지 않는다. capability를 재호출하지 않는다.

### Plan 대비 변경

실제 kind handler 등록 전에 #346 O-1~O-3 저장소 gate만 분리한다. Runtime Plan §12.3의 implementation detail이며 원본 Plan·Contract·Case 결정은 수정하지 않는다. [#346 Implementer 확인 댓글](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/346#issuecomment-6296651923)을 적용한다. Search O-4 확인 대기는 그대로 두며 이 저장소가 `candidate_id`를 만들거나 해석하지 않는다.

### 새로 고정된 implementation detail

| 항목 | 선택 |
| --- | --- |
| ID 없는 객체 | 명시 ref가 없으면 `runtime:{execution_id}:{ordinal}`. 순번은 `objects`의 0-based 위치이며 persistence retry에서 같은 순서를 쓴다. payload의 `id` 등 키를 추측하지 않는다. |
| 명시 ref | caller가 제공한 문자열을 그대로 보존한다. 소비자는 ref를 해석하지 않는다. |
| 참조 index | `[kind, ref]`의 모호하지 않은 JSON encoding을 SHA-256한 32-byte unique index. 원문 kind/ref도 대조해 digest 충돌을 성공으로 취급하지 않는다. Contract에 없는 임의의 짧은 ASCII ref 제한은 추가하지 않는다. |
| JSON 저장 표현 | Python이 구조만 검증한 strict JSON을 LONGTEXT로 저장하고 읽을 때 JSON으로 복원한다. MySQL native JSON은 uint64/int64 범위 밖 정수를 double로 바꾼다는 실제 DB 재현이 있어 피했다. SQL JSON parser의 숫자 범위를 다시 적용하는 `JSON_VALID` constraint도 두지 않는다. 모듈에 새 숫자 제한을 요구하지 않으며 원문 숫자 타입·값을 보존한다. |
| replay | 같은 execution 전체 객체 snapshot·case·job kind·ordinal·ref·payload가 같으면 no-op. 다른 binding/content는 `ProducedConflict`. UPDATE/upsert/delete 경로는 제공하지 않는다. batch INSERT의 savepoint는 caller가 충돌을 잡고 commit해도 일부만 남지 않게 한다. |
| Reader | 단일 dict는 그대로 반환한다. 여러 객체는 입력 ref 순서의 payload tuple을 caller의 `assemble(kind, payloads)`로 전달한다. module별 projection·형 변환은 후속 composition의 몫이다. missing/wrong kind/중복 ref/mixed execution/empty/assembler 없는 다중 결과는 오류다. |
| 외부 저장소 | recording 등 자기 저장소가 있는 ref는 Runtime에 복제하지 않는다. 이 reader는 저장소에 있는 ref를 읽는 구현이며, 도메인별 외부 ref 선택과 공개 조회 조립은 후속 작업이다. |

### Contract / Decision / Baseline 영향

변경 없음. JobExecution 공개 필드와 전이·T1/T2 구분·readout 1 execution/public 호출 1회·취소 produced 정책·lease/retry/timeout을 유지한다. 다른 Owner 공개 surface에 새 필수 인자를 추가하지 않는다. `StoredObservationAdapter`, Case 8-13, 실제 Search/readout/recording export handler, RT-11은 구현하지 않는다.

### Owner 확인 포인트

Runtime/Ops deferred review: opaque store와 COMMIT receipt 검증, ref/index 구현 선택. Case 후속 composition은 기존 callable에 reader를 주입하고 다중 객체의 의미를 조립한다. 이번 slice는 실제 handler 배선·비동기 Real E2E 완료를 주장하지 않는다.

<a id="verification"></a>

### 검증

검증 원본은 ignored `.codex-scratch/rt10a-20261021/`에 있다. 아래 최종 결과와 별도로 이전 실패·중단 이력을 보존한다.

| 최종 검증 | 결과 |
| --- | --- |
| gate/payload/Worker unit | 6,364 PASS · 711.49초 |
| 실제 MySQL 8.4.7 child | 834 PASS · 2,502 PASS phases · 682.994초 · skip/xfail 0 |
| strict JSON/JUnit CLI | PASS |
| 원본 mandatory 전체 | 1 PASS · 1088.23초 · wrapper exit0/1090.61초/source drift0 |
| 전체 parameter mutation | 5,997건 모두 거부 · 신규 저장소 364건 포함 |
| 신규 metadata/family 누락 | 125건 모두 거부 · exact Counter 일치 |
| 보존 확인 | 기존 필수 inventory·checker 함수 AST·frozen migration15·workflow30분·nested900/outer1800 불변 |
| 소스·원본 보고서 | 현재 mandatory snapshot 해시 일치 · mutation 전후 JSON/JUnit 해시 일치 |

최종 원본은 `mandatory-owned-ca-retry*`, 대조 결과는 `final-validation.json`, 단위 검증 이후 Recording head assert 한 곳의 동등성은 `unit-source-equivalence.json`에 있다. 독립 reviewer는 코드 P2 두 건의 수정·DDL·unit14, 실제 child JSON/JUnit·신규 inventory·소스563개·기존 gate 보존을 직접 확인했다. parent의 최종 mutation Counter는 root의 별도 audit 결과이며 reviewer가 전체 MySQL을 다시 실행했다고 주장하지 않는다. 전체 pytest와 현재 diff의 원격 CI는 미실행이다.

- 시작 HEAD와 fetched develop: `596e8a162b71949e7b3189e994921bb6247aac4b`; branch `codex/rt10a-produced-store`, 처음 index/worktree clean.
- 기존 Worker/dispatch/migration unit baseline: 81 PASS. 최초 기본 temp 경로 실행은 73 PASS/8 setup ERROR였으며 workspace basetemp로 보정한 결과와 구분한다.
- 새 payload unit: RED 10 FAIL → GREEN 10 PASS.
- 실제 MySQL 저장소/T1: RED 22 FAIL → GREEN 22 PASS; 직접 T1 receipt RED 3 FAIL → GREEN receipt/batch 4 PASS. 실제 MySQL 8.4.7 및 COMMIT OK 폐기 proxy를 사용한다.
- 신규 독립 gate family의 inventory RED 11 FAIL. 기존 필수 inventory·strict checker 함수·workflow30분·mandatory nested900초는 유지하고 새 obligations만 추가한다.
- 최초 migration 회귀 RED는 8 FAIL/19 PASS였다. 새 head와 table inventory에 대한 기대값만 보정한다. 이 실행은 후반 root의 별도 파일 변경 3건으로 source drift가 보고되어 final evidence로 쓰지 않는다.
- 처음 gate unit 회귀는 inventory 확장 도중의 중간 실행이라 작업 고유 인자로 확인한 프로세스만 중단했다. 최종 source로 다시 검증한다.

리뷰 보완과 최종 검증 진행:

- nested object corruption RED: 3 FAIL/1 기존 PASS → 관련 produced/Worker unit 74 PASS. 기존 Worker·T2·redelivery·migration MySQL 회귀는 274 PASS/319.66초, source drift0였다.
- 두 번째 독립 리뷰는 MySQL native JSON의 정수 `18446744073709551616` 및 큰 음수 손실을 실제 SELECT로 재현했다. 제품 테스트 RED 2 FAIL 뒤 lossless JSON text binder로 보완했다. 그 뒤 **신규 MySQL 전체 28 PASS/32.43초, source drift0**다. 큰 정수의 첫 읽기·JSON primitive 구분·같은 T1 receipt 재조회도 포함한다.
- 독립 최종 리뷰: produced unit14 PASS, frozen-to-be migration/live metadata DDL 일치, binder primitive roundtrip·잘못된 JSON 거부를 확인했다. 코드 수정이나 MySQL 전체 재실행을 reviewer가 했다고 주장하지 않는다. 남은 P1/P2는 보고되지 않았다.
- 숫자 P2 발견 시 진행 중이던 첫 mandatory와 중간 inventory gate unit은 고유 command line으로 확인한 이번 프로세스만 중단했다. 이 중단 실행에서 strict 전체 PASS를 주장하지 않는다. 최종 inventory28 parameter/13 family로 원본 mandatory와 gate unit을 다시 실행한다.

제한: 저장소 공개 append/read 경로는 엄격한 JSON snapshot을 사용하지만, privileged raw SQL로 LONGTEXT를 직접 바꾸는 것을 DB JSON constraint가 막지는 않는다. 그런 변경은 지원되는 repository 경로가 아니다. 저장소가 module schema/유효성을 검증하거나 결과를 해석하지는 않는다. 중복되는 명시 kind/ref를 다른 execution에 재귀속하는 append는 conflict이며, 기존 저장 객체를 재사용할 때는 refs-only 경로를 유지한다. payload 크기는 기존 MySQL packet/storage와 Python JSON parser의 자원 한계를 따른다.

전체 gate 실행 이력:

- gate/payload/Worker unit **6,364 PASS/711.49초**, wrapper exit0/717.562초/drift0. 그 뒤 소스 차이는 Recording migration 테스트의 head 기대 문자열 `runtime_0004 → runtime_0005` 한 곳이다. reviewer가 563개 해시와 해당 역치환 SHA를 대조해 unit 대상·의존성 불변을 확인했다. 바뀐 원본 Recording 테스트도 별도로 1 PASS다.
- 첫 완료 mandatory의 child는 **832 PASS/2 FAIL**, 834 selected/2502 phases/661.778초. strict CLI는 거부했고 parent도 FAIL했다. 실패는 위 Recording head 기대값과 로컬 비TLS percent-password 인증 오류다. 기본 TLS의 동일 인증 원본은 1 PASS였다. 이 두 검증을 합쳐 원래 전체가 통과했다고 주장하지 않는다.
- 기본 TLS mandatory 재실행은 **child900초 TimeoutExpired · parent1 FAIL/900.93초**(wrapper904.906초/drift0)다. nested900/outer1800·workflow30분을 늘리지 않았다. timeout 이후 이번 command line의 자식 잔여는 없었다.
- 설치된 PyMySQL1.2.3/SQLAlchemy2.1.3/cryptography50.0.1/pytest8.4.2는 `uv.lock`과 같았다. dependency를 바꾸지 않았다. 로컬 TLS 8회 실측은 기본0.547초, 이번 서버의 CA를 명시한 설정0.218초다. 전체 timeout 원인을 이 표본만으로 단정하지 않는다.
- 최종 로컬 재실행은 이미 허용된 harness URL 옵션 `ssl_ca=<이번 서버의 공개 CA>`와 `ssl_check_hostname=false`를 사용한다. PyMySQL은 CA 검증(CERT_REQUIRED)을 적용하고 TLS cipher를 확인했다. 자동 생성된 local CN의 hostname 검증은 기본 설정과 같이 끈다. 제품 설정·DB 권한·durability·dependency·원본 테스트/strict/timeout은 그대로다. 최초 잘못 조합한 verify 옵션의 certificate 오류도 scratch 기록으로 남겼으며 dialect가 지원하는 옵션으로 보정했다.
- 위 CA/TLS 설정에서 원래 percent-password 인증과 신규 저장소28개를 합친 **29 PASS/21.62초/drift0**를 확보했다. 이후 원본 mandatory 전체·mutation도 이 설정으로 재실행해 위 최종 결과를 확보했다.

- 첫 CA/TLS 전체는 833 PASS/1 FAIL이었다. 유일한 실패는 기존 RT-11 upload interruption의 API 자식8초 startup deadline이다. 해당 원본4모드는 변경 없이4 PASS/16.38초였으며, 같은 소스·설정의 다음 원본 전체가 위 최종 결과로 통과했다. RT-11 제품/fixture/제한은 수정하지 않았다. 이전 전체 실패를 별도4 PASS로 합성하지 않는다.

상태는 **IN_PROGRESS · Refs #297 (RT-10(a))**다. gate slice 검증을 전체 RT-10 handler/Real E2E 완료로 해석하지 않는다. 최종 전달 파일 해시와 자원 점검은 ignored `handoff-manifest.json`에 남긴다.

자원 정리: 중단 실행이 남긴 소유 UUID schema3개를 테이블·연결 확인 후 정리했고, 종료 전 transaction0·기본 schema5개·기본 계정만 확인했다. helper는 Linux shutdown/datadir 정리 뒤 Windows relay의 일시적인 TCP 수락 때문에 exit1이었다. 최초 실패를 보존한다. 사용 한도로 마지막 읽기 전용 점검이 실행되지 않았고, 사용자 재개 요청 후 같은 점검을 완료했다. 현재 Windows54381 listener·Linux listener·임시 datadir·검증 자식 프로세스는 없으며 공유 relay를 강제 종료하지 않았다. `resource-final.json`에 현재 관측과 최초 실패를 함께 기록했다.

현재 diff 원격 CI는 미실행이다. 모든 변경은 미커밋·미스테이징으로 남긴다.
