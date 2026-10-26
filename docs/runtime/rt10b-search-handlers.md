# RT-10(b) Search handlers — implementation checkpoint

**IN_PROGRESS · Refs #297 (RT-10(b)) · 2026-10-25**

This is an uncommitted implementation checkpoint before independent review. It is
not full RT-10 acceptance or a merge recommendation. No reviewer/subagent,
staging, commit, push, PR, branch switch or worktree creation was performed.

## Verified baseline and agreements

- Current branch: `codex/rt10b-handler-registry`. HEAD and a fresh read-only
  `git ls-remote origin refs/heads/develop` both resolve to
  `ea580ac6e1f0a035bf0938fcb8a097394f4b20d1` (merged PR #329).
- [#303 Runtime acceptance](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/303#issuecomment-6380230633):
  pass the execution's `UsageSink` through public call arguments; Search performs
  begin/finish per HTTP attempt, propagates `UsageError` without retry, and never
  finalizes. Worker finalizes after T1. #303 is still **open**; diagnostic work
  outside #329 remains separate. Its open status alone does not block these calls.
- [#297 Case input/result agreement](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6381933011)
  and [Runtime response](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6384372018):
  use `CaseStore.observation_input`; Fine returns `analysis_run` and
  `visual_evidence`; IncidentClip is a separate `INCIDENT_CLIP_BUILD` execution.
  Worker must not choose downstream jobs or build a clip inside Fine.
- PR #385 merge SHA is `c491a95b8726377c2eca2ac3dad6bcc6ce416670`.
  GitHub Actions API directly confirms its head `1dd9bd7f...` has successful
  [boundary run 39552040227](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39552040227)
  and [python-tests run 39552040245](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39552040245).
- The same API confirms #329 head `91d2778c...` has successful
  [boundary run 40109830290](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/40109830290)
  and [python-tests run 40109830291](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/40109830291).
  These are predecessor/head CI results, not remote CI for this uncommitted diff.

## Selected slice and behavior

The Search kind group implements `HINT_EXTRACT`, `COARSE_SEARCH`, and
`FINE_VERIFY` adapters. Inputs come from public CaseStore reads and ProducedReader
in a short caller transaction; external work starts after releasing it. Fine uses
the job's fixed generation/candidate/interval, not the currently selected candidate.
The four-coordinate Case interval is compared without treating the candidate's
`representative_ms` as part of that input. Fine resolves exactly one source and
passes the scope's explicit latency budget so a fresh SearchService need not have
the earlier Coarse process's cache.

Each public invocation receives `context.usage_sink`; no fallback sink or handler
finalize is added. Checkpoints surround input reads, resource acquisition, resolver
and capability boundaries. The supplied media service context exits on cancellation
and exception. A future Recording factory must create/close RecordingService per
execution under RD-09a; this slice does not instantiate one or prove its lifecycle.

Each Search result is one opaque produced payload. Coarse/Fine use the actual
`analysis_run` ref for both the object and terminal receipt. This allows the
existing ProducedReader to return one wrapper dictionary and post-T1 reconciliation
to link usage to that Run. Intent excludes SearchLedger usage from its payload;
authoritative Runtime usage remains in the existing ledger. No produced repository,
migration, T1, receipt, ownership or recovery implementation was changed.

Stock Worker wiring registers only `HINT_EXTRACT`. Coarse/Fine require an explicit
execution resource `service_factory`; they remain `RUNTIME_UNREGISTERED_KIND` when
it is absent. The stock entrypoint still lacks full Case T2/stored adapter wiring.
This is a partial root, not a working production Search pipeline.

Excluded: `INCIDENT_CLIP_BUILD`, `PLATE_READ`, `OVERLAY_TIME_READ`,
`REPORT_VIDEO_EXPORT` and `PLATE_IMAGE_EXPORT`.
No unsupported capability is represented by a successful stub. Tests compare the
Search subset against current `JOB_KINDS` and check unregistered default behavior.

## Blocking discovery — implementation stopped

JobExecution Contract §6 requires a module-prefixed `failure_kind`, with names
registered in the module's failure taxonomy. Tech Spec §6.2 also requires provider
account/authentication failures to be distinguishable from general INFRA.

The current draft handler forwards `IntentHintResult.failure_kind` (for example
`PROVIDER_ERROR` or `CONFIG_ERROR`) and the first failed AnalysisRun issue's kind
(for example `INFRA`). These are not a documented JobExecution mapping. The
Search taxonomy document is still marked draft. Coarse collapses provider errors
to `INFRA / PROVIDER_CALL_FAILED`; Fine may raise an exception instead of returning
a failed Run. AnalysisRun validation also permits FAILED with no issues, while the
draft handler indexes the first issue. Successful tests do **not** resolve these
failure-path gaps. The handler must not be merged or enabled in production as-is.

No new taxonomy, arbitrary `SEARCH_` concatenation, parsing of exception text,
Search internal import, or alternate terminal policy was introduced to resolve
this discovery. Product implementation stopped at this boundary; the current
draft and its limitations are retained for inspection.

Required Owner judgment:

1. Search Owner: define/document JobExecution failure names and mapping from intent
   status and AnalysisRun issues, including issue priority/empty FAILED runs and
   account/authentication distinction. Confirm how Fine module failures are exposed.
2. Runtime/Contract Owner: confirm that mapping and the terminal/produced behavior
   for a Fine exception versus a returned failed Run. Preserve actual failed Run
   refs and post-T1 usage reconciliation; do not invent a successful result.
3. Recording/Case composition dependencies remain: durable RecordingFacts, public
   source restoration/configuration, API/Worker stored adapter injection, then Case's
   automatic Coarse→Fine dispatch. No private schema shortcut was added.

## TDD and direct evidence

Evidence lives in PR-excluded `.codex-scratch/rt10b-20261025/`. Every attempt has
its own artifacts; later passes do not reclassify earlier failures.

| Direct execution | Result and scope |
| --- | --- |
| Initial handler RED | 12 failures before `search_handlers` existed (`red.xml`) |
| Input/handler GREEN | 23 passed (`green4.xml`); earlier fixture-ref, strict JSON and append-only test-fixture failures retained |
| Composition RED→GREEN | 2 failed (missing composition/intent config) → 50 passed (`composition-green.xml`) |
| Public capabilities + offline SDK transport | 9 passed (`capability.xml`): all three kinds × normal/begin failure/finish failure; HTTP counts, sink identity, no retry and null KRW cost |
| Receipt regression RED→GREEN | 2 failed (separate Run/object refs) → 33 passed (`receipt-green.xml`) |
| Fixed Case interval RED→GREEN | 1 failed (full span comparison) → 33 passed (`span-green.xml`) |
| Final related offline regression | **1,235 passed, 6 skipped, 612 deselected**, 3 existing SDK serializer warnings, 59.27s (`regression-final.xml`) |
| New real MySQL 8.4.7 Search chain | **3 passed**, 9 successful phases, skip/xfail 0 (`mysql-search-green.json/.xml`); normal/deadlock rollback/actual COMMIT response loss |
| Existing real MySQL regression | **71 passed**, 213 successful phases, skip/xfail 0 (`mysql-regression.json/.xml`): produced store, Worker usage/reconciliation, cancel checkpoint, Case reflection |
| Gate negative controls | 15 passed, 8,103 deselected (`gate.xml`); bypass/missing JUnit/metadata mutation checks |
| Boundary / Contract fixtures | violations 0; 62 structure / 26 JSON / 104 semantic fixture checks passed |
| Diff and protected paths | `git diff --check` passed; checker, workflow, Contract fixtures, jobs core, Search/Case/Recording/Readout files unchanged against HEAD (checkout newline normalization only) |

The final offline command selected `tests/search tests/worker tests/case
tests/common/jobs tests/common/usage -m 'not mysql'`. Four skips are optional typer
AIhub tests and two are unavailable external Case video cases; no skip/xfail policy
was changed. The new MySQL test uses actual Case commands, Runtime Worker,
execution-scoped durable sinks, real Search/Gemini adapter and offline provider
transport. It checks three distinct execution usage records, T1 replay without
repeating paid calls, produced payloads, Case T2 and sanitized logs. Fine is
NOT_OBSERVED, so no Recording fact read is permitted by that test. Its injected
stored adapter is test composition, not completed stock composition.

Preserved unsuccessful runs include Windows sandbox subprocess permission failures
(`regression2.xml`: 32 failed / 1,203 passed / 6 skipped), Linux missing media/CLI
dependencies (`regression-linux.xml`: 12 failed / 1,199 passed / 30 skipped),
Windows MySQL preflight setup errors, and successive new MySQL integration failures
(media duration fixture, receipt refs, Case interval shape, missing stored adapter).
The final Windows related regression was explicitly run with process permission.
The no-test command typo and missing Python dependency attempts are not passes.
See per-run counts in scratch `audit.json`; no counts are summed into a full suite.

Fresh MySQL reports have matching selection, unique nodes, complete successful
setup/call/teardown phases and JUnit. Removing one actual JUnit testcase was
rejected for each report. The unchanged full inventory validator **rejects both
subsets** with `required MySQL role/scenario missing`. This is an expected refusal,
not strict full-gate PASS. No inventory/checker or nested gate bypass was added.

## Unexecuted checks and resources

Whole pytest, whole MySQL/nested 900s wrapper, the entire 8,118-test gate unit inventory, standalone
Recording/Readout suites, live paid provider, full API/Worker cross-process E2E and
remote CI for this diff were not run. The changed surface is isolated to Search
adapters/config/input wiring; related offline and focused actual MySQL tests cover
its persistence boundary. Repeating the whole suite/required DB inventory before
resolving the failure Contract and production composition blockers would not prove
those missing semantics and would duplicate expensive predecessor coverage. Old
CI is evidence only, not a substitute for new acceptance. Workflow 30 minutes and
nested 900 seconds remain unchanged (scratch runner itself uses 880 seconds).

Owned MySQL audit (`server-final.json`) records only system schemas plus the test
base schema, only default accounts, no non-audit client, transactions 0 and data
locks 0. The helper exited, the exact `/dev/shm/rt10b-*` datadir was removed, and
port connect returned refusal. Shared tools/previous evidence were retained.

Independent review may inspect this draft after the user's explicit request; no
reviewer was called. Failure taxonomy remains a merge blocker and may require
Owner clarification before a complete implementation review. Scratch RAW,
JSON/JUnit, runners, cache/temp trees, DB material and the local execution plan
are PR-excluded. No staging/index changes were made.

## 2026-10-26 — resumed confirmed boundaries (append-only follow-up)

**IN_PROGRESS · Refs #297 (RT-10(b)); HINT authentication/budget acceptance pending.**

The user authorized continuing confirmed Coarse/Fine/HINT work without waiting for
the remaining Search Owner response. The original 15 modified/untracked files were
backed up byte-for-byte with hashes and a tracked patch in excluded
`.codex-scratch/rt10b-20261026/pre-update/`. No paths overlapped incoming develop
changes. The current branch fast-forwarded from `ea580ac6...` to latest
`4a69a292f55ed48b9f679c1016087d3acd11a994` (including #327, #358 and #401).
All 15 original file hashes matched immediately after fast-forward; index stayed
empty. The initial sandbox Git ref write was denied, then the authorized same
fast-forward succeeded with filesystem permission. No commit/stash/branch/worktree
was created.

### Confirmed mapping and remaining dependency

[#297 Runtime acceptance](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6387601291)
and [Search Owner answer](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6392679689)
resolve the earlier generic taxonomy question: consume the three public helper
functions, do not duplicate their rules. FAILED runs preserve their actual Run
receipt/payload; PARTIAL remains execution success. Case-command §11 already says
failed intent becomes JobExecution FAILED while Case continues with empty hints;
this is not a new Runtime policy.

**PR #403 remains open/unmerged**, at `00549ff23d27ac327a9305cb22b4661b68be403f`.
Thus its public helpers are not installed in latest develop. `SearchFailures` is
only a structural port for the confirmed public function names. Default discovery
uses `daesingo.search`; when any required helper is absent the Search kinds remain
unregistered, with no input read/provider invocation. Tests can inject a port
double, and a separate excluded snapshot verifies the exact public implementation.
There is no copied taxonomy, private import or unmerged Search code in this branch.
After the real helpers are available, default registration is HINT only; media
factory injection remains required for Coarse/Fine. This supersedes the earlier
checkpoint's unsafe raw-failure forwarding, not its historical test results.

The error-mapping try block wraps only a public Search invocation. Input loading,
transaction work, factory enter/exit, checkpoints, payload serialization and T1
remain outside it. `UsageError` and cooperative cancellation propagate unchanged.
Result helpers receive only the Search result or AnalysisRun. Mapping does not
finalize usage, create a Run on exception, dispatch downstream jobs, or change T1.

### Explicit pending acceptance

[#403 HINT follow-up](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/403#issuecomment-6398537018)
still has no subsequent Owner answer at the final read. Actual SDK + MockTransport
and an injected clock in the #403 snapshot observe:

| HINT response | Budget left | Budget spent |
| --- | --- | --- |
| 401 / 403 / 404 | public helper returns SEARCH_PROVIDER_CONFIG | returns SEARCH_DEADLINE_EXCEEDED |
| 500 | SEARCH_PROVIDER_ERROR | SEARCH_DEADLINE_EXCEEDED |

These are **pending observations**, not accepted semantic assertions or success
criteria. Runtime passes the public result through and does not inspect causes,
status codes or elapsed budgets to override it. `hint-pending.json` retains eight
separate observations, one HTTP call each. No test freezes the spent-auth behavior
as correct. Owner correction and a later acceptance run are still required.

### New direct verification (separate from all 2026-10-25 evidence)

| Execution | Result |
| --- | --- |
| Boundary TDD | **23 RED → 23 GREEN** (`red-boundary.xml`, `green-boundary.xml`); initial test-import mistake retained separately in `red.xml` |
| Focused current-workspace tests | **64 PASS** (`focused.xml`) |
| Related current-workspace regression | **2,000 PASS / 21 SKIP / 713 deselected**, 3 SDK serialization warnings, 202.43s (`regression.xml`) |
| Fresh actual MySQL 8.4.7 | **74 PASS / 222 successful phases / skip=xfail=0**, 98.17s (`mysql-final.json/.xml`); three new real Search chains plus produced/usage/reconciliation/cancel/Case regressions |
| Gate negative controls | **15 PASS / 8,103 deselected** (`gate.xml`) |
| Dependency snapshot | **95 PASS**, 7.05s (`owner-final.xml`), from latest develop plus exact #403 Search source and current Worker files |
| Snapshot old-handler negative control | **16 FAIL / 4 PASS** (`owner-red.xml`); restoring the pre-resumption handler exposes raw failure mapping/missing-issue/Fine exception defects. Snapshot handler was restored and the 95-test run above rerun afterward |
| Boundary / fixture / diff | violations 0; Contract 62/26/104; diff check PASS |

The 95-test dependency run includes 20 checks of real public helper/default registry
projection and actual SDK failed capabilities, including Coarse failed Run usage
refs and Fine exception without a fabricated Run. It is neither develop integration
nor an acceptance result for pending HINT spent-auth behavior. Snapshot-source
hashes/revisions are recorded separately. Current-workspace happy-path tests inject
a success-only policy double while #403 is absent; those results do not claim real
helper integration. No counts from different executions are combined.

The related regression selected Search/Worker/Case/jobs/usage/Recording/Readout
with `-m 'not mysql'`. Existing skips are four optional typer imports, two missing
Case videos, and fifteen Recording real-media opt-ins. No skip/xfail rule changed.
Both the successful DB report and JUnit are checked for unique complete selection,
successful setup/call/teardown, and no skipped/xfail phases. Removing an actual
JUnit entry is rejected. The unchanged full-inventory checker rejects the 74-test
subset for missing mandatory role/scenario; **full strict gate is not PASS**.

Whole pytest, whole MySQL/nested mandatory wrapper, the entire gate mutation suite,
paid provider, full API/Worker cross-process E2E and current-diff remote CI were not
run. Related regression already takes about 202 seconds and focused real DB about
98 seconds; jobs core/checker/workflow/other Owner code are unchanged. Repeating
the broader mandatory inventory does not resolve the unmerged dependency, pending
HINT semantics or unfinished production media/T2 composition. Workflow 30 minutes
and nested MySQL 900 seconds remain unchanged. Command/setup mistakes, the initial
sandbox denial and the negative-control failures are retained, not called passes.

Owned DB/helper shutdown, exact datadir removal and port refusal are recorded in
`server-final.json`. Only system schemas plus the dedicated base schema/default
accounts existed; non-audit clients, transactions and data locks were zero. Old
evidence and shared runtimes were retained. All snapshot/RAW/JSON/JUnit/runner/cache
and DB material, plus the local execution plan, remain PR-excluded. Independent
fresh-context read-only review is the next step explicitly authorized by the user;
its outcome will be appended without modifying this history.

## 2026-10-26 — fresh independent read-only review

The user-requested reviewer was dispatched in this same conversation with
`fork_turns=none`, receiving requirements/base/file manifest rather than the
implementation conversation. The reviewer inspected all 17 changed files, SoT and
current #403 state, and ran only `git diff --check`; no tests or DB runs were made
by the reviewer. Before recording this result, the author independently verified
all 17 manifest hashes plus HEAD/branch were unchanged and index remained empty.

- **No new P1/P2 defect found** in the delivered Search adapter scope. This is a
  static review result, not independent execution evidence or merge acceptance.
- **P3, deferred:** tracked successful composition tests inject the policy port,
  while tracked discovery tests cover helper absence only. Add a maintained test
  supplying callable public attributes and omitting `failures=` to catch discovery
  accidentally always returning None. The excluded #403 snapshot covers actual
  default integration for this run but does not replace a maintained regression.
  No production defect was demonstrated; the minor was recorded without an
  unrequested additional implementation/re-review pass.
- **Declined to judge:** unfinished production Recording/media/T2 lifecycle and
  cross-process composition, explicitly excluded clip/readout/export handlers,
  whole pytest/full required DB gate/current-diff CI. None is silently treated as
  completed. They remain separate dependencies/acceptance limits.
- HINT spent-auth remains **pending acceptance** and #403 remains open/unmerged.
  Public helper actual integration must be checked after the dependency is merged.
  The review does not approve that HINT semantic behavior or full RT-10 acceptance.

Fresh review text and integrity evidence are excluded scratch artifacts. Final
state remains **IN_PROGRESS · Refs #297 (RT-10(b))**, uncommitted and unstaged;
no push, PR creation, branch/worktree creation or additional reviewer occurred.

## 2026-10-26 — independent production composition follow-up

After the preceding review, the user authorized durable Recording facts/source
queries, API/Worker stored adapters, production Coarse/Fine media, existing T1/T2
integration and separate-process E2E while #403/#405 remain pending. These are
subsequent changes, not a reinterpretation of the earlier 17-file review. The
earlier P3 default-discovery test gap is now covered. Scope, RED→GREEN, direct
2254-test offline / 226-test MySQL runs and their limits are recorded in the
[production composition checkpoint](rt10b-production-composition.md). That note
also records the later documentation-only develop fast-forward and resource
cleanup. A new fresh read-only review is required for this expanded draft.

IN_PROGRESS · Refs #297 (RT-10(b)); #403 HINT spent-auth and #405 STALE policy
remain pending acceptance. No stage/commit/push/PR.

## 2026-10-26 — expanded-draft review follow-up

The new fresh read-only review found one P2: non-SQLAlchemy Runtime transaction
outcomes could reach the Search helper from an injected capability resolver.
It was reproduced, corrected with an explicit four-exception guard and verified
with RED2 21 FAIL/4 PASS → 25 PASS plus 167 focused regressions. The same reviewer
read the two-file delta and judged P2 resolved with no new P1/P2. These results
do not replace earlier run identities or resolve #403/#405. See the chronological
[review/correction record](rt10b-production-composition.md). IN_PROGRESS · Refs
#297 (RT-10(b)); no staging/commit/push/PR.
