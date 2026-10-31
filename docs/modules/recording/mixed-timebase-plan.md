# Mixed time base implementation plan

Status: IN_PROGRESS · Refs #425 · Related #452, #460.

Authority: [Issue and reproduction](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/425),
[MP4 observation](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/425#issuecomment-6490185400),
[Owner decision](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/425#issuecomment-6493673627).

Goal: preserve decoded frame PTS, duration, count and source provenance when
individually validated, same-geometry H.264 outputs have different clocks.
No fixed FPS, gap repair, tolerance increase, taxonomy or operational limit change.
Implement inline using TDD; fresh read-only GPT-6.1 Sol / High review afterwards.
No worktree, staging, commit, push, deployment, remote hosts or provider calls.

## Design

- Keep the existing same-time-base path. Mixed outputs use a separate internal
  normalization step, shared by AnalysisSource and IncidentClip. Public schemas,
  source stream facts, prepared-media persistence and provenance remain unchanged.
- Reduce fractions before computing a common reciprocal integer clock. Compute
  LCM with division before multiplication and a checked bound, using Python
  integers. Verify every PTS, duration, accumulated offset and endpoint is an
  integer tick. Reject invalid coverage or unsupported numeric ranges with
  Recording `UNSUPPORTED_MEDIA`; IncidentClip retains its existing public wrapper.
- Preserve original selected coverage internally, separately from encoded
  coverage. A mixed chain must match it exactly, even if a single conversion
  previously passed its established tolerance. Do not change the single-input rule.
- Remux validated parts to the shared MP4 track timescale; independently probe
  frames and packets. No additional lossy encoding or encoder FPS conversion.
- FFmpeg concat's manifest durations and offsets use AV_TIME_BASE (microseconds).
  Compute that transport offset with integer arithmetic, then restore the exact
  intended tick offset for each part's packets with setts. Preserve presentation
  PTS, duration and packet count; join decode intervals
  separately with a shared reorder delay so different B-frame delays cannot alter
  a seam sample duration; independently verify final decoded coverage.
  Range-check binary64 expression integers as well as MP4/muxer integer fields.
  A remux/concat result that cannot preserve coverage is rejected, never repaired
  by changing expectations. Existing strict decode and faststart checks remain.
- Preserve byte budgets, cancellation checkpoints, cleanup leases and transaction
  ownership. Extra files live only inside the existing chain TemporaryDirectory.
  No DB checkout is introduced and no Runtime error is converted into media error.

Primary references (FFmpeg n8.1):
[concat offset](https://github.com/FFmpeg/FFmpeg/blob/n8.1/libavformat/concatdec.c),
[setts arithmetic](https://github.com/FFmpeg/FFmpeg/blob/n8.1/libavcodec/bsf/setts.c),
[MP4 bounds](https://github.com/FFmpeg/FFmpeg/blob/n8.1/libavformat/movenc.c).

## Execution ledger

- [x] RED: at least two real synthetic files, Issue clock combinations, public
  AnalysisSource and IncidentClip; verify individually successful conversion.
- [x] GREEN: rational planning, checked remux and exact concat projection.
- [x] Negative controls: wrong offset/PTS/duration/frame count and bypassed
  normalization detected; overflow and unrepresentable coverage safely rejected.
- [x] Regression: same clocks, gaps/overlaps/coverage/corruption, source hashes,
  stream selection, byte/duration budgets, process/lease cleanup, Worker receipts.
- [x] Real media: metadata-first read-only inventory; minimal relevant sample;
  distinguish available local media from unverified original Issue repro sets.
- [x] Fresh review, reproduced fixes and same-reviewer delta check; append Notes
  and Log evidence, cleanup task-only artifacts and leave unstaged diff.

Validation uses the existing local FFmpeg/ffprobe 8.1 image, not Windows PATH.
Full pytest, mandatory MySQL and mutation inventory remain remote CI conditions.

## Implemented numeric rules and limitations

`T = lcm(denominator(reduce(value)))` over every observed frame PTS/duration
and encoded packet PTS/DTS/duration, output clock `1/T`. Original MediaStream
time bases remain source facts. MaterializedVideo.time_base describes each
encoded part (and the returned final derived output), not the original clock.
Unused ticks do not constrain T. Frame observations must still be
integral in their observed part clock. All packet facts are read before remuxing
so decode-time precision participates in the common clock decision.
`scale <= INT_MAX // factor` is checked before multiplication. All arithmetic up
until FFmpeg is `Fraction`/Python integer. `T <= 2^31-1` follows movenc's option
range. Every selected source frame must equal the individually encoded frame
exactly; a prior single-input tolerance does not establish mixed-chain support.
Each frame's PTS, positive duration, cumulative part offset and endpoint must be
an integral tick. Source coordinates and original stream facts are not overwritten.

Per-part MP4 stream copy is independently checked against frame and packet clocks.
The actual encoded packet PTS set must match the decoded frames one-to-one.
Decode intervals must be contiguous and cover exactly the part length. Packet
PTS/DTS and expression operands/results stay in `[-(2^53-1), 2^53-1]`, a stricter
subset of int64 because setts uses binary64. Durations are positive and at most
INT_MAX; adjacent DTS deltas are strictly below INT_MAX (movenc rewrites equality).
PTS-DTS must fit the supported signed offset range (conservatively absolute value
at most INT_MAX). Unsupported or missing timing observations are rejected.

Manifest durations are integer microseconds, rounded down only for concat's
transport. The known concat offset is rescaled using integer nearest/ties-away
arithmetic; packet-ordinal balanced lookup expressions restore exact presentation offsets.
Their logarithmic tree depth avoids FFmpeg AVExpr's depth limit; leaves and operands
are exact integers. Decode intervals are separately concatenated, then shifted by one common maximum reorder
delay so PTS >= DTS. Neither the frame expectation nor the source time is rounded.
Final output must have the planned clock, zero presentation origin, exact frame
PTS/duration/count and exact planned packet PTS/DTS/duration, then pass strict
full decode, format/faststart/byte checks and source fingerprint revalidation.

Identical-clock inputs retain the previous concat path and validation. This change
adds no encoder/FPS choice, API field, DB schema, transaction, receipt or Case rule.
It adds remux/probe work and retains the existing in-memory part bytes limitation.
The four nominal AVI clocks in #425 have denominator LCM **12679469020444296**
(direct integer calculation), above INT_MAX. This alone does **not** establish
rejection: actual frame and packet observations are needed to determine the
required grid. A sparse 1fps pair with nominal clocks 1/65537 and 1/65539 is
verified on output clock 1/1. The original nine-file set is unavailable as a
confirmed repro set, so its representability and connection result are unverified.
No rounding to make an unrepresentable clock fit and no one-hour service commitment
is introduced. The current concat transport also requires each part to span at
least one microsecond; that is an implementation limitation, not a claim that all
smaller mathematical durations are impossible in MP4.

## Runtime consumption audit

`worker/search_handlers.py` maps only the agreed Analysis size-limit code on
context entry. UNSUPPORTED_MEDIA still reaches `KindRegistry.dispatch`'s generic
RUNTIME_HANDLER_ERROR, then the existing candidate-search failure notice. There is
no agreed UNSUPPORTED_MEDIA-specific terminal/Case mapping in the checked taxonomy.
That mapping/action remains an Owner decision; this implementation adds none.
IncidentClip keeps its existing INCIDENT_CLIP_BUILD_FAILED public wrapper and
RECORDING_INCIDENT_CLIP_BUILD_FAILED Worker mapping. Input, checkpoint, persistence,
T1/T2 and caller transaction code are unchanged. Focused existing mapping tests
explicitly cover unknown Recording codes staying Runtime failures.
