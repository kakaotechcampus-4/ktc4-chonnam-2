# RT-14 approved public deployment implementation plan

> Implement inline with superpowers:executing-plans and test-driven-development.
> User explicitly prohibits checkout/worktree creation, staging, commits, push,
> dispatch and AWS changes. Final review: fresh GPT-6.1 Sol, high, read-only.

**Goal:** Implement #450 approved §3 and design §13.6/§16.1; retain
`RT14_EXECUTION_ENABLED=false`; AWS/public acceptance remains pending.

**Authority:** [Owner approval](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/450#issuecomment-6522291826),
[follow-up](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/450#issuecomment-6522296524),
`docs/runtime/rt14-deployment-design.md`. No Gate reopening.

**Architecture:** Web build stage in the existing production image; revision
marker and content manifest, immutable host release directories; host Caddy
package separate from Compose; atomic symlink publication with durable journal.
Public smoke is a separate read-only CLI used after successful SSM and independently.

## Tasks

- [x] 1. Rollback: test pending/failed tip with successful target, rejected target
  CI/ancestry/digest, preserve secret-scan dependency. Change only tip gate selection
  in `deploy/aws.py`; tests in `tests/deploy/test_aws_deploy.py`.
- [x] 2. Artifact: test revision/manifest mismatch and unsafe files; implement
  `deploy/web_artifact.py`, `docker/web_release.mjs`, Docker build/context changes.
  Build real Web locally, validate the exact output; retain local image builds.
- [x] 3. State: add fault tests in `tests/deploy/test_ec2_deploy.py` for initial
  failure, pointer/state write/unlink interrupts and rollback. Implement journal
  snapshots, pointer verification/publication and fail-closed reconciliation.
  No automatic adoption, restore, downgrade or volume removal.
- [x] 4. Ingress: implement `deploy/public_smoke.py`, `deploy/Caddyfile`, protected
  DDNS updater and host service examples. Test DNS/TLS/HTTP/revision, no redirect,
  same-origin API errors and sanitized failure. Wire workflow post-SSM + smoke-only.
- [x] 5. Run focused deploy/secret/Worker, quality, boundary, Contract, actionlint,
  actual local Web build and loopback Caddy routing/TLS. Docker checks limited to
  changed artifact boundary. No repeated full pytest/MySQL.
- [x] 6. Update recovery/public runbook, Notes, README and Log with requirements
  matrix, all files, evidence and unexecuted acceptance. Fresh review and delta
  confirmation, final diff/staging check.

## Review focus

Target gate failure/cancellation/skip never becomes success; dirty journal and
pointer mismatch never silently adopted; first bootstrap preserves data; Web
manifest binds the exact image; TLS/redirect/proxy fallback cannot fake smoke;
private response/exception/argv never escapes. Test doubles are not AWS evidence.

## Execution ledger

- Start: branch `codex/rt14-public-deployment`, HEAD and GitHub develop
  `3819a5ddae6d1d446b79c7b1e644358b3680ba29`; clean index/worktree.
  #479/#483/#484/#488/#491 merged. #450 body and all five comments read.
- Ruling: user already approved design and inline implementation; no repeated
  plan approval or skill-required commits/worktree operations.
- Ruling: old Notes contain historical pending decisions. Preserve history with
  explicit dated supersession and operational links; approval is authoritative.

- Implementation: rollback 2 RED -> 33 GREEN; bundle 6 RED -> 6 GREEN;
  pointer/fault 6 RED -> GREEN; smoke 15 RED -> GREEN; DDNS 4 RED -> GREEN.
- Ruling: Caddy runs as host package; read-only bind mount of public-only releases
  gives Caddy access without widening protected /opt/daesingo permissions.
- Ruling: staging identity also binds manifest hash to exact image digest; reusing
  an existing revision cannot silently accept rewritten files+manifest.
- Validation: Linux final focused 106 PASS; Windows focused 136 PASS, guard delta
  58 PASS; Web 224 PASS (2 concurrent workers; no test policy changes), actual
  npm build, Docker Web stage and final COPY boundary, loopback Caddy PASS.
- Quality/boundary/Contract/actionlint/diff PASS; complete production image
  regression/mysql/test acceptance deferred to post-push CI as requested.
- Fresh reviewer: GPT-6.1 Sol/high, fork none. Initial no product findings;
  tuple test strengthened from reviewer observation, delta confirmation pending.
- Environment failures are kept separately: default pytest temp permissions,
  initial npm dependency missing, Web temp ENOENT and PowerShell OOM; scanner
  snapshot clean but history execution failure pending bounded-concurrency retry.

- Final: controls17 PASS; snapshot2331/history1535 findings0, existing exceptions
  only. Actual GitHub RT14_EXECUTION_ENABLED read false, untouched.
- Same-reviewer delta: 11 PASS, no remaining product finding. EOF whitespace fixed.
- Owned Docker image tags removed with exact ID checks; no shared cache/base
  removal. Changes remain unstaged/uncommitted. Actual AWS/public acceptance pending.
