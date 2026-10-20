# RT-11(a) source upload

**RT-11 IN_PROGRESS · Refs #298 (RT-11(a)) · PR #382 · merge SHA pending.**

Implementation note; Contract/Decision/Baseline and other module surfaces retain
their existing authorities. Evidence: ignored `.codex-scratch/rt11a-20261020/`.

## Sources and starting point

Retained checkout/branch `codex/rt11a-source-upload`. HEAD, origin/develop and
actual remote develop were `85da60b63e784efcbbfb00369244a133b470688e`; clean worktree
and empty staging. GitHub PR #381 was MERGED at that SHA, with remote
boundary-check/python-tests SUCCESS. Issue #302 was CLOSED. Issue #298 was OPEN,
latest body read directly, comments0. Those checks belong to REC-1, not this diff.

Compared Plan RT-11/§12, Tech §13, HTTP §3.5/§5.2/§7-6–9, Baseline B-U1/3/4/§2.6,
REC-1(a–c), Implementation Log, current API/storage/errors/logging, CaseStore and
record_source_registered, Recording capability/repository, gate and workflow.
The requested runtime-ops-workflow §4-2 pointer resolves through its router to
**ops-spec.md §4-2**; the workflow itself contains no upload policy.

## Implementation choices

POST /cases/{case_id}/sources accepts exactly one file part, a nonempty filename,
and no extra part. Part Content-Type/extension do not classify media. MIME
quoted-string decoding preserves original filename as opaque metadata; it never
selects the generated storage name. Success exposes only case_id,
source_asset_ref, case_view. HTTP §5.2 defines no Location header.

