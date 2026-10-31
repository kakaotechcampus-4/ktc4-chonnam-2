<a id="rec-1c-ownership-and-persistent-media-reads"></a>

# REC-1(c) 소유권과 영속 미디어 읽기

REC-1 IN_PROGRESS · Refs #302 · PR pending · merge SHA pending.

이 구현 메모는 Plan REC-1, Ops §4-2, Accepted RD-17/#246,
HTTP §3.5/§5.5/§5.6/§9.1, Baseline B-C3, REC-1(a)/(b) 및 현재 코드를 따른다.
Issue #302를 직접 읽었다(댓글 없음). PR #380은 develop에
`e0f2942210fe525a70f42a76f89ccfb45a05dd5b`로 병합됐으며 boundary-check와
python-tests 검사가 통과했다. 해당 원격 결과는 (b)의 결과이며 이 미커밋 변경의
결과가 아니다.

<a id="design-and-implementation-plan"></a>

## 설계와 구현 계획

기존 Recording 흐름이 이 작업의 경계를 정한다. 공개 capability 형태는 HTTP §9.1과
Plan REC-1이 Recording에 명시적으로 위임한다. Case 인터페이스, callback, 역방향
의존성, 스키마/단계 변경이나 새 Owner 의무는 필요 없다. 사용자 지시는 이 경계
안에서 계속 진행하도록 승인한다.

- [x] RED: 소유권, 영속 읽기, 잘못된 입력, 기존 행, 충돌, 원자적 쓰기, 실패 의미에
  대한 unit 및 실제 MySQL 테스트를 작성하고 보고서를 보존한다.
- [x] GREEN: `owns_frame(case_id, frame_ref) -> bool`과
  `owns_asset(case_id, ContractRef) -> bool`을 추가한다(source/derived만).
  누락과 다른 case는 모두 False를 반환한다. 프레임 소유권은 stream→source→case를
  따르며 직접적인 frame 연결만으로는 소유권을 부여하지 않는다. Ref 문구는 불투명하다.
- [x] GREEN: `read_frame(ref) -> bytes`를 유지하고
  `read_frame_image(ref) -> FrameImage(content, content_type, image_format)`을
  추가한다. 저장된 바이트가 기준이다. PNG는 기존 extractor 출력이며 기존 PNG도
  해당 바이트에서 식별할 수 있다. 알 수 없는 기존 이미지는 unavailable이며 바이트를
  지어내거나 읽기 중 미디어 도구를 실행하지 않는다.
- [x] GREEN: `register_derived_asset(payload, *, content=None,
  content_type=None, case_id=None)`를 확장하고
  `open_derived_asset(ref) -> OpenedDerivedAsset(stream, content_type, byte_size)`을
  추가한다. 메타데이터 전용 호출은 계속 유효하다. 바이트 누락이나 메타데이터 사용
  불가는 기존 UNAVAILABLE 오류를 발생시키고, 알 수 없는 식별자는 HTTP §5.6에 따라
  UNKNOWN_REF를 발생시킨다. 이전 메타데이터 전용 get_derived_asset은 NOT_FOUND
  호환성을 유지하며 새 open capability만 해당 누락 사례를 변환한다.
  HTTP 응답 매핑은 RT-11에 남는다. Content-Type은 매개변수 없는 media type으로
  검증하고 바이트와 대조한다. 이 어댑터는 기존 PNG extractor 및 isom MP4 materializer
  출력을 인식하며 새 Contract enum이나 모든 코덱을 포괄하는 허용 목록이 아니다.
  MP4 검사는 ftyp/isom, moov, mdat가 있는 완전한 최상위 box를 요구하고, PNG 검사는
  기존 extractor signature와 IEND 경계를 확인한다. 어느 쪽도 전체 코덱 디코딩 가능성을
  증명하지 않는다. 다른 형식은 명시적 어댑터 확장이 필요하며 읽기는 octet-stream
  fallback을 추측하지 않는다.
- [x] 동결된 recording_0001의 nullable blob을 유지한다. 스키마 revision은 필요 없다.
  내부 미디어 descriptor는 기존 kind/JSON 표현을 사용한다. 메타데이터, 바이트,
  descriptor, 선택적 case 연결은 하나의 InnoDB statement를 공유하며 동시 중복을
  포함한 충돌은 statement 전체를 실패시킨다.
