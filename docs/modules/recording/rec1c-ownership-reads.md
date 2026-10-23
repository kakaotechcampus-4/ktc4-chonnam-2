# REC-1(c) ownership and persistent media reads

REC-1 IN_PROGRESS · Refs #302 · PR pending · merge SHA pending.

This implementation note follows Plan REC-1, Ops §4-2, Accepted RD-17/#246,
HTTP §3.5/§5.5/§5.6/§9.1, Baseline B-C3, REC-1(a)/(b), and the current code.
Issue #302 was read directly (no comments). PR #380 merged into develop at
`e0f2942210fe525a70f42a76f89ccfb45a05dd5b`; its boundary-check and python-tests
checks passed. Those remote results belong to (b), not this uncommitted change.

## Design and implementation plan

The existing Recording flow bounds this work. Public capability shape is
explicitly delegated to Recording by HTTP §9.1 and Plan REC-1. No Case interface,
callback, reverse dependency, schema/stage change or new Owner obligation is
needed. The user's instruction authorizes continuing inside this boundary.

- [x] RED: unit and real MySQL tests for ownership, durable reads, invalid input,
  legacy rows, conflicts, atomic writes and failure semantics; preserve reports.
- [x] GREEN: add `owns_frame(case_id, frame_ref) -> bool` and
  `owns_asset(case_id, ContractRef) -> bool` (source/derived only). Missing and
  cross-case both return False. Frame ownership follows stream→source→case;
  a direct frame association alone never grants ownership. Ref text is opaque.
- [x] GREEN: preserve `read_frame(ref) -> bytes`; add
  `read_frame_image(ref) -> FrameImage(content, content_type, image_format)`.
  Stored bytes are authoritative. PNG is the existing extractor output; legacy
  PNG can be identified from those bytes. Unknown legacy images are unavailable,
  without inventing bytes or running media tools during reads.
- [x] GREEN: extend `register_derived_asset(payload, *, content=None,
  content_type=None, case_id=None)` and add
  `open_derived_asset(ref) -> OpenedDerivedAsset(stream, content_type, byte_size)`.
  Metadata-only calls remain valid; missing bytes or unavailable metadata raises
  the existing UNAVAILABLE error; unknown identities raise UNKNOWN_REF as HTTP
  §5.6 requires. The older metadata-only get_derived_asset keeps its NOT_FOUND
  compatibility; only the new open capability translates that missing case.
  HTTP response mapping remains RT-11. Content-Type is validated as a bare media
  type and checked against the bytes. This adapter recognizes the existing PNG
  extractor and isom MP4 materializer outputs, not a new Contract enum or an
  exhaustive codec allowlist. MP4 checks require complete top-level boxes with
  ftyp/isom, moov and mdat; PNG checks match the existing extractor signature and
  IEND boundary. Neither proves full codec decodability. Other formats need an
  explicit adapter extension; reads never guess an octet-stream fallback.
- [x] Keep the nullable blob in frozen recording_0001. No schema revision is
  needed. Internal media descriptors use the existing kind/JSON representation.
  Metadata, bytes, descriptor and optional case link share one InnoDB statement;
  conflicts fail the whole statement, including under concurrent duplicates.
- [x] Run Recording regression, real MySQL strict JSON/JUnit acceptance and
  parameter/metadata/family omission mutations, migrations, boundary, Contract
  and workflow checks; retain timeout/skip/xfail policy. Obtain fresh independent
  review, assess whole pytest coverage, audit resources, preserve prior evidence.

## Storage and trade-offs

Frame bytes already persisted by (a) remain authoritative. This avoids tool
version, original-media availability and decode drift during reads, at the cost
of MySQL storage/packet/memory usage. Derived bytes reuse the existing LONGBLOB;
no external publication or filesystem transaction is introduced. Actual payload
capacity is bounded by MySQL max_allowed_packet and statement/driver overhead,
below the LONGBLOB theoretical capacity. This is not an unlimited upload/export
promise; large payloads and Object Storage remain separate capacity/Owner work.

Legacy metadata-only assets stay readable as metadata and unavailable as bytes.
Legacy FrameRef bytes are returned unchanged by read_frame; the richer image
read succeeds only when a supported image can be identified. The existing
byte_size≥0 model still permits metadata-only zero-size assets; empty byte
publication cannot identify a PNG/MP4 format and is explicitly rejected. No
bytes or media type is invented for legacy zero-size/metadata-only assets.

Repository/service do not commit, roll back, retry or own the Connection. COMMIT
ACK loss remains unknown, never a rollback claim. Ownership reads do not lock
Case or call it; Case-first transaction composition stays with the caller.

