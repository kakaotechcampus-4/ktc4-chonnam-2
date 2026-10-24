# RT-11(c) — stored DerivedAsset HTTP read

Status: **RT-11 IN_PROGRESS · Refs #298 (RT-11(c))** · Related #387.
This is an implementation/review note, not a Contract or Owner Decision.

## Sources and prerequisite

Issue #298; HTTP Contract §3.5, §5.2, §5.5, §5.6, §7-6–§7-9;
Runtime Tech Spec §13; Provisional Baseline B-U1/B-U3/B-U4/B-F1/B-F2/§2.8;
Runtime Implementation Plan RT-11/REC-1; Recording REC-1(a)/(b)/(c) and its
current public capabilities were checked. The asset route is exactly
`GET /cases/{case_id}/assets/{asset_ref}`. Cache policy is the Contract's
`private, no-store`; frame configuration does not apply to assets.

PR #388 merged at `1f830afeac93309e9ef9c8eb90fcfaced0f97ae0`. Its remote
[boundary-check](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39753758821)
and [python-tests](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39753758715)
succeeded, including the MySQL execution gate. These are predecessor results,
not evidence for the present uncommitted implementation.

The initial investigation stopped before editing because `owns_asset` still
used PAD SPACE ownership comparisons. PR #394 subsequently merged at
`2ffd67ebcf62a974a165942c911c27468fb7f0ce`, which matched local HEAD,
origin/develop and a fresh remote develop SHA check on resumption. Its
[boundary-check](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39993802597)
and [python-tests](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39993802621)
succeeded; the latter's full pytest and MySQL execution gate steps succeeded.
Issue #387 was confirmed closed/completed through GitHub. No CI was rerun here.

At the user's instruction the pre-existing untracked #387 plan was moved,
without reading/reusing/editing its content, from
`docs/superpowers/plans/2026-10-23-recording-exact-ownership.md` to
`.codex-scratch/issue387-20261023/2026-10-23-recording-exact-ownership.md`.
SHA-256 before and after:
`9A43517890F3DCA4306F75464525CF272EF5A0DB83A17993D733FEAE71E7EADD`.
`git status --short` was empty after this move; the archive is ignored.

## Design and boundaries

`ApiComposition.load_asset` validates the Case ID with the existing Case
validator, then uses the existing public CaseStore existence check. It creates
a transaction-local RecordingService on the caller Connection. It asks
`owns_asset(case_id, ContractRef(kind='derived_asset', ref=asset_ref))` before
calling `open_derived_asset(asset_ref)`. PR #394's binary exact association
residual and restored asset identity check are reused through that capability;
no SQL/schema/table inspection is added to the API.

The stream is read and closed inside the callback, including read failures.
The callback returns only bytes and content type; it does not commit, rollback
or close the caller Connection. The existing `run_api_transaction` owns that
boundary and retains its typed error behavior. Header construction starts only
after commit and connection checkin. ASGI sends retain no DB or stream resource.
Request cancellation can leave a synchronous read finishing in its worker
thread; that thread still closes the stream and ends its transaction. There is
no detached task needing an application-owned lifetime manager.

Recording validates stored bytes/descriptors and supplies the actual format.
The API checks the read length against the public byte size. The supported
Recording outputs are currently PNG and isom MP4. The API maps those actual MIME
types to constant ASCII names `daesingo_asset.png` / `daesingo_asset.mp4`;
unknown types fail closed rather than guessing an extension. Content-Length is
the returned bytes' length. Neither ref text, original filename, vehicle number
nor locator enters headers or logs. Format signature checking is not a full
codec decodability guarantee.

Unknown, foreign and invalid-kind references use `404 http.not_found`.
Recording `UNAVAILABLE` uses `404 http.ref_unavailable`; `TEMPORARY_FAILURE`
uses `503 http.dependency_unavailable`. Unexpected/validation failures and
unknown commit outcomes preserve existing 500 behavior. Case validation failures
are 404. Error text, traceback and DB details are not rendered.

Assets do not consume frame permits. Range requests receive the complete 200
body. No provider, decoder, regeneration, creation endpoint, Case change,
schema/migration, RT-10 wiring, retention or cleanup policy change is included.
The existing immutable associations are consumed as implemented by Recording;
this work adds no concurrent reassignment/mutation protocol.

## Direct verification and review material

Change inventory (15 files, including the final Implementation Log entry):