- [x] Recording 회귀, 실제 MySQL strict JSON/JUnit 인수 테스트, 매개변수/메타데이터/
  family 누락 변이, 마이그레이션, 경계, Contract, workflow 검사를 실행하고 timeout/
  skip/xfail 정책을 유지한다. 새 독립 검토를 받고 전체 pytest 커버리지를 평가하며
  자원을 감사하고 이전 증거를 보존한다.

<a id="storage-and-trade-offs"></a>

## 저장과 절충점

(a)가 이미 영속화한 프레임 바이트를 계속 기준으로 삼는다. 이로써 읽기 중 도구 버전,
원본 미디어 가용성, 디코딩 차이를 피하지만 MySQL 저장/packet/메모리 사용 비용이
발생한다. Derived 바이트는 기존 LONGBLOB을 재사용하며 외부 게시나 파일시스템
트랜잭션을 도입하지 않는다. 실제 payload 용량은 MySQL max_allowed_packet 및
statement/driver overhead로 제한되어 LONGBLOB의 이론 용량보다 작다. 이는 무제한
업로드/내보내기 약속이 아니며 큰 payload와 Object Storage는 별도 용량/Owner 작업이다.

기존 메타데이터 전용 asset은 메타데이터로 읽을 수 있으나 바이트는 unavailable이다.
기존 FrameRef 바이트는 read_frame이 그대로 반환하며 더 풍부한 image read는 지원되는
이미지를 식별할 수 있을 때만 성공한다. 기존 byte_size≥0 모델은 메타데이터 전용
zero-size asset을 계속 허용한다. 빈 바이트 게시는 PNG/MP4 형식을 식별할 수 없어
명시적으로 거부한다. 기존 zero-size/메타데이터 전용 asset에 바이트나 media type을
지어내지 않는다.

저장소/서비스는 커밋, 롤백, 재시도를 하지 않으며 Connection을 소유하지 않는다.
COMMIT ACK 손실은 계속 불명확하며 롤백을 주장하지 않는다. 소유권 읽기는 Case를
잠그거나 호출하지 않으며 Case-first 트랜잭션 조합은 호출자에게 남는다.

제외 범위: HTTP route, 인증, Case/Runtime 제품 코드, RT-10/RT-11 조립,
retention/purge, Object Storage, 고아 locator 조회와 정리.
이 작업에서는 staging, commit, push, PR 생성을 승인하지 않는다.

<a id="delivery-files"></a>

## 전달 파일

| 파일 | 목적 |
| --- | --- |
| `src/daesingo/recording/service.py` | 공개 소유권/읽기 capability와 등록 |
| `src/daesingo/recording/__init__.py` | 공개 분리 읽기 projection |
| `src/daesingo/recording/media_content.py` (신규) | 비공개 바이트/형식 검증과 읽기 projection |
| `src/daesingo/recording/repository.py` | 메모리 내 영속화 동등성 |
| `src/daesingo/recording/mysql_repository.py` | 호출자 Connection 원자적 영속화 |
| `tests/recording/test_ownership_reads.py` (신규) | Unit 인수 테스트 |
| `tests/recording/test_recording_repository_mysql.py` | 실제 MySQL 인수 테스트 |
| `tests/recording/test_recording_repository_compatibility_mysql.py` | 실제 PNG 호환성 assertions |
| `tests/recording_acceptance.py` | 독립 필수 증거 목록 |
| `scripts/check_mysql_test_report.py` | 추가되는 필수 증거 의무 |
| `src/daesingo/recording/README.md` | 공개 진입점 문서 |
| `docs/modules/recording/rec1c-ownership-reads.md` (신규) | 설계, 절충점, 최종 보고 |
| `docs/runtime/runtime-implementation-log.md` | 추가 전용 구현 이력 |

13개 파일 모두 미커밋 상태다. 무시되는 `.codex-scratch/rec1c-20261019/**` 아래의
모든 작업 helper, 스냅샷, 미디어, RAW, pytest/JSON/JUnit/mutation 파일과 검토자
보고서는 향후 PR에서 제외한다. 기존 scratch, archive, 무관한 untracked 파일은
보존한다. 스키마 revision이나 Case/Runtime/HTTP/Worker/retention/Object Storage
제품 파일은 포함하지 않는다.

<a id="verification-history-and-limits"></a>

## 검증 이력과 한계

- 유효한 최초 RED: unit + 실제 MySQL 41 FAIL/0 ERROR, 이후 41 PASS.
  앞선 Windows 자동 매개변수 ID 실패는 별도 harness 실패 시도로 남는다.
  이후 입력/privacy, 손상 메타데이터, 실제 형식 RED는 수정과 함께 보존한다.
  누락 asset Contract 보정은 영구 unit + 실제 MySQL RED2 FAIL → GREEN2 PASS
  증거를 갖는다.
