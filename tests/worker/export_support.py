"""External OCR is offline; Recording issues all actual frame identities/pixels."""
from daesingo.readout.paddle_provider import RecordingFrameSource
from daesingo.readout.providers import OcrProvider, PlateReading, PlateFrameReading, AssociationReading, OverlayReading, NOT_PRESENT


class ExportOcr(OcrProvider):
    label = "offline-native-frame-test"

    def __init__(self, recording):
        self.source = RecordingFrameSource(recording, sample_ratios=(.2, .4, .6))

    def read_plate(self, input_ref, target_hint):
        frames = self.source.frames(input_ref.incident_clip_ref)
        return PlateReading(AssociationReading("ASSOCIATED", False, None, "offline"), [
            PlateFrameReading(frame.frame_ref, [10, 10, 80, 30], "12가3456", .99, {"plate_px_height": 30})
            for frame in frames])

    def read_overlay_time(self, input_ref):
        return OverlayReading(NOT_PRESENT)
