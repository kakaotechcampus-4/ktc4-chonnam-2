# REC-1(b) registration input

Status: IN_PROGRESS · Refs #302 (REC-1(b)) · PR pending · merge SHA pending.
This is an implementation note, not a new Contract or Owner Decision.

## Sources and implementation boundary

Compared directly with Runtime Implementation Plan REC-1/§12, Ops §4-2,
RD-17/#246 (including the final decision comment), HTTP Contract §5.2/§9.1,
Baseline B-C3, the current #302 body/comments, REC-1(a) persistence notes,
Implementation Log, Recording models/service/repositories/migration/tests and
the implementation merged by PR #379. #302 had no comments when inspected.

PR #379 merged into develop at `978fed34d8bedf2cf5cf6d2c7d04e557cd670004`.
Its PR HEAD was `dd2ec4957748af40c6dc9708158c5c03082aea26`.
The remote [boundary-check run](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39212568969)
and [python-tests run](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39212568964)
both completed successfully; the latter's full pytest and strict MySQL gate
steps also succeeded. These results belong to REC-1(a), not this uncommitted diff.
The current remote develop commit was verified through the GitHub connector;
local HEAD and origin/develop both matched the merge SHA, with an empty index
and clean worktree before editing. No branch/worktree was created.

## Filename and locator

`register_local_source(path, *, original_filename=None, case_id=None)` continues
to return only the existing SourceAsset/MediaStream contracts. The optional
filename is private LocalSource registration metadata, excluded from its repr.
It is persisted in the existing local_source JSON payload and restored by a new
repository/service. Time observation uses that original text rather than the
canonical storage basename. No filename field is added to a canonical model.

HTTP §5.2 requires passing the user's filename and forbids using it as storage
path. Current SoT defines no trimming, Unicode normalization, basename extraction,
extension allowlist or filename length limit. None is introduced here. Strings
are preserved exactly, including whitespace, combining Unicode, separators,
empty text and NUL. They are inert metadata, not validated filesystem names.
Non-string values and non-UTF-8-encodable Python surrogate strings fail with a
fixed ValueError before dependency access; input text is not echoed. This adds
no HTTP status/code for malformed filenames. Any future rejection/normalization
policy needs its authority checked before implementation.

The canonical locator remains a validated relative path beneath storage_root.
Original filename never selects, renames, opens or publishes a file. Existing
absolute/traversal/different-root/symlink/junction checks remain in place.
Old JSON without original_filename restores None without rewriting stored rows;
legacy path-only registration keeps the existing basename observation behavior.
No original upload filename is fabricated for old data.

## Failure taxonomy

HTTP §5.2 already maps UNSUPPORTED_MEDIA to 422 http.source_rejected and
TEMPORARY_FAILURE to 503 http.dependency_unavailable. The route is not implemented
here. Unexpected errors and COMMIT uncertainty retain the existing boundary.

