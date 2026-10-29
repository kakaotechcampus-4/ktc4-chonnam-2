"""Exactly one detached Recording export; T1 owns the execution result receipt."""
from dataclasses import dataclass

from daesingo.common.jobs.execution import HandlerResult
from daesingo.common.jobs.produced import ProducedObject
from daesingo.recording import RecordingCapabilityError
from daesingo.worker.registry import KindRegistry


@dataclass(frozen=True)
class ExportInput:
    case_id: str
    request: dict


FAILURES = {
    "REPORT_VIDEO_EXPORT": {"REPORT_VIDEO_EXPORT_FAILED": "REPORT_VIDEO_EXPORT_FAILED"},
    "PLATE_IMAGE_EXPORT": {"PLATE_IMAGE_EXPORT_FAILED": "PLATE_IMAGE_EXPORT_FAILED",
        "PLATE_IMAGE_OUTPUT_LIMIT_UNSATISFIABLE": "PLATE_IMAGE_OUTPUT_LIMIT_UNSATISFIABLE"},
}


def export_registry(*, load, service_factory=None):
    if service_factory is None:
        return KindRegistry({})

    def invoke(context):
        context.checkpoint()
        data = load(context)
        context.checkpoint()
        with service_factory(data) as recording:
            context.checkpoint()
            capability = recording.export_report_video if context.kind == "REPORT_VIDEO_EXPORT" else recording.export_plate_image
            try:
                asset = capability(**data.request)
            except RecordingCapabilityError as error:
                failure = FAILURES[context.kind].get(error.code)
                if failure is None:
                    raise
                result = HandlerResult(status="FAILED", failure_kind=failure)
            else:
                result = HandlerResult(objects=(ProducedObject(kind="derived_asset_result",
                    payload={"derived_asset_ref": asset.derived_asset_ref}),))
            context.checkpoint()
        context.checkpoint()
        return result

    return KindRegistry({kind: invoke for kind in FAILURES})
