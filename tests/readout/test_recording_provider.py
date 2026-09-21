from daesingo.readout import api, providers
from daesingo.readout.contracts import InputRef
from daesingo.recording import RecordingService, load_recording_fixture


def test_recording_provider_reads_incident_clip_frame_bytes():
    recording = RecordingService.from_fixture(load_recording_fixture("scenario_happy_001"))
    seen = []

    def read_plate(frames, input_ref, target_hint):
        frame, content = frames.read_at(12.48)
        seen.append(content)
        return providers.PlateReading(
            association=providers.AssociationReading(
                status="NOT_PROVIDED",
                target_hint_used=False,
                track_ref=None,
                association_method="FALLBACK_ONLY",
            ),
            frames=[providers.PlateFrameReading(
                frame.frame_ref, [0, 0, 20, 20], "12가3456", 0.9, {}
            )],
        )

    provider = providers.RecordingOcrProvider(
        recording,
        plate_reader=read_plate,
        overlay_reader=lambda frames, input_ref: providers.OverlayReading(
            presence=providers.UNDETERMINED
        ),
    )
    request = api.ReadRequest(
        case_id="case_h001",
        candidate_id="candidate_h001",
        input_ref=InputRef(
            "clip_h001", "readout-native", "SOURCE_DERIVED_INCIDENT_CLIP"
        ),
    )

    run, result = api.read_plate(request, provider=provider)

    assert run.outcome == "SUCCEEDED"
    assert result.best_frame.frame_ref == "fr_h001_thumb"
    assert seen == [b"fixture-frame:fr_h001_thumb"]