- gate-unit 5,539-pass 실행은 보존된 증거다. 해당 소스, 독립 목록, checker 함수,
  workflow는 변경하지 않았다. 격리된 후속 UNKNOWN_REF 보정은 파일 세 개의 함수
  세 개를 변경한다. 검토자는 정확한 저장 소스/AST 차이를 비교한 뒤 이 한정적 재사용을
  수용했다. 이는 모든 최종 제품 코드를 재실행한 것이 아니다.
- 앞선 완전한 Recording 결과는 682 PASS/기존 외부 미디어 opt-in 15 SKIP이었다.
  UNKNOWN_REF 이후 직접 재실행은 681 PASS/15 SKIP/1 FAIL이었다. packet-limit
  테스트에서 예상된 게시 DBAPI 오류가 발생한 뒤 서버가 연결을 끊은 Connection에서
  정리 롤백이 실패했다. 이는 실제 실패 실행이며 최종 GREEN이 아니다. 실행 중
  소스 해시는 달라지지 않았다.
- 원본 필수 실행 세 건은 변경하지 않은 중첩900초 제한에 도달했다. 세 번째는 원래
  child argv나 제한 시간을 변경하지 않고 실제 stdout/stderr를 관측했으며 로컬
  non-TLS PyMySQL 새 계정 인증 실패도 드러냈다. 이 시도들에는 완전한 내부
  JSON/JUnit이나 성공한 strict 변이가 없다. 이를 성공 보고서로 합치지 않는다.
- 기본 TLS RAM-server 필수 실행은 통과했다. helper는 작업 소유 datadir/safe-cleanup
  prefix만 변경한다. 기본 commit flushing은1로 유지하며 유효 flush 방식은 디스크
  서버의 O_DIRECT 대신 RAM의 fsync다. 독립 검토대로 이 실행 환경은 논리 MySQL
  트랜잭션과 서비스 재구성을 검증할 수 있으나 호스트/전원 손실 시 디스크 내구성을
  증명할 수 없다.

현재 diff의 원격 CI는 pending이다. PR #380 원격 성공은 과거 (b) 증거다.
전체 pytest는 재실행하지 않았다. 새 검토자가 완전한 영향 범위 Recording, 전체
모듈 간 MySQL/마이그레이션/strict/mutation 실행, 보존된 변경 없는 gate 검사,
경계/Contract 증거를 확인한 뒤 생략을 명시적으로 승인했다. 수정하지 않은 전체
unit 모음은 향후 현재 diff의 원격 CI 역할로 남는다. 로컬 전체 모음 PASS는
주장하지 않는다.

## 최종 실행 증거와 자원 감사

| 구분 | 실제 결과 / 적용 범위 |
| --- | --- |
| 최종 소스 직접 재실행 | `recording-cleanup-final`: 682 PASS / 기존 외부 미디어 opt-in 15 SKIP, MySQL68개/204 phase 모두 PASS, xfail0, wrapper exit0/source drift0 |
| 실제 MySQL 전체 실행 | `mandatory-ram-final`: child768 PASS/2304 phase/744.172초, skip/xfail/JUnit 실패0; 원본 outer1 PASS/1162.06초, wrapper exit0/drift0 |
| strict·mutation | 원본 strict CLI root/reviewer 각각 PASS768; parameter5139 모두 거부, Recording884 layer/272 metadata/14 family 누락 모두 거부 |
| gate 보존 증거 대조 | gate unit5539 PASS; 이후 checker 함수·독립 inventory·gate test·workflow byte 불변. 제품 missing 오류 보정3함수와 packet cleanup1Expr의 정확한 source/AST 차이를 별도 감사 |
| mandatory 이후 변경 | test 파일1개에서 packet 정리의 `conn.invalidate()` 한 Expr만 추가. 원본 assertion 전부 유지, 현재 source의 단독 packet1 PASS 및 전체 Recording68 MySQL 재검증. 이전 전체 MySQL을 최신 source 전체 재실행으로 바꾸지 않음 |
| 정적·보존 | boundary 위반0, Contract62구조/26JSON/104의미 PASS; frozen migration·원본 mandatory 함수·900초·workflow30분·skip/xfail 정책 불변, (a)150/(b)148 증거 해시·원본 Log prefix 보존 |