Excluded: HTTP routes, authentication, Case/Runtime product code, RT-10/RT-11
assembly, retention/purge, Object Storage, orphan locator lookup and cleanup.
No staging, commit, push or PR creation is authorized in this task.

## Delivery files

| File | Purpose |
| --- | --- |
| `src/daesingo/recording/service.py` | Public ownership/read capabilities and registration |
| `src/daesingo/recording/__init__.py` | Public detached read projections |
| `src/daesingo/recording/media_content.py` (new) | Private byte/format validation and read projections |
| `src/daesingo/recording/repository.py` | In-memory persistence parity |
| `src/daesingo/recording/mysql_repository.py` | Caller-Connection atomic persistence |
| `tests/recording/test_ownership_reads.py` (new) | Unit acceptance |
| `tests/recording/test_recording_repository_mysql.py` | Actual MySQL acceptance |
| `tests/recording/test_recording_repository_compatibility_mysql.py` | Actual PNG compatibility assertions |
| `tests/recording_acceptance.py` | Independent required evidence inventory |
| `scripts/check_mysql_test_report.py` | Additive required evidence obligations |
| `src/daesingo/recording/README.md` | Public entry documentation |
| `docs/modules/recording/rec1c-ownership-reads.md` (new) | Design, trade-offs and final report |
| `docs/runtime/runtime-implementation-log.md` | Append-only implementation history |

All 13 files remain uncommitted. All task helpers, snapshots, media, RAW,
pytest/JSON/JUnit/mutation files and reviewer reports under ignored
`.codex-scratch/rec1c-20261019/**` are excluded from a future PR. Existing scratch,
archive and unrelated untracked files are preserved. No schema revision or
Case/Runtime/HTTP/Worker/retention/Object Storage product file is included.

## Verification history and limits

- Valid initial RED: unit + actual MySQL 41 FAIL/0 ERROR, then 41 PASS.
  The earlier Windows automatic-parameter-ID failure remains a separate failed
  harness attempt. Later input/privacy, damaged-metadata and actual-format REDs
  are preserved alongside their fixes. The missing asset Contract correction
  has permanent unit + actual MySQL RED2 FAIL → GREEN2 PASS evidence.
- The 5,539-pass gate-unit execution is preserved evidence. Its source,
  independent inventory, checker functions and workflow remain unchanged. The
  isolated later UNKNOWN_REF correction changes three functions in three files;
  reviewer compared the exact saved source/AST delta before accepting this
  bounded reuse. It is not a replay of all final product code.
- The earlier complete Recording result was 682 PASS/15 existing external-media
  opt-in SKIP. After UNKNOWN_REF, the direct replay was 681 PASS/15 SKIP/1 FAIL:
  the packet-limit test received the expected publication DBAPI error, then its
  cleanup rollback failed on the server-disconnected connection. This is a real
  failed run, not a final GREEN. Its source hashes did not drift during execution.
- Three original mandatory executions hit the unchanged nested900-second limit.
  The third observed actual stdout/stderr without changing the original child
  argv or deadline; it also exposed a local non-TLS PyMySQL fresh-account auth
  failure. No complete inner JSON/JUnit or successful strict mutations exist for
  those attempts. They are not combined into a successful report.
- The default-TLS RAM-server mandatory execution passed. Its helper changes
  only the owned datadir/safe-cleanup prefix. Default commit flushing remains1;
  effective flush method is fsync on RAM versus O_DIRECT on the disk server.
  This runtime can validate logical MySQL transactions and service reconstruction,
  as independently reviewed, but cannot prove host/power-loss disk durability.

Current-diff remote CI is pending. PR #380 remote success is historical (b)
evidence. Whole pytest was not rerun: the fresh reviewer explicitly approved
omission after checking complete affected Recording, the full cross-module
MySQL/migration/strict/mutation execution, preserved unchanged gate checks and
boundary/Contract evidence. Untouched full unit suites remain the role of the
future current-diff remote CI. No local full-suite PASS is claimed.

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

## Remaining integration and nonblocking risks

No new Owner interface or decision is required inside the approved Recording
boundary. API Consumer deferred review and RT-11 routing/HTTP response mapping
remain their existing integration work. Orphan lookup belongs to its separate
boundary. Current format recognition is deliberately bounded to the existing
PNG/isom-MP4 outputs and does not decode entire files. Larger payload capacity
needs deployment sizing; max_allowed_packet is an actual finite limit. These
limitations do not create a new Contract format list or Object Storage policy.

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
