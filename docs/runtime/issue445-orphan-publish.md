# P-6 orphan publish — implementation notes

IN_PROGRESS · Refs #445 · Related #299. Deployment is deferred.

## Authority and starting state

2026-10-31: branch `codex/issue445-orphan-publish-cleanup`, HEAD and remote
develop `326f91334a4878b34135631e6b0e660b2c791b98`; index/worktree initially clean.
No repository AGENTS.md found; supplied AGENTS instructions and CLAUDE.md router
apply. Issue #445 has no comments. #299's closing comment explicitly transfers
P-6; PR #390 preserves publish and PR #409 adds observation only. Their historical
test results are not evidence for this change.

## Design and implementation choices

Only API upload publishes durable filesystem originals (`source/<uuid hex>`).
Recording `local_source` metadata registers their relative locator; prepared
analysis/incident, frame and derived content use Recording MySQL BLOBs. Worker
materializers produce temporary files under their existing leased temp root.
Product purge and BLOB lifecycle are outside this change.

The public Recording capability accepts one canonical managed relative publish
locator and returns REGISTERED, UNREGISTERED or UNKNOWN. SQL/connection failures
remain failures, never absence. Runtime consumes the public surface, not tables.
The repository uses a current locking read of local-source metadata, not a
consistent snapshot. NOWAIT contention is fail-closed, including an abandoned
client's still-live transaction. The caller owns transaction completion; runtime
uses a fresh short transaction and releases its connection before file deletion.

Reuse root-level OS leases: API holds a shared publish lease before upload and
through registration commit/rollback and cancellation cleanup. Scanner holds the
exclusive nonblocking lease through lookup and identity-checked deletion. A live
producer postpones the entire root. Locks are never removed or replaced. OS
crash release does not establish DB rollback: the current locking query must
also succeed. Query then unlink alone is not atomic; the cooperating writer
protocol and pinned filesystem identity provide separate necessary protections.

Only direct canonical UUID files in pinned source are candidates. Existing
staging/temp publish protection stays intact. Reject links, reparse points,
multiple hardlinks, changed identity/version and unprovable root relationships.
Do not infer identity from a locator. Relative canonical registrations protect
the name regardless of stored root-key spelling; noncanonical stored locators
make absence uncertain (potentially deferring the whole root).

Alternatives considered: age alone cannot protect stalled registration; a new
durable publish timestamp/table expands schema unnecessarily; per-file leases
require a new alias-safe lock identity. Reusing coarse root leases preserves the
existing tradeoff: active work can postpone unrelated cleanup.

B-C2 remains 86400 seconds and B-C4 startup plus 3600-second fixed delay. Adopt
mtime as an implementation choice consistent with existing cleanup; equality is
preserved. A backward wall clock delays cleanup; a forward jump may advance
age eligibility but cannot bypass registration/lease/identity checks. No new
operating profile, retention policy or byte limit is selected.

POSIX advisory leases require cooperating writers; arbitrary SQL/direct file
writers and mount namespace/bind aliases are outside that guarantee. Windows
uses the existing pinned handles and OS-confirmed alias normalization. Exact
platform executions, limitations, review and acceptance evidence follow below.

## Capability and ownership

| Boundary | Meaning |
| --- | --- |
| Public entry | `RecordingService.read_publish_registration(locator)`; exported `PublishRegistration` enum |
| Input | Exactly `source/[0-9a-f]{32}`. Invalid namespace, spelling, type or traversal returns UNKNOWN before repository access |
| REGISTERED | A durable local-source metadata row names this relative locator; do not delete |
| UNREGISTERED | Successful current read found no matching row and no ambiguous stored locator; not independent deletion authorization |
| UNKNOWN / exception | Invalid/unsupported result or locator is UNKNOWN; DB/connection/lock errors propagate. Composition maps only the exact enum to True/False/None; scanner deletes only for `is False` |
| Transaction | Caller-owned open MySQL transaction. `SELECT payload ... WHERE kind='local_source' FOR UPDATE NOWAIT`; no BLOB fetch, DML, commit, rollback, retries or file lookup in that method |
| Runtime composition | Fresh `run_api_transaction` on existing RC/UTC API engine, returned connection before unlink. Runtime has no new Recording table/schema query |
| Stale caller | Current locking read sees newer committed data under REPEATABLE READ even when the caller already established a stale consistent snapshot |
| Mock | In-memory repository returns UNKNOWN: it cannot establish durable cross-process absence |

