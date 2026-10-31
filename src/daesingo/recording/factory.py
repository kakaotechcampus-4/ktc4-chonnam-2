"""Recording-owned explicit runtime profile configuration; no canonical defaults."""
from dataclasses import dataclass

from .materialization import AnalysisProfile, LocalAnalysisMaterializer
from .service import RecordingService
from .time_sources import LocalTimeSourceObserver
from .incidents import IncidentClipEncoding, LocalIncidentMaterializer
from .analysis_limits import AnalysisSourceLimits

RECORDING_KEYS = ("DAESINGO_RECORDING_ANALYSIS_PROFILE_REF", "DAESINGO_RECORDING_ANALYSIS_HEIGHT",
                  "DAESINGO_RECORDING_ANALYSIS_PRESET", "DAESINGO_RECORDING_ANALYSIS_CRF",
                  "DAESINGO_RECORDING_FILENAME_OFFSET", "DAESINGO_RECORDING_INCIDENT_HEIGHT",
                  "DAESINGO_RECORDING_INCIDENT_PRESET", "DAESINGO_RECORDING_INCIDENT_CRF",
                  "DAESINGO_RECORDING_ANALYSIS_MAX_BYTES", "DAESINGO_RECORDING_ANALYSIS_MAX_DURATION_MS")


@dataclass(frozen=True)
class RecordingSettings:
    profile_ref: str | None = None
    profile: AnalysisProfile | None = None
    filename_offset: str | None = None
    incident_encoding: IncidentClipEncoding | None = None
    analysis_limits: AnalysisSourceLimits | None = None

    def __post_init__(self):
        if (self.profile_ref is not None or self.profile is not None) and (
                self.profile_ref is None or self.profile is None or not isinstance(self.analysis_limits, AnalysisSourceLimits)):
            raise ValueError("explicit Recording profile and AnalysisSource limits required")

    @classmethod
    def from_mapping(cls, values):
        offset = values.get(RECORDING_KEYS[4]) or None
        LocalTimeSourceObserver(filename_offset=offset)  # validate without observing media
        incident = None
        if any(key in values for key in RECORDING_KEYS[5:8]):
            if not all(values.get(key, "").strip() for key in RECORDING_KEYS[5:8]):
                raise ValueError("explicit IncidentClip encoding required")
            profile = AnalysisProfile(int(values[RECORDING_KEYS[5]]), values[RECORDING_KEYS[6]],
                                      int(values[RECORDING_KEYS[7]]))
            incident = IncidentClipEncoding(profile.height, profile.preset, profile.crf)
        analysis_keys = RECORDING_KEYS[:4] + RECORDING_KEYS[8:]
        if not any(key in values for key in analysis_keys):
            return cls(filename_offset=offset, incident_encoding=incident)
        if not all(values.get(key, "").strip() for key in analysis_keys):
            raise ValueError("explicit Recording profile configuration required")
        try:
            limits = AnalysisSourceLimits(int(values[RECORDING_KEYS[8]]), int(values[RECORDING_KEYS[9]]))
        except (ValueError, TypeError, OverflowError):
            raise ValueError("explicit positive integer AnalysisSource limits required") from None
        return cls(values[RECORDING_KEYS[0]].strip(), AnalysisProfile(int(values[RECORDING_KEYS[1]]),
            values[RECORDING_KEYS[2]], int(values[RECORDING_KEYS[3]])), offset, incident, limits)


def build_incident_recording_service(repository, settings: RecordingSettings, *, temp_root=None,
                                     materializer_factory=None, case_id=None):
    """Explicit clip-only composition; existing Analysis factory is unchanged."""
    if settings.incident_encoding is None:
        raise ValueError("explicit IncidentClip encoding required")
    materializer = (materializer_factory(settings.incident_encoding) if materializer_factory is not None else
                    LocalIncidentMaterializer(settings.incident_encoding, temp_root=temp_root))
    return RecordingService(repository, incident_materializer=materializer, durable_prepared=True, case_id=case_id)


def build_recording_service(repository, settings: RecordingSettings, *, temp_root=None, materializer_factory=None,
                            case_id=None, analysis_checkpoint=None):
    materializer = None
    if settings.profile_ref is not None:
        profiles = {settings.profile_ref: settings.profile}
        materializer = (materializer_factory(profiles) if materializer_factory is not None else
                        LocalAnalysisMaterializer(profiles, temp_root=temp_root))
    return RecordingService(repository, analysis_materializer=materializer,
        time_source_observer=LocalTimeSourceObserver(filename_offset=settings.filename_offset),
        durable_prepared=True, case_id=case_id, analysis_limits=settings.analysis_limits,
        analysis_checkpoint=analysis_checkpoint)
