"""Read the append-only export request; never follow mutable current selection."""
from pydantic import BaseModel

from daesingo.recording.exports import PlateImageRequest, ReportVideoRequest, export_fingerprint
from daesingo.worker.export_handlers import ExportInput


class ExportInputs:
    def __init__(self, *, transaction, store_factory):
        self.transaction, self.store_factory = transaction, store_factory

    def __call__(self, context):
        def read(conn):
            store = self.store_factory(conn)
            if store.conn is not conn:
                raise ValueError("export input connection mismatch")
            case = store.get_case(context.case_id)
            records = [r for r in case.job_records if r["job_id"] == context.job_id]
            if (len(records) != 1 or records[0]["case_id"] != context.case_id
                    or records[0]["kind"] != context.kind):
                raise ValueError("export job binding mismatch")
            models: dict[str, type[BaseModel]] = {"REPORT_VIDEO_EXPORT": ReportVideoRequest, "PLATE_IMAGE_EXPORT": PlateImageRequest}
            model = models.get(context.kind)
            if model is None:
                raise ValueError("unsupported export kind")
            request = model.model_validate(store.export_input(context.case_id, context.job_id)).model_dump(mode="json")
            if records[0]["input_fingerprint"] != export_fingerprint({"kind": context.kind, "input": request}):
                raise ValueError("export input fingerprint mismatch")
            return ExportInput(context.case_id, request)
        return self.transaction(read)