원래 `/tmp` 서버와 RAM 서버 모두 종료 전 schema는 system4+owned base1,
계정은 초기 기본4개뿐이고 다른 client/transaction/data lock0이었다.
max_allowed_packet64MiB 복구와 init/server 로그 보존을 확인했다. 종료 후
두 소유 datadir·mysqld·Linux MySQL listener와 Windows 소유 Python helper는
없다. 테스트가 남긴 소유 schema는 앞선 timeout별 별도 감사 후 정리했다.

**종료 직후의 cleanup은 전체 PASS가 아니었다.** 두 helper의 마지막 포트
assertion은 실패(exit1)했다. Windows의 기존 공유 `wslrelay.exe` PID36320이
`127.0.0.1:53333`, `127.0.0.1:55890` listener를 유지했고, TCP는 받지만
MySQL handshake는 없었다. 해당 Linux listener/DB/process/data는 없었으며,
정확한 RAM 포트의 일시 재바인드 후에도 잔여가 남았다. reviewer는 당시 이를
공개된 비차단 OS 포워딩 잔여로 판정했다. 공유 WSL 재시작은 하지 않았다.

**최종 후속 검사(2026-10-19 18:13:10 UTC)는 두 포트 모두 닫힘**이다.
Windows listener 부재 관측 후 원래 `assert_port_closed`를 두 포트에 각각
재실행해 모두 통과했다(`port-recheck-final.json`). 공유 relay를 kill/restart한
적은 없으며 제거 시점·원인은 단정하지 않는다. 초기 helper exit1·당시 잔여
자료는 그대로 보존하고 후속 PASS로 소급하지 않는다.

원본 timeout3건, 비TLS 인증 오류, packet cleanup 실패와 이전 중간 결과는
모두 그대로 보존하며 최종 PASS와 합산하지 않는다. 전체 pytest·현재 원격
CI 미실행 및 RAM의 전원 장애 내구성 한계도 유지한다.

<a id="remaining-integration-and-nonblocking-risks"></a>

## 남은 통합과 비차단 위험

승인된 Recording 경계 안에서는 새 Owner 인터페이스나 결정이 필요 없다.
API Consumer의 연기된 검토와 RT-11 routing/HTTP 응답 매핑은 기존 통합 작업으로
남는다. 고아 데이터 조회는 별도 경계에 속한다. 현재 형식 인식은 의도적으로 기존
PNG/isom-MP4 출력에 한정하며 파일 전체를 디코딩하지 않는다. 더 큰 payload 용량은
배포 규모 산정이 필요하고 max_allowed_packet은 실제로 유한한 제한이다. 이러한
한계는 새 Contract 형식 목록이나 Object Storage 정책을 만들지 않는다.

## 최종 독립 판정

fresh reviewer `/root/rec1c_independent_review`의 `reviewer/final-review.md`는
Issue #302 전체 Scope와 아래 3개 Acceptance Criteria 충족을 확인했다.
남은 actionable P1/P2와 새 Owner 판단은 없다.

| Issue #302 Acceptance Criteria | 최종 판정 |
| --- | --- |
| 같은 DB의 새 RecordingService가 SourceAsset·CaseView FrameRef·DerivedAsset을 재등록 없이 역참조 | 충족: 저장 metadata/bytes/관계 복원, 실제 PNG 및 DerivedAsset read |
| caller rollback 후 등록 없음 | 충족: caller Connection/transaction 참여, 원자성·관계 실패·rollback 검증 |
| 다른 case ref는 소유 아님 | 충족: source/frame/derived owned/cross-case/missing, 잘못된 family·privacy 검증 |

기존 filename·UNSUPPORTED_MEDIA/TEMPORARY_FAILURE 회귀를 포함해 전체 Scope도
충족했다. 저장된 Frame bytes를 authoritative source로 선택하고 새 DerivedAsset
bytes/Content-Type·image-format capability를 제공하며, frozen schema와 기존
Caller/Owner 의미를 보존한다.

최종 manifest/문서 해시 정리를 마치면 검토상 커밋·최종 PR 준비가 가능하고,
향후 최종 PR에는 **Closes #302 사용 가능**이다. 사용자 요청대로 staging,
commit, push, PR 생성은 수행하지 않았다. 현재 diff 원격 CI와 실제 병합은
pending이므로 merge-ready 또는 DONE을 주장하지 않는다. **REC-1 IN_PROGRESS**,
PR 번호·merge SHA pending을 유지한다. 위 공유 WSL forwarding 종료 지연 이력과
형식·용량·RAM 실행 한계는 비차단 위험이며, 새 제품 Owner 의무로 바꾸지 않는다.