This P-6 implementation request authorizes adding the capability; the decision
is visible in Recording README rather than silently treating the old Plan as
already imposing it. Runtime/Recording Owner and PR review must confirm its
documented scope and conservative tradeoffs. No Owner acceptance or Issue closure
is claimed here.

## Synchronization, failure and deletion conditions

1. API obtains shared orphan lease before staging creation; its monotonic
   idle/total clocks start before this wait. Existing staging lease still spans
   staging creation/receive/fsync/close/publish. Actual production filesystem
   writer is `api.upload.publish`; Worker does not publish these originals.
2. Root identity is checked before staging open and before/after publish. The
   route shields and awaits its registration worker even after asyncio cancel.
   `ApiComposition.register_source` also leases direct invocations, validates
   root after preprobe and completes the existing Case + Recording transaction.
3. Orphan scanner takes a nonblocking exclusive root lease. It opens source
   **through the leased media directory**, not an independent pathname reopen.
   Current media/source identities are rechecked before deletion. Only direct
   ordinary UUID files with one link and `mtime_ns < cutoff` are candidates.
4. Lookup must affirm committed absence. Pending registration rows cause NOWAIT
   failure and preservation. API has inserted local-source metadata before
   submitting COMMIT; a process crash/lost commit acknowledgement cannot convert
   an in-flight registration into a safe negative query. Tests distinguish OS
   lease release from the server transaction's later resolution.
5. After lookup/transaction end, reopen the leaf, compare device/inode, size,
   mtime/ctime, ordinary type, link count and directory entry version, then use
   the existing Windows delete handle or POSIX unlinkat. The exclusive lease is
   still held. A later cooperating registration waits and then rejects a file
   already deleted. Registered names are preserved even if their bytes changed.

Lock order is orphan lease → staging lease (receive) → file preparation →
Case lock → Recording DML (registration); staging is released before DB. Scanner
uses orphan exclusive → short Recording-only query, never Case/staging locks.
There is no DB transaction while waiting for filesystem leases or deleting bytes.
The existing repository constructor/prepared registration retain their existing
short filesystem metadata validation; expensive probe/hash/encode remains outside
checkout. `FOR UPDATE NOWAIT` may contend with another root's registration and
conservatively defer cleanup. Full local-source payload scans are O(registrations)
per candidate and deliberately avoid a new schema/index; large inventories can
delay uploads and cleanup. This is a documented implementation limitation.

Windows orphan uses native `LockFileEx` shared/exclusive byte-range locks; nested
route/composition leases and concurrent producers are permitted. Existing
staging/temp CRT locking behavior is unchanged. POSIX uses `flock`. Persistent
lease files are never deleted by the product. Process death releases OS locks;
unknown DB state is still protected by current reads. Access failure differs
from ordinary lock contention and does not spin indefinitely. Cleanup retains
startup, completion-relative interval, local duplicate-scan exclusion and owned
shutdown join; filesystem/DB stalls can still delay join.

| Observation | count / bytes / failed |
| --- | --- |
| Actual ordinary file removal | +1 / snapshot bytes after identity recheck / 0 |
| Registered, live root, young/equal age, unsafe link or changed leaf identity | 0 / 0 / 0 |
| Concurrent filesystem disappearance | 0 / 0 / 0 |
| UNKNOWN or any lookup exception, including FileNotFoundError | 0 / 0 / +1 per candidate |
| Metadata/delete error | 0 / 0 / +1 for the item; continue other entries |
| Root/lease identity or access failure | no deletion / 0 / +1 for root-level failure, or +1 per candidate when detected during item processing |

Events are `storage.cleanup.orphan.{count,bytes,failed_count}` with the existing
integer count field. Empty Context submission retains only timestamp, level,
service, event and count, never locator/path/filename/Case ID/exception text.
The API startup event test now requires **nine** exact cleanup events (previously
six staging/temp events); no existing assertion was relaxed.

## Direct verification and retained failure history

