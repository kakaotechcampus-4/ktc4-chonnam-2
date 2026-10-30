# RT-14 deployment preparation implementation plan

**Status:** IN_PROGRESS · Refs #450 · Related #287, #460, #452

**Goal:** prepare reviewable deployment tools without accessing or changing AWS.
**Spec:** Issue #450, user request 2026-10-30, Runtime Plan RT-14, Ops §2/4-1/19.
**Architecture:** trusted develop-only manual workflows; CI-built amd64 ECR digest;
SSM to an explicitly installed root-owned controller; existing Compose services,
external existing volumes, protected versioned config files. No host builds.

## Constraints and rulings

- No commit/staging/push/PR/comment/dispatch or real AWS/service operations.
- Existing HEAD and fetched develop: `4876e646171ba9f0195de52d11741f3c39fb51a0`; clean index/worktree.
- #473–#477 merged; their historical CI is not verification of this change.
- RD-12b–e/h, RD-13a/c/d, RD-11a and actual RD-07c remain open in SoT.
  Tools implement a candidate path, require explicit owner-approved host policy;
  neither implementation nor a config flag constitutes owner acceptance.
- Ruling: ECR pull candidate follows user's CI/registry preference and avoids
  large repeated EC2 builds. S3 delivery and host build add no required value here.
- Ruling: migration failure leaves writers stopped and persistent dirty marker;
  no automatic rollback, retry, schema downgrade or volume deletion.
- Ruling: deploy from a pinned application image carrying its Compose source;
  host controller is separately installed/reviewed, never auto-updated by SSM.
- Ruling: no new public endpoint/domain/OAuth; internal read-only smoke only.
- Logging/restart/retention and disk budgets must be explicit approved inputs,
  never invented production defaults. CloudWatch resources are pre-provisioned.

## Work

- [x] 1. Tests first: immutable input validation, fixed subprocess diagnostics,
  SSM pending/success/nonzero/missing/timeout/cancel, exact account/role check.
- [x] 2. Implement safe OIDC/AWS orchestration and separate manual workflows;
  preserve regression/mysql/test and all existing required checks.
- [x] 3. Tests first: host lock, single migration, dirty marker, health failure,
  known-good atomic promotion, config-aware rollback, volume ownership guard.
- [x] 4. Implement host controller and image/runtime deployment preflight;
  actual Worker process registration marker, live/ready and read-only API smoke.
- [x] 5. Document protected inputs, minimum IAM actions/resources, exact commands,
  backup/media consistency, partial DDL recovery and capacity/retention pending.
- [x] 6. Focused tests, source/rendered Compose, boundary/fixtures/actionlint/diff;
  existing image/cache only if needed, no full local pytest/full MySQL.
- [x] 7. Fresh read-only reviewer without implementation history; regressions for
  findings, same reviewer recheck. Append notes/log and leave unstaged.

## Review focus

Untrusted dispatch refs and OIDC subjects; exception/CLI leakage; SSM delivery vs
execution; dirty or uncertain migration; old config/schema rollback; competing
deploys and operator recovery; unchanged media/DB ownership; synthetic vs actual
AWS/production evidence. Runtime memory/disk capacity cannot be inferred from
an empty Docker inventory.
