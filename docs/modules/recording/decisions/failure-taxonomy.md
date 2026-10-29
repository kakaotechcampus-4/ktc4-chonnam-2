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
