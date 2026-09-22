from types import SimpleNamespace

import numpy as np

from daesingo.readout.paddle_provider import (
    PaddleOcrProvider,
    SourceFrame,
    TextBox,
    _hint_bbox,
    _to_frame_boxes,
    pick_plate,
)


def test_target_crop_only_uses_bbox_from_the_same_frame():
    hint = SimpleNamespace(frame_ref="fr_target", bbox_xywh=[10, 20, 30, 40])

    assert _hint_bbox(hint, "fr_other") is None
    assert _hint_bbox(hint, "fr_target") == (10, 20, 30, 40)

    restored = _to_frame_boxes(
        [TextBox("23두4874", 0.9, (30, 60, 330, 120))], (10, 20), 3
    )
    assert restored[0].box == (20, 40, 120, 60)


def test_target_crop_enlarges_only_the_hint_frame_and_restores_its_coordinates():
    frame = SourceFrame("fr_target", 5.0, np.zeros((100, 200, 3), dtype=np.uint8))
    seen = []

    class Engine:
        def predict(self, image):
            seen.append(image.shape)
            yield SimpleNamespace(json={"res": {
                "rec_texts": ["36 3105"], "rec_scores": [0.9],
                "rec_boxes": [[30, 60, 330, 120]],
            }})

    provider = PaddleOcrProvider(SimpleNamespace(frames=lambda _: [frame]))
    provider._engine = Engine()
    hint = SimpleNamespace(frame_ref="fr_target", bbox_xywh=[10, 20, 30, 40])

    boxes = provider._boxes("clip", frame, hint)

    assert seen == [(168, 138, 3)]  # padded 46×56 target crop, enlarged 3×
    assert boxes[0].box == (12, 32, 112, 52)
    assert pick_plate(boxes) is None
    assert pick_plate(boxes, allow_digits_only=True).text == "36 3105"


def test_target_hint_never_reads_an_unhinted_frame_as_associated():
    target = SourceFrame("fr_target", 5.0, np.zeros((100, 200, 3), dtype=np.uint8))
    other = SourceFrame("fr_other", 6.0, np.zeros((100, 200, 3), dtype=np.uint8))
    seen = []

    class Engine:
        def predict(self, image):
            seen.append(image.shape)
            yield SimpleNamespace(json={"res": {
                "rec_texts": ["23두4874"], "rec_scores": [0.9],
                "rec_boxes": [[30, 60, 330, 120]],
            }})

    provider = PaddleOcrProvider(SimpleNamespace(frames=lambda _: [target, other]))
    provider._engine = Engine()
    hint = SimpleNamespace(frame_ref="fr_target", bbox_xywh=[10, 20, 30, 40], track_ref="track")

    reading = provider.read_plate(SimpleNamespace(incident_clip_ref="clip"), hint)

    assert [frame.frame_ref for frame in reading.frames] == ["fr_target"]
    assert reading.association.status == "ASSOCIATED"
    assert reading.association.target_hint_used is True
    assert len(seen) == 1


def test_mismatched_target_hint_does_not_fall_back_to_full_frame_ocr():
    frame = SourceFrame("fr_other", 5.0, np.zeros((100, 200, 3), dtype=np.uint8))

    class Engine:
        def predict(self, image):  # pragma: no cover - must not be called
            raise AssertionError("mismatched hint must not trigger full-frame OCR")

    provider = PaddleOcrProvider(SimpleNamespace(frames=lambda _: [frame]))
    provider._engine = Engine()
    hint = SimpleNamespace(frame_ref="fr_target", bbox_xywh=[10, 20, 30, 40], track_ref="track")

    reading = provider.read_plate(SimpleNamespace(incident_clip_ref="clip"), hint)

    assert reading.frames == []
    assert reading.association.status == "NOT_PROVIDED"
    assert reading.association.target_hint_used is False
    assert reading.association.region is None
