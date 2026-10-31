"""Detached canonical JSON facts for Case's public RecordingFacts port."""
from .service import RecordingService


class RecordingFacts:
    def __init__(self, repository):
        self.repository = repository

    def get_incident_clip(self, incident_clip_ref):
        with RecordingService(self.repository) as service:
            return service.get_incident_clip(incident_clip_ref).model_dump(mode="json")

    def get_time_source_candidates(self, source_asset_ref):
        with RecordingService(self.repository) as service:
            return [c.model_dump(mode="json") for c in service.get_time_source_candidates(source_asset_ref)]

    def list_case_asset_facts(self, case_id):
        with RecordingService(self.repository) as service:
            return [c.model_dump(mode="json") for c in service.list_case_asset_facts(case_id)]

    def get_derived_asset(self, ref):
        with RecordingService(self.repository) as service:
            return service.get_derived_asset(ref).model_dump(mode="json")

    def get_export_transform(self, ref):
        with RecordingService(self.repository) as service:
            return service.get_export_transform(ref)
