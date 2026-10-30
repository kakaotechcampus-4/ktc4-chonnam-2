# RT-15(c) secret scan implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline. User instructions prohibit worktree creation, checkout, staging, commit, push, PR creation, comments and deployment.

**Goal:** Reproducible offline pre-deploy secret detection without disclosing findings.

**Architecture:** Pin Gitleaks 8.30.1 release archives, executables and upstream rules by SHA-256. A standard-library Python wrapper captures child output, emits only built-in rule IDs and counts, and never writes an original finding report. Scan a hardlink view of Git-managed/current nonignored files and full HEAD ancestry separately. No source copies or baseline. Fail closed on incomplete history, unsupported files, integrity errors and scanner errors.

**Tech Stack:** Python >=3.12, Git, Gitleaks 8.30.1; Linux/Windows x64.

**Spec:** Runtime Implementation Plan RT-15 and §12; Ops Spec §7/§19/§21; user request in this chat (non-disclosure and local-only completion constraints).

## Global constraints

- Keep quality, boundary/Contract, regression, mysql and test meanings unchanged.
- No provider validation, AWS/OIDC permissions, credential rotation or history changes.
- No broad repository allowlist, inline suppression or baseline. Strip upstream global path exclusions; document remaining built-in detector limitations.
- Full HEAD ancestry including root, side branches and merge resolutions; reject shallow/partial clones. No automatic fetch by scanner.
- Manual/reusable workflow restricted to this repository's develop ref; deployment jobs depend on it. No PR-triggered execution of fork code.
- General PR gate placement follows measured findings/cost, with unresolved findings blocking pre-deploy.

## Review focus

- Deleted/side-branch/merge-resolution secrets and depth-1 clones.
- Scanner failure versus findings; missing output or dependencies cannot pass.
- Inline/config/ignore bypasses and exact exception scope (initially no local exceptions).
- Credential-bearing paths, adjacent code, stdout/stderr, reports and artifact upload.
- Reusable workflow permissions and pre-deploy dependency propagation.

## Tasks

- [x] 1. Write real CLI synthetic controls before runner: clean/detect/clean, dirty tracked/untracked, ignored scratch versus tracked ignored path, history deletion/merge/root, shallow and tool failure. Observe RED.
- [x] 2. Implement pinned installer and fail-closed wrapper. Verify checksums, synthetic controls, counts-only report and captured failures. Run actual snapshot/history scans with no raw output.
- [x] 3. Add manual/reusable develop-only CI and pre-deploy dependencies. Preserve old CI meanings. Validate workflow with actionlint and focused tests.
- [x] 4. Update README, Implementation Notes and append-only Log with measurements, limitations, #301 acceptance mapping and pending remote CI.
- [x] 5. Fresh read-only reviewer without author history; fix findings and obtain same-reviewer delta confirmation. Run focused boundary/Contract/quality/diff checks and remove only owned temporary resources.

## Execution ledger

