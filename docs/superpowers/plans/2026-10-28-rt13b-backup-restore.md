# RT-13(b) local logical backup / restore

**Status: IN_PROGRESS · Refs #300 (RT-13(b))**

User-supplied specification: this session's RT-13(b) request; canonical scope:
Runtime Plan RT-13/§12 and #300 Owner approval comment 6433879506.
Implementation is inline, TDD, followed by one history-free read-only reviewer
and follow-up review on that same reviewer. No staging/commit/push/PR/Issue changes.

## Design and constraints

Reuse the existing Compose services, helper guards and synthetic HTTP upload.
Add a host-side, standard-library-only logical tool using the MySQL 8.4 client's
existing read-only password file. Only `daesingo` is supported (the Compose DB).
Require stopped application writers, one container-local operation lock, and
exclusive artifact creation. Restore requires an empty database and exact local
migration heads. Use a versioned single-file envelope with length/SHA256 around
SQL; re-dump after import and compare all schema/data bytes before success.
The envelope detects corruption, not malicious replacement/authenticity.
Database-only backup retains no media bytes; acceptance retains the SAME media
volume and verifies persisted metadata/ref/bytes after a clean DB restore.

Alternatives: raw SQL lacks integrity/identity checks; physical volume copies
are outside the approved logical boundary. No production policy is introduced.
Existing migration, readiness, UID, secret, rotation and recovery semantics stay.

## Tasks / ledger

- [ ] 1. Write focused envelope, DB selection, collision, command failure,
  partial-restore, migration, duplicate/cancel and non-disclosure tests; preserve
  RED. Implement `scripts/backup_compose.py`; verify GREEN and deploy regression.
- [ ] 2. Write failing acceptance guard/probe tests. Add
  `scripts/smoke_backup_restore.py`, `tests/deploy/backup_probe.py`; reuse the
  RT-13(a) isolated project/cleanup guards and run an actual Docker restore.
  Seed case/upload + terminal job execution and compare durable identities,
  migration heads, tables, media refs/hashes, API ready and Worker dispatch.
- [ ] 3. Run relevant actual MySQL tests, boundary/Contract/workflow/diff checks.
  Keep original failures and distinguish unit tests, direct Docker execution,
  historical evidence and preserved-report inspection. No full pytest/MySQL/
  strict gate unless the user-specified expansion triggers apply.
- [ ] 4. Append implementation Notes/log and README pointer. Fresh read-only
  review of diff/SoT/tests/cleanup/privacy; fix P1/P2 through TDD and obtain
  follow-up confirmation. Leave worktree unstaged and report every remaining gap.

Review focus: cancellation while Docker exec continues; partial DDL failure;
wrong/forged dump identity; unrelated Docker resources and existing artifact
collisions; sensitive values in subprocess errors/evidence/diff.

Preflight (direct): branch `codex/rt13b-backup-restore`, HEAD/develop
`071bbcca53fc7381592abcb0df7bcb3060324aa2`, clean index/worktree; #417 merge
`61adb7c377719237e0b5659dd5c69bb4447220bc` is an ancestor. GitHub #300 body and
Owner approval retrieved. Engine 29.9.2 available through elevated read-only
check; Linux WSL root available. Sandbox-only access failures are not Engine
unavailability. User-selected repository/branch is used in place.

## Completion ledger (append-only)

Task 1: RED24 → GREEN24; final focused/deploy109PASS after review regression2.
Task 2: helper RED4; actual acceptance1 19PASS/cleanupPASS. P2 source-object
omission actual Engine RED2 (exit0) → GREEN2 (exit25); final code acceptance2
separately 19PASS/cleanupPASS, no summation across runs.
Task 3: boundary/Contract/Compose/workflow/diff PASS. Related MySQL original
85PASS/1FAIL (missing Windows helper env), failed-test-only rerun1PASS with
existing binary paths; original not relabeled. Full pytest/MySQL/strict not run.
Task 4: Notes/Log/README updated. Fresh reviewer initial P1=0/P2=1; same reviewer
source follow-up existing P2 fixed/new P1P2=0 and direct deploy109PASS. Final
acceptance2/audit evidence inspection pending. Owned Docker/temp resources
removed; shared caches/networks retained. No stage/commit/push/PR/Issue mutation.

Task 4 final: same reviewer inspected acceptance2/audit/documents and confirmed
existing P2 fixed, no remaining/new P1/P2. Reviewer direct deploy109PASS is
separate from preserved actual Engine evidence inspection. All four tasks are
complete within the authorized local scope; IN_PROGRESS #300 and uncommitted,
unstaged state retained. Full remote gates and actual cancellation fault
injection remain unverified and explicitly disclosed.
