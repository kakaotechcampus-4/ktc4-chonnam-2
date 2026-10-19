# REC-1(a) implementation boundary

Refs #302. This is an implementation note, not a Contract or Owner Decision.

## Acceptance and storage

The caller supplies an active SQLAlchemy Connection and owns its transaction.
The repository/service never commits, rolls back, retries, or owns the connection.
New service/repository instances using the same database and storage root restore
SourceAsset, MediaStream, FrameRef, DerivedAsset metadata and existing case/ref
associations without registration. Timeline, span resolution and stored fixture
metadata retain their existing repository semantics.

Original media stays in the supplied filesystem root. Only validated relative
locators, the registration fingerprint and stream indices enter MySQL. Absolute,
traversing, symlink-escaping and different-root locators must fail closed without
printing a path. The adapter does not copy, publish, rename or delete files.
FrameRef metadata and image bytes are stored together in MySQL (transactional
InnoDB rows); no frame file publication occurs. Rollback removes both metadata
and bytes. DerivedAsset ref, metadata and explicit case associations are durable;
its final bytes/Content-Type read surface remains REC-1(c).

The private `recording_entry` table partitions payloads by kind. A SHA-256 digest
of the opaque identity is the unique lookup key; an auto-increment ordinal
preserves existing list/registration ordering. Existing Contract JSON is stored
in `payload`; only FrameRef rows carry image data in nullable `LONGBLOB content`.
Original files, AnalysisSource bytes and locally materialized IncidentClip bytes
are not copied into that column. Relative source locators retain the original
registration size/mtime/hash and stream indices. A digest of the resolved root
binds those locators to the same configured root without storing its absolute
path. Validation runs on registration and each locator restoration, including
symlink/junction containment checks.

Case/ref associations use the existing internal associate_case_asset/get_case_assets
boundary. A ref in case A's list must not appear in case B's list. This is not the
final public ownership API, nor permission to infer ownership from a ref string.
Registration input and actual Case attachment/composition remain REC-1(b)/RT-11.

## Alternatives and transaction boundary

| Approach | Assessment |
| --- | --- |
| Caller-Connection SQL adapter, JSON contract payloads and transactional frame bytes | Selected: preserves existing models, no filesystem/DB dual publication |
| Rehydrate an in-memory snapshot and flush it later | Rejected: stale snapshots, hidden flush boundary and rollback cache hazards |
| Filesystem frame publication plus metadata rows | Deferred: needs publication/orphan coordination outside this slice |

Only Recording tables and recording_alembic_version belong to this module.
The common migration runner needs an explicit Recording registry entry; other
modules' schema and frozen revisions stay unchanged. MySQL DDL is forward-only,
implicitly committed and cannot promise transactional downgrade. Tests must
distinguish DML rollback from partial DDL after a failed revision.

AnalysisSource bytes/stream factories and inspection caches remain process-local.
The existing local IncidentClip materialization lifetime is not promoted to a
durability guarantee here; complete media publication and DerivedAsset bytes are
follow-up acceptance. No HTTP routes, public ownership surface, purge policy,
orphan lookup, Worker composition, taxonomy change or new Case/Runtime obligation
is introduced. No exactly-once guarantee or claim that a lost COMMIT ACK means
uncommitted data is made.

## Verification sequence

1. Actual MySQL RED for restore, rollback, ownership, storage, migration and errors.
2. Minimal adapter/interface/migration implementation and GREEN.
3. Recording and API/Worker regressions, full required MySQL JSON/JUnit inventory.
4. Parameter/metadata/family omission mutations, boundary/Contract/workflow checks.
5. Fresh read-only review and explicit resource cleanup audit.

## Changed file inventory

All paths below are relative to the repository. No staging, commit, push or PR
creation is part of this task.

| Purpose | Files |
| --- | --- |
| Adapter and existing repository type boundary | `src/daesingo/recording/mysql_repository.py`, `src/daesingo/recording/repository.py`, `src/daesingo/recording/service.py`, `src/daesingo/recording/spans.py` |
| Recording migration and runner registry | `migrations/recording/alembic.ini`, `migrations/recording/env.py`, `migrations/recording/script.py.mako`, `migrations/recording/versions/0001_recording.py`, `src/daesingo/common/db/migrate.py` |
| Actual MySQL acceptance and independent inventory | `tests/recording/test_recording_repository_mysql.py`, `tests/recording/test_recording_repository_compatibility_mysql.py`, `tests/recording_acceptance.py` |
| Strict evidence and existing migration regression | `scripts/check_mysql_test_report.py`, `tests/common/db/test_mysql_gate.py`, `tests/common/db/integration/test_migration_gate.py`, `tests/common/db/integration/test_migrations.py` |
| Implementation notes and append-only history | `README.md`, `src/daesingo/recording/README.md`, `docs/modules/recording/rec1a-persistence.md`, `docs/runtime/runtime-implementation-log.md` |

