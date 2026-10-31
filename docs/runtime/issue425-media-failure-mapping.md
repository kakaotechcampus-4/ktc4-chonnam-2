# #425 analysis input failure mapping — Implementation Notes

Status: IN_PROGRESS · Refs #425 · Related #297. Request specification, 2026-10-31 KST.

## Plan and constraints

Implement inline using systematic debugging and TDD, then a fresh read-only GPT-6.1
Sol / High review. This request supplies the implementation and execution scope;
no additional plan approval, worktree, branch switch, commit or external write.

- [x] Reproduce preparation UNSUPPORTED_MEDIA as RUNTIME_HANDLER_ERROR (RED).
- [x] Register the literal taxonomy, isolate the single preparation invocation,
  and verify FAILED / RECORDING_UNSUPPORTED_MEDIA / produced=[] (GREEN).
- [x] Exercise production registry composition, excluded boundaries, size limit,
  success, cancellation and cleanup with synthetic input/provider doubles.
- [x] Run a dedicated MySQL subset for T1/T2, replay, receipts and Case projection.
- [x] Run Runtime quality, boundaries, Contract fixtures and diff checks.
- [x] Review, document evidence, append the Runtime log and clean owned resources.

Starting branch: `codex/issue425-media-failure-mapping`; HEAD:
`d1f57b343c509ef2d5ea42aa119487d79c9adc43`. Working tree and index were clean.

## Source decisions and scope

