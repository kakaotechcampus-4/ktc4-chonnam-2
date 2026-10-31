# Recording execution failure taxonomy

Confirmed by Runtime and Recording Owners in [#297 comment 6464169000](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6464169000), 2026-10-28.

| Public capability error | JobExecution status | failure_kind | produced |
| --- | --- | --- | --- |
| `RecordingCapabilityError.code == "INCIDENT_CLIP_BUILD_FAILED"` from `build_incident_clip()` | `FAILED` | `RECORDING_INCIDENT_CLIP_BUILD_FAILED` | `[]` |

This is a literal one-to-one mapping, not a prefix-generation rule. Unknown codes
are not classified by this mapping. No raw exception, path, locator or credential
is included in the terminal failure. Input reads, context lifecycle, checkpoints,
transactions and persistence errors retain their Runtime boundaries. The handler
does not retry the capability within an execution. Case may issue a new clip job;
Fine success and its produced remain unchanged. Runtime automatic retry remains
limited to the existing STALE policy.

## RT-10(b) export wiring — 2026-10-29 provisional implementation

The PM delegation in the implementation request permits the following Runtime
wire choices, with #47 Owner review deferred. This is not a new Owner approval
or a change to the existing report export Contract.

| Capability error, only from that invocation | status | failure_kind |
| --- | --- | --- |
| `export_report_video`: `REPORT_VIDEO_EXPORT_FAILED` | `FAILED` | `REPORT_VIDEO_EXPORT_FAILED` |
| `export_plate_image`: `PLATE_IMAGE_EXPORT_FAILED` | `FAILED` | `PLATE_IMAGE_EXPORT_FAILED` |
| `export_plate_image`: `PLATE_IMAGE_OUTPUT_LIMIT_UNSATISFIABLE` | `FAILED` | `PLATE_IMAGE_OUTPUT_LIMIT_UNSATISFIABLE` |

Each failure has no produced object. Unknown codes and input/persistence/context
faults retain Runtime handling. Cancellation propagates. Case maps the first two
to existing `recording.report_video_export_failed` and
`recording.plate_image_export_failed` notice codes. Limit exhaustion also uses the
plate failure notice with no same-input `GENERATE_PLATE_IMAGE` action.
The bounded strategy and deferred items are in the
[Implementation Notes](../../../runtime/rt10b-recording-exports.md).

## #425 analysis input preparation — 2026-10-31 request specification

The following literal is adopted by this implementation request. It is not a
terminal value previously approved in the #425 Owner comment.

| Capability error, only from that invocation | JobExecution status | failure_kind | produced |
| --- | --- | --- | --- |
| `prepare_analysis_source_from_resolution`: `RecordingCapabilityError.code == "UNSUPPORTED_MEDIA"` | `FAILED` | `RECORDING_UNSUPPORTED_MEDIA` | `[]` |

Applies to the shared production analysis input preparation for `COARSE_SEARCH`
and `FINE_VERIFY`, not `HINT_EXTRACT`. This is not an automatic prefix rule or a
global Recording exception converter. Unknown codes, input/metadata reads,
factory configuration, DB/transaction/commit/persistence errors, checkpoints,
cancellation, usage, Search/provider calls and context exit/cleanup retain their
existing boundaries. The factory catches only the single preparation invocation;
its repository calls propagate database/transaction exceptions unchanged.
No exception text, filename, path, locator or video content enters the terminal.
Existing size-limit, IncidentClip and export mappings remain unchanged.

Case continues to consume FAILED through its existing projection and notices;
this mapping does not establish a new notice, action or retry policy. Details and
the unposted Case Owner proposal are in the
[Implementation Notes](../../../runtime/issue425-media-failure-mapping.md).