| Area | Files |
| --- | --- |
| API | `src/daesingo/api/app.py`, `composition.py`, `errors.py`, new `routes_assets.py`, `README.md` |
| Asset tests | new `tests/api/test_assets.py`, `test_assets_mysql.py`, `test_assets_network_mysql.py`, `asset_process.py` |
| Required evidence | new `tests/asset_acceptance.py`; `scripts/check_mysql_test_report.py`; `tests/common/db/test_mysql_gate.py`; `tests/common/db/integration/test_migration_gate.py` |
| Implementation record | new `docs/runtime/rt11c-asset-read.md`; appended `docs/runtime/runtime-implementation-log.md` |

Current-run commands, RAW output, JSON/JUnit and hashes are retained under
`.codex-scratch/rt11c-20261024/`, excluded from the PR. Tests and independent
required inventory are versioned; the checker independently declares matching
requirements. The nested actual-report mutation test covers each asset
parameter, metadata omission and whole family omission. Workflow 30 minutes,
nested MySQL 900 seconds, skip/xfail rejection and strict JSON/JUnit meanings
remain intact. Existing checker/fixture optimization regression tests remain.

Direct verification so far:

- PR #394 prerequisite: 33 selected real MySQL tests passed (3 deselected).
- RED: unit 9 failed/5 passed; real MySQL 11 failed/5 passed/29 deselected,
  because the route was absent. Tests expecting a pre-existing safe 404 passed
  already; this is not represented as all tests failing.
- Initial GREEN attempt: 57 passed/2 failed. Unicode Case aliases exposed missing
  use of the existing Case ID validator in the new loader. The loader now calls
  it; the Case module was not changed.
- Expanded HTTP/ASGI/MySQL: 69 passed. Final asset suite including TCP and
  additional filename/header checks: 72 passed, including 58 MySQL tests and
  174 setup/call/teardown phases. All selected MySQL tests passed, skip/xfail 0.
- Strict checker RED: all 8 omitted asset families were incorrectly accepted
  by the previous checker. After extending the checker, the 8 family checks
  plus 4 valid-evidence/optimization tests passed.
- Boundary and Contract fixtures passed. The first boundary invocation had a
  console encoding error when printing its success line; rerunning with Python
  UTF-8 mode passed. No checker policy was altered for this environment issue.

### Final execution record

All product/test Python sources stayed unchanged during the following runs.
No predecessor report was used as a replacement for current execution.

| Execution | Result |
| --- | --- |
| Unselected whole pytest | **11,969 passed / 2 failed / 26 skipped**; 2,703.03 s pytest time |
| Gate unit inside that whole run | **8,106 passed**, no skip/failure |
| Independent complete MySQL inventory, excluding the self-repeating gate module | **1,004 passed / 3,012 phases / MySQL skip 0, xfail 0**; strict JSON/JUnit CLI PASS |
| First nested self-repetition | Failed at the unchanged 900 s subprocess limit; no complete child JSON/JUnit |
| Isolated nested recheck | Failed because its child had **999 passed / 1 failed**; child completed in 618.60 s, within 900 s |
| Upload size recheck after freeing own temp XML | **2 passed**, same assertions/limits |
| Upload process interruption recheck | **4 passed**, unchanged 8 s startup budget |
| Current actual-report mutation-body replay | **8,116 parameter mutations** and **1,404 metadata/family omissions** rejected; asset subset **754 + 240** |

Whole-run failures were exactly:

1. `tests/api/test_sources.py::test_default_one_gib_exact_and_next_byte_are_streamed_without_whole_body_buffer[False]`:
   extra-byte request returned 503 instead of 413. The same failure reproduced
   once; about 1 GiB free disk was observed during diagnosis. After deleting
   only this task's completed gate RED temp XML, both original parameters passed.
   Disk space is a supported hypothesis, not a confirmed errno/root cause.
2. `tests/common/db/integration/test_migration_gate.py::test_actual_report_rejects_each_missing_migration_check`:
   first child timed out at 900 s. The isolated recheck's child then failed
   `tests/api/test_sources_interruption_mysql.py::test_owned_process_kill_keeps_file_before_row_order[before_publish]`
   at the existing 8 s owned-API startup budget, with the process still alive.
   All four interruption modes later passed without changing source or budget.
   Neither failed nested execution is reclassified as successful.

The whole-run MySQL report contains 1,005 selected tests / 3,015 phases and one
failed phase (the nested parent). Its strict checker result is **FAIL**. The
isolated failed child is also rejected by the checker. The separate 1,004-test
report is a new direct execution and passes the unmodified strict meanings;
it is not a splice of failed and passing reports. Its four collection skips
are unrelated non-MySQL Typer-dependent modules, not MySQL skips. Whole-run 26
skips comprise those four modules plus unavailable external video/archive inputs.

