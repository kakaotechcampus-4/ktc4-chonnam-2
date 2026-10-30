# Issue #465 media toolchain implementation plan

> Execute inline with TDD; retain all changes unstaged and uncommitted as requested.

**Status:** IN_PROGRESS · Refs #465 · Related #460

**Goal/spec:** Implement the Owner decision in Issue #465 and its Owner comment:
exactly matching FFmpeg/ffprobe 8.1, unchanged Recording strict validation, real
ordinary MP4 materialization, no #467 fixture workaround.

**Architecture:** Build official 8.1 source in a separate stage. Pin its verified
SHA-256, base image identity and Debian package snapshot. Copy only the two tools,
their required runtime dependencies and a generated binary identity manifest.
Container API/worker startup and an explicit preflight fail closed on unsupported,
mixed or altered binaries. Run ordinary 30fps MP4 through public Recording APIs in
the deployed image via Compose smoke and CI; preserve existing generic CI tests.

## Tasks and review focus

- [x] Verify official source signature/checksum and immutable image/package inputs
  before Dockerfile edits. Record source provenance and limitations in Notes.
- [x] Add failing deployment preflight tests for unsupported/mixed versions,
  configuration/hash mismatch, missing tools, and prevention of API/worker exec.
  Run RED; implement in `docker/runtime.py`; run GREEN.
- [x] Add a real public Recording MP4 acceptance helper using 30fps/default MP4
  timescale. Run it with old Linux tools for RED, then the pinned image for GREEN.
  Validate output frame duration/coverage and decode, IncidentClip and cleanup.
- [x] Replace apt ffmpeg in `Dockerfile` with the pinned source stage; preserve
  runtime UID/config/health budgets. Extend deployment policy tests as needed.
- [x] Integrate image media acceptance into `scripts/smoke_compose.py` and CI.
  Run Docker config/build/startup/readiness/smoke, focused deploy/Recording/media,
  AVI/MKV/fallback, #467 chain, boundary/Contract/workflow/diff checks.
- [x] Append Implementation Notes and Log with exact author/reviewer evidence,
  #460 commands, private-source availability, cleanup and excluded artifacts.
- [x] Fresh read-only reviewer without conversation history: inspect all changes,
  run focused checks, grade P1/P2/P3. Fix findings with TDD and ask same reviewer
  to recheck. Full regression/MySQL strict gate remain remote CI conditions.

## Constraints

No strict/coverage, timeout, skip/xfail, DB/migration/inventory policy changes.
No inferred frame lengths. No private originals, credentials, downloaded artifacts,
cache exports or raw/JUnit/scratch in delivery. No commit/push/PR or staging.

## Alternatives considered (implementer decision)

Use official signed source with pinned hash: selected for verifiable provenance and
same-build binaries. A third-party binary needs separate artifact and dependency
verification. Debian's existing package does not meet the Owner's exact 8.1 rule.
No additional product/Owner choice is required by this implementation detail.