- Start: branch codex/rt15c-secret-scan, HEAD 6b116e4a1317dc8e5c13e34b05481107bc00ca21; tree/index clean. Fetched origin/develop identical, 1,519 reachable commits, nonshallow. PR #483/#484 merged; Issue #301 comments empty.
- Ruling: proceed inline under the user's explicit implementation request and Plan §12.3 delegation; no additional design approval or Git mutations.
- Ruling: select Gitleaks over TruffleHog (provider verification unnecessary/prohibited) and detect-secrets (baseline-oriented workflow would require separate history enumeration). Official evidence and integrity pins belong in Notes.
- Controls: first script-absent RED included one clone-setup error; corrected file URL. Hardlink controls require sandbox escalation on this Windows host, and fail closed without it. Final standard-library controls 14/14 PASS (41.910s).
- Ruling: per-file stdin alternative rejected after measured 0.704s startup/file and losing filename-dependent rules; retain read-only hardlinks, no source copies.
- Ruling: a synthetic Git -diff attribute hid a historical text secret (RED); force --text/--no-renames (GREEN). Disable replacement refs, reject grafts and partial history.
- Measurements: initial snapshot2314/file findings2 in12.98s; history1519/occurrences24 in69.38s, all generic-api-key, unclassified. No baseline, no source/paths revealed. General PR gate deferred; pre-deploy fails pending classification. Retest history after --text is in progress.
- Focused94 PASS (23.80s); standalone unit12 PASS. Boundary/quality/actionlint final verification and fresh read-only review in progress. Remote CI/deploy deliberately unexecuted.
- Final verification supersedes progress entries above: boundary/Contract PASS, import fixtures258PASS88.58s, Runtime Ruff and mypy Linux/win32 each87 files clean, new scripts/test Ruff and actionlint1.7.12 PASS. Final unit12PASS0.59s, author full16controls PASS59.792s.
- Final history after --text:1519commits/24occurrences76.41s, final snapshot2315files/2occurrences8.47s, both exit1. No credential classification or clean claim.
- Fresh reviewer directly original14controls PASS65.989s + unit12PASS0.59s. Confirmed local Git signature verifier execution P2, author independently reproduced RED then --no-show-signature fixed it. Same reviewer directly delta2controls PASS7.345s and code/workflow recheck: no remaining functional/security findings.
- Deployment-target ancestry binding was separately RED→GREEN; no reliance solely on live remote develop ancestry. Notes/log record nits fixed; same reviewer final document delta requested. Owned scratch cleanup pending; no Git mutations or remote execution authorized.
- Complete: same reviewer final documentation delta has no findings. Owned .codex-scratch/rt15c (tools/archives/synthetic repos) and the one failed sandbox TEMP removed after absolute-target checks. No remaining scanner views. No staging/commit/push/PR/deployment performed; actual findings and remote CI remain pending outside local implementation completion.


## Authorized exception/non-disclosure delta plan

- [x] Add test-first narrow exception and output/error sentinel controls; observe RED.
- [x] Bind A01/A02 to exact rule, hashed path, coordinates, exact detected-content fingerprints; keep all other findings/errors blocking. No baseline or rule/path disable.
- [x] Record investigation-only raw-output incident separately from product runner behavior; prevent unsafe diagnostic report modes and verify synthetic failure output.
- [x] Scan current files and full HEAD ancestry; verify same-position changed credential still fails. Run focused, quality, boundary/Contract, workflow and diff checks.
- [x] Same fresh reviewer delta, documentation/README/Log updates, owned temporary cleanup, leave unstaged/uncommitted.

A01/A02 baseline before modification: current2/history24 -> 2 exact-location items (A01 current1/history11, A02 current1/history13), both confirmed false positives; product runner still exit1. The private classification's temporary investigation helper printed a raw success payload. This was an output-procedure breach, independent of no suspected issued credential in these findings. Product counts-only runner was not its source. No raw values, code or detected paths are reproduced here.


Authorized delta evidence: exceptions-disabled control current2/history24 exit1/77.84s; exact template enabled current0+allowed2/history0+allowed24 exit0/77.09s (1519commits,2316files). Real reviewed-source clone2subtests PASS13.228s with same-width generic-value mutation current/history exit1. Final controls17PASS, unit29PASS1.75s; focused107PASS44.22s plus latest missing-execution/orchestration unit delta. Boundary/import258/Contract62+26+104/Runtime quality87 per platform/actionlint/diff checks passed. Same reviewer synthetic checks + direct28 and separate1 PASS, residual findings0. Product CLI/template never had the investigation raw report dump path; error boundaries hardened independently. Private original finding/source fields are not reproduced. Final post-document snapshot/owned cleanup/index check pending.

Final delta completion: post-document snapshot0/unhandled+2precise exceptions/exit0/8.47s; fullHEAD1519 history0+24precise exceptions/exit0/77.09s. Owned exception scratch/tools/helper/hash metadata removed after absolute/reparse checks, views0. Whole10-file whitespace/diffPASS, index empty, branch/HEAD unchanged. Reviewer final code/docs no findings, direct28 plus separate1 attributed accurately. Remote CI/publish/deploy deliberately not run; issue301 staysIN_PROGRESS.