Starlette RequestBodyLimitMiddleware counts raw bytes including overhead without
requiring Content-Length. Its receiver sits inside the access receive proxy to
avoid wrapping HTTP413 in an AnyIO ExceptionGroup. The existing locked Starlette
1.8.0 is pinned explicitly (Baseline ≥1.6); only missing python-multipart0.0.32
is added. Its [upstream changelog](https://github.com/Kludex/python-multipart/blob/master/CHANGELOG.md)
records header bounds and CR/LF boundary scanning fixes. No existing dependency
is upgraded. Callback parsing writes chunks directly into shared staging in a
threadpool; no form()/UploadFile/full request buffer or spool is used. Final
multipart completion is checked. Parser diagnostics use an instance-owned null
logger; shared loggers are unchanged.

Existing UploadSettings supply idle60s, duration1800s and raw1GiB. Empty messages
do not refresh the idle byte clock. Stock Uvicorn returns500 on response-less
return/exception/cancel; [ASGI HTTP messages](https://asgi.readthedocs.io/en/stable/specs/www.html)
have no HTTP close send event. An API-owned
H11Protocol adapter implements the already fixed no-status abort policy with a
private callback capturing the current request cycle. It marks disconnected,
disables keepalive, wakes the cycle and closes transport. Trusted abort state
lets access logging unwind without false failed/completed500 events. Supported
invocation remains python -m daesingo.api, explicitly selecting that adapter.
Generic ASGI hosting must supply this capability; stock Uvicorn is insufficient.
A fresh boundary reviewer independently proved this route before product code.
It is Plan §12.3 implementation detail, not a new timeout policy/Owner obligation.

Shared staging → flush/file fsync → close → st_dev check → atomic os.replace into
generated source locator all precede DB checkout. POSIX additionally fsyncs final,
staging and root directories before registration. Windows has no equivalent
directory fsync primitive; its tests do not prove power-loss directory durability.
Then one caller transaction uses existing CaseStore.load_for_update, checks
INTAKE, creates Recording's MySQL adapter on that Connection, registers source
and calls unchanged record_source_registered. Its second Case lock is already
owned by the same transaction. Only after COMMIT ACK does a separate public
case.get_view build201. Recording repository never commits/rolls back itself.

Fresh implementation review found the first version still hashed/probed the
whole source inside that transaction. Two actual MySQL RED tests and an
independent reviewer real-AVI/default-ffprobe RED reproduced it. The existing
public FfprobeMediaProbe and RecordingService(media_probe=...) seam now prepares
media before checkout. A request-local adapter checks dev/ino/size/mtime_ns/
ctime_ns identity before/after preparation and again on registration, returning
the prepared result without hashes/tools under the Case lock. Typed preparation
errors are deferred until registration to preserve missing404/non-INTAKE409
precedence. Mutation gives TEMPORARY_FAILURE without rows. No Recording public
surface change or extra Owner obligation is needed. The server-owned published
file remains subject to the existing shared-filesystem trust boundary.

UNSUPPORTED_MEDIA→422, TEMPORARY_FAILURE→503, unexpected→safe500, using only
Recording code. Source-only HTTP exceptions preserve existing unrelated error
mapping. Existing precommit DB503/unknown COMMIT500 semantics remain. A failed
postcommit view is500, never a promise of non-application. Response loss leaves
file_count N+1; retry is a new registration with unchanged revision semantics.

Rowless staging/final files may remain after failure. RT-12 owns cleanup; no
frames/assets/Range/retention/purge/Object Storage/capacity/concurrency/Worker/Web/
auth policy is introduced.

## Verification progress

- Initial RED: HTTP/ASGI/subprocess29 FAIL, actual MySQL4 FAIL. The initial
  two-file splice and assumed Recording getter were test mistakes, later fixed;
  their first failures do not prove corrected assertions.
- First GREEN attempt:49 PASS/4 FAIL and MySQL3 PASS/1 getter test FAIL. Streaming
  HTTP413 grouping, overly broad422 mapping, Windows connection-aborted handling
  and fixture errors were diagnosed and corrected; failures remain preserved.
- Focused raw1GiB exact/+1/Content-Length present/absent, storage/fsync/device,
  streaming/timeouts/process and existing API regression:59 PASS. GiB fixtures
  are explicitly removed after assertions, without full-body allocation.
- Expanded MySQL registration/rollback/filename/concurrency/checkout/abort/COMMIT
  ACK/response loss20 PASS before final inventory. First process-kill run3 PASS/
  1 global transaction-audit FAIL; audit now uses AUTOCOMMIT and exact schema
  ownership, excluding itself. The final actual strict run below covers all four.
- New gate family RED12 FAIL→GREEN12 PASS. Initial independent inventory36
  obligations/12 families grew to38 after review, additional to all old inventory.
  Final strict JSON/JUnit/parameter/metadata/family results are recorded below.
- Boundary PASS, Contract62 structure/26 JSON/104 semantic PASS. Initial Windows
  cp949 output failed printing an em dash; explicit UTF-8 rerun passed.

Follow-up: source-only413 now includes Connection:close, so rejected incomplete
requests cannot cause Uvicorn to resume body draining/keepalive. RED2 FAIL/2 PASS
became GREEN4 PASS; reviewer independently checked actual declared and chunked
CLI packets, Contract413 and EOF. The prepared-probe fix passes all **38** current
MySQL upload obligations in12 families (65.08s, wrapper exit0/source drift0).
Reviewer directly generated AVI, ran actual ffprobe with checkout0 and a
separate Case NOWAIT lock, then verified201 and new service restore. Earlier
whole-suite attempt was deliberately interrupted after127.766s for this review
fix; its exit1/drift0 remains preserved, never relabeled PASS. Final whole-suite
failure and successful isolated strict execution are recorded below.

The whole regression is not all green. Its two failures and scoped follow-up,
fresh review, preservation and resource audit are recorded below. Current diff
remote CI is pending. No staging/commit/push/PR has been performed.

## Complete delivery inventory

| Area | Files |
| --- | --- |
| Root facts/dependencies | README.md; pyproject.toml; uv.lock |
| Implementation records | docs/runtime/runtime-implementation-log.md; docs/runtime/rt11a-source-upload.md |
| API composition | src/daesingo/api/__main__.py; src/daesingo/api/app.py; src/daesingo/api/composition.py; src/daesingo/api/errors.py |
| Upload implementation | src/daesingo/api/routes_sources.py; src/daesingo/api/upload.py; src/daesingo/api/upload_protocol.py |
| HTTP/ASGI/process tests | tests/api/test_sources.py; tests/api/test_sources_process.py; tests/api/source_process.py; tests/api/test_process_safety.py |
| MySQL acceptance | tests/api/test_sources_mysql.py; tests/api/test_sources_interruption_mysql.py; tests/upload_acceptance.py |
| Strict gate | scripts/check_mysql_test_report.py; tests/common/db/test_mysql_gate.py; tests/common/db/integration/test_migration_gate.py |

22 files total. tests/api/test_process_safety.py adds exactly the expected
http=cli.UploadH11Protocol dictionary entry in the existing child, preserving
all signal/cleanup/logger assertions. Exact byte substitution and frozen hash
proof are in signal-expectation-impact.json. Scratch/RAW/archive/pytest reports/
media/temporary env files are excluded from PRs; pre-existing evidence is
preserved, not deleted.

## Whole-suite result and current-source follow-up

Frozen full-final completed **9381 PASS /26 existing opt-in SKIP /2 FAIL** in
2714.09s (wrapper2725.875s, exit1, source drift0). Failures were:

- Existing signal child expected exact old Uvicorn kwargs, omitting the newly
  required HTTP protocol. Its AssertionError prevented the intended interrupt.
- Original mandatory MySQL function's nested subprocess exceeded900s. It has no
  completed child JSON/JUnit/mutation evidence. Original full strict gate rejects
  that failed report; it is preserved without merging/doctoring results.

After the isolated test expectation correction, all process-safety + HTTP/ASGI/
default1GiB + real timeout + existing app checks pass: **104 PASS**,84.99s, wrapper
exit0/drift0. No product code changed after the full freeze. Reviewer explicitly
accepted this isolated expectation adaptation and scoped rerun while retaining
the failed whole-run result.

The exact newly owned RAM MySQL server had4 default accounts, no other client/
transaction/data lock and a single abandoned harness UUID schema after timeout.
Its tables and zero connections were recorded, then only that schema was
removed. InnoDB flush_log_at_trx_commit=1, sync_binlog=1 and packet64MiB were
observed. Original mandatory was rerun alone under unchanged nested900s/
outer1800s; its completed result follows.

The isolated rerun's child now completed **806 tests /2418 passed phases**,
JUnit870.196s, skip0/xfail0. Root ran the unchanged strict JSON/JUnit CLI and it
passed. The unchanged900s deadline leaves only29.804s in this local run. Current
diff remote CI is still pending.

## Final local evidence and independent review

The original mandatory function completed **1 PASS in1235.87s**, wrapper1238.296s,
exit0, source drift0. Exact parameter omission inventory is **5633 =5139 prior
+494 upload** (38 upload identities ×13 layers), all rejected. Upload metadata
omissions152 and family omissions12 give164 additional rejected cases. The
reviewer independently derived38 additions/12 families against git HEAD and
verified exact Counters, no duplicate identities, all rejected, and XML artifacts.
This preserves all old required inventory, checker function ASTs, nested900s,
workflow30min, and strict selected-test skip0/xfail0. The full-suite26 external
opt-in skips are outside that strict selection and their source bytes equal HEAD.

Fresh reviewer directly ran55 HTTP/app checks,2 real CLI timeout checks, a real
AVI/default ffprobe/MySQL success with checkout0 and an independently available
Case NOWAIT lock, and2 raw CLI413/EOF probes. Both P2 findings (413 keepalive and
probe inside transaction) were corrected and independently rechecked. Reviewer
also directly ran strict806 JSON/JUnit CLI, boundary/Contract/diff checks and
verified mutation/preservation/current-source evidence. No remaining product
P1/P2 or new Owner policy decision was identified.

Root direct results include104 current HTTP/ASGI/default1GiB/process/app checks,
38 upload MySQL obligations, original mandatory+all omission mutations, and the
failed9409-case full run. These are distinct from reviewer direct executions
and historical remote CI. No combined report changes the failed full result.

Preservation: REC-1(c)16228 evidence files and REC-1(a)/(b)150/148 evidence files
match their recorded hashes. Original Implementation Log bytes remain an exact
prefix; additions are chronological.557 frozen source/config files differ only
in the reviewed signal expectation entry, proved by exact byte reversal; product,
gate and config drift0. Workflow bytes and frozen migrations are unchanged.
Boundary PASS; Contract62 structure/26 JSON/104 semantic PASS; diff check PASS.
Only python-multipart0.0.32 was added; all earlier locked versions are unchanged,
and uv lock --check --offline passes. Native POSIX production publish-function
probe observed file fsync→replace→three directory fsyncs on the same device;
this is not a full Linux HTTP/MySQL or power-loss test.

## Owned resources, remaining limits and handoff

Before shutdown, MySQL8.4.7 had only four default accounts, system schemas plus
the owned base schema, other clients0/transactions0/data locks0. The abandoned
owned UUID schema from the failed full timeout was recorded and removed before
the successful isolated rerun; no unrelated schema or account was changed.
Shutdown removed the owned mysqld, RAM datadir and socket.416 owned upload files
were hashed before removal; three owned test links were removed as links only.
No owned test Python process remains. Per-test API process/listener cleanup and
orphan conditions remain in raw evidence.

**Cleanup limitation:** original helper shutdown exited1 because Windows port
62501 remains open in shared wslrelay.exe PID25236, which also owns unrelated
port58501. WSL ss shows no Linux62501 listener and no MySQL backend remains.
The shared relay/WSL was not stopped. Complete listener cleanup is not claimed;
reviewer classified this as nonblocking OS residue. Captured MySQL logs, final
DB/process/listener audits, per-file hashes and original helper failure remain
under `.codex-scratch/rt11a-20261020/`.

Nonblocking risks: the private close adapter depends on pinned Uvicorn internals;
the supported API CLI supplies it, generic stock ASGI hosting does not. Windows
has no directory fsync primitive used here; RAM tests do not prove power-loss
durability. Prepared stat identity retains the existing storage trust boundary.
Native filesystem stalls are not fully bounded by receive deadlines. The local
MySQL child870.196/900s has a small timing margin; the Windows whole run45m14s
does not establish success under the unchanged Linux CI30min workflow.

Local changes are reviewable and technically ready for a commit/intermediate PR
with these results disclosed; remote CI and merge readiness are not established.
The user requested stopping before staging/commit/push/PR, and none was done.
Remaining product P1/P2: none identified by fresh review. Owner decisions: none
introduced. Current PR number/merge SHA: pending. **RT-11 IN_PROGRESS**;
**Refs #298 (RT-11(a))**. FrameRef/DerivedAsset and all other excluded scope remain
future work. Scratch/RAW/archive/pytest outputs/media/temp env and evidence logs
are excluded from the22-file delivery; pre-existing unrelated files were preserved.

## PR #382 CI duration fixture correction (uncommitted follow-up)

The sections above preserve the original implementation evidence. This follow-up
starts at current HEAD `fd0595def4026605530cc4f31c6613481e2a9746`, on the unchanged
branch with clean worktree/empty staging. PR #382 is open. Remote run39418471074,
job118613193000 reported9381 PASS/27 SKIP/1 FAIL in1538.27s: only
`test_receive_abort_sends_no_status_and_never_registers[duration]` failed, with
three ASGI messages forming400 `http.malformed_request`. Boundary-check passed;
the later **MySQL execution gate was SKIPPED**, not successful. The original job
log, job/run/PR JSON and SHA256 manifest are preserved in the new ignored
`.codex-scratch/rt11a-ci382-20261020/`; no remote rerun was requested.

The original fixture sends ten `b'-'` chunks with20ms configured delays, idle40ms,
total70ms, and multipart `boundary=boundary`. Its third byte makes `b'---'`, which
is malformed. The exact original test reproduced400/three messages on Ubuntu
24.04.1, Python3.12.3, uv0.11.15 and the same locked dependencies. CI used Python
3.12.15; that patch-version difference is disclosed. The pinned uv has no managed
3.12.15 download entry locally, so its failed exact-version setup attempt is
preserved. Initial local pytest missing-basetemp-parent error is setup evidence,
not the later actual test RED.

Separate instrumentation retained exact chunks/settings and receive/parser/abort
events. The third invalid byte reached parser at upload elapsed66.931ms, before
the70ms deadline; it returned400 with registration0. Changing only the payload to
a valid open multipart part under the same real delays/settings produced a
`duration` abort, zero ASGI messages and registration0. Actual CI per-chunk elapsed
times were not logged; configured timing is known, and measured timings belong to
the local reproduction. These observations identify a timing-dependent malformed
test input, not evidence that production should suppress an earlier parser error.

Only the test source changes: the duration input is a valid open part followed by
data bytes, and a test-local receiver clock advances20ms per byte arrival. A controlled
RED with the old malformed input preceded the payload correction. GREEN checks
zero messages/registration, exact `duration` close reason, four consumed chunks,
three staged payload bytes, and no final file. Idle/disconnect assertions remain;
the real CLI timeout tests still exercise unmocked elapsed-time cancellation and
transport closure. No arbitrary sleep increase, timeout relaxation, product,
Contract/Baseline, dependency, workflow, DB or strict-gate change is made.

The ASGI test helper's optional arrival callback defaults to None. Its close
observer now records the already-set trusted scope abort reason. The MySQL helper
consumer ignores close entries; its receive path is unchanged. Independent review
found no need for a new local DB/full pytest replay solely for this test fixture.
The new-head remote whole regression and strict MySQL gate remain mandatory.

Focused Linux3 PASS and Windows3 PASS. Fresh reviewer independently ran33 HTTP/
real CLI timeout checks (GiB cases2 deselected), and three in-memory negative
controls correctly failed when duration enforcement, transport close, or the
correct abort reason was removed. Reviewer did not edit product/tests/docs/git.

The first broader Linux run preserved94 PASS/10 FAIL,149.52s. Failures involved
short CLI-child startup/communication limits. Import-only benchmark measured
5.545s from `/mnt/c` versus1.936s from a192-file SHA-identical native source
snapshot. This single benchmark supports import slowdown; it does not prove the
cause of every timeout. No Git checkout/worktree was created. The same104 tests
then passed with native source for child imports and unchanged timeout values:
**104 PASS/skip0,86.34s**, wrapper89.734s/exit0/source unchanged. The first94/10
failed result is preserved separately and is not relabeled PASS.

Boundary, Contract fixtures and diff checks pass.192 product source files plus
the gate/harness/inventory/workflow/dependency files were compared against HEAD:
198 files total, zero changes. The reviewer independently rehashed the192 native
source copies and confirmed exact equality. Only this test and the two Runtime
record documents change in the correction. Original Log bytes remain an exact
prefix; old scratch/RAW/archive/pytest evidence was not edited or deleted.

Root cleanup retained per-file hashes before removing67 newly owned Linux and3
Windows upload files. No owned Linux test Python process remained; Windows process audit
also found none. Per-test real API listener/child cleanup assertions passed in the
native run. No new MySQL server, schema or account was created. New inactive
Linux env/cache/source snapshot and raw reports remain excluded test tooling;
pytest links were recorded without traversal. No shared WSL relay was stopped.

Reviewer-only fixture cleanup has a separate audit limitation: its cleanup script
removed generated upload files, then was interrupted during slow metadata checks
before writing its in-memory per-file hashes/count. That count/hash record cannot
be recovered or claimed. A final read-only check records zero remaining generated
upload files in those four exact reviewer roots; raw logs/XML remain preserved.
This does not replace root's retained67/3 records or any test result.

This correction is at the user's first-report stopping point: no staging, commit,
push or CI rerun. Current fix remote CI/MySQL gate success and merge readiness
are not established. RT-11 IN_PROGRESS; Refs #298 (RT-11(a)).