Because the nested children failed before their mutation loops, the unchanged
mutation/assertion body of the versioned gate test was executed separately on
the current direct 1,004-test JSON/JUnit. All 8,116 mutations and 1,404 omissions
were rejected, with original report/source SHA-256 unchanged. This is explicitly
an actual-report replay, **not a successful nested subprocess acceptance**.
The exact replay helper and counts remain in scratch for independent inspection.

Boundary, Contract fixtures (62 structure / 26 JSON / 104 semantic checks),
actionlint for both existing workflows, and `git diff --check` passed. Workflow
30 minutes, nested 900 seconds, startup 8 seconds, required inventory,
skip/xfail rejection and existing optimization regression tests are preserved.
Current-diff remote CI and a fully passing whole pytest have **not** been obtained.
The nested acceptance failure remains a merge blocker; startup/initial timeout
causes and CI 30-minute headroom need independent follow-up. No upload, startup,
cleanup or CI policy source was changed to turn these failures green.

### Resources and handoff

Both owned MySQL 8.4.7 processes and their helper processes ended. Both generated
`/dev/shm/rt11c-<uuid>` datadirs were removed and their Linux ports refused
connections. Final Windows netstat had no entries for either owned port.
An earlier Windows connect check failed before this final verification; its
exact cause is not established and its failure is retained.

Both pre-shutdown audits had no non-audit client, transaction or data lock and
only the four default accounts. The first server's clean-schema assertion
failed because the forcibly timed-out pytest left one disposable test schema;
the server finally block still removed its entire owned datadir. The second
server's five-schema audit passed. Neither assertion failure nor cleanup is
reported as a successful first audit. Shared WSL/relay services were not changed.

Two zero-byte repository-root cleanup lock artifacts created by tests were
hashed and removed after all DB/process tests ended. Source and evidence
snapshots, RAW, JSON/JUnit, mutation inventories, runners, CA/logs and the archived
#387 plan are excluded from the PR. No personal original video was added.
The endpoint buffers the stored bytes in memory; no new streaming/size policy
or full-codec validation guarantee is introduced. Existing predecessor
cleanup/disconnect/import-watchdog uncertainties are not claimed resolved.

No reviewer/subagent, commit, staging, push or PR creation is authorized for
this implementation conversation. Independent re-review should start from
the uncommitted diff and the evidence/limitations in the appended final record.


## P2 follow-up — 2026-10-24 (incomplete; observation semantics pending)

Status remains **RT-11 IN_PROGRESS · Refs #298 (RT-11(c))**. The preceding
execution record is historical; its full/nested failures remain failures.
This follow-up has not completed both P2 fixes or final acceptance.

| Item | Direct evidence in this follow-up |
| --- | --- |
| P2-1 product RED | `p2-red-network`: 1 failed, specifically absent `api.asset.bytes` and `api.asset.download_latency_ms` after body-send OSError. The test first proves common `api.request.completed(status=200)` exists while real body send is pending. No common event or product observation behavior has been changed. |
| P2-1 undefined semantics | Plan §RT-11 and Baseline list both event names only. Common logging permits `status`, `count`, `duration_ms`; Frame uses FAILED/CANCELLED but does not distinguish disconnect from send error. The user required reporting undefined names/meanings before expansion. An explicit question is pending about four terminal statuses and successfully returned ASGI-send payload bytes. No schema/meaning has been silently invented. The new product test is intentionally still RED. |
| P2-2 negative control | `tcp-negative`: 1 failed at “no actual downstream drain wait observed” when a scratch-only plugin makes FlowControl.drain return immediately. An entered/completed send is rejected. |
| P2-2 GREEN | Initial real TCP probe passed; after adding strict `ASGI ended >= transport disconnect observed` ordering, `tcp-order-green`: 1 passed. Socket send/receive buffers and transport watermarks are bounded; the real Uvicorn drain task must still be pending after one scheduler turn. Snapshot on the server loop proves body send pending, lifetime not ended, write paused, checkout 0. Client close then must cause transport disconnect and request termination. All Uvicorn request tasks/connections and the server thread must end. Existing payload size and timeouts are retained; no asset/frame permit was introduced. |
| Independent regression (not final acceptance) | `independent-regression`: 129 passed, including 58 actual MySQL tests / 174 phases, skip/xfail 0. Asset HTTP/ASGI/TCP/MySQL plus Frame lifetime, common access observation and API cleanup. P2-1's known-RED file is explicitly outside this independent run. |
| Structural checks | Boundary PASS (0); Contract fixture PASS (62/26/104); both workflows actionlint PASS; diff check PASS. Workflow 30 minutes, nested 900 seconds, startup 8 seconds, inventory and strict policies unchanged. |

### Failure investigation: facts and unavailable historical evidence

