import hashlib
import json
import os

import pytest

from daesingo.readout import OcrProvider
from daesingo.readout.providers import (
    AssociationReading,
    PlateFrameReading,
    PlateReading,
)
from eval import paths, run, score
from eval.runners.impls import readout_paddle
from eval.tools import build_private_aihub172

PLATES = {"P172_TRAIN_0000": "12가3456", "P172_TRAIN_0001": "34나5678",
          "P172_TRAIN_0002": "56다7890"}


def _source(tmp_path):
    """aihub172.py sample 산출물 모양의 가짜 입력."""
    src = tmp_path / "track2"
    (src / "crops").mkdir(parents=True)
    items = []
    for sample_id in PLATES:
        blob = ("jpeg-" + sample_id).encode()
        (src / "crops" / (sample_id + ".jpg")).write_bytes(blob)
        items.append({"sample_id": sample_id, "file_path": f"crops/{sample_id}.jpg",
                      "width": 266, "height": 126, "bytes": len(blob),
                      "sha256": hashlib.sha256(blob).hexdigest()})
    (src / "manifest.json").write_text(json.dumps(
        {"meta": {"source": "aihub_172", "split": "training"}, "items": items}),
        encoding="utf-8")
    (src / "gt_plate.LOCAL_ONLY.json").write_text(json.dumps(
        {"items": [{"sample_id": k, "gt_plate_text": v} for k, v in PLATES.items()]},
        ensure_ascii=False), encoding="utf-8")
    return src


class _ScriptedProvider(OcrProvider):
    """0000 은 맞게, 0001 은 틀리게, 0002 는 신뢰도 낮게(보류) 읽는다."""

    label = "scripted"

    def __init__(self, frame_source):
        self.frame_source = frame_source

    def read_plate(self, input_ref, target_hint):
        ref = input_ref.incident_clip_ref
        self.frame_source._paths[ref]  # 공급자가 표본을 아는지 확인한다
        text, conf = {"P172_TRAIN_0000": ("12가3456", 0.9),
                      "P172_TRAIN_0001": ("34나5679", 0.9),
                      "P172_TRAIN_0002": ("56다7890", 0.3)}[ref]
        return PlateReading(
            association=AssociationReading("LOW_CONFIDENCE", False, None, "FALLBACK_ONLY"),
            frames=[PlateFrameReading("crop_" + ref, [0, 0, 200, 60], text, conf,
                                      {"plate_px_height": 60, "sharpness": 1.0})])


@pytest.fixture
def private_root(tmp_path, monkeypatch):
    root = tmp_path / "private"
    monkeypatch.setattr(paths, "private_root", lambda: str(root))
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path / "repo_predictions"))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path / "repo_results"))
    return root


def test_builder_keeps_plate_text_out_of_samples(tmp_path, private_root):
    assert build_private_aihub172.main(["--source", str(_source(tmp_path))]) == 0
    base = private_root / "manifests" / "private_aihub172_plate"
    samples = (base / "samples.json").read_text(encoding="utf-8")
    for plate in PLATES.values():
        assert plate not in samples
    gt = json.loads((base / "gt" / "gt_plate.json").read_text(encoding="utf-8"))
    assert {i["true_text"] for i in gt["items"]} == set(PLATES.values())
    assert {i["legibility"] for i in gt["items"]} == {"READABLE"}


def test_run_and_score_stay_under_private_root(tmp_path, private_root, monkeypatch):
    build_private_aihub172.main(["--source", str(_source(tmp_path))])
    monkeypatch.setattr(readout_paddle.paddle_provider, "PaddleOcrProvider", _ScriptedProvider)
    monkeypatch.setattr(readout_paddle, "version", lambda _: "3.7.0")

    assert run.main(["--impl", "readout:paddle-crop", "--manifest", "private_aihub172_plate",
                     "--stage", "plate", "--run-id", "plate_t"]) == 0
    assert score.main(["--prediction", "plate_t"]) == 0

    assert not (tmp_path / "repo_predictions").exists()
    assert not (tmp_path / "repo_results").exists()
    result_path = next((private_root / "results").glob("plate_t.ap1.*.json"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    plate = result["plate"]
    assert plate["n"] == 3
    assert plate["exact_accuracy"] == 0.5          # 답한 2건 중 1건
    assert plate["readable_abstention_rate"] == pytest.approx(1 / 3)
    assert plate["abstain_reasons"] == {"OCR_LOW_CONFIDENCE": 1}
    assert plate["wrong_accept_rate"] is None       # 판독불가 정답이 없다
    assert result["meta"]["prediction_ref"]["path"].startswith("<DAESINGO_EVAL_PRIVATE_ROOT>")


def test_runner_refuses_public_manifest():
    with pytest.raises(readout_paddle.RunnerPreflightError, match="private_"):
        readout_paddle.run({"manifest": "mock_pack", "stage": "plate"})


def test_private_root_must_be_configured(monkeypatch):
    monkeypatch.setattr("daesingo.common.load_env_file", dict)
    with pytest.raises(OSError, match="DAESINGO_EVAL_PRIVATE_ROOT"):
        paths.private_root()
    assert paths.is_private("private_x") and not paths.is_private("b_youtube")
    assert os.path.basename(paths.manifest_dir("b_youtube")) == "b_youtube"


def test_builder_m2_drops_samples_whose_plate_is_in_another_split(tmp_path, private_root):
    import zipfile

    other = tmp_path / "valid_labels.zip"
    with zipfile.ZipFile(other, "w") as z:
        z.writestr("a.json", json.dumps({"value": PLATES["P172_TRAIN_0001"]}, ensure_ascii=False))
        z.writestr("b.json", json.dumps({"value": "99하9999"}, ensure_ascii=False))
    assert build_private_aihub172.main(
        ["--source", str(_source(tmp_path)), "--exclude-plates-zip", str(other)]) == 0
    base = private_root / "manifests" / "private_aihub172_plate_m2"
    samples = json.loads((base / "samples.json").read_text(encoding="utf-8"))
    assert [s["sample_id"] for s in samples["samples"]] == ["P172_TRAIN_0000", "P172_TRAIN_0002"]
    assert samples["meta"]["manifest_version"] == "m2"
    assert samples["meta"]["exclusion"]["n_excluded"] == 1
    gt = json.loads((base / "gt" / "gt_plate.json").read_text(encoding="utf-8"))
    assert gt["meta"]["gt_version"] == "ap2" and len(gt["items"]) == 2