Ffprobe now requests structured error codes with `-show_error`. A stable input
with AVERROR_INVALIDDATA, or valid successful metadata without a supported video
stream, is UNSUPPORTED_MEDIA. The numeric tag follows FFmpeg's
[libavutil error definition](https://www.ffmpeg.org/doxygen/trunk/group__lavu__error.html).
Missing tool, access/read failure, timeout, changed input, unknown nonzero result,
invalid JSON and malformed tool metadata remain TEMPORARY_FAILURE. Stderr,
exception wording, filename extension and part Content-Type do not classify
input. Read/hash stability is checked before trusting a deterministic rejection.
Messages never include subprocess stdout/stderr/argv or the local path.

## Transaction, linkage and ownership

Registration joins the supplied Connection. Optional case linkage reuses the
existing Recording-owned case_asset row representation. SourceAsset, streams,
indices, locator, filename and that link are written in one InnoDB statement, so
even a caller that catches a statement error and commits cannot retain a partial
registration. Repository/service does not commit, rollback, retry or own the
Connection. Same file registered again still gets a new logical asset; there is
no dedupe or upload idempotency promise. Concurrent registrations remain distinct.
Lost COMMIT ACK is unknown: a caller error can coexist with durable registration.

No new Case interface/callback, reverse dependency, Case schema or obligation is
needed. Case's existing `record_source_registered(case_id, source_asset, *,
media_streams, store)` remains the authority for INTAKE acceptance and manifest
counts. Tests compose that existing function on the same Connection, locking
the Case first. Case rejection rolls back registration and Recording linkage.
Recording alone does not verify Case existence/stage or change Case counts.
Actual HTTP composition stays RT-11(a). No Case or Runtime product code changes.
No unresolved Owner decision blocks this Recording-only slice; final public
ownership lookup and any change to Case semantics still require their existing
Owner boundaries.

## Schema and verification

No schema change or revision is necessary: the private JSON payload already
supports additive metadata. recording_0001 and all frozen migrations stay intact.
Existing fresh/previous upgrade, rerun, failure-safety, rejected downgrade and
old-row preservation tests remain mandatory. FrameRef bytes stay in MySQL;
DerivedAsset metadata/ref durability and original storage semantics are unchanged.

New registration_input and registration_taxonomy families extend both independent
acceptance inventory and strict checker inventory. Existing required evidence,
checker functions, JSON/JUnit checks, skip/xfail rejection, workflow 30-minute
timeout and nested MySQL 900-second timeout are preserved. Parameter, metadata
and family omission mutations include the new obligations automatically.

Execution evidence is isolated in ignored `.codex-scratch/rec1b-20261019/`.
Pre-existing scratch/RAW/archive/reports and unrelated untracked files are outside
the delivery. Final results and independent review are recorded as follow-up
entries in Runtime Implementation Log; historical records are preserved.

Excluded: final sources HTTP route, final ref-to-case ownership API, DerivedAsset
bytes/Content-Type, public FrameRef image format, retention/purge/object storage,
orphan cleanup, RT-10 Worker and RT-11 HTTP composition. No staging, commit, push
or PR creation is performed by this task.

## Final verification (2026-10-19)

These are distinct, overlapping executions. Counts must not be added as unique
test coverage. Raw failures and incomplete attempts remain preserved.

| Execution | Observed result |
| --- | --- |
| Initial unit RED | 21 FAIL / 1 PASS; wrong feature behavior, separate from initial tmp access errors |
| Initial actual MySQL RED | 10 FAIL across two selections |
| Additional input validation RED | surrogate 1 FAIL; case-id input 4 FAIL |
| Fresh review reproduction | malformed duration without video: 2 FAIL, permanent regression 2 FAIL / 9 PASS, then GREEN |
| Final Recording suite | 616 PASS / 15 explicit external-media/placement opt-in SKIP; includes 43 passing MySQL Recording tests |
| Entire required actual MySQL inventory | 743 PASS / 2,229 passing phases / skip 0 / xfail 0; JUnit 884.009 seconds |
| Original mandatory integration function | 1 PASS in 1,092.42 seconds; wrapper 1,096.5 seconds, source drift 0 |
| Strict JSON/JUnit CLI | PASS; independently repeated by fresh reviewer |
| Original parameter mutations | 4,814 rejected, including Recording 559 layer variants |
| Recording metadata/family omissions | 172 metadata plus 11 complete-family omissions rejected |
| Gate unit regression | 5,261 PASS |
| API process-safety initial final selection | 44 PASS / 1 FAIL, setup_import_watchdog_5s before GO trigger |
| Same failed API node, isolated | 1 PASS with the original watchdogs |
| Same full API process-safety file, idle recheck | 45 PASS / one existing Starlette deprecation warning |
| Final boundary / Contract fixture / static | boundary 0; structure 62 / JSON 26 / semantic 104 PASS; diff-check PASS |

The independent reviewer found one P2 classification-order defect: malformed
format duration could be masked by no-video rejection. Two permanent RED cases
preceded moving duration validation ahead of that rejection. The reviewer then
repeated its original reproduction as 2 PASS. No timeout or failure-kind policy
was relaxed for this repair. All subsequent mandatory and focused source hashes
match the final product/test code.

The first whole pytest attempt ended at 76% with exit 124 and seven F progress
markers, without final JSON/JUnit or completed inner evidence. Its configured
guard was 1,800 seconds, but observed wrapper elapsed time was 5,715.203 seconds
across the interruption; the cause is unconfirmed. Its source drift was only
probe.py and the permanent review tests. Collection-order reconstruction yielded
seven failure candidates, not authoritative tracebacks. Those candidate scopes
were subsequently exercised by the complete original mandatory test, gate unit
suite and API process-safety reruns. This does not convert that partial whole
attempt into PASS or establish the exact original failures' causes.

Fresh independent reviewer `/root/rec1b_independent_review` judged a duplicate
whole pytest replay unnecessary for this bounded Recording/input/inventory
change: final complete Recording tests, real cross-module MySQL/migrations,
strict report plus exact mutation coverage, gate units and unchanged-deadline
API checks cover the changed behavior. Untouched modules' complete unit suites
were not replayed. **There is no completed final whole-pytest PASS.** The initial
API watchdog failure also remains a failed attempt despite later passes; a
machine/load explanation is an inference, not a confirmed diagnosis.

The original strict checker functions, old required inventory, frozen migrations,
workflow 30-minute and nested MySQL 900-second limits are unchanged. The 884.009s
JUnit duration leaves little room beneath the nested limit; interpreter startup
also consumes subprocess budget, so JUnit subtraction is not an exact wall-time
margin. This is a performance risk, not permission to increase the timeout.
The previous REC-1(a) evidence manifest's 150 files and the full original
Implementation Log byte prefix were rehashed and preserved.

Current-diff remote CI remains pending because no commit/push/PR was created.
REC-1(a)'s remote PASS does not replace it. No complete whole-suite-green or merge
readiness claim is made. The remaining 15 Recording skips require user-supplied
external media/placements and are not MySQL skips. No new Owner judgment is
required inside the implemented Recording-only boundary; future normalization
policy, final ownership/media API and actual RT-11 composition retain their
existing authority and scope.

## Delivery files

| Purpose | Files |
| --- | --- |
| Registration and observation | `src/daesingo/recording/probe.py`, `service.py`, `time_sources.py` |
| Caller-Connection persistence and in-memory parity | `src/daesingo/recording/repository.py`, `mysql_repository.py` |
| Tests | `tests/recording/test_registration_input.py`, `test_local_source_registration.py`, `test_recording_repository_mysql.py` |
| Independent inventory and checker inventory | `tests/recording_acceptance.py`, `scripts/check_mysql_test_report.py` |
| Documentation and append-only history | `src/daesingo/recording/README.md`, `docs/modules/recording/local-source-registration.md`, `docs/modules/recording/rec1b-registration-input.md`, `docs/runtime/runtime-implementation-log.md` |

All `.codex-scratch/**` helpers, raw reports, media and pytest temporary resources
are excluded from a future PR, including this task's evidence. Existing RAW,
archive and unrelated untracked files are not changed or deleted. Final resource
audit, manifest and reviewer verdict are appended to Implementation Log.

Resource checks found only system schemas plus the owned base schema, only
default MySQL accounts, no remaining test clients or transactions. The owned
server stopped through the helper and its datadir was removed. The interrupted
server's known datadir was already absent; its original logs could not be read
and are not claimed preserved. Two resumed-server logs were copied before stop.
Final Windows/WSL checks found no owned Python/MySQL process or listener on the
two recorded server ports. Four owned junction endpoints were removed without
deleting ordinary files. The prior REC-1(a) 150 evidence hashes remain unchanged.
