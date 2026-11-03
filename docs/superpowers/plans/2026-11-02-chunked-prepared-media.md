# Chunked prepared media implementation plan and design

> **For agentic workers:** use superpowers:executing-plans; implementation stays in this chat. A fresh read-only reviewer reviews the final diff.

**Goal:** reduce prepared-media SQL command/result working sets without changing public media identities, ownership, limits or retry policy.

**Architecture:** additive `recording_media_chunk` table; versioned descriptor in the existing prepared-content row. Serialize publishers on the canonical media row and publish chunks, manifest and case link inside a nested SAVEPOINT. Read one bounded slice at a time into an owned temporary file and validate length, SHA-256 and container signature before returning a detached stream.

**Tech stack:** existing SQLAlchemy Core, PyMySQL, Alembic, tempfile and pytest/MySQL 8.4.

**Spec:** user request attached to this chat; #530 head `fdcccfa9` P2-0b/0c and Decision Gate, #537, current source at `f1e8d82f`.

## Constraints and decisions

- Start: `codex/issue452-chunked-media-storage`, HEAD `f1e8d82f44e2bcf630a3f2fde009035f1436d7ec`, no worktree/staged changes. Normal checkout; use the user-designated checkout/branch in place. #538 merged at this HEAD, independently confirmed on GitHub.
- User delegates Runtime/Recording internal choices and asks for implementation now; proceed without additional design approval. No commit, staging, push, PR, external comment, CI trigger or merge.
- Compared: packet increases retain full-payload allocations; filesystem/object storage changes durability/backup contracts. DB chunks satisfy the requested existing transaction and backup boundary.
- Initial maximum chunk 256 KiB: worst-case escaping is 2 bytes per byte (confirmed PyMySQL hex path in #537 and installed driver inspection), with 16 KiB command/metadata allowance and an additional packet reserve. Never batch chunk INSERTs. Determine actual chunk size from session packet and a private injectable command budget; metadata commands are checked against that budget too.
- Existing `get_prepared_content` bytes callers (export materializers/snapshots) retain their interface as a documented compatibility allocation. Analysis stream and metadata paths must use bounded reads; no full bytes assembly there. Legacy BLOBs use SQL substring reads and server-side length/hash for immutable comparison.
- Anonymous TemporaryFile uses the configured Recording temp root (0600 on Unix), is closed on failure/cancellation and owned by the returned stream on success. It survives service close just as a detached BytesIO did. No durable file publication or retention policy.
- Caller owns outer commit/rollback. Failed SAVEPOINT cleanup must preserve the initiating exception and invalidate the unsafe connection so caller catch+commit cannot publish partial data. No new retries.
- Forward-only additive revision; no bulk conversion. New writes have NULL legacy content and are unreadable by old code: legacy read support does not authorize application rollback.
- Backup currently hex encodes BLOBs, groups extended INSERTs and captures entire dumps in memory. Bound dump statements with skip-extended-insert; retain and document whole-dump memory limitation.
- Resource preflight: initial available RAM 851,412 KiB / disk 3.27 GiB. Large 38,359,627-byte control deferred unless resources improve. Never use preserved `issue452-capacity-db`.

## Review focus

- Savepoint rollback/release failure, disconnect and deadlock preserve original DB classification.
- Equal/conflicting concurrent publishers and failed case association preserve immutable data and unrelated caller work.
- Oversized/corrupt/missing/extra/out-of-order chunks cannot escape integrity validation or leak files/cursors.
- Legacy reads and additive migration retain historical migration failure/downgrade tests.
- Detached stream cleanup, caller-owned connection lifetime, logical backup and empty-target restore.

## Tasks

- [x] 1. RED metadata-only projection and bounded stream/manifest validation tests; implement metadata projection and private stream helpers.
- [x] 2. RED actual MySQL command budget, savepoint failures, conflict/concurrency, detach and legacy/migration tests; implement chunk schema/publisher/read paths and update current-head assertions/inventory without changing historical semantics.
- [x] 3. RED backup statement bound; implement minimal dump option and directly run backup → empty dedicated target → re-open/hash verification.
- [x] 4. Run focused durable/service/Search/migration/backup regressions, Runtime quality/boundary/Contract/Ruff/diff checks. No full local pytest or mandatory MySQL sweep.
- [x] 5. Fresh independent read-only review, fix findings with RED→GREEN, same reviewer recheck; append Implementation Notes and Runtime Log evidence, limits, NOT_RUN/UNKNOWN/NOT_REACHED.

Final evidence and preserved failures: [Runtime Log](../../runtime/runtime-implementation-log.md) and
[Implementation Notes](../../modules/recording/chunked-prepared-media.md).