Evidence below is this task's own execution; counts from separate runs are not
summed. Raw outputs/JSON/JUnit/internal runners stay ignored in
`.codex-scratch/issue445/`. All media and DB schemas are synthetic and owned.

| Run | Direct result |
| --- | --- |
| `red1b.txt` → `green1b.txt` | Missing capability/scanner: 23 FAIL → 23 PASS |
| `red2.txt` → first focused | API wiring/lease: 2 FAIL; then focused1 192 PASS |
| `red3.txt`, `posix1.raw` | Lookup FileNotFoundError failed-count defect reproduced; Windows 1 FAIL/4 PASS and POSIX 1 FAIL/162 PASS/7 platform skips |
| `posixred.raw` → `posix2.raw` | Leased-root and post-query replacement: 2 FAIL, then 182 PASS/7 existing platform skips |
| `red4.txt` → focused3 | Lease wait omitted from deadlines: 1 FAIL; focused3 210 PASS after fix |
| `red5.txt` → `green5.txt` | Windows nested CRT lease: child 10-second timeout with outer lease held → native shared-lock regression/API 5 PASS |
| `mysql2.raw` | 16 new MySQL tests completed, then first existing HTTP test stalled on nested Windows lease. Verified owned pytest PID terminated; partial raw/run retained, not PASS |
| `mysql3.raw/.json/.xml` | MySQL 8.4.7: 50 PASS (new 16 + existing API upload 34), skip/xfail 0, all 150 phase reports PASS |
| `focused4.txt` | Windows: 246 PASS, existing Starlette deprecation warning only |
| `posix3.raw` | WSL Ubuntu POSIX: 185 PASS, 7 existing Windows-only skips, same warning |
| `mysqlposix.raw/.json/.xml` | WSL Python + actual MySQL 8.4.7: new 16 PASS, skip/xfail 0 |
| `red6.txt` → `finalstorage.txt` | Lock access failure miscounted as contention: 1 FAIL → final Windows orphan 33 PASS |
| `posixfinal.raw` | Final lock-access delta and POSIX orphan boundary: 31 PASS, skip 0 |
| Quality | Final `quality4.txt`: Ruff + mypy linux/win32 (87 source files each) PASS |
| Boundary/Contract/diff | `boundary2.txt`: 0 violations; Contract 62 structural/26 JSON/104 semantic checks PASS; `git diff --check` PASS |

`red1.txt` had scratch access errors, `green1.txt` had sandbox-denied hardlink
creation; they are environment failures, not product GREEN. Tests then used owned
basetemp and approved native filesystem access. The first boundary script failed
while printing an em dash through cp949; the same check passed with Python UTF-8.
Initial mypy Optional cleanup guard error was fixed without suppressions.

Negative controls are actual dangerous behavior on synthetic files: bypassing
the lease deletes an active pre-registration file; replacing the locking query
with a normal consistent read deletes an uncommitted registration's file.
The RR snapshot test also proves a normal query misses a later commit while
the public capability sees it. Thread Events/IPC Pipe handshakes control race
points; no sleep-based race assertions. Separate spawn processes cover publish
before DB, uncommitted/commit/rollback, crash before DB and crash with transaction.
An explicit test-only DB lock barrier observes dead-session resolution.

## Platform scope and remaining limits

- Windows execution used local NTFS synthetic files, ordinary/extended namespace,
  case/separator/dot/actual 8.3 aliases, junctions, hardlinks, readonly, pinned
  handle and process boundaries. Existing storage sharing/metadata/lifecycle
  tests also ran. No Windows skip was added or taken in focused4.
- POSIX source checkout is on WSL `/mnt/c` (v9fs); storage/lifecycle test basetemp
  is `/tmp/issue445-posix*` on ext4, confirmed with stat/findmnt. MySQL POSIX
  tests use scratch basetemp on `/mnt/c`. These are WSL Linux process/filesystem
  results, not tests on a separate deployed native Linux host or container.
- Arbitrary **noncooperating** POSIX directory/file renames between the final
  identity check and syscall cannot be atomically excluded by advisory leases.
  Detected substitutions fail closed; do not interpret that as universal safety
  against hostile direct filesystem writers, direct SQL inserts, bind mounts,
  mount namespaces, UNC/network filesystems or untested Windows filesystems.