Read [#425](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/425),
including [Recording Owner's decision](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/425#issuecomment-6493673627).
That decision supports mixed time bases and preserves typed rejection for inputs
that cannot be represented exactly. It does **not** approve the new terminal
literal; `RECORDING_UNSUPPORTED_MEDIA` is specified by this implementation request.
[PR #499](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/499) was verified
merged, with merge commit equal to the starting HEAD. Its common-time-axis
implementation and strict validation are unchanged.

Review focus: only actual preparation errors; context lifecycle and transaction
errors must remain Runtime-owned; cancellation and UsageError must propagate;
no exception details in terminal; Case failure must not become success/no-result.

## Before and after; exact boundary

Previously `search_handlers` caught only the size-limit code on service factory
entry. A preparation `UNSUPPORTED_MEDIA` reached `KindRegistry.dispatch` and became
`FAILED / RUNTIME_HANDLER_ERROR`. There was no produced receipt for that execution.

Now `ProductionMediaFactory` catches `RecordingCapabilityError` around **only**
`recording.prepare_analysis_source_from_resolution(resolution, profile_ref)`.
Only literal code `UNSUPPORTED_MEDIA` emits the internal `_UnsupportedAnalysisInput`
signal. Recording's context exits before that signal reaches the handler; a
cleanup failure replaces it and remains a Runtime error. The handler catches the
signal only at entry, checkpoints cancellation, and returns
`FAILED / RECORDING_UNSUPPORTED_MEDIA` with `objects=()` and `produced=()` (stored
as `[]`). No Search AnalysisRun is created by the rejected execution and no
produced receipt is fabricated.

| Boundary | Behavior |
| --- | --- |
| COARSE_SEARCH / FINE_VERIFY production preparation | Both use the same factory and public Recording preparation call; new mapping applies |
| HINT_EXTRACT | Separate text extractor; unchanged, no media factory entry |
| Input read / factory construction / Recording context entry / metadata ownership / resolve_span / observe_time_sources / Search configuration | Outside the new catch; even the same raw UNSUPPORTED_MEDIA remains Runtime-owned |
| DB read / publish / transaction / commit inside prepare | Repository propagates SQLAlchemy and transaction exceptions, not media capability errors; new catch does not match them |
| Unknown Recording codes | Reraised to existing Runtime boundary |
| Checkpoints / cancellation / UsageError | No new conversion; cancellation checkpoint after cleanup wins over a pending preparation failure |
| Search/provider, resolver, body, context exit/cleanup | No new conversion; existing Search/public helper or Runtime boundary |
| Size-limit mapping | Existing literal entry mapping retained, including its original scope; not generalized |
| IncidentClip / export | Existing public wrappers and confirmed mappings unchanged |

The prepare method also performs repository reads and durable publication. The
audit covered `get_timeline`, local source/index reads, and `_publish_prepared` →
`add_prepared_media`; those MySQL operations raise DB/transaction errors. Tests
inject faults **while inside the real prepare call**, independently at read,
materialization and publication, and assert that injection was reached. No new
global converter, Recording public API, schema, migration, receipt, retry,
time-axis arithmetic or strict validation was introduced.

## Direct author verification

Python from `.venv/Scripts/python.exe`; offline Windows FFmpeg/ffprobe from PATH
(`ffmpeg-9.0.1-essentials_build`). Only generated one-second video and synthetic
Search results/errors were used. Dedicated local MySQL 8.4 container used tmpfs,
a random localhost port and random task-only credentials. Harness created and
dropped per-test schemas; no shared DB was used.

All commands used `-o cache_dir=.codex-scratch/issue425-mapping/cache` after RED,
and task-specific `--basetemp` under that ignored directory. Raw logs and MySQL
report are ignored scratch only.

| Check / command scope | Observed result |
| --- | --- |
| RED: `pytest tests/worker/test_unsupported_media_mapping.py -q` before product changes | 2 failed, both expected `RECORDING_UNSUPPORTED_MEDIA`, actual `RUNTIME_HANDLER_ERROR`; COARSE and FINE; two existing cache permission warnings |
| First GREEN + existing size-limit mapping tests | 9 passed |
| New boundary matrix alone, before extra injection-reached assertions | 48 passed; final strengthened/formatted matrix repeated: 48 passed / 30.58 s |
| Focused regression command below, including strengthened nested read/publish assertions | 176 passed, no skip, 109.15 s |
| Dedicated `pytest tests/worker/test_unsupported_media_mysql.py -q` with `DAESINGO_REQUIRE_MYSQL=1` and `--mysql-report` | 12 passed, no skip/xfail, 30.96 s; after fixture alias/format cleanup: 12 passed / 44.19 s; report: MySQL 8.4.13, 12 selected/passed, zero collection errors |
| `python scripts/check_runtime_quality.py` | Ruff PASS; mypy linux and win32 PASS (87 files each) |
| `python scripts/check_boundaries.py` | PASS with UTF-8 output; initial CP949 console encoding error was rerun with `PYTHONIOENCODING=utf-8` |
| `python scripts/check_contract_fixtures.py` | 62 structure / 26 JSON / 104 semantic checks PASS |
| Ruff on both new test files | PASS after fixture aliases and formatting |
| `git diff --check` | PASS at author verification |

Focused regression command (not full pytest):

```text
python -m pytest tests/worker/test_unsupported_media_mapping.py
  tests/worker/test_analysis_source_limit_mapping.py
  tests/worker/test_search_handlers.py tests/worker/test_search_failure_boundary.py
  tests/worker/test_production_media.py tests/worker/test_export_handlers.py
  tests/recording/test_mixed_timebase.py -q
```

The new matrix covers the exact terminal, no Search construction/capability after
rejection, raw same-code failures outside preparation, unknown code, SQLAlchemy,
BeforeCommitFailure, CommitOutcomeUnknown, TransactionBoundaryError,
TransactionRetryExhausted (known/unknown outcome), UsagePersistenceError,
CancellationRequested, and cancellation requested during rejection or cleanup.
Existing success, Search/provider and size-limit cases remain green; the mixed
time-base tests also exercise IncidentClip wrappers and cleanup without modifying
#499 code. An initial test fixture patched the wrong repository class; it was
corrected and strengthened with explicit in-prepare injection assertions.

MySQL's 12 cases are COARSE/FINE × normal, T1 rollback, T1 lost COMMIT response,
T2 rollback, T2 lost COMMIT response, and T1→T2 delivery gap. They use actual
`compose_search_registry` with automatic `ProductionMediaFactory`, `SearchInputs`,
Recording/MySQL repository, MediaRoot, Worker terminal persistence, and
`StoredCaseReflector`. Fine's preceding Coarse succeeds with a synthetic Search
candidate. Failed preparation invokes media exactly once and no subsequent
Search capability. T1/T2 transaction replay, redelivery and idle Worker restart
add no media/provider calls. Tests check durable status/kind/empty produced,
no produced object, processed execution, receipt unchanged on replay, no duplicate
job, no RUNNING job, pool checkout count zero and no Recording temp residue.
These fixtures issue no HINT job; the absence of a video Search call is not
confused with any earlier text/HINT provider call.

## Case consumption and unposted Owner proposal

`ExecutionOutcome.failure_kind` accepts a string. `CaseReflector` passes the new
literal through unchanged. COARSE's FAILED branch records failure without reading
produced payload; FINE's FAILED branch settles the observation and does not follow
the successful Fine/clip path. T2, receipt and redelivery code is unchanged.

| Actual existing projection, verified through stored CaseView | Remaining policy |
| --- | --- |
| COARSE: stage SEARCHING, `coarse_search=FAILED`, no running job or fabricated candidate/no-result success | General `search.candidate_search_failed` notice and `RETRY_SEARCH` remain |
| FINE: selected candidate retained, observation outcome FAILED, no downstream job or running job | General blocking `search.visual_verify_failed`, actions=[]; existing Case view omits unstarted downstream steps and exposes no separate Fine failure progress row |

The Fine projection assertions were corrected to match the existing three DONE
steps (file_intake/coarse_search/candidate_review), **not** a new progress schema.
Failure is exposed by the existing blocking notice, not treated as NOT_OBSERVED
or successful evidence. No new Case/Web code, copy, action or retry policy was added.

**Draft comment for Case Owner — not posted:**

> Refs #425 / Related #297. Runtime now distinguishes Recording analysis input
> rejection as FAILED / RECORDING_UNSUPPORTED_MEDIA / produced=[] for Coarse and
> Fine, with no raw exception, filename, path, locator or video content. Existing
> T2/receipt semantics are preserved. Current Coarse still shows the general
> candidate-search failure and RETRY_SEARCH; current Fine still shows the general
> blocking visual verification failure with no notice actions. Please decide a
> dedicated safe notice and feasible exit for this new kind. Proposed copy for
> review: “이 영상은 현재 분석용으로 준비할 수 없습니다. 다른 입력으로 다시 시도해 주세요.”
> This does not claim source corruption or permanent lack of mixed-time-base
> support. Same-input retry may repeat deterministic rejection; proposal: avoid
> presenting it as the sole recovery path for this kind, while leaving transient
> Search failures' retry policy intact. Confirm which existing input replacement,
> re-registration or return-to-input flow can actually be offered, and whether it
> can preserve already produced candidates/results. If replacement requires a new
> Case or a separate command, decide that behavior explicitly before adding UI
> actions. Fine should preserve the selected candidate and offer the feasible
> input/candidate exit that Case/Web agree; no new action enum is proposed here.
> Acceptance: FAILED stays visible, no infinite RUNNING or no-candidate success,
> no raw media details, no duplicate execution on receipt replay, and a tested
> user exit after both Coarse and Fine rejection. This is a policy proposal for
> your review, not an approved or implemented notice/retry change.

## Complete change file inventory

| File | Purpose |
| --- | --- |
| `src/daesingo/worker/production_media.py` | Isolate and signal unsupported public preparation only |
| `src/daesingo/worker/search_handlers.py` | Convert the internal entry signal to the specified terminal |
| `docs/modules/recording/decisions/failure-taxonomy.md` | Register the literal before use with request authority and exclusions |
| `tests/worker/test_unsupported_media_mapping.py` | RED/GREEN, production bridge and excluded-boundary matrix |
| `tests/worker/test_unsupported_media_mysql.py` | Real production composition, terminal, T1/T2/replay/receipt, CaseView/resource checks |
| `docs/runtime/issue425-media-failure-mapping.md` | This mapping's plan, evidence, scope and unposted proposal |
| `docs/runtime/runtime-implementation-log.md` | Append-only mapping record; prior history preserved |

## Review, cleanup and unverified scope

Fresh **GPT-6.1 Sol / High**, without implementation conversation inheritance,
reviewed the seven candidate files and related Recording/repository/lifecycle,
registry, terminal, Case projection and export boundaries. **No actionable
findings; no product correction or same-reviewer recheck was needed.**

| Reviewer verification | Evidence scope |
| --- | --- |
| Direct: new mapping, existing size-limit, Search failure boundary | 104 passed / 33.14 s; direct `git diff --check` PASS |
| Direct first attempt | Reviewer parent temp directory did not exist: 44 fixture setup errors and 60 passes; created the parent and reran successfully; not a product failure |
| Reviewed author evidence, not reviewer execution | RED, 176-test regression, final 48-test matrix, MySQL 12/report, quality/boundary/fixtures logs and test assertions |
| Not run by reviewer | MySQL, original Issue media, full remote CI |

Reviewer changed no source/docs/index/DB/container and did not read credentials.
Direct reviewer execution used only a separate ignored scratch directory.

The dedicated DB had zero
remaining harness schemas before removal; its task-owned container and tmpfs were
removed after checking the ownership label. Shared images/cache and prior task
scratch were preserved. This task's generated pytest media/temp/cache directories,
credential file and temporary helper scripts were removed; small raw evidence
logs/report remain in ignored `.codex-scratch/issue425-mapping/` only. Reviewer
generated media/temp/cache are also removed after review; review results are
recorded above. Runtime Log's complete original HEAD byte prefix is verified preserved.
Final branch and HEAD match the start. Exactly seven candidate files remain
modified/untracked, all unstaged; index is empty and `git diff --check` passes.
The original #425 AVI nine-file / MP4 two-file reproduction sets have **not** been
retested. No actual provider, user originals, AWS, EC2 or deployment was used.
Full local pytest, mandatory MySQL, full mutation inventory and Docker OCR
acceptance were deliberately not run. A later push must satisfy the full remote
CI gates; #499's earlier CI does not validate this new uncommitted diff.

This implements the independent Runtime/Recording mapping only. #425 remains
IN_PROGRESS; original-set validation and the user guidance/exit policy remain
separate outstanding work. No claim of #425 completion or resolved user guidance.
