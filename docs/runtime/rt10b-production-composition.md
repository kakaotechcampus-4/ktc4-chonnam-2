# RT-10(b) — durable Recording / production Search composition checkpoint

**IN_PROGRESS · Refs #297 (RT-10(b))**. 2026-10-26 follow-up to
[the Search adapter checkpoint](rt10b-search-handlers.md). This records the
user-authorized independent composition work while #403 and #405 remain pending;
it is not whole RT-10 acceptance or a merge approval.

## Scope and dependency boundary

The existing 17-file unstaged draft was backed up before work. The same branch,
`codex/rt10b-handler-registry`, remained in use. Implementation/tests ran against
`4a69a292f55ed48b9f679c1016087d3acd11a994`. On resuming after the usage limit,
origin/develop had four additional Case documentation changes (#354/#406/#397).
All 37 current changed files were backed up, incoming paths were disjoint, and a
fast-forward to `42ddea72bb927e7adedf352ba53d160bda1aa049` preserved every hash and
the empty index. The incoming Fine 70-second/repetition-policy/status notes do not
require a new Runtime orchestration or retry policy. No source changed in that
update, and the earlier test runs retain their original execution identity.

This slice connects HINT_EXTRACT / COARSE_SEARCH / FINE_VERIFY adapters to durable
Recording reads, stored Case observations, production Coarse/Fine media and the
existing T1/T2 paths. Default Search registration still requires the three real
public failure helpers, absent from this develop. Tests explicitly supply a
confirmed-policy port; this is not a production fallback or a taxonomy copy.
Without the helpers, the existing unregistered-kind failure remains. With helpers
and an explicit media profile, production Coarse/Fine composition is available.

- **#403 pending acceptance:** intent/HINT 401/403/404 plus exhausted budget.
  Latest inspected discussion still ends at `6398537018`; no Runtime remapping or
  semantic acceptance was added. The PR is open/unmerged at `00549ff23d27ac327a9305cb22b4661b68be403f`.
- **#405 pending:** terminal notification, its own receipt, and Case policy after
  all attempts become STALE. Existing T2 and `case_applied_at` remain for the
  existing SUCCEEDED/FAILED delivery only; no STALE projection was introduced.
- INCIDENT_CLIP_BUILD, PLATE_READ, OVERLAY_TIME_READ, REPORT_VIDEO_EXPORT and
  PLATE_IMAGE_EXPORT handlers remain excluded/unregistered. This slice neither
  chooses a candidate nor issues downstream jobs on Runtime authority.

## Public composition and storage

Recording owns the new detached facts/source reads and its persistence. Runtime
does not query Recording's schema. `RecordingFacts` implements Case's existing
facts port; API and Worker CaseStore share the caller Connection, `read_executions`,
`ProducedReader` and `stored_adapter_factory`. API command timeline lookup and
Worker T2 use a short-lived RecordingService on that caller Connection. A lazy
repository facade allows Case-only reads and failed Coarse T2 without requiring
media files/root to be inspected.

Execution media uses a separate RecordingService per execution, closed by its
context manager even on failure/cancellation. Repository operations use short
Runtime-owned transactions and return detached data; file inspection, encoding
and provider I/O do not hold a DB checkout. ProductionMediaFactory follows public
get_media_stream / owns_asset / resolve_span / observe_time_sources /
prepare_analysis_source_from_resolution, with cooperative checkpoints between
capabilities, then Search's RecordingAnalysisSourceResolver and public factory.
Case-selected VIDEO refs are required and ownership is checked before inspecting
the media. The currently supported input is one explicit TIMELINE_RELATIVE range;
the Runtime does not pick an arbitrary stream or infer another scope.

Recording's module factory consumes a mapping with
`DAESINGO_RECORDING_ANALYSIS_PROFILE_REF`, `DAESINGO_RECORDING_ANALYSIS_HEIGHT`,
`DAESINGO_RECORDING_ANALYSIS_PRESET`, `DAESINGO_RECORDING_ANALYSIS_CRF` and optional
`DAESINGO_RECORDING_FILENAME_OFFSET`. No profile keys means media composition is
disabled; partial/invalid profile configuration fails startup. Encoding defaults
or a filename timezone are not invented. Runtime forwards module mappings and
does not interpret provider secrets or profile semantics.

Durable prepared media is opt-in (`durable_prepared=True` via the Recording
factory). Legacy default ephemeral lifecycle remains. Recording's existing
InnoDB generic entry table stores immutable prepared metadata, verified MP4 body
descriptor and optional case association atomically. No migration/schema change
was needed. A content/metadata fingerprint supplies a stable opaque ref;
observations preserve first stored candidate identities across service/process
restart. Original source paths remain under Recording's existing storage root.

AnalysisSource bytes can be restored through the existing public
`open_analysis_source`. IncidentClip model/body durability is tested inside
Recording, but **no public open_incident_clip API is added**; existing compatibility
explicitly requires that surface to be absent. Clip/readout orchestration remains
outside this slice. Durable preparation can outlive a failed T1; retention/orphan
deletion policy is not changed. Repeating materialization can repeat encoding,
although identical output has the same immutable ref. No encode-cost elimination
or large-object throughput claim is made.

The new facts listing preserves external source lineage and clip provenance.
Known metadata without verified content is UNKNOWN rather than falsely AVAILABLE.
Legacy `lookup_asset_facts` unknown/error behavior is preserved; the detached
listing performs its own metadata fallback. RemoteCopy is not an AssetFacts kind.

Search handlers return the actual module payload/ref to the existing RT-10(a)
object store. The Worker persists object + terminal + produced in the same T1;
rollback and COMMIT-unknown identity checks remain unchanged. FAILED Run keeps its
real receipt, exceptions do not fabricate Runs, PARTIAL is execution success.
Execution UsageSink is passed unchanged; the handler does not finalize it.
Public Search helper application is limited to Search capability results/errors.
Runtime load/checkpoint/factory/transaction/persistence/serialization failures are
not mapped as Search failures. SQLAlchemy errors bubbling through a capability,
UsageError and cancellation propagate before the helper. Ownership fences,
timestamp ordering, late-result guards and existing T2 redelivery are unchanged.

## Direct execution evidence

All following runs belong to this composition task and are preserved separately
under excluded `.codex-scratch/rt10b-composition-20261026/`. Earlier Search adapter
runs/snapshots and remote PR CI remain historical evidence, not these local runs.

| Check | RED / intermediate failures | Subsequent result (one execution each) |
| --- | --- | --- |
| Durable facts, restoration, persistence-error boundary | corrected RED: 6 FAIL / 24 PASS; initial import mistake retained | 70 PASS / 2 existing real-video SKIP |
| Real MySQL durable prepared objects / transaction facade | 4 FAIL | 4 PASS; final expanded current file 6 PASS |
| Production media / explicit module config | 10 FAIL; later test-double and explicit-VIDEO-ref failures retained | 33 PASS |
| Stored API/Worker Case adapters / normal, FAILED, PARTIAL T2 | initial collection error, then 4 FAIL | 4 PASS |
| Bootstrap / default reflector | 2 FAIL / 8 PASS | 53 PASS |
| Legacy facts/case links | 3 FAIL | 11 PASS |
| Source lineage / failed T2 without media | 1 FAIL each | 11 PASS |
| Separate API/Worker processes | 4 FAIL: test request omitted case_id | 4 PASS, 39.63 s |
| Related offline regression | 1 FAIL / 2253 PASS / 21 SKIP: prohibited extra clip API | **2254 PASS / 21 existing SKIP**, 970 deselected, 213.45 s |
| Related actual MySQL regression | 1 FAIL / 221 PASS: misplaced test tail NameError | **226 PASS**, 159.38 s |
| Current durable MySQL after removing extra clip API | separate follow-up | **6 PASS**, 3.41 s |
| Existing gate negative controls | bypass / JUnit / metadata mutation checks | **15 PASS**, 8103 deselected |

The removed clip API was not defended by changing the existing assertion. Strict
datetime restoration, unsupported remote-copy facts and fixtures were corrected;
all intermediate failures, sandbox child-process failure, request/fixture mistakes
and the usage-limit non-executed approval attempt remain distinct records. No
failed run was merged with a later PASS. The default present-helper discovery
test now omits the override and supplies public callable attributes, covering the
previous review's P3 gap; an already-correct path is not claimed as a feature RED.

The offline selection is Search/Worker/Case/jobs/usage/Recording/Readout/API with
`-m 'not mysql'`. Its skips are four optional typer imports, two Case external
videos and fifteen Recording real-video opt-ins. Warnings: one existing
FastAPI/httpx deprecation and three malformed-usage serializer warnings. No
skip/xfail policy was loosened.

Actual MySQL covers existing Recording persistence/compatibility, new facts,
Search T1 object atomicity/rollback/unknown COMMIT, execution usage/cancellation,
API START_ANALYSIS/views, Case result reflection and production process E2E.
The 226-test run includes the four process cases; do not add those counts. The
final six-test follow-up overlaps that run and is not additive either.

Process E2E uses separate spawned API and Worker OS processes, real MySQL and
ffmpeg, production media/registry/T1/T2, and real SDK with MockTransport for the
external provider. API HTTP runs through ASGI TestClient in its child process,
not a TCP listener. Cases: normal, Coarse PARTIAL, Coarse FAILED, Fine FAILED.
The test explicitly invokes public Case Fine issuance after selection; it does
not prove automatic product orchestration or the excluded clip/readout jobs.
The confirmed-policy test port does not prove merged #403 integration.

JSON/JUnit audit verifies unique complete selection, successful setup/call/teardown
and no skip/xfail for 226 tests/678 phases, six/18, and four/12 respectively.
Removing an actual JUnit entry is rejected by the unchanged validator. Its full
inventory check intentionally rejects each subset for missing required roles;
**full strict MySQL gate is not PASS**. Boundary violations 0; Contract fixture
structure/JSON/meaning 62/26/104 PASS; diff whitespace check PASS. Contracts,
Case/Search/Readout/jobs source, gate/inventory/workflows remain unchanged from
the checked-out base. Workflow 30 minutes and nested MySQL 900 seconds remain.

Whole pytest, entire mandatory MySQL/nested wrapper, entire gate mutation suite,
live paid provider and remote CI of this uncommitted diff were not run. Related
offline (~213 s) and DB (~159 s) coverage includes the changed boundaries; repeating
unrelated inventories does not settle pending #403/#405. Large MP4/BLOB limits,
provider production behavior and multi-range media remain acceptance limits.

## Resources and review handoff

Owned MySQL 8.4.7 stopped; the exact owned datadir was removed and its port refused
connections. Before shutdown only system schemas/default accounts plus the owned
base schema remained; non-audit clients, transactions and data locks were zero.
Child processes joined. Two new empty root cleanup lock files were exclusively
opened, backed up and removed; no preexisting file was deleted. Shared runtimes,
old evidence and backup material were retained.

Plans, all scratch/RAW/JSON/JUnit/cache/runner/temp/DB and review-package artifacts
are PR-excluded. No stage/commit/push/PR/new branch/worktree. A fresh reviewer
without this conversation's implementation history is the next authorized step;
its actual result will be appended. Pending owner decisions stay pending.

## 2026-10-26 — fresh read-only review and P2 correction

One new independent reviewer was started with `fork_turns=none`, receiving the
requirements, base and 40-file manifest rather than implementation history.
It confirmed all hashes, HEAD/branch and empty index. It read the whole bounded
draft, SoT/current remote agreements and preserved reports without running tests,
DB or validators, creating another agent, or changing files. Initial result:
**P2 one, P1 none, no additional P3**. This is a static review, not merge approval.

The P2 was an actual boundary gap: Runtime `TransactionRetryExhausted` is a
RuntimeError, not SQLAlchemyError, so a transaction exception propagating through
an injected Search resolver/gateway could enter the Search helper. A scratch
reproduction with `outcome_unknown=True` returned SEARCH_UNCLASSIFIED instead of
the existing RUNTIME_HANDLER_ERROR. It does not imply every current local media
execution takes that path; the normal prepared source uses local execution state.

After the review, only search_handlers.py and its failure-boundary test changed.
The fix rethrows the four existing explicit Runtime transaction exceptions before
the helper: BeforeCommitFailure, CommitOutcomeUnknown, TransactionBoundaryError
and TransactionRetryExhausted. It does not exclude RuntimeError as a whole or
alter common DB runner/registry/T1 semantics. Regression covers six DB failures
across HINT/Coarse/Fine/resolver and the actual transaction runner exhausting
three disconnected acquisition attempts, checking zero helper calls and resource
closure. First RED was 21 FAIL/4 PASS including one test sleep-injection mistake;
corrected RED2 was **21 FAIL/4 PASS**, all expected classification failures.
Minimal fix: **25 PASS**. Related handler/input/media/bootstrap/Recording factory
and DB transaction offline regression: **167 PASS**, 12.59 s. These are separate
direct runs, overlap earlier suites and are not added to their counts.

The same independent reviewer then checked only that two-file delta read-only,
confirmed the follow-up 40 hashes/remaining 38 files unchanged, index empty and
HEAD/branch unchanged, and judged **P2 resolved, no new P1/P2**. It did not run the
tests. There was no second reviewer or additional agent. Before this result was
appended, the author checked the delta was limited to those two source/test files.

The earlier 2254-test offline and 226-test MySQL runs precede this final exception
guard change. They remain preserved direct evidence at that source revision;
they are not relabeled as post-fix executions. A full repeat or new MySQL server
was not needed for the guard-only change: no SQL/lifecycle/transaction algorithm
changed, and the 167-test focused run includes its real runner exhaustion path.
Boundary/Contract fixtures/diff and JSON/JUnit omission audit were rechecked.
The failed RED/setup runs remain distinct. The previously listed whole-suite,
live-provider and remote-CI non-executions remain in force.

Declined to judge remains: merged #403 integration and pending HINT taxonomy,
#405 terminal policy, excluded clip/readout/export/automatic product orchestration,
large media/BLOB and Search internal temp/SDK lifecycle under production load,
whole pytest/full mandatory MySQL/current-diff CI. None is counted as acceptance.
The new guard does not resolve these Owner/dependency questions. Current remote
reads still show #297/#303 open with the same sink/helper agreements, no new
#403/#405 answer. Final state: **IN_PROGRESS · Refs #297 (RT-10(b))**, all edits
unstaged/uncommitted, no push/PR/new branch/worktree. Full 40-file inventory and
immutable review/evidence manifests are retained in excluded scratch; two local
plans and all RAW/JSON/JUnit/runner/temp/DB artifacts remain PR-excluded.

## 2026-10-26 — merged #403 integration / PR #407 CI reproduction

**IN_PROGRESS · Refs #297 (RT-10(b))**. The new user request is limited to the
merged Search helper/default registry integration and the four failed PR #407
process cases. #405 STALE exhaustion notice/receipt/Case policy stays excluded.
This follow-up supersedes the earlier dependency status without editing history.

The initial checkout was clean on codex/rt12b-observability at
`42a4712d7f63eda64f3fd9766ac6765caae9869a`. After confirming both tree and index
clean, the requested codex/rt10b-handler-registry branch was selected, also clean
at `52629d4b562ee4ef03070e39fb23e83f44dcaf62`. Remote PR #403 is merged at
`405512cd0c8b74fd602b9557668f8603fd9d286e`, the fetched origin/develop. The
branch and incoming changes have no overlapping paths from their common base
42ddea72. A no-commit merge completed without conflicts; no semantic choice or
conflict resolution was performed. Its automatic index changes were unstaged.
HEAD remains 52629d4b, MERGE_HEAD is 405512cd, and the merge is deliberately
uncommitted with an empty index. Incoming web/Search files belong to that upstream
integration; they are distinct from this task's authored test/document changes.

Remote evidence is separate from direct execution:

- PR #403 head `8a5413109575631f8b0e0e8664274c96f443d325`: python-tests run
  40253669661 and boundary-check 40253669630 succeeded. These are predecessor
  head CI results, not CI of this uncommitted integration or a merge-SHA CI claim.
  The Owner follow-up 6406363557 covers intent auth/spent-budget correction.
- PR #407 head 52629d4b: python-tests run 40230798384 / test job 121281892941
  failed. normal/partial/failed/fine_failed each reported HTTP calls 0 instead
  of 1. The nested actual-report test failed from those same four child cases;
  the full remote result was 5 failed / 12182 passed / 33 skipped. The subsequent
  MySQL execution-gate step was skipped. This run remains failed permanently;
  later local passes do not relabel it.

The three real helpers now import from daesingo.search and default registry
discovery already works; no additional production dispatcher/taxonomy code is
needed. The process helper's temporary ConfirmedPolicyPort was removed. It now
calls compose_search_registry with no failures override. New offline checks use
the installed helpers for HINT/Coarse/Fine and observe that Runtime input,
transaction, persistence and checkpoint errors never reach the Search error
helper. Their first three failures came from a mismatched test context/sink, not
a production defect; that setup run is retained separately and the corrected
characterization is 15 passed. Search results/exceptions keep Owner mapping;
there is no local reclassification.

The actual CI failure was reproduced locally: Windows original cases passed,
while Ubuntu ffmpeg/ffprobe 6.1.1 produced the same four HTTP-0 failures
(linux-process-baseline: 4 failed, 203.25 s). Scratch exception tracing identified
Recording output validation's missing final frame duration/pkt_duration. Probe
snapshots show both generated H.264 MP4 variants (with/without B frames) fail this
existing strict check, whereas generated MPEG-4 AVI passes with observed coverage.
Recording's policy is not loosened and no frame tail is invented from fps or
container duration. The integration fixture now uses that supported AVI input,
with matching filename suffix/MIME; generated media, public preparation and real
Search media conversion remain in the test. This does not certify general H.264
MP4 compatibility on old ffprobe; that existing limitation remains explicit.

Process tests retain HTTP exactly 1 and pool checkout 0 assertions, add expected
terminal status/failure-kind diagnostics in the private test pipe, and add a HINT
scenario. It runs a separate HINT Worker, observes Case's existing T2 issue Coarse,
then uses separate Coarse/Fine Workers. Fine selection/issuance is still explicitly
performed through Case in the test; Runtime does not acquire orchestration policy.
The existing HTTP public-field privacy assertions remain in force.

Direct evidence at this checkpoint (overlapping runs are not added):

| Execution | Result |
| --- | --- |
| Initial merged import/boundary baseline | 73 passed |
| Real helper/default integration + Owner SDK auth/timeout/usage checks | 151 passed, 6.19 s |
| Related Search/Worker/Case/jobs/usage/Recording/Readout/API offline | 2328 passed / 21 existing skipped / 970 deselected, 327.87 s |
| Actual MySQL T1 payload/rollback/unknown COMMIT, usage/cancel, stored T2 | 72 passed, 58.99 s |
| Windows process cases, now real default helpers + HINT | 5 passed, 91.22 s |
| Unchanged gate bypass/JUnit/parameter mutation controls | 14 passed (earlier overlapping subset 4 passed) |
| Boundary / Contract fixture / diff | violations 0; 62/26/104 checks; diff PASS |

The offline skips remain four optional typer imports, two external Case videos
and fifteen Recording real-video opt-ins. Warnings are the existing one
FastAPI/httpx deprecation plus three malformed-usage serialization warnings.
No skip/xfail policy was changed.

An intermediate file named linux-process-green is **5 failed**, not a pass: after
fixing the media fixture, WSL shared-filesystem I/O caused peer response timeouts
(472.50 s). The subsequent traced AVI normal run also timed out. These runs are
retained as failures. No timeout was raised: Ubuntu packages were extracted only
into owned test scratch, then the tools and temporary media were placed in an
owned Linux-native /tmp directory. Same-code normal then passed in 92.25 s with
the original per-peer timeout. The complete Linux-native matrix is still running
at this chronological checkpoint; its result will be appended below.

### Final direct validation and resource audit

The complete Linux-native run finished **5 passed, 474.95 s**: normal, partial,
failed, fine_failed and hint. It uses the same Ubuntu ffmpeg/ffprobe
6.1.1-3ubuntu5 reported in PR #407 CI. No code changed between the Windows and
Linux final runs; the latter changed only test tool/media filesystem placement.
The first same-code native normal check overlaps this run and is not additive.
The prior five-test WSL timeout execution remains failed, even though its filename
contains green. These distinguish the original fixture failure from local test
environment delays; neither was hidden by larger timeouts or fake capabilities.

The final direct DB reports are 72 tests/216 setup-call-teardown phases, Windows
process 5/15 and Linux process 5/15. Each has unique complete collection/selection,
all phases passed, no collection error and no skip/xfail. The unchanged JUnit
validator accepts each report; removing an actual JUnit testcase is rejected.
The full inventory validator rejects each subset for missing required roles,
so **the full strict MySQL gate is not PASS**. All production source and protected
Contract/gate/harness/workflow paths match the conflict-free integrated snapshot.
The authored changes are tests and chronological documentation only.

Whole pytest, the full mandatory MySQL/nested wrapper, the entire gate mutation
matrix, live paid provider, broad media/BLOB acceptance and current-diff remote
CI were not executed. Related offline 2328 tests, helper-focused 151, actual DB72
and both-OS process matrices cover this integration. Repeating the full remote
inventory would duplicate those checks and cannot produce CI evidence for an
uncommitted/unpushed revision. The previous remote #407 failure is not cleared by
these local results. Workflow 30 minutes, nested MySQL900 seconds, per-peer60
seconds and runner880 seconds were maintained.

Owned MySQL8.4.7 stopped, its exact datadir was removed and its port refused new
connections. Before shutdown, only system schemas/default accounts plus the
dedicated base schema remained; non-audit clients, transactions and locks were
zero. Process test peers joined. Owned Linux-native tools/media and the newly
downloaded host package cache were removed after retaining package hashes and
evidence. Two new zero-byte root lock files (unignored, absent in initial clean
checkout) were exclusively opened, backed up and removed. Shared runtimes and
earlier evidence were retained. All new scratch/RAW/JSON/JUnit/runner/probe/stack
and temporary DB material is PR-excluded.

#405 stays pending by the user's explicit scope instruction. Clip/readout/export
handlers, general old-ffprobe H.264 MP4 coverage and production provider/temp/SDK
lifecycle acceptance remain outside this bounded integration. No extra Runtime
mapping or T2/case_applied_at extension was introduced. The next step is one
fresh-context read-only review of this integration delta; its result will be
appended without changing the execution history. HEAD52629d4b / MERGE_HEAD405512cd
and empty index are retained, with no staging/commit/push/PR update.

### Usage-limit resume, additional develop update and review follow-up

The first fresh review turn stopped at an account usage limit and produced no
review verdict. On the user's explicit resume request, the author verified all
57 review hashes, HEAD52629d4b/MERGE_HEAD405512cd, empty index and no conflicts,
then resumed the same independent reviewer. Its read-only review found no P1/P2
and one P3: the new HINT scenario checked Coarse issuance but not the extracted
values. This is a coverage gap, not an observed production defect. The test now
also checks the public CaseView preserves vehicle="white car" and
situation="red signal" from the provider fixture. The review did not run tests.

A fresh remote read during resume found develop had advanced to
`a08d671547a9e1a79deac2464d0d0ae43f34f17f` (merged #395). The ten additional
paths include Search provider cut-off-response handling and its tests/experiment
notes/scripts. They do not overlap the six authored files. Both old/new automatic
merge trees were computed without content conflicts, all 57 current files were
backed up, and the additional paths were checked against the old tree before
updating. The first update attempt was refused because index stat data was not
refreshed; a direct update-ref of MERGE_HEAD was also refused by Git. Neither was
a content conflict or a successful update. The index was restored and authored
hashes remained intact. After refreshing stat data, the two-tree update succeeded;
the ten files matched upstream exactly and all six authored hashes remained
unchanged. The guarded pending-merge metadata was set atomically to a08d6715
(Git's update-ref does not accept this pseudoref), and automatic index changes
were unstaged again. No commit/rebase/new branch/worktree was created. HEAD remains
52629d4b; MERGE_HEAD and fetched origin/develop are now a08d6715; index empty.

Direct revalidation on this latest source, kept separate from the 405512cd runs:

| Run | Result |
| --- | --- |
| Real helper/SDK/usage/runtime failure boundary focused | 153 passed, 15.14 s |
| Actual MySQL T1/receipt/unknown COMMIT/usage/cancel/T2 | 72 passed, 52.42 s |
| Windows separate API/Worker normal/partial/failed/fine_failed/hint | 5 passed, 95.62 s |
| Boundary / Contract fixtures / diff | violations 0; 62/26/104 checks; PASS |

The latest five process cases include both new public HINT-value assertions and
the HTTP1/pool0/terminal/privacy checks. Latest DB evidence has 72 tests/216 phases
and 5/15, complete/unique/all passed/no skip-xfail. Actual JUnit omission is rejected;
full inventory still rejects these subsets for missing required roles. Production
source matches the latest automatic integrated snapshot; no authored production
code, taxonomy or policy change was added.

The earlier offline2328 and Linux5 runs remain evidence of the 405512cd source;
they are not relabeled as a08d6715 executions. They were not repeated wholesale
after the additional change: only provider error handling/imports and Owner tests
changed, while media/Runtime DB/worker code was unchanged. Latest focused153 covers
the new SDK length/content-filter exception cases, and latest Windows process5
and DB72 cover the integration paths. The eight-minute Linux matrix plus portable
tool reprovisioning/full offline repetition would duplicate unchanged platform
coverage. Full pytest/mandatory nested gate/full mutation/live provider/current
diff remote CI remain unexecuted; no full gate or remote CI PASS is asserted.

The second verification uses a separate owned MySQL server and distinct report/
readiness/CA/shutdown records; first-server evidence/log copies are retained.
Final cleanup and the same reviewer's read-only assessment of this additional
delta will be recorded below. #405 and the earlier excluded acceptance remain
pending. **IN_PROGRESS · Refs #297 (RT-10(b))**.


### Final independent read-only re-review and handoff

The same independent reviewer checked the additional develop delta and two HINT
assertions without inheriting the author's conversation. It confirmed the P3
resolved and found **no new P1/P2/P3**. It read all62 latest manifest hashes and
the2136-file integrated snapshot, verified all ten extra upstream files against
their a08d6715 Git blobs, and confirmed HEAD52629d4b/MERGE_HEADa08d6715, index empty
and zero conflict entries. It read author JUnit153/72/5, but did not run tests,
DB or validators, mutate any file/ref/index or create another agent. Its judgment
is limited static review, not whole RT-10 acceptance or merge/remote-CI approval.

Before recording this outcome the author rechecked all62 hashes unchanged. The
second owned MySQL8.4.7 also exited; its exact datadir is absent, port refuses
connections, only default system accounts/schemas plus the dedicated base remain,
and non-audit clients/transactions/locks are zero. Original-server log copies,
both execution histories and reviewed source snapshots remain separate. No root
lock residue or owned native media/tools remains; scratch evidence is retained
and excluded from PR scope.

Latest-source Linux full process execution, full pytest/mandatory nested gate/
mutation suite/current uncommitted CI, general old-ffprobe MP4/large media/live
provider/operational lifecycle, excluded clip/readout/export and whole RT-10
acceptance remain unexecuted or declined as documented above. #405 stays explicitly
pending. Final authored delta is six test/document files, separate from56 automatic
upstream paths (62 working-tree paths total). Final state is **IN_PROGRESS · Refs
#297 (RT-10(b))**, pending uncommitted merge with empty index; no commit/push/PR
mutation. The user receives the result before any integration publication.


### 2026-10-26 — PR #407 timeout: systematic investigation and bounded optimization

**IN_PROGRESS · Refs #297 (RT-10(b)).** The initial branch was
`codex/rt10b-handler-registry`, HEAD
`dac940dc2bb638a56df8fa03953c77c6f171ac96`, with an empty working tree and index.
No branch/ref/index operation was needed. Read-only remote checks confirmed the
same PR head, base/develop `1943cb51e2bd579a02f09d67f104f16c52666c88`, Draft,
MERGEABLE/UNSTABLE, boundary success and python-tests cancellation. No remote
workflow was rerun or PR changed.

The preserved PR log is run40321183978/job121566213929; the latest successful
develop push is run40320484510/job121563856235 at that exact base. The following
are GitHub step timestamps, except the explicitly named pytest summary:

| Stage | Successful develop | PR #407 | Interpretation |
| --- | --- | --- | --- |
| Setup/container/checkout/tools, excluding smoke | 53s | 59s | Sum of recorded setup step durations; +6s |
| Synthetic media smoke step | 3s | 4s | pytest itself 1.25s vs1.33s; both1 passed |
| Full pytest step | 1729s, SUCCESS | 1754s, CANCELLED | Incomplete PR duration is not a completed-suite regression delta |
| Full pytest summary | 12446 passed/33 skipped,1721.76s | Absent | No explicit failure or final summary in cancelled log |
| Following strict MySQL gate | 1s,1027 tests,skip0/xfail0 | SKIPPED | PR has no success evidence for this step |
| Whole job | 1789s | 1821s including cancellation/cleanup | Successful baseline already close to30min |

The PR's last full progress line is at12:45:37.2756209Z (97%,12312 outcome
characters); cancellation is at12:46:09.123704Z. No `F`/`E` appears in those
completed progress rows. This does not prove that an unfinished test passed.
Remote quiet output does not identify the active node. A fresh **Linux
collection-only** run has12610 items; removing135 added tests derives12475 base
items, matching the successful remote outcome count (module collection skips
are separate). This is a derived baseline order, not an executed base checkout.
Windows has16 extra OS-specific parameters and must not be used unadjusted.

Conditional on matching Linux collection/order and ordinary72-character pytest
progress flushing, the possible active range is teardown of item12312 through
the next unprinted block ending12384: redelivery12312-12343,
reflection12344-12383, and the first search-capability item12384. This is a
candidate range, not a recorded active-node diagnosis or evidence of a hang.

The same common-node block1081-1152 took741.282535s on develop and783.925966s on
PR (+42.643431s). It contains the nested real-MySQL test at1142 **and71 other
items**; captured child stdout hides the child/mutation boundary remotely.
The enclosing gate-unit block1153-9648 was173.452s vs172.184s: no increase there.
The new E2E neighborhood10441-10512 was25.744s vs81.334s; its last five common
items differ because of the five inserted scenarios, so55.590s is a neighborhood
comparison, not an exact sum of new test durations. Other new tests and
individual nested/mutation costs cannot be separated from remote quiet logs.
The five new E2Es also run inside the mandatory nested inventory. Evidence
supports aggregate budget pressure with added work, not a single blamed test.

A fresh synthetic diagnostic executed the existing complete mutation body,
without launching a DB or asserting actual-MySQL acceptance. Linux cProfile
measured232.17s before/73.72s after; deepcopy cumulative cost171.27s before/0.67s
after. Windows cProfile measured274.72s/144.69s. These instrumented local values
are not remote CI savings. An **unprofiled serial Linux pair** measured68.014s
before/40.442s after (27.573s lower). It used fresh995-node synthetic reports in
both arms, HEAD's mutation body vs the current body, and left both input reports
unchanged. All2842 generated artifact SHA256 values matched, including8415
parameter mutation records. Other local verification was running on this host;
these timings are diagnostic observations, not a controlled CI budget forecast.

The minimal change only reduces evidence copying: family omissions own the
filtered lists and retain read-only nodes; metadata omissions reuse the existing
single-node isolation helper. Every fresh nested invocation, inventory, JSON/
JUnit validation and materialized mutation XML remains. No product code,
validator, workflow, required check, skip/xfail rule,900s/30min limit, retry,
receipt or #405 policy changes. AST checks confirm identical integration
inventories and fresh-child/validation prefix; workflow/validator/harness/gate
unit source bytes equal HEAD.

TDD first failed because the omission helper did not exist (1 failed/2 passed,
0.62s), then reproduced the existing full-copy algorithm and failed on copying
retained evidence (1 failed/2 passed,0.66s). The optimized helper passed3 tests in
0.40s. RED outputs are preserved separately and not relabeled as success. The
full gate-unit/helper run passed8412 tests in383.37s (Windows, command elapsed
386.66s). Direct boundary check found0 violations; Contract fixtures passed
62 structure/26 JSON/104 semantic checks. Full fresh real-MySQL nested acceptance
was then started on a separate owned8.4.7 loopback server; its final result and
cleanup follow below. No previous JSON/JUnit/report is used as acceptance for
this change. Scratch RAW, JSON/JUnit, timing probes, profiles, runners and DB
materials are excluded from PR scope.

The complete outer pytest/current remote CI have not been run for this dirty
candidate. Focused gate units plus the full fresh nested inventory target the
only changed behavior and avoid another duplicate entire30-minute workload.
Remote active-node identity, exact per-new-test remote durations and whether this
optimization alone restores the30-minute budget remain unconfirmed. New remote
CI must complete the entire pytest summary **and** following strict gate under
the unchanged limits before any merge-readiness claim.

Diagnostic setup failures are separate from acceptance results: an initial
synthetic driver stopped with AttributeError because it assumed a unit-level
`write_junit` helper existed; it had not entered the mutation body. The corrected
scratch driver builds its own synthetic XML. The first unprivileged WSL
collection attempt was denied with E_ACCESSDENIED before collection and was
reissued with approved read-only host access. These attempts are not converted
to PASS or combined with the subsequent measured runs.


### Fresh MySQL/mutation completion and review handoff — 2026-10-26

The separate Windows pytest invocation passed the actual nested-gate parent:
**1 passed in966.96s** (command elapsed969.59s, parent call966.77s). Its newly
executed child has1027 selected items,3081 passed phases, no skip/xfail and
JUnit suite time838.736s. The subprocess900s bound is unchanged; the parent also
performs validation/mutations after that subprocess exits. The observed child
phase-report span is835.0s. The difference from the parent call includes child
startup/shutdown, report handling, validation and mutation; it is not an exact
isolated mutation timer and is not a remote timing comparison.

The child covers the five actual production-process scenarios, including
normal/partial/failed/fine_failed/hint. Their fresh setup+call+teardown times sum
to95.756s (22.018/19.054/12.066/17.435/25.183s respectively). Worker HTTP-call1,
pool-checkout0, real T1/T2/produced assertions were unchanged and executed.
All8415 parameter mutations and1501 metadata/family omissions were rejected.
The direct strict CLI accepts this new child's JSON/JUnit (exit0); separate
copies with one missing setup phase or JUnit testcase are rejected (exit1 each).
These intentional negative results remain separately recorded.

Collection-only inspection identifies1045 current MySQL-marked tests. The
nested1027 and the separately executed parent do **not** constitute a full
current MySQL invocation. Seventeen other unchanged tests were not rerun:
durable facts6, Case composition4, Search handlers3, Case execution-read/result-
reflection4. Full outer pytest and all-MySQL-in-one-process remain unexecuted;
the changed mutation path was exercised through the complete fresh mandatory
nested command plus8412 gate-unit/helper tests, with over22 minutes of local
verification command durations (the runs overlapped; this is not wall time).
Another full product regression would duplicate unchanged
code coverage. Remote develop's1027 gate count and this child's1027 are different
sets and must not be treated as interchangeable evidence. No former CI artifact
was substituted into the new nested test.

Owned MySQL8.4.7 completed its schema/account/client/transaction/lock audit,
shut down and removed its exact UUID datadir. Linux listener closure was verified.
Original evidence reports, RAW, JSON/JUnit, mutation XML, probes and runners are retained only
under ignored task scratch, excluded from PR scope. Other services/old scratch
were not modified. Final Windows port check and fresh independent read-only
review are recorded separately below.

There is no product/Contract/Accepted Decision/Baseline or CI-policy delta.
#405 STALE notification/receipt/Case policy stays pending. The remaining merge
blocker is a new remote full pytest plus following strict gate under the
unchanged30min/900s limits; local speedup is not proof this budget now fits.
No staging, commit, push, PR mutation or CI rerun has occurred.


Cleanup qualification: the Linux shutdown receipt confirms no client other than
the auditor (plus MySQL's system event scheduler), transactions0/locks0, only
system accounts/schemas plus the dedicated base, exited owned process and absent
UUID datadir; Linux connect_ex111. The initial Windows probe was denied10013;
approved host access later returned10035 after2s, so immediate Windows connection
refusal is **not established**. No shared WSL/forwarding service was changed.
This is a cleanup-observability limitation, not evidence of a surviving MySQL
process. A fresh reviewer will assess only the five-file uncommitted delta and
the separately labeled evidence; source/ref/index remain unchanged at handoff.


### Fresh independent read-only review result — 2026-10-26

A new reviewer with `fork_turns=none` checked only the five-file uncommitted delta,
its SoT and preserved evidence. It found **no P1/P2/P3** in that scope: the current
family consumers/validators do not edit retained nodes, single-node metadata
copy preserves original isolation, and the omission assertions/XML/fresh child/
limits remain intact. It independently read the raw hashes and JSON/JUnit counts,
while explicitly distinguishing these preserved author runs from its own read-
only inspection. It ran no tests/DB/remote CI and made no edits or subagents.
Branch/HEAD/index and all five manifest hashes were unchanged before and after
review. The author reverified all five before appending only this outcome and
its log entry; reviewed source snapshots remain in ignored scratch.

This is not whole RT-10 acceptance or a merge-readiness decision. Full current
remote pytest plus following strict gate, real CI savings and remote active-node
identity remain unconfirmed; #405 stays pending. Final delivery remains
**IN_PROGRESS · Refs #297 (RT-10(b))**, uncommitted/unstaged, with no branch,
commit/push/PR or CI mutation.


### 2026-10-27 — PR #407 second timeout: tail and unit-fixture investigation

**IN_PROGRESS · Refs #297 (RT-10(b)).** Initial branch was
`codex/rt10b-handler-registry`, HEAD
`bc45925595dd540012432cd6dabd90ddcf06c9b6`, working tree/index clean. No branch,
ref, staging, commit/push, PR or CI operation was performed. Read-only PR metadata
confirmed this head, Draft/MERGEABLE/UNSTABLE, boundary success and the new
python-tests cancellation. That commit contains the previous evidence-copy
optimization; its old investigation/review history above remains unchanged.

Current run40334969445/job121613963782 and preceding
40321183978/job121566213929 are preserved separately. A fresh remote query found
a newer successful develop run40331287437/job121601052393 at
`4295abfff7e89297a75762ba653678240c8280d9`. Compared with the former develop
baseline1943cb51, only three Case decision documents changed, with no code/tests.
That newer success is the primary comparison below; the old successful run and
its RAW remain a fourth, separately labeled series. Checkout was not updated.

| Recorded stage/interval | Previous PR | Latest PR | Latest successful develop |
| --- | --- | --- | --- |
| Setup step sum excluding smoke | 59s | 51s | 57s |
| Media smoke step | 4s | 4s | 4s |
| Full pytest step | 1754s CANCELLED | 1761s CANCELLED | 1693s SUCCESS |
| Same outcome1081-1152 block | 783.926s | 742.443s | 720.580s |
| Same gate-unit interior1225-9576 | 143.509s | 163.816s | 138.776s |
| Final full-pytest summary | Absent | Absent | 12446 passed/33 skipped,1686.74s |
| Following strict gate | SKIPPED | SKIPPED | SUCCESS,1027 tests/skip0/xfail0 |

The two interior rows are parts of full pytest, not extra stages to add to it.
Their inferred common-node endpoints match all revisions. The nested-containing
block includes the actual parent at1142 and71 other tests. A41.483s reduction
from the previous PR is observed for that whole block; remote logs still cannot
split child vs mutation cost or attribute the entire reduction to one function.
The unit interior increased20.307s, consuming part of that headroom. E2E/tail
blocks with the same numerical offsets have different endpoints after added
unit/new RT-10 tests; they are retained as neighborhoods only, not exact per-node
comparisons. The machine comparison records endpoint equality explicitly.

Latest final progress:12456 outcome characters (12427 dots/29 skips),98%, at
2026-10-26T14:25:54.3041261Z; cancellation14:26:23.0134016Z,28.709s later.
No F/E/xfail or final pytest summary was observed. A fresh untouched-head Linux
collection has12611 items. Under matching collection/order and normal72-outcome
flushes, possible active work is teardown of12456 or subsequent work through
12528 before its next progress line. Last inferred node is
`test_search_failure_boundary.py::test_persistence_error_propagating_through_search_is_still_runtime_owned[resolver-error5]`.
The73-item candidate window covers the remaining Search boundary tests, handlers,
handler MySQL/inputs, all sweep-worker tests, reconciliation/usage and first
usage-worker MySQL case. No particular remote active node or hang is confirmed.
The two newly authored unit guards below are outside this historical collection.

**Direct tail execution:** the last reported node plus all155 unprinted nodes
were run in exactly their original Linux order, checked by a collection plugin.
All156 passed in176.86s (command185.66s), with468 passing setup/call/teardown
reports and no skip/xfail. Per-node values and order are in the task's ignored
`tail-node-phase-summary.json`. Aggregate phase times include:

| Tail file group | Setup | Call | Teardown |
| --- | --- | --- | --- |
| sweep-worker MySQL31 | 19.380s | 101.433s | 1.282s |
| worker MySQL20 | 11.368s | 8.984s | 0.743s |
| Search handler MySQL3 | 3.297s | 8.200s | 0.132s |
| usage reconciliation MySQL6 | 3.049s | 4.693s | 0.195s |

Total observed phase time168.367s; other time includes collection/reporting.
The sweep subprocess tests are legitimate acceptance work, retained unchanged.
Local Linux/WSL filesystem, load and MySQL8.4.7 differ from GitHub, so these times
are not a remote remaining-time prediction. No product wait/lease/cleanup or
process coverage was shortened.

**Confirmed avoidable costs:** the full pre-change unit/helper profile passed
8412 tests in167.78s. Numbered temporary-directory allocation6077 calls cost
28.983s cumulatively, with18425500 find_prefixed generator calls/resumptions
(not an exact scandir-entry count) while finding suffixes;
this grows with earlier evidence directories. Role omissions redundantly deep-
copied newly built, independently owned synthetic reports; deepcopy304 top-level
calls/14889721 recursive calls cost23.677s. These are directly measured fixture
costs, not proof of the sole cause of the remote timeout. The remote overall
symptom remains accumulated work exceeding the existing budget.

**Minimal TDD change:** only this unit file allocates each parameter case's fresh
UUID directory through pytest's public factory, `numbered=False`, inside the
same managed base and with the same `junit.xml` writer/validator. It does not
change outer report destinations, artifact transfer/structure, CI orchestration,
retention settings, inventory, test identity/selection or acceptance checks.
Role omissions use their already fresh report without a second full copy.
No baseline/synthetic/actual validation result is cached or reused across runs.

The guards reject sibling directory scans and fresh-report deepcopy. Initial
Windows focused attempts omitted an owned basetemp and failed default temporary
root allocation; those failures are preserved and not called valid RED/GREEN.
With explicit new workspace basetemp, both old algorithms failed their intended
guards (2 failed,0.96s); the minimal implementation plus existing XML-call guard
passed3 tests(0.93s). Subsequent full Linux unit/helper profile passed8414 tests
in160.73s, preserving every former case plus the two guards.

Numbered allocations fell6077→8 and find_prefixed resumptions18425500→17; deepcopy top-
level304→5, cumulative23.677→0.091s. Whole-profile wall improvement is only7.05s:
concurrent local DB verification and observed filesystem stat time6.894→33.910s
plus subprocess waiting differ. These observations are not converted to a CI
speedup claim. A separate unprofiled serial pair executed all299 role and6069
parameter checks using the real pytest temporary-path allocator and fresh
synthetic reports:53.123→33.879s. All1734 generated mutation XML hashes matched.
That pair excludes whole-pytest overhead and actual MySQL acceptance.

Diagnostic postprocessing initially failed because pstats received a Path rather
than str after baseline pytest had already exited0; the driver failure and
pytest result are distinct. The existing profile was read without rerunning or
relabelling it. An initial byte-level invariant check also failed on an unchanged
CRLF checkout helper; raw/HEAD hashes, newline-normalized equality and empty Git
diff are recorded explicitly. No source change was made to that helper.

AST/normalized-content checks preserve unit inventories, every former
parametrization, the strict validator, mysql harness, actual mutation helper,
nested command/900s bound and workflow30min. No product/Contract/Decision/
Baseline delta, test exclusion, job split, timeout increase or required-check
change. #405 remains pending. The fresh actual nested/evidence validation and
resource cleanup results follow below; no old actual report is substituted.


### Fresh actual evidence, scope and cleanup — 2026-10-27

The post-change fresh real-MySQL nested parent passed1 test in697.52s (command
699.42s). Its newly executed child has1027 selected tests/3081 passing phases,
no skip/xfail, JUnit suite613.169s. All8415 parameter mutations and1501 metadata/
family omissions were rejected. The separate strict CLI accepts the new original
report/XML(exit0); copies with a missing setup phase or missing JUnit case each
fail(exit1), retained as negative controls. Original reports are kept untouched.
The five independent API/Worker production-search E2Es also passed in this child.
No earlier actual JSON/JUnit was used to satisfy acceptance.

These nested timings are fresh validation observations, not a measured effect
of the unit-only change: the changed unit file is not in the nested command.
The entire default outer pytest and all1045 MySQL tests in one invocation were
not run. Direct node-set comparison of the new nested, separate parent and tail
shows14 unexecuted MySQL nodes: durable facts6, Case composition4, Case execution-
read/result-reflection4. This coverage disclosure is not a combined full-suite
PASS. Complete affected unit/helper, mandatory real inventory/mutation and the
full requested tail were exercised; another full outer product regression would
duplicate unchanged product code and requires the new remote budget check anyway.

The owned MySQL8.4.7 audit showed only system schemas/accounts plus ci_tail_test,
only the auditor/system scheduler, transactions0 and locks0. Owned process exit,
exact UUID datadir removal and Linux connect_ex111 are confirmed. Windows first
returned connect_ex0 and a later bounded probe10035; no immediate Windows refusal
or protocol outcome was established. The listener query produced no listener
row and exit1, not affirmative port-closure proof. No shared WSL/forwarder/service
was changed and no surviving owned MySQL process was observed. This Windows
cleanup-observability limitation is explicit. Native tail/profile/pair directories
were scoped TemporaryDirectory allocations and removed at exit; task RAW, JSON/
JUnit, XML, diagnostics, profiles and runners remain ignored and PR-excluded.

Full changed-source boundary/Contract/diff checks and a fresh independent read-
only review of the new three-file delta follow. Current state remains
**IN_PROGRESS · Refs #297 (RT-10(b))**. New remote full pytest **and** subsequent
strict gate success under unchanged30min/900s are required before merge readiness;
if still cancelled, no timeout/job/inventory/required-check/artifact-policy change
is authorized by these performance observations.


### Fresh review P3 and retention compatibility follow-up — 2026-10-27

The independent `fork_turns=none` reviewer read only the new three-file delta and
preserved evidence, found no P1/P2 and one P3. It verified all three first-manifest
hashes and empty index. The P3 was a conditional behavior difference omitted by
the earlier naming-only description: with `tmp_path_retention_policy=failed`,
standard tmp_path removes each passed case directory, while a plain mktemp
fixture does not. Current CI's default `all` and external report delivery were
unaffected. The first candidate/review snapshots and finding remain preserved.

The author checked the installed pytest implementation, added a real subprocess
regression with one passed parameter case and one intentional controlled failure
(so session success cannot hide per-case cleanup), and observed the retained
passing XML RED:1 failed in2.55s. The fixture now delegates to standard tmp_path
for non-`all` policies; the default-all fast allocator remains identical. Focused
4 passed in2.43s includes the existing XML-call guard. The deliberately failing
child is an expected negative control, not a product/outer-suite failure and not
relabeled as PASS.

Final unprofiled Linux unit/helper execution passed8415 tests in113.68s. All8412
original cases remain, plus three guards; no skipped/failed/error JUnit cases.
This is a new execution with different instrumentation from167.78/160.73s, not a
comparable whole-suite speedup claim. The previously measured default-all core
functions are AST-identical after this compatibility follow-up; the53.123/33.879s
pair remains tied to its earlier source snapshot. The new retention guard itself
cost8.24s in this local final run, not an inferred remote cost.

The fresh actual nested/mutation execution above preceded only this unit fixture
compatibility follow-up. None of its selected code, validator, harness, actual
mutation helper or nested command changed; the unit file is not selected there.
Those results are not relabeled as a new run. Another697s actual repetition was
not required for this isolated unit-only branch. Full outer/current remote CI
remain unexecuted and merge-blocking. Follow-up read-only review of the final
three-file delta and result-only documentation follows.


### Final independent review and uncommitted handoff — 2026-10-27

The same independent reviewer, originally started with `fork_turns=none`, read
only the retention follow-up/final three-file delta and preserved records. It
confirmed the original P3 resolved and found **no new P1/P2/P3** in that scope.
Non-all policy delegation preserves standard per-case cleanup; default-all
allocator/report delivery and all original8412 cases remain. It independently
compared the RED/GREEN child XML (one passed parameter/one intentional probe
failure, no errors/skips), final8415 JUnit cases and actual-child selection.
It did not run tests/DB/remote CI or change files/refs/index. Original and final
review manifest hashes, branch/HEAD and empty index were preserved. The author
rechecked all three final hashes before appending only this result and its log.

This is not approval of the entire PR/RT-10 or proof of remote timeout resolution.
The latest remote remains CANCELLED with following strict SKIPPED. New full
pytest final summary and following strict success under unchanged30min/900s are
still required. #405 pending; whole outer/current remote validation and the14
unexecuted MySQL nodes remain disclosed. Source is uncommitted/unstaged on
bc459255; no commit/push/PR/CI operation was performed. Status remains
**IN_PROGRESS · Refs #297 (RT-10(b))**.
