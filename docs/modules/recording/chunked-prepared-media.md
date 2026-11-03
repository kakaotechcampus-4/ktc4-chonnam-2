# Prepared-media DB 청크 저장·분할 조회 구현 메모

Refs [#452](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452),
[#530](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/530),
[#537](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/537).
정철원(Runtime/Recording), 2026-11-02. Contract/운영 한도/제품 지원 길이 변경 문서가 아니다.

## 출발 상태와 근거

- 작업 checkout `C:\ktc4-chonnam-2`, 브랜치 `codex/issue452-chunked-media-storage`,
  HEAD `f1e8d82f44e2bcf630a3f2fde009035f1436d7ec`. 시작 working tree/staging 비어 있음.
  지정한 checkout에서 작업하며 merge/rebase/타인 변경 덮어쓰기를 하지 않았다.
- #538의 GitHub merged 상태와 merge SHA가 현재 HEAD인 것을 직접 확인했다.
  #530은 확인 당시 open, head `fdcccfa9`; 최신 본문·댓글·계획 P2-0b/0c와 Decision Gate를 읽었다.
  과거 #537 기록의 미병합 상태를 현재 상태로 사용하지 않는다.
- [기존 capacity 기록](../../runtime/experiments/2026-11-02-local-capacity-probe.md)의
  38,359,627 B → command 76,721,052 B / packet 64 MiB 실패는 보존한다.
  과거 packet128 대조의 저장/재조회/rollback과 timeout↔OOM 인과는 여전히 UNKNOWN이다.
- 현재 `_get()`의 metadata SELECT에도 content가 포함됐고, prepared-media는 전체 BLOB이 들어간
  다중 행 INSERT였다. 이를 현재 코드에서 확인한 뒤 변경했다.
- 비공개 제출 자료 저장소, 원본 15개, 기존 실패 DB volume, 운영 DB/AWS/provider는 읽거나 사용하지 않았다.

## 저장 구조와 불변 조건

| 항목 | 구현과 이유 |
| --- | --- |
| migration | forward-only `recording_0002`, `recording_media_chunk(kind, entry_key, chunk_index, content)` 추가. 기존 테이블/BLOB 일괄 변환 없음 |
| manifest | 기존 `prepared_content.payload`에 version=1, chunk_size/count, 총 byte_size, SHA-256, media type. 공개 Contract JSON/ref/provenance는 그대로 |
| 청크 | 최대 256 KiB. 기본 SQL command 예산 1 MiB; session packet에서 64 KiB reserve를 뺀 값과 작은 쪽 사용. 실제 escaping 2배 + SQL/metadata allowance 16 KiB를 제외해 크기 산출 |
| command guard | PyMySQL cursor.mogrify로 실제 바인딩·escaping 후 byte 길이(+command byte)를 보내기 전에 검사. 청크별 단일 INSERT, executemany 금지. SQL/영상/credential 출력 없음 |
| metadata | `_get` 기본 projection은 payload만. content가 필요한 frame/derived read만 명시. Case prepared AssetFacts는 검증된 manifest/descriptor만 읽고 영상/임시 파일을 열지 않음 |
| 동일 ref | canonical media 행의 duplicate no-op INSERT/locking current read로 직렬화. 모델과 descriptor가 같으면 청크 재전송 없음; 다르면 conflict, 새 case link도 남기지 않음 |
| legacy 재등록 | 기존 BLOB을 읽어 Python에서 비교하지 않음. 잠긴 metadata/descriptor와 server-side 길이·SHA2를 대조. 원래 BLOB은 갱신/재전송하지 않음 |
| deletion | 기존 purge 표식 의미 유지. 새 물리 삭제·retention 정책 없음 |

청크 상한은 전송 working set을 제한하기 위한 내부 값이며 처리량/동시 지원 수의 최적값 주장이 아니다.
command guard의 검사용 escaping도 청크 단위 추가 할당을 한다. driver allocation peak 자체는 측정하지 않았다.

### Prepared metadata의 정확한 숫자 표현 — 2026-11-03 후속

실제100초 재현에서 새 metadata를 JSON으로 저장·조회하는 동안 `timeline_range.end_sec`가
`100.00000033333333`에서 `100.00000033333332`로 바뀌어 같은 모델의 불변성 대조가 거부됐다.
양쪽 타입은 float이며 인접한 float의1ULP 차이를 직접 확인했다. 작은 합성 재현만의 추정에서
실제 입력의 계측으로 확인한 후 수정했다.

`analysis_source`/`incident_clip` 행만 내부 payload를
`{"__recording_prepared_metadata__":{"version":1,"json":"<original model JSON>"}}`
형태로 저장한다. 내부 JSON 문자열의 숫자는 MySQL의 숫자 parser에 다시 전달되지 않는다.
읽기 경계 `_get`/`_models`에서 원래 모델 dictionary를 복원하므로 public Contract의 number 타입,
원래 float 값·duration·timeline/provenance와 `stable_media` fingerprint 입력은 유지된다.
정확한 모델 동등성 검사는 그대로이며1ULP라도 다른 값의 재등록은 계속 거부한다.
epsilon·반올림·형식 검증 삭제·시간축 수정은 없다.

version/type/외부·내부 key 형태가 잘못된 envelope와 중복 JSON key·비정상 숫자는 거부한다.
metadata-only 등록과 content 연결도 같은 표현을 사용한다. 기존 native JSON dictionary는 그대로 읽고
동일 ref 재등록 때 갱신하지 않는다. 이미 legacy 값이 바뀐 경우 원래 값을 추측해 복구하지 않는다.
DDL/migration·BLOB/manifest/chunk 형식·서비스 interface는 바꾸지 않았다.

**읽기 호환성:** 새 코드는 기존 raw payload를 읽지만, 이 envelope를 모르는 이전 코드(#544 포함)는
신규 prepared metadata를 읽을 수 없다. schema revision이 같다는 것만으로 rollback 호환성을 보장하지 않는다.
운영 적용·rollback은 실행하지 않았으며 승인된 release/code rollback 대상 검토가 필요하다.
측정·RED/GREEN·실제 검증 근거는 [후속 기록](../../runtime/experiments/2026-11-03-metadata-publish-fix.md)을 따른다.

### 배포·rollback에 사용할 revision 조건

청크 저장과 metadata envelope는 **서로 다른 읽기 호환성 경계**다. schema head가 같거나
같은 public Contract를 사용한다는 이유로 구버전 reader를 안전하다고 판단하지 않는다.
아래는 revision의 **필요조건**이며 실제 배포/rollback 승인이나 운영 데이터 점검 결과가 아니다.

| 대상 데이터에 존재하는 형식 | revision에 필요한 reader | 제외할 revision |
| --- | --- | --- |
| legacy BLOB + native metadata만 있음이 확인됨 | 실제 schema heads·legacy descriptor/BLOB·job/case 행을 해석하는 검증된 코드 | 새 형식 부재만으로 과거 revision을 승인하지 않음. 이미 적용된 `recording_0002` 등 실제 schema와의 호환도 필요 |
| 신규 청크 + native metadata | `recording_0002` schema, version1 manifest·청크 분할 조회·detached stream과 legacy 읽기를 모두 지원 | 청크를 모르는 revision. 신규 media 행의 legacy content가 NULL이므로 기존 BLOB reader로 대체 불가 |
| 신규 metadata envelope 있음 | `__recording_prepared_metadata__` version1을 정확히 decode하고 legacy native metadata도 읽는 코드. metadata-only 행에도 필요 | envelope를 모르는 revision. 청크 reader만 있는 #544/#546 코드도 제외 |
| 청크와 envelope 모두 있음 | 위 두 reader 조건을 **모두** 충족하고 실제 schema/job/data에 검증된 revision | 둘 중 하나라도 모르는 revision |

확인한 코드 기준점은 다음과 같다.

- 청크 구현은 #544 merge `52585e38c073e48ea312c9b6510870b4bcac4d92`에 포함된다.
  이는 기능을 확인할 기준점이며 모든 후속 revision의 호환성이나 운영 known-good 상태를 자동 보장하지 않는다.
- 현재 checkout HEAD `fb40402676f7712fb86e67c468fb1c50f327bfed`는 #546 merge이며 청크 reader는 있지만
  `prepared_metadata.py`와 envelope decode 연결은 포함하지 않는다. **이 HEAD를 새 metadata 지원 revision으로
  배포하거나, envelope 발행 후 rollback 대상으로 승인하면 안 된다.**
- 새 표현을 지원하는 후보는 이 수정의 codec와 repository encode/decode 연결을 모두 포함하고 기능이 유지된
  **향후 커밋의 검증된40자 SHA**여야 한다. 지금은 미커밋이므로 해당 SHA·배포 image digest는 아직 없다.
  로컬 실험의 source ro mount/집계 hash·브랜치 이름·기존 image ID는 그 배포 revision을 대신하지 않는다.

실제 선택에는 기존 [release/job 호환 승인](../../runtime/rt14-public-deployment.md#5-release-job-호환-승인-checklist)과
[controller](../../../deploy/ec2.py)의 조건도 함께 적용한다.

1. 배포 candidate와 rollback candidate 각각의 정확한 commit SHA·immutable image digest·config tuple을 식별하고,
   실제 schema heads와 **그 시점의** media/job/case 데이터 형식에 대한 호환 근거를 승인 기록에 연결한다.
   운영 형식의 존재/부재는 이번에 조회하지 않았다. 불명확하면 구버전 사용을 승인하지 않는다.
2. 기존 `schema.json`이 있는 환경에 배포할 때 `schema_parent`는 그 현재 schema authority revision과 일치해야 한다.
   이 release revision과 Alembic의 `recording_0002` 문자열은 별개다. metadata 수정은 DDL을 추가하지 않으므로
   Alembic head만으로 envelope 읽기 호환성을 판정할 수 없다.
3. `rollback_targets`에는 위 표와 job 호환 조건을 만족한 **검증된 revision SHA만** 넣는다.
   controller는 deploy 시 기존 current revision이 candidate의 rollback_targets에 포함돼야 하고,
   rollback 시 current/previous 중 선택한 exact release가 현재 schema authority의 rollback_targets에 있어야 한다.
   오래된 release의 과거 목록으로 현재 schema authority를 대체하지 않는다.
4. 현재 current가 새 형식을 읽지 못한다면 이를 rollback_targets에 허위로 넣어 deploy guard를 통과시키지 않는다.
   호환 조건을 만족하는 revision/승인된 전이 경로가 확보되지 않으면 **배포를 보류**한다.
   previous/known-good라는 이름만으로 같은 DB에 대한 안전한 rollback이 되지 않는다.
5. 승인된 `backup_reference`와 job/kind/payload·schema 호환 검토를 함께 보존한다. backup 존재나 job drain만으로
   이미 발행된 청크/envelope를 구버전 코드가 읽게 되지는 않는다. `recording_0002`는 forward-only이며
   schema downgrade·데이터 삭제·자동 restore를 code rollback의 우회 수단으로 사용하지 않는다.

이번 변경에서 운영 deploy/rollback/복원·image publish는 실행하지 않았고 사용할 운영 revision도 승인하지 않았다.
신규 데이터 발행 후 **기존 코드로의 rollback이 안전하다는 주장은 하지 않는다**.

## 실패 원자성·stream 수명

caller가 outer transaction을 소유한다. 청크·manifest·case link publish는 nested SAVEPOINT로 묶고
각 statement 실패 시 해당 작업만 되돌린다. 실패를 caller가 잡고 commit해도 신규 부분 상태가 없고,
그 전에 같은 transaction에서 수행한 정상 작업은 남는다. 내부 outer commit/rollback·새 retry는 없다.

SAVEPOINT 시작/해제의 DB 오류에도 기존 errno/disconnect classifier와 비민감 예외 규칙을 적용한다.
rollback/해제가 불가능한 경우 initiating 오류를 보존하고 불확실한 connection을 invalidate한다.
이 경우 caller가 계속 commit하여 부분 publish를 확정할 수 없으며, deadlock으로 server가 이미
전체 transaction을 되돌린 경우에 외부 작업까지 보존한다고 약속하지 않는다. COMMIT ACK loss는 UNKNOWN이다.

청크 PK/count/min/max와 각 index의 한 행을 확인한다. SELECT의 content는 SUBSTRING으로 제한하고
실제 길이도 함께 확인하므로 손상된 oversized BLOB을 한 결과 행으로 가져오지 않는다.
총 길이·SHA-256·기존 MP4 signature 경계를 검증하며 익명 TemporaryFile에 순서대로 기록한다.
누락/추가/순서/크기/hash/manifest 변조는 반환 전에 거부한다. Legacy도 SUBSTRING으로 읽는다.

stream은 offset 0의 독립 seekable 파일이고 caller가 닫는다. 반환 후 cursor/connection/transaction을
점유하지 않으며 service.close 이후에도 이미 반환된 stream은 유효하다. 생성 중 취소/예외는 파일을 닫고,
transaction facade는 COMMIT/최종화 실패·실패한 시도의 stream도 정리한다.
production factories는 설정된 temp root와 기존 MediaRoot의 ancestor pin/lease를 주입한다.
Unix 파일 mode는 tempfile의 0600이며 O_TMPFILE/close 수명이다. 디스크 여유 사전 확인은 경쟁적 예약이나
quota 보장이 아니며, 쓰기 중 ENOSPC 등도 예외 정리 경로를 따른다. 새 temp retention 정책은 없다.

## 호환성·남는 할당

- 새 코드가 legacy BLOB과 기존 ref/hash/소유권을 읽는 것은 지원한다.
- **구버전 코드는 신규 청크 행을 읽을 수 없다.** 신규 media 행의 legacy content는 NULL이다.
  `recording_0002` 이후 발행 데이터가 있는 release의 rollback_targets에 청크를 모르는 revision을
  넣으면 안 된다. 기존 배포의 schema_parent/rollback_targets/backup_reference·job 호환성 승인 계약은
  그대로이며, 코드/운영 rollback을 실행하거나 승인하지 않았다.
- metadata availability는 저장된 publish 사실이다. 매 목록 조회마다 영상 integrity를 다시 스캔하지 않는다.
  실제 stream을 열 때 길이/hash를 검증한다.
- `open_analysis_stream`/`open_prepared_stream`의 DB 분할 조회는 전체 bytes/list를 만들지 않는다.
  기존 `get_prepared_content`의 **bytes 반환 호환 API와 export snapshot/report materializer caller는
  전체 bytes 할당이 남는다**. 이 경계를 제거하려면 기존 export 입력·snapshot 인터페이스도 stream으로
  옮겨야 한다. prepared-media의 모든 consumer나 제품 전체 메모리가 bounded하다는 주장은 하지 않는다.
- materializer의 part/최종 content bytes, 서비스 실행 중 content 보유, derived export BLOB,
  Search 재인코딩/base64/JSON working set은 별도 병목이다.

## 실제 DB·백업 검증과 한계

새 owner label `issue452-chunked-media`의 internal network/DB volumes만 사용했다.
DB CPU 0.5 / RAM 512 MiB / swap 추가 없음, buffer pool32 MiB, redo16 MiB, connections12,
packet64 MiB, binary/performance/general log 미사용. 테스트 runner CPU1 / RAM256 MiB,
소스 ro, provider 없음. 기존 image의 라이브러리를 재사용하고 Python source는 현재 checkout을 사용했다.
이미지에 pytest가 없어 기존 Windows 환경의 순수 Python pytest 패키지만 후순위로 참조했다.

초기 host available851,412 KiB / C free약3.27 GiB, Docker VM available7,028,056 KiB였다.
검증 도중 host available2,336,960 KiB도 확인했다. 같은 시점/정의의 값이 아니므로 합산하지 않는다.
기존 실패 규모의 38.36 MB 대조는 disk reserve와 낮은 초기 host 여유 때문에 NOT_RUN이다.
작은 합성 1 MiB 입력으로만 이번 전달 경계를 검증했다.

| 직접 계측 | 관측 |
| --- | --- |
| MySQL | 8.4.13, session packet67,108,864 B |
| 저장 media | AnalysisSource/IncidentClip 각1,048,576 B, 각43청크, 총86행 |
| 주입 budget | 65,536 B command 예산 테스트 PASS; 해당 쓰기의 청크24,576 B |
| 실제 command 최대 | 524,463 B. 같은 probe의 **기본 256 KiB 청크 rollback 대조까지 포함**하며 64 KiB 주입 쓰기만의 최댓값이 아님 |
| 실제 결과 row packet 최대 | 24,585 B, PyMySQL packet._data 길이. TCP wire/전체 result allocation이 아님 |
| 저장·재조회 | 새 연결에서 두 media 길이/hash 일치, checkout0, 신규 ref rollback, 같은 Connection ID 유지, Aborted_clients delta0 |
| Python 메모리 | seed probe ru_maxrss85,072 KiB / restore verify83,020 KiB. 프로세스 전체 HWM; driver별 allocation·DB peak·동시 처리량은 미측정 |
| 논리 backup | artifact4,226,377 B, 최대 INSERT line49,288 B, 새 빈 target restore 후 전체 re-dump bytes 일치 |
| 복원 media | 각1,048,576 B / 두 hash 일치 / 86청크 / 새 연결 detached checkout0 |

`backup_compose.py`에 `--skip-extended-insert`만 보완하여 hex 청크들이 다시 하나의 SQL로 묶이지 않게 했다.
release heads/envelope/hash, 빈 target guard, 전체 re-dump 비교를 유지했다. 기존 backup 도구는 여전히
subprocess capture/pack/unpack/restore 동안 전체 dump를 여러 bytes 객체로 보유한다.
legacy/derived의 큰 한 행도 그대로 dump된다. 대규모 backup 메모리 전체를 bounded로 만든 변경은 아니다.

### 실패 이력 보존

1. 기본 Windows temp/cache 권한 setup 실패 → 작업 소유 basetemp/no-cache로 수정 후 RED 재실행.
2. image에 pytest 없음, 신규 control DB 미생성의 harness 오류 → 기존 환경 후순위 참조/신규 control DB 준비.
3. 첫 두 restore harness가 mysqladmin **socket** ping으로 초기 임시 server를 준비 완료로 오인했다.
   둘째에서 고정 오류2013을 확보했고 OOM/컨테이너 restart는 없었다. 실패 target에 재시도하지 않았다.
   **TCP final-server readiness**를 적용한 별도 세 번째 빈 volume에서 restore/hash PASS.
   이는 harness 선행조건 수정이며 packet/RAM 상향·제품 오류의 성공 전환이 아니다.
4. 실제 DB 관련 첫 회귀140 PASS + `test_actual_report_rejects_each_missing_migration_check` FAIL:
   전체 strict evidence 환경변수 미지정. 사용자 범위 밖인 전체 mandatory/strict·mutation을 실행해 채우지 않았다.
5. 추가 export 회귀는 URL port 생략으로 기존 proxy가 연결하지 못해 QUEUED 대기; runner SIGINT 종료,
   33개 완료 PASS이나 run 전체는 중단이다. 명시적 :3306으로 별도 유한 재실행.
6. Windows 단위 테스트에서 context 종료 직후 temp directory entry가 보인 두 실패를 보존한다.
   delete-pending/listing 경쟁으로 **추정**하며 내부 원인을 확정하지 않았다. 단일 재실행은 PASS였고,
   파일이 실제로 존재하는지와 handle close를 함께 검사하도록 보완한 최종 focused 실행도 PASS다.

## 검증·리뷰

최종 수치와 reviewer 직접 실행/작성자 증거 검토 구분, 정리 상태는
[Runtime Log](../../runtime/runtime-implementation-log.md)의 같은 날짜 청크 저장 항목을 따른다.
초기 리뷰의 transaction 실패 stream 누수·metadata 전체 읽기·temp pin/lease·기존 단일 INSERT 회귀를
RED/실제 재현 후 보완했다. 기존 이력이나 실패를 덮어쓰지 않는다.

NOT_RUN: 전체 로컬 pytest, 전체 mandatory MySQL/strict/mutation/aggregator, 38.36 MB 대조,
실영상 encode/20분 E2E/1시간 지원/provider/ingress/AWS/운영 배포·rollback.
NOT_REACHED: 이번 합성 저장 실험의 실제 Search provider/Case/Web 경로.
UNKNOWN: 과거 packet128 실험의 성공 여부·OOM 인과, 새 구조의 대규모 peak/처리량/동시 지원 수.

20분 E2E 전에는 materializer의 part/최종 bytes·서비스 content 보유, Search source/media/request 크기와
coarse/fine·base64/JSON, Case 대기/timeout·발주/병합, 실제 ingress body/time 예산을 각각 검토해야 한다.
시간 분할 탐색·Search cap·Case timeout·운영 Recording 한도는 변경하지 않았다.

## 변경 파일과 역할

| 역할 | 파일 |
| --- | --- |
| 저장/조회 | `src/daesingo/recording/mysql_repository.py`, 신규 `chunked_media.py`, `repository.py`, `transactional.py`, `service.py` |
| temp 정책 주입 | `src/daesingo/common/storage/media.py`, `src/daesingo/worker/production_media.py`, `incident_clip_composition.py`, `export_composition.py` |
| schema | 신규 `migrations/recording/versions/0002_media_chunks.py` |
| backup command | `scripts/backup_compose.py` |
| 새 RED/GREEN·MySQL | `tests/recording/test_chunked_media.py`, `test_chunked_media_mysql.py` |
| 기존 회귀/current head | `tests/recording/test_recording_repository_mysql.py`, `test_analysis_source_limits_mysql.py`, `tests/common/db/integration/test_migrations.py`, `tests/deploy/test_backup_compose.py` |
| 필수 inventory | `tests/recording_acceptance.py`, `scripts/check_mysql_test_report.py`; 신규 각 parameter에 독립 증거 identity 부여 |
| 계획·기록 | `docs/superpowers/plans/2026-11-02-chunked-prepared-media.md`, 이 메모, `rec1a-persistence.md`, `docs/runtime/runtime-implementation-log.md` |

기존 `recording_0001` seed→upgrade 데이터 보존은 명시적으로 남겼다. 현재 head 검사와 실패 주입 revision의
부모만 `recording_0002`로 정합화했다. 과거 failure/downgrade 의미를 일괄 head 검사로 대체하지 않았다.
