"""Audited no-provider result jobs; command names are not an admission boundary.

Export/preview handlers perform local Recording work without UsageSink.begin;
their current T2 appliers do not issue paid successors. Clip/OCR are deliberately
not exempt: clip has successors and OCR uses the invocation reservation path.
Unknown/future kinds always retain the guarded analysis path.
"""
LOCAL_RESULT_KINDS = frozenset({"REPORT_VIDEO_EXPORT", "PLATE_IMAGE_EXPORT", "CANDIDATE_VIDEO_PREVIEW"})


def local_only(jobs):
    return bool(jobs) and all(job["kind"] in LOCAL_RESULT_KINDS for job in jobs)