- **Upload 503:** one instrumented invocation of the original failing `[False]`
  test passed (1 passed, 7.38 s). Scratch instrumentation around `_storage_call`
  preserved each open/finish/close/publish boundary, actual staging/source sizes,
  disk free and a traceback/errno capture on any raised exception. No OSError
  occurred. Free space was 7,740,743,680 bytes at start and 6,664,900,608 bytes
  before the second request. The exact request finished/published 1,073,741,694
  stored payload bytes; the extra-byte request opened staging and never reached
  parser.finish/publish, consistent with the existing 413 assertion passing.
  Original errno/traceback and disk/staging state at the historical failure were
  never captured and cannot be reconstructed. Disk pressure remains a hypothesis,
  not a confirmed cause. Upload receiver/body-limit/publication sources have no
  diff; RT-11(c) only adds a GET route and loader, but absence of a direct upload
  diff alone does not exclude timing/resource effects.
- **Nested 900 s:** the historical timeout preserves the command and parent
  traceback but no per-node live trace, child PID or complete child report. Its
  last completed/active node and child DB/bootstrap/import/cleanup/relay state at
  timeout cannot be established. No historical process state is invented.
- **Startup 8 s:** one focused instrumented original `before_publish` invocation
  passed (1 passed, 5.14 s; call 4.0176805 s), preserving launcher PID 22780,
  interpreter PID 35332, poll states, import/function trace and stdout/stderr.
  Interpreter-site to first API import was 0.797 s; create_app began at 613510.531,
  bootstrap returned at 613510.578, compose_api returned at 613510.781 and
  create_app returned at 613510.921. These timestamps describe this passing,
  instrumented run only. The first reachable listener was followed by checkpoint
  and owned-process kill; no startup timeout or unexpected error was reproduced.
  Cleanup.start runs in a thread (not covered by this main-thread profile), and
  relay scheduling was not separately instrumented. Thus the earlier >8 s phase
  and the relation to the 900 s timeout remain unconfirmed. Limits were unchanged.
- **Inventory runtime contribution (historical, measured):** the retained failed
  nested child's JUnit assigns 45.957 s summed testcase time to 58 asset tests,
  within 613.385 s summed testcase time / 618.60 s pytest wall time. This is not
  a counterfactual run without assets and does not prove they caused either limit.
- **New harness issue, kept separate:** two initial minimal-RED attempts under the
  restricted execution environment stalled before the test coroutine. The saved
  5-second faulthandler stack is Windows asyncio loop creation in fallback
  socketpair.accept. Those attempts were stopped by exact test command/PID and
  do not count as product RED. The loopback-enabled execution produced the real
  product RED above. This does not establish the historical startup timeout cause.

### Remaining work and acceptance boundary

P2-1 requires the pending event/field-meaning decision, then implementation,
four-outcome/bytes/latency/privacy/error/non-asset regression GREEN and product
negative control. The current minimal test remains RED. P2-2's test improvement
has direct negative-control and real-network evidence, but both fixes are not
jointly complete. Consequently **final whole pytest = 0 runs; final nested = 0
runs** in this follow-up. Final strict unit/mutation/JSON/JUnit acceptance is also
pending. The requested exactly-once final executions have not been consumed or
replaced with the independent 129-test run or historical evidence.

Outstanding merge blockers are P2-1 and final acceptance, plus unconfirmed causes
of historical full/nested failures. Existing nonblocking limits (whole-asset
memory buffering, optional external video/archive validation, best-effort event
sink) remain documented above. No P1 review finding has been independently
reclassified as a new P1.

### Resource and PR-exclusion record

The owned MySQL 8.4.7 server/helper exited, its exact generated datadir was
removed, and Linux connect returned 111. Shutdown audit: only system+base schema,
default four accounts, no non-audit client, transaction or data lock. Windows
cleanup found no owned test Python process and no listener/active TCP connection;
57 TIME_WAIT entries remained at that snapshot (PID 0, not live DB checkout).
The TCP test asserts request-task/connection/server-thread cleanup. No root
cleanup lock artifact remained. Own diagnostic temp directories were removed
after preserving RAW/JSON/JUnit/traces. Shared WSL/relay services were untouched.

All scratch material under `.codex-scratch/rt11c-p2-20261024/` (including the
before-source snapshot, original RED, negative control, diagnostics and manifests)
is PR-excluded. Earlier scratch evidence and the #387 archived plan are preserved
without reuse/modification. No staging, commit, push, PR or reviewer/subagent call.


### Current complete changed-file inventory (16 files)

