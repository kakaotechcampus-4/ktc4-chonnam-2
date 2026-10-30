# Issue #465 — MP4 deployment toolchain Implementation Notes

**IN_PROGRESS · Refs #465 · Related #460**

## Owner decision and investigated cause

[Issue #465](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/465)
and its Owner comment select exactly matching **ffmpeg 8.1 / ffprobe 8.1**.
`materialization.py` requires observed last-frame duration for ordinary MP4;
verified coverage is supplied only for the existing fallback/millisecond-MKV
paths. The Ubuntu 6.1.1 tools reproduce `마지막 frame duration 근거가 없습니다
(duration/pkt_duration 누락)` at **output** verification through public
`RecordingService.prepare_analysis_source_from_resolution`.

No Recording validator, duration/coverage inference, encoder argument, fallback
rule or #467 fixture is changed. #467's 10fps/1/10-tick input is a CI portability
fixture, not the ordinary MP4 solution. This regression generates 30fps H.264
MP4 with the muxer's default timescale and asserts it is not 1/10.

## Verified supply and reproducible build inputs

| Input | Identity / verification |
| --- | --- |
| Official source | [ffmpeg-8.1.tar.xz](https://ffmpeg.org/releases/ffmpeg-8.1.tar.xz) |
| SHA-256 | `b072aed6871998cce9b36e7774033105ca29e33632be5b6347f3206898e0756a` — calculated from downloaded bytes; Docker verifies with `sha256sum -c -` before extraction |
| Detached signature | [official .asc](https://ffmpeg.org/releases/ffmpeg-8.1.tar.xz.asc), directly verified with GnuPG: **Good signature** |
| Release key | [official key](https://ffmpeg.org/ffmpeg-devel.asc), fingerprint `FCF986EA15E6E293A5644F10B4322F04D67658D8`; matches upstream MAINTAINERS / [official fingerprint history](https://ffmpeg.org/pipermail/ffmpeg-cvslog/2015-October/094859.html). Local GPG web-of-trust remains unknown; no claim of locally certified trust. |
| Independent release identity | [official mirror n8.1](https://github.com/FFmpeg/FFmpeg/releases/tag/n8.1), tag object `a65b3bfe9dacc3b20597ef199d0afdd8bc8128e2`, peeled commit `9047fa1b084f76b1b4d065af2d743df1b40dfb56`; fetched and checked before image edits. Build uses signed release tarball, not a floating Git branch. |
| Python base | `python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337` — obtained from actual registry pull/inspect |
| uv build input | `ghcr.io/astral-sh/uv:0.11.15@sha256:e590846f4776907b254ac0f44b5b380347af5d90d668138ca7938d1b0c2f98d3` — actual pull/inspect |
| Debian packages | Signed Debian and Debian-security snapshots at `20261027T000000Z` (date recorded in base's apt source comments). Snapshot access and libx264-dev `2:0.164.3095+gitbaee400-3` availability checked before build. Historical expiry check disabled only for `apt-get update`; signature/hash authentication remains enabled. |

The same source/configuration invocation produces both binaries. Autodetection
is disabled; libx264, zlib and drawtext's font libraries are explicitly enabled. Separate stages keep
compiler, headers, source/downloads and uv cache out of runtime. Runtime installs
only libx264-164/zlib1g and the existing report-stamp capability's font libraries
(FreeType, HarfBuzz, Fontconfig, FriBidi plus DejaVu fonts), with their runtime
package dependencies; FFmpeg libraries are
statically linked into the two tools. No ffplay is built/copied. Base, source,
Python lock and package inputs are fixed; bit-for-bit final OCI digest equality
across platforms/builders is not claimed.

## #460 support / operator handoff

Supported deployment pair: **exactly ffmpeg 8.1 AND ffprobe 8.1 from this image's
same build**. No `>=8.1`, suffix, patch-release or Windows 9.x support claim.
The preflight hashes whichever binary PATH resolves against the build's generated
manifest, checks exact release tokens and matching configuration. API/worker
cannot exec on missing, altered, mixed or unsupported tools and emit only a static
`media_toolchain_invalid` diagnostic. Migration and readiness budgets are unchanged.

```sh
docker build --tag daesingo-issue465:local .
docker run --rm --network none daesingo-issue465:local ffmpeg -version
docker run --rm --network none daesingo-issue465:local ffprobe -version
docker run --rm --network none daesingo-issue465:local python /app/docker/runtime.py media-preflight
docker run --rm --network none \
  --mount type=bind,source="$PWD/tests/deploy/media_acceptance.py",target=/opt/media-acceptance.py,readonly \
  daesingo-issue465:local python /opt/media-acceptance.py
sudo python scripts/smoke_compose.py --evidence /tmp/issue465-compose.json
```

Preflight alone is not media acceptance. The helper executes registration,
relative timeline/span resolution, AnalysisSource bytes, explicit observed output
tail duration, strict coverage/decode, IncidentClip/provenance and cleanup. It
covers synthetic MP4/AVI/MKV and two ordinary MP4 sources concatenated through
public APIs. The regression CI job builds/runs the same deployed image with no
network in the acceptance container. Compose smoke runs preflight in API/worker
and actual media acceptance in worker after migration/readiness, before its
existing persistence/recovery checks. Test helpers are read-only mounts, not image
content. Generic distro-tool CI smoke remains separate and does not claim MP4
product support.

## Author execution evidence (2026-10-30, Asia/Seoul)

| Condition | Evidence / current result |
| --- | --- |
| Starting state | Branch `codex/issue465-mp4-ffprobe-81`; HEAD/local origin/develop/remote develop all `177505530cf6bc0f6575d846ae188a0868d4ae3e`; clean working tree and empty index before work |
| Linux old-tool RED | Ubuntu ffmpeg/ffprobe `6.1.1-3ubuntu5`, ordinary 30fps MP4: public AnalysisSource fails at output strict missing-tail check. Original immutable test input SHA-256 `5b2187d2557ff8a9cf4ba57b0d0a3f1d4c4b034ec897d50a4272f7b6d162da1f` retained outside repository for same-byte GREEN. |
| Preflight TDD | New controls RED 14 failures, then Windows unit file **17 passed**; Docker source pin policy RED then deployment/runtime files **72 passed** |
| Windows supplementary | Local **9.0.1**; synthetic MP4/AVI/MKV + MP4 chain AnalysisSource/IncidentClip PASS. Focused deploy/workflow/Recording/worker **296 passed, 1 existing opt-in skip**, 85.35s. This is not pinned 8.1 acceptance. |
| Structural checks | Boundary PASS; Contract structure 62 / JSON 26 / semantic fixtures 104 PASS; Compose source structural policy PASS; diff whitespace PASS. First boundary invocation had Windows cp949 output encoding error, rerun with UTF-8 passed. |
| Linux pinned image / same-byte GREEN | Pending build/acceptance; append actual result below, do not interpret pending as PASS. |
| Docker config/build/startup/readiness/media | Pending actual Compose smoke. |
| Linux fallback / IncidentClip / #467 chain | Pending pinned-image focused run. |
| Two actual MP4 types | Unavailable in the known local source folder / eval dataset folder (no MP4 inputs found). Private originals are not fetched, copied into repo or printed. No real-input or provider first-search success claim. |

Docker Desktop's Windows Linux endpoint was unavailable. WSL Ubuntu's existing
interrupted package configuration was repaired and its Linux Docker engine used.
A direct build from the Windows mount hit Docker sender xattr permissions; a
Linux-native temporary workspace with tracked delivery files was used instead.
An early archive extraction raced archive completion and failed; after archive
completion, extraction and build were restarted. These preparation failures are
not successful build evidence.

## Remaining gates, exclusions and review

No DB/migration/inventory changes: full mandatory MySQL was deliberately not rerun.
Full regression, mandatory MySQL and strict gate remain required **remote CI after
the user's eventual push**. CI is not run remotely in this uncommitted session.
No timeout, skip/xfail or strict-validation policy relaxation.

RAW/JUnit, scratch, temporary source archive/checkouts, synthetic MP4, GPG home,
credentials, Docker cache exports and private originals are excluded from PR.
Fresh read-only reviewer findings and directly executed commands/results will be
appended separately from author evidence. No staging/commit/push/PR/Issue mutation.

## Acceptance follow-up — author investigation

The first pinned image passed the same-byte synthetic MP4, ordinary MP4/AVI/MKV
and MP4-chain media helper, plus runtime tool/cache audit and six actual container
negative controls (API/worker/preflight, mismatched 8.1/5.1.9 and unsupported
8.0/8.0). Linux focused tests exposed **294 PASS / 2 FAIL / 1 opt-in SKIP**:
the test-only mount omitted pytest from subprocess import paths, and disabling
library autodetection removed `drawtext` used by the existing #467 report export.
The latter is a product regression of the initial build, not an accepted limit.
The existing export test and the extended deployment helper both produced RED;
the final build explicitly enables the font libraries above. Results after that
fix must be recorded separately below.

Compose 2.40.3 and 2.24.6 both rendered explicit `create_host_path: false` as an
empty bind object, causing the existing strict structural checks to fail before
resources were created. This matches compose-go's [bool `omitempty` field](https://raw.githubusercontent.com/compose-spec/compose-go/v2.4.0/types/types.go).
New **5 RED → GREEN** cases require a separately valid source with explicit
false, restore only empty rendered bind options for its approved mount targets,
and reject source omission/true, rendered true and unknown targets. Source policy
is unchanged; resolved validation does not mutate input. The whole deploy folder
then passed **129 tests**. Both unsuccessful Compose attempts remain FAIL evidence.

The pinned-image pytest launcher copies only pytest's test dependencies into its
disposable container and drops to UID/GID 10001 before executing tests. These
dependencies do not enter the shipped image. The Windows focused run's existing
skip is `test_opt_in_tail_only_real_pair_analysis`, requiring actual sources and
explicit placements; no skip was newly introduced.

## Delivery file manifest

- `.github/workflows/python-tests.yml`
- `Dockerfile`
- `docker/runtime.py`
- `scripts/check_compose.py`
- `scripts/smoke_compose.py`
- `tests/deploy/media_acceptance.py`
- `tests/deploy/test_compose.py`
- `tests/deploy/test_runtime.py`
- `docs/runtime/issue465-mp4-toolchain.md`
- `docs/runtime/rt13a-docker-compose.md`
- `docs/runtime/runtime-implementation-log.md`
- `docs/superpowers/plans/2026-10-30-issue465-media-toolchain.md`

## Final pinned-image author verification

Final source build with all required drawtext/font capabilities succeeded:
image ID `sha256:70a81faf778ad7c1f694426ae285a1ce3ae0f72982224dc2710ce9c5812ef900`.
This is a local verification image identity, not a pushed production digest.

- Same-byte RED→GREEN: the original 6.1-generated MP4, SHA-256
  `5b2187d2557ff8a9cf4ba57b0d0a3f1d4c4b034ec897d50a4272f7b6d162da1f`,
  passed public AnalysisSource / strict observed-tail coverage / decode and
  IncidentClip in final Linux 8.1. SHA-256 remained identical after execution.
- Final deployed helper: ordinary MP4, AVI, MKV and two-MP4 chain all PASS,
  including AnalysisSource, IncidentClip, report stamp and plate crop. Containers
  ran with `--network none` and default UID/GID 10001. The original fixed input is
  synthetic; helper's `actual_source` JSON key only means externally supplied
  input and must **not** be interpreted as real/private-source evidence.
- Final Linux focused run: **311 PASS, 1 existing real-pair opt-in SKIP, 26.14s**.
  Explicit selection: `tests/deploy`, `tests/test_ci_orchestration.py`, Recording
  `test_materialization_frame_duration.py`, `test_analysis_tail_policy.py`,
  `test_multi_span_analysis_source.py`, `test_multi_span_incident_clip.py`,
  `test_ci_media_smoke.py`, `test_exports.py`, and Worker `test_media_paths.py`.
  This includes AVI/MKV verified coverage, positive/negative fallback policy,
  IncidentClip, #467 single/chain/manifest/error/privacy and report/plate tests.
- Runtime audit PASS: both tools' `ldd` resolved; no gcc/cc/make/curl/uv/nasm,
  source/build directory, uv cache, apt lists or downloaded `.deb` files remain
  in runtime. Required dynamic dependencies and font data remain.
- Final actual container fail-closed controls PASS: matched manifest hashes for
  controlled mismatched (8.1/5.1.9) and unsupported (8.0/8.0) executables still
  blocked all API/worker/preflight entrypoints, six assertions, static error only.
  Separate unit cases also cover altered binary/hash, configuration differences,
  missing tool/manifest and version suffix/patch/9.x rejection.
- Final Windows deployment/workflow checks: **165 PASS, 17.84s**; final Windows
  9.0.1 helper also PASS with report/plate coverage. Source boundary, Contract
  fixture and whitespace checks PASS. README fact sections were compared with
  the changed workflow/build; no conflicting statement needed editing.

The full Compose smoke is still pending at this entry; its separate no-cache
build and subsequent migration/readiness/recovery results are not inferred from
the successful standalone image acceptance above.

## Resume audit — environment changed during interruption

On resumption, branch/HEAD stayed `codex/issue465-mp4-ffprobe-81` /
`177505530cf6bc0f6575d846ae188a0868d4ae3e`, with the same unstaged delivery files
and empty index. Local `origin/develop` had independently advanced to
`1a784b9d1bad14197f8779387be8ef7e4618fa44`; no merge/rebase/reset was performed.
Previous WSL `/tmp` workspace/report and the verification image were unavailable,
and the Docker engine observed on resume was 29.9.2 with Compose v5.6.1,
Linux x86_64. Previous directly observed test results above remain historical
execution evidence. The previous Compose run reached command/view successfully,
but its final report was not observed; full PASS/cleanup is not inferred.

A new isolated Compose smoke is running from a current delivery-only Linux
workspace, with its report persisted to ignored Windows scratch. New fresh review
has directly passed deployment/workflow **165 tests (10.47s)**, boundary, Contract
fixtures, Compose source structure and diff checks. Final smoke result and review
verdict will be appended after observation.

## Final resumed Compose acceptance and review evidence

**IN_PROGRESS · Refs #465 · Related #460**

The current-source isolated Compose smoke completed with process exit **0**,
report **PASS**, cleanup **PASS**. All ten recorded stages passed:
`compose_config`, `clean_build` (no cache),
`migration_failure_blocks_startup`, `clean_up_migration_ready`,
`pinned_media_materialization`, `cross_container_media_identity`, `command_view`,
`kill_stale_attempt2`, `inspect_secrets_settings`, `recreate_persistence`.
The cleanup report has empty `failures` and `remaining` arrays. Independent
post-run Docker label/name queries returned no project containers, volumes,
networks or tagged image. The no-cache image examined before cleanup was
`sha256:66ee0bccda379f71bd2948e711d57c2b8a5ed265c8f9e6271d5c8f2722a98883`.
It was not pushed. Raw report is ignored scratch, not a delivery file.

### Issue #465 completion-condition evidence

| Issue condition | Observed result / remaining boundary |
| --- | --- |
| MP4 first analysis, synthetic and two real types | Same-byte synthetic MP4 RED under 6.1.1 → strict AnalysisSource GREEN under pinned 8.1. Final Compose worker media path PASS. Two real types were unavailable; no real/private-source/provider first-search success claim. |
| AVI / MKV / fallback regressions | Author pinned Linux focused 311 PASS / 1 pre-existing actual-pair opt-in SKIP; fallback success/failure/strictness, IncidentClip, #467 chain/error/privacy/export covered. Final Compose MP4/AVI/MKV/chain + exports PASS. |
| Supported ffmpeg/ffprobe rule recorded | Exactly same-build 8.1, source/signature/hash/base/snapshot proof and #460 operator commands above; binary/hash/configuration/version mismatch fail closed. |
| Actual MP4 regression in CI or Compose | Both present: required deployed-image step in regression CI and actual Compose worker helper. Remote workflow execution still pending eventual user push. |

### Fresh read-only review, separately attributed

The first fresh reviewer had no inherited implementation conversation and directly
ran Windows deploy/workflow **165 PASS (17.29s)**, Windows helper PASS,
original pinned Linux helper/preflight/runtime/hash audit PASS, and narrow Linux
fallback/IncidentClip/#467 checks **58 PASS (5.29s), no skip**. Its final evidence
recheck was interrupted; those results remain historical direct reviewer evidence.

A new fresh read-only reviewer after resume directly ran:

- Windows 9.0.1 deploy/workflow **165 PASS (10.47s)** and supplementary media
  selection **146 PASS / 1 existing actual-pair opt-in SKIP (84.69s)**.
  These two disjoint reviewer selections total **311 PASS / 1 existing SKIP**.
- Current no-cache Linux 8.1 image above: standalone preflight **exit 0** and
  default-UID, `--network none`, disposable-container helper **all four groups
  PASS (6.29s, exit 0)**, including report/plate operations. The mounted helper
  SHA-256 `dc0eac44516197234f3bad909381f32c96391a44a58a4a51ca2be96333d2afb1`
  matched the reviewed checkout exactly.
- Boundary, Contract fixtures, source Compose structure and `git diff --check`
  PASS. Original Implementation Log byte prefix preserved and index empty.

The new reviewer initially attempted the old image ID, which was unavailable:
no Linux test executed in that attempt. Its subsequent successful current-image
run is separate evidence. Neither reviewer rebuilt, stopped, retagged or pruned
author resources. Current code review found no actionable P1/P2/P3; final
Notes/Log/report consistency recheck follows this appendix.

### Cleanup, exclusions and remaining gates

Downloaded official tarball/signature/key, public source checkout and transport
archives created for this task were removed from owned Windows scratch after
verification. The final Compose run removed its own Docker containers, volumes,
network and image. Shared daemon images/anonymous volumes/cache belonging to
other work were not removed; no global prune or cache export was performed.
Ignored raw reports, test output/temp files and small diagnostic launchers stay
outside the twelve-file delivery manifest. No credential or private original
was added to repository files or logs.

Full local pytest and full mandatory MySQL were not rerun; no DB/migration/
inventory change requires that duplicate work. Final full regression, mandatory
MySQL and strict gate remain **post-push remote CI conditions**. Windows pinned
8.1 and non-amd64 Linux were not separately validated. Actual two-type MP4 and
provider first-search acceptance remain unexecuted because originals were not
available. No timeout, skip/xfail or strict validation was relaxed. HEAD stayed
unchanged; all twelve delivery files remain unstaged/uncommitted, with no
commit, push, PR or external Issue/Notion mutation.

Final same-reviewer Notes/Log/report consistency recheck: **no actionable
P1/P2/P3 findings**. Reviewer inspected the persisted ten-stage Compose PASS /
cleanup PASS report, exact twelve-file manifest, unchanged HEAD, empty index
and original Log byte prefix. Full Compose execution is author evidence;
current pinned Linux helper/preflight and Windows selections are reviewer-direct
evidence as labeled above. No source fix or unresolved review finding remains.

After final review, the owned Linux temporary workspace `/tmp/issue465-work`
was also removed after resolving and verifying its exact path. Final diff check
is clean; HEAD and empty index remain unchanged.