- A noncanonical legacy/local-source locator makes absence UNKNOWN for unrelated
  names too. Ignoring root-key spellings and root-wide active protection can
  preserve an entire root. No cleanup throughput or disk-pressure guarantee.
- Root/lock replacement by external actors and coordination across DBs pointing
  at the same media root are not supported. Every deployed writer must use the
  same DB and lease protocol; old binaries must not concurrently publish without
  this lease. No mixed-version deployment was executed.
- No full pytest/full MySQL inventory/strict whole-suite gate or Docker build
  was run. Required inventory/checkers/timeouts/skip/xfail policies were unchanged.
  Final integrated whole-suite and remote CI remain conditions after user push.

## Fresh review

Fresh `GPT-6.1 Sol`, reasoning high, no conversation-history fork, read-only.
Initial P1 root reopening and P2 deadline/failure-accounting findings were
reproduced and fixed; the same reviewer inspected deltas and the new Windows
shared-lock fix. Its subsequent judgment found no additional actionable defect
within the cooperative-writer model. Reviewer inspected author evidence and
directly ran only `git diff --check`; it did **not** execute the test suite.
Final documentation/small lock-error delta review found no remaining actionable
code finding. Its minor observation-table correction (root-level versus
per-candidate identity failure count) was applied without changing code. The
same reviewer confirmed this exact documentation delta with no remaining finding.

## Complete candidate file list

| Area | Files |
| --- | --- |
| API | `src/daesingo/api/composition.py`, `routes_sources.py`, `upload.py`, `README.md` |
| Storage | `src/daesingo/common/storage/_filesystem.py`, `cleanup.py`, `src/daesingo/common/README.md` |
| Recording | `src/daesingo/recording/__init__.py`, `mysql_repository.py`, `repository.py`, `service.py`, `publication.py`, `README.md` |
| API tests | `tests/api/test_api_cleanup.py`, `test_orphan_upload.py` |
| Storage tests | `tests/common/storage/test_orphan_publish.py` |
| Recording tests | `tests/recording/test_publish_registration.py`, `test_publish_registration_mysql.py` |
| Runtime docs | `docs/runtime/README.md`, `issue445-orphan-publish.md`, `runtime-implementation-log.md` |

## Issue acceptance evidence and PR/Owner checks

| #445 completion criterion | Evidence / remaining confirmation |
| --- | --- |
| Registered files preserved | MySQL committed/current RR reads, original API commit/unknown-commit regression |
| Active and young files preserved | Exact age equality, wall-clock tests, route/producer leases, process IPC and cancellation tests |
| Failed lookup / uncertain identity preserved | UNKNOWN/error tests, real NOWAIT contention, alias/link/root/leaf replacement tests |
| Only old unregistered publish removed | Strict mtime predicate + managed UUID direct files + successful exact verdict + final identity verification |
| Runtime does not query Recording schema | Public facade composition and unchanged boundary gate PASS |
| Safety/transaction/race/privacy tests | Focused Windows/POSIX + actual MySQL/process evidence above; remote whole CI pending |
| Notes/Log/P-6 decision | This note, Recording README, appended Implementation Log; Owner acceptance pending |

PR/Owner must confirm coarse-root/legacy-alias conservatism, mtime implementation
choice, common DB/all-writer protocol and current-read lock cost, then validate
post-push whole integrated CI. This session performs no staging, commit, push,
PR, external comment, merge, Issue closure, provider/AWS call, workflow dispatch
or deployment. RT14 variable was not mutated; its current remote value could not
be re-read because automatic approval review rejected that read as a provider
call. Historical false evidence is not represented as a new verification.

## Owned-resource cleanup and handoff

The task-owned MySQL server was identified by exact recorded datadir before
shutdown: non-audit clients, InnoDB transactions and data locks were all zero.
Its port closed, its exact `/tmp/issue445-<generated UUID>` directory and the
five explicitly named POSIX test temp roots were removed. No container/image
was created, removed or rebuilt. Eighteen Windows task temp roots were removed,
with zero matching roots remaining. The final Git audit is recorded in the
handoff evidence. RAW/failure originals/JSON/JUnit and small
diagnostic scripts remain ignored; other tasks' scratch/cache/images are intact.
