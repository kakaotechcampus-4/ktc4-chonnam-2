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
