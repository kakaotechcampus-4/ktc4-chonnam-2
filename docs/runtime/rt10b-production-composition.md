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