Execution reports and diagnostic helpers live in the ignored, task-owned
`.codex-scratch/rec1a-20261019/` directory, outside this delivery inventory.

## Verification and readiness (2026-10-19)

The implementation was tested against an owned MySQL 8.4.7 server. These are
separate executions, with overlapping coverage; their counts must not be added.

| Evidence | Observed result |
| --- | --- |
| Initial actual MySQL acceptance before adapter implementation | 25 FAIL, then implementation and GREEN |
| Final Recording acceptance plus independent-review reproductions | 28 required tests + 3 reproductions: 31 PASS |
| Entire required MySQL inventory | 728 PASS, 2,184 passing phases, skip/xfail 0, JUnit 883.700 seconds |
| Strict CLI against that original JSON/JUnit | PASS, independently repeated by the reviewer |
| Original mutation-function suffix executed separately | 4,619 parameter mutations rejected; Recording 364 layers plus 112 metadata and 9 family omissions rejected |
| Existing gate unit inventory | 5,094 PASS, preserved from this implementation session; checker functions and inventory remain unchanged since that run |
| Final boundary / Contract fixture / static checks | 0 violations; 62 structure / 26 JSON / 104 semantic checks PASS; old inventory and frozen migrations preserved |

The aggregate scratch runner timed out at its own 1,200-second guard during
mutations. It is **not PASS**. Its completed, untouched 728-test MySQL JSON/JUnit
was validated directly, then the exact original test-function AST suffix from
`report = json.loads(...)` through its final artifact write ran with the original
globals and assertions. There was no mocked subprocess result or fabricated
execution report. Source/AST/input hashes and normal completion are recorded in
`mutation-recovery-command.json` and `mutation-recovery-result.json`. The reviewer
independently checked the AST identity. Workflow 30 minutes and nested MySQL 900
seconds were not changed. The 16.3-second nested margin is a performance risk.

Caller rollback, uncommitted visibility, same-stream serialization, actual lock
timeout, failed multi-row writes, disconnect, unrelated SQL errors and lost COMMIT
ACK were exercised on real MySQL. Lost ACK remains an unknown outcome: committed
refs can restore despite the caller receiving CommitOutcomeUnknown. No exactly-once
or non-commit guarantee is introduced. Fresh/new-instance restoration, real PNG
bytes after deleting the original, and cross-case negative retrieval all passed.
Fresh/previous-revision upgrade, data preservation, rerun and schema metadata
comparison passed. Downgrade is rejected; failed DDL can remain partially applied
under existing forward-only MySQL migration policy.

The final non-MySQL consumer selection was **1,224 PASS / 17 SKIP / 2 FAIL**.
Recording had 544 PASS / 15 external-media skips; Worker 91 PASS; Case 475 PASS /
2 external-video skips. API process-safety tests exceeded their unchanged total
5-second deadline. A file recheck had 43 PASS / 2 FAIL; isolated failing scenarios
had 8 PASS / 1 FAIL. This is **not an overall green regression**. A read-only virtual
HEAD comparison substituted the four changed import modules with their HEAD
source: both current and virtual HEAD exceeded the deadline in three paired
cases. Both include an extra import loader, so this is differential diagnostic
evidence, not an untouched HEAD pytest result. A separate 20-second diagnostic
guard allowed the unchanged lifecycle/listener/signal assertions to finish in
6.963 / 7.025 seconds. It does not replace or relax the original 5-second test.
An environment/timing cause is an inference; its exact cause is unconfirmed.
No API implementation or process timeout policy was changed.

All raw attempts, including configuration, cleanup and timeout failures, are
preserved separately. The earlier complete full-pytest attempt had 3 FAIL and
the later full attempt was deliberately stopped; neither is a final PASS.
`verification-final.json` separates these current results. The reviewer ran
boundary/Contract/static/strict checks directly and inspected implementation-run
MySQL/pytest/OS evidence; the reviewer did not repeat the entire database suite.

The initial resource audit found two owned test schemas after aggregate timeout;
they were explicitly removed and a new audit confirmed no clients, transactions,
locks or test accounts. The owned server was gracefully stopped, logs copied,
and its exact temporary data directory removed. The initial failed cleanup check
remains in `pre-cleanup-leftovers.json`, separate from the corrected audit.

Contract, Accepted Decision and Baseline meanings/values are unchanged. This
slice adds no Case/Runtime obligation. REC-1 remains IN_PROGRESS / Refs #302 with
PR and merge SHA pending. Source registration/composition remains (b)/RT-11;
final ownership and DerivedAsset bytes/Content-Type remain (c). Original
IncidentClip byte publication lifetime remains a follow-up limitation.
The current diff has no remote CI result. Original API timing failures and current
CI must remain visible in merge readiness; REC-1(a) code/acceptance readiness is
separate from a clean whole-project regression or REC-1 completion.