- `docs/runtime/runtime-implementation-log.md`
- `scripts/check_mysql_test_report.py`
- `src/daesingo/api/README.md`
- `src/daesingo/api/app.py`
- `src/daesingo/api/composition.py`
- `src/daesingo/api/errors.py`
- `tests/common/db/integration/test_migration_gate.py`
- `tests/common/db/test_mysql_gate.py`
- `docs/runtime/rt11c-asset-read.md`
- `src/daesingo/api/routes_assets.py`
- `tests/api/asset_process.py`
- `tests/api/test_asset_lifetime.py`
- `tests/api/test_assets.py`
- `tests/api/test_assets_mysql.py`
- `tests/api/test_assets_network_mysql.py`
- `tests/asset_acceptance.py`


## Owner-approved P2 implementation — 2026-10-24

Status: **RT-11 IN_PROGRESS · Refs #298 (RT-11(c))**.
The preceding P2 semantics-pending record is preserved history. The decision is
now resolved by [Runtime/Ops Owner comment](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/298#issuecomment-6380891047), directly retrieved in this follow-up.

### Implementation Notes

- A dedicated pure-ASGI AssetLifetimeMiddleware surrounds access/BaseHTTPMiddleware
  for exact GET /cases/{case_id}/assets/{asset_ref} requests (including root_path).
  It adds no semaphore, database operation, provider call, generation surface,
  Case/Recording/schema/migration or retention policy. Existing ownership and
  caller-transaction loading remain unchanged.
- download_latency_ms.duration_ms uses monotonic time from outer entry to the
  final downstream body send returning, or exception/cancellation termination.
  Normal post-final application cleanup does not extend download duration.
- api.asset.bytes is **successfully returned downstream send bytes, not client-received bytes**.
  It includes partial sends and error-response bytes that returned normally,
  excludes the failing chunk, and never uses Content-Length. It is neither client
  receipt nor TCP ACK. A server may return normally even after client disconnect.
- Each matched request attempts each terminal metric exactly once through existing
  bounded best-effort ApiEvents. Normal completion uses actual HTTP status text,
  any exception uses FAILED, and task cancel or no final body uses CANCELLED.
  No DISCONNECTED status or new logging fields are added. The middleware does not
  rewrite HTTP status or include raw case/ref/filename/locator/error text. Its
  server-issued trace is shared with the common access event for assets only;
  api.request.completed retains its global response-creation meaning.
- Real-MySQL send exit cases now assert these metrics. A new partial_failure
  parameter requires count=3 after a three-byte successful chunk followed by
  failed send. Required inventory is extended independently to 59 asset tests;
  checker caches/copy optimization and all existing strict policies are retained.

### Direct verification before the single final whole run

- Existing branch/HEAD and the 16-file source SHA-256 manifest matched exactly;
  staging was empty, and the preserved #387 plan hash matched. The prior stage
  did not provide an aggregate RAW/JSON/JUnit hash manifest, so historical equality
  of every evidence byte is not claimed. At resume, 158 original top-level/child
  artifacts were hashed and frozen separately. A recursive read of mutation XML
  was stopped for excessive I/O; those XML files were not modified.
- Initial product RED: 24 failed. Twenty reached absent-metric assertions; four
  normal-path cases also had a test-helper return-value mistake (request returns
  messages, not None). Initial GREEN attempt: 20 passed / those 4 failed. Corrected
  assertions with product metric bypass: 24 failed specifically on absent metrics;
  same assertions with implementation: 24 passed. All raw results are preserved.
- Expanded focused final source: 166 passed, including 59 actual MySQL tests /
  177 phases, MySQL skip/xfail 0. Includes incomplete/cancel/fatal termination,
  exact final-send timing, error HTTP statuses, partial bytes, ownership/exact
  identity, commit/checkin, send cancellation and actual TCP backpressure/disconnect,
  plus existing Frame lifetime/access observation/API cleanup regressions.
- New strict-parameter RED: 3 failed / 8 passed because the old checker accepted
  complete deletion or missing node/parameter metadata for partial_failure.
  After independent inventory extension: 11 passed.
- The full unselected pytest invocation below includes the nested MySQL gate
  exactly once. No independent nested rerun is planned. Failed final invocations
  remain failures and will not be rerun or spliced with passes.


### Final exactly-once execution and independent handoff

| Final-source execution | Complete result |
| --- | --- |
| Whole unselected pytest, one invocation | **12,016 passed / 3 failed / 26 skipped**; 2,099.93 s pytest; 2,125.828 s runner including startup/report completion |
| Whole-run MySQL inventory | **1,006 tests / 3,018 phases, all passed**, MySQL skip/xfail 0; strict JSON/JUnit CLI **PASS** |
| Nested child, one invocation inside whole pytest | **1,001 passed / 3,003 phases**, skip/xfail 0; 597.26 s pytest under unchanged 900 s; strict JSON/JUnit CLI **PASS** |
| Nested parent including actual-report mutations | **PASS**, call 819.498782 s (child plus strict/mutation assertions); not a second child invocation |
| Strict gate unit in whole execution | **8,117 passed** |
| Asset tests in whole execution | **109 passed**, including 59 actual MySQL tests; independent focused run remains 166 passed and is not added to whole counts |
| Actual-report negative evidence | **8,129 parameter mutations + 1,408 metadata/family omissions rejected**; asset subset **767 + 244** |

Whole-run failures are preserved, not replaced by focused PASS or MySQL PASS:

- `tests.api.test_process_safety::test_keyboard_interrupt_distinguishes_startup_from_serving[server-0]`: Failed: owned child exceeded 5s (stdout=b'', stderr=b'')
- `tests.api.test_process_safety::test_cli_cleanup_failure_is_quiet_and_restores_signals[RuntimeError]`: Failed: owned child exceeded 5s (stdout=b'', stderr=b'')
- `tests.api.test_process_safety::test_actual_server_cleanup_failure_exit_and_listener_release`: Failed: owned child exceeded 5s (stdout=b'', stderr=b'')

All three failed their existing **5-second total child-process deadline**, with
empty stdout/stderr. The parent traceback and original child source are retained
in full.raw/full.xml/full-failures.txt. There is no per-phase trace for these
three `-c` children, so import/startup/cleanup location and causal connection to
RT-11(c) are **unconfirmed**. They do not perform an asset GET, but the new import
and app wiring exist in this source; that alone neither establishes nor excludes
timing impact. No source/timeout/assertion change, standalone retry or second
whole/nested invocation was made after these failures. This whole run is **FAIL**
and remains a **merge blocker** even though both MySQL report gates pass.

The 26 skips are four Typer-dependent collection modules and 22 unavailable
external video/archive/explicit-opt-in inputs; none are selected MySQL skips.
The old whole 503/900 s failures and failed nested 8 s startup remain historical
failures. Their missing original errno/per-phase evidence cannot be reconstructed.
Current upload size tests and both sets of upload process interruptions passed;
this does not prove those historical causes were fixed. Existing one-invocation
upload/startup diagnostic results are preserved in the preceding P2 record.

**Environment correction:** compact.exe marked the owned full-temp directory
with inherited NTFS compression. This affected fixture files as well as text
reports; the runner comment saying “text evidence only” was too narrow. Logical
media bytes and assertions were unchanged, but physical disk allocation/pressure
differs. This whole run is not evidence of reproducing the old disk-pressure
condition. No shared directory, MySQL datadir or production/CI policy was changed.
The diagnostics plugin only records progress/PIDs/stdout/stderr and optional
6-second owned-child stacks. It does not select/deselect tests or alter budgets.

All **583 versioned/untracked Python source hashes** were unchanged throughout
the final run. All **158 original artifact hashes fixed at resume** remain
unchanged, and the archived #387 plan hash still matches. Neither prior reports
nor fresh full/nested JSON/JUnit were spliced or edited. The whole/nested
invocation ledger is exactly **1 / 1**. Workflow remains 30 minutes, nested 900 s,
owned-upload startup 8 s, process-safety 5 s; inventory, skip/xfail and JSON/JUnit
semantics and gate optimizations were not weakened.

**Current-diff remote CI was not run**: no staging, commit, push or PR creation.
The 2,099.93-second Windows local whole execution exceeds 30 minutes; it is not
a measurement of the Ubuntu CI runner. CI 30-minute headroom is unverified.
Predecessor PR #388/#394 remote successes remain prerequisite history only.

**Cleanup:** owned MySQL 8.4.7/helper exited; exact generated datadir removed;
Linux port refused connection. Shutdown audit had system four + base one schemas,
four default accounts, no non-audit client, transaction or data lock. Native
Windows audit contained only its two auditor/launcher processes, no surviving
test child; owned-port active connections/listeners 0, with 209 PID-0 TIME_WAIT
entries at that snapshot. No forced post-run Python kill was necessary. TCP tests
assert their request task, drain task, connection and server thread cleanup.
Two newly generated zero-byte root cleanup locks were hashed and removed after
all processes ended. Own temporary test trees were removed after preserving
original reports, mutation inventories and JSON interruption evidence. Shared
WSL/relay services were untouched.

**Merge blockers:** the three unresolved whole-run process-safety failures and
current-diff remote CI not obtained. P2-1 semantic/implementation block is resolved;
P2-2 has current-source real TCP and MySQL regression evidence. Nonblocking known
limits remain whole-asset memory buffering, bounded best-effort event delivery,
and unavailable external media/archive validation; client receipt/ACK is outside
the approved metric meaning. Historical timeout/disk causes are not claimed solved.

PR-excluded evidence is under `.codex-scratch/rt11c-owner-20261024/`: owner approval,
resume/frozen/review hashes, RAW, JSON/JUnit, failed-child tracebacks, progress,
mutation inventories, process/DB cleanup, runners and snapshots. Prior scratch
and #387 plan remain excluded and untouched. No reviewer/subagent was called.
Status remains **RT-11 IN_PROGRESS · Refs #298 (RT-11(c))**.


### Complete final changed-file inventory (17 files)

- `docs/runtime/runtime-implementation-log.md`
- `scripts/check_mysql_test_report.py`
- `src/daesingo/api/README.md`
- `src/daesingo/api/app.py`
- `src/daesingo/api/composition.py`
- `src/daesingo/api/errors.py`
- `tests/common/db/integration/test_migration_gate.py`
- `tests/common/db/test_mysql_gate.py`
- `docs/runtime/rt11c-asset-read.md`
- `src/daesingo/api/asset_lifetime.py`
- `src/daesingo/api/routes_assets.py`
- `tests/api/asset_process.py`
- `tests/api/test_asset_lifetime.py`
- `tests/api/test_assets.py`
- `tests/api/test_assets_mysql.py`
- `tests/api/test_assets_network_mysql.py`
- `tests/asset_acceptance.py`


### Process-safety root-cause investigation — unresolved (2026-10-24)

Status remains **RT-11 IN_PROGRESS · Refs #298 (RT-11(c))**. No product,
fixture, test assertion, child 5-second limit, sleep, workflow or gate change
was made for this investigation. Only this note and the implementation log
receive follow-up records; the full PR candidate inventory remains 17 files.

**Resume verification:** branch `codex/rt11c-derived-asset-read`, HEAD
`2ffd67ebcf62a974a165942c911c27468fb7f0ce`, empty staging, the same 17 candidate
paths and hashes, 115 handoff evidence hashes and 158 earlier evidence hashes
all matched before investigation. Remote develop was read directly as
`a89a57020f36d7bfef1d62e1af8ba9ef9a28627a`; its only changes from HEAD were two
Case decision documents. The dirty checkout was never switched/reset/stashed.
Separate `git archive` snapshots were used: HEAD plus the exact current 17-file
overlay, and clean remote develop. All 583 frozen Python hashes matched the
current snapshot byte for byte; all snapshot file hashes still matched after
execution. Process-safety tests, CLI, API events, common logging, frame lifetime
and storage cleanup are byte-identical between the two snapshots.

The original whole raw log, JUnit and progress records were read, including
test order and recorded runtime environment. All three failures occurred at
Windows `subprocess.py:1630`: `_communicate()` had joined its **stdout reader**
until the remaining deadline and found it alive. They did not time out in the
subsequent `process.wait()`. Both pipes were empty after the test's kill/reap.
The displayed `Popen returncode=1` is its later traceback representation after
cleanup; it does not establish the child's state before kill. No historical
child phase/stack/PID evidence exists for those three `-c` children, so their
internal import/startup/cleanup/atexit phase cannot be recovered from empty
output. The original whole result remains **12,016 PASS / 3 FAIL / 26 SKIP**.

Scratch-only diagnostics kept the same `Popen` arguments apart from adding
file-only phase observations to the child source, original assertions and
`communicate(timeout=5)`. They recorded parent spawn/communicate, both pipe
readers and wait, actual interpreter PID, per-import and top-level/local
statement boundaries, selected main/composition/cleanup/server calls and
atexit entry/tail. Side-channel files never replaced stdout/stderr. A lighter
follow-up omitted product profiling and scheduled a single file-only stack
dump at 3.5 seconds; no stack dump fired. Instrumentation is not an equivalence
proof: it can perturb scheduling. Thus uninstrumented children were also run.
Async profiler call/return entries include coroutine suspension/resumption;
they must not be counted as distinct requests or final shutdowns.

Direct, serial comparisons used the same Python 3.12.14 environment and owned
MySQL 8.4.7 require-mode preflight for both sources. A/B/C below mean the three
original failed nodes in their originally reported order.

| Direct comparison, each source run separately | Current RT-11(c) | Clean develop |
|---|---|---|
| A, B, C isolated, with phase observations | 1 PASS each | 1 PASS each |
| Original-order minimal predecessor bundle, with phase observations | 6 PASS | 6 PASS |
| Entire process-safety module, with phase observations on relevant children | 45 PASS | 45 PASS |
| Same minimal bundle, original uninstrumented children | **5 PASS / 1 FAIL (C)** | 6 PASS |
| Original immediately preceding frame TCP, health and owned MySQL modules, then process-safety; uninstrumented children | 53 PASS | 53 PASS |
| Three predeclared paired minimal-bundle runs, light observations | 6 PASS in each of 3 runs | 6 PASS in each of 3 runs |

The minimal bundle selected the immediate predecessor of A, then A, predecessor
of B, then B, predecessor of C, then C, preserving original relative order.
The resource bundle includes six actual MySQL nodes / 18 successful phases per
source, no skip/xfail. These subset reports are not a new required-inventory
strict gate or a new whole/nested result. Per-node diagnostic observations are
A **0/8 timeouts**, B **0/8**, C **1/8** on current source; develop is **0/8** for
each. Counts combine specified diagnostic modes, not independent statistical
trials; they exclude the earlier whole failure and do not estimate production
failure probability. The new C RED raw/JUnit is preserved unchanged under
`current-control/`; its 5-second failure also occurred in stdout-reader join,
with empty pipes. That run intentionally had no child phase instrumentation.

Observed successful lifecycle boundaries:

| Boundary | A | B | C |
|---|---|---|---|
| Imports and app composition | SQLAlchemy/API imports, real create_app/compose_api | API import; fake app/composition | Uvicorn/API imports; real create_app before CLI main |
| Ready/serving | Mock serve entry, no listener or ready handshake | Mock run entry, no listener or ready handshake | Real startup/bind, existing main_loop hook obtains listener; no added ready handshake |
| Signal action | Handler installation, Python-raised KeyboardInterrupt, restored-handler assertions | Handler installation and restoration around injected close failure | Uvicorn signal capture/restoration; no externally delivered OS signal |
| Shutdown/cleanup | Composition close, event close, both engine disposal returns | Injected close raises; CLI returns expected failure quietly | Actual Uvicorn shutdown, composition cleanup failure retained, listener-close and refusal assertions pass |
| Finalization | atexit entry/tail, both reader EOFs, process wait returns | Same | Same |

For the **failed** historical A/B/C and new uninstrumented C, only the parent
stdout-reader deadline phase is confirmed; the child phase remains unknown.
Do not substitute the successful lifecycle observations for a missing failed
stack. Instrumented target children ended with only the main thread in their
atexit tail; no asset load call or HTTP asset scope occurred. In C the asset
and frame middleware scopes were `lifespan`, following their existing bypass.
No asset metric send, frame permit acquisition or asset DB transaction is on
these test paths. The fresh subprocesses isolate parent permit state. CLI,
logging, semaphore and DB/server cleanup implementations are unchanged by this
investigation; the resource-prefix comparison also passed on both sources.
RT-11(c) still adds imports/router construction and lifespan middleware dispatch,
so those facts do **not** prove absence of a timing contribution.

**Hypothesis and limit:** phase observations tested whether the total budget
was consumed in imports/startup rather than shutdown. Successful runs reached
all boundaries, but no timed-out child was caught with a phase/stack record.
The hypothesis remains unconfirmed. Historical host scheduling, cache and full
OS environment were not captured and cannot be reconstructed. New MySQL
port/datadir, snapshot paths and noncompressed fixture trees differ from the
historical whole run; both comparison variants shared these conditions. Neither
host/disk contention, Windows launcher/pipe behavior, observer effect nor an
RT-11(c) timing regression is established as the cause. Develop did not
reproduce, so this is **not** evidence of a confirmed pre-existing develop bug.

**No fix / no RED→GREEN claim:** original failures and the additional C RED
remain unresolved. Later targeted passes are observations, not a repair and
not a whole pytest PASS. No whole pytest, nested required MySQL gate or remote
CI was rerun here. Earlier 1,006-node whole MySQL and 1,001-node nested strict
successes remain preserved evidence; the whole FAIL and missing current-diff
remote CI remain merge blockers. Unresolved timing/observer effects remain
investigation limits. Existing buffering/best-effort telemetry limits continue.

**Cleanup/evidence:** the owned comparison MySQL/helper exited, exact generated
datadir was removed and its port refused connections. Audit: four system schemas
plus the base schema, four default accounts, no non-audit client, transaction or
data lock; native owned test-process audit found zero residuals. All report and
snapshot source hashes were retained. Generated zero-byte snapshot cleanup
locks are preserved by hash and removed only after process exit. Diagnostics,
snapshots, failed/passing raw/JUnit, environment and order, phase JSONL, optional
stack files, manifests and resource audits are PR-excluded under
`.codex-scratch/rt11c-process-safety-20261024/`. Existing evidence and the #387
archived plan were not changed. No reviewer/subagent, staging, commit, push or
PR creation was used.
