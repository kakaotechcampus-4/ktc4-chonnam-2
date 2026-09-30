import json

import pytest

from eval import paths, run, score
from eval.runners.impls import yolo_persistence
from eval.scorers import persistence
from eval.tools import build_private_aihub172


def test_runs_ignores_misses_before_first_and_after_last_detection():
    assert persistence.runs([False, True, True, False, True, False]) == (2, 1)
    assert persistence.runs([True, False, False, True]) == (1, 1)
    assert persistence.runs([False, False]) == (0, 0)
    assert persistence.runs([True, True, True]) == (3, 0)


def test_iou_matches_readout_definition():
    assert persistence.iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert persistence.iou((0, 0, 10, 10), (10, 0, 10, 10)) == 0.0
    assert abs(persistence.iou((0, 0, 10, 10), (5, 0, 10, 10)) - 50 / 150) < 1e-9


def _gt(frames):
    return {"items": [{"video_id": "v1", "frames": [
        {"frame_no": n, "car_bboxes_xywh": [[0, 0, 10, 10]]} for n in frames]}]}


def test_score_counts_detections_by_iou_threshold():
    hit = [{"bbox_xywh": [0, 0, 10, 10], "conf": 0.9}]
    near = [{"bbox_xywh": [5, 0, 10, 10], "conf": 0.9}]   # IoU 0.33 — 검출 아님
    pred = [{"video_id": "v1", "frames": [
        {"frame_no": 1, "detections": hit}, {"frame_no": 2, "detections": near},
        {"frame_no": 3, "detections": hit}, {"frame_no": 4, "detections": hit}]}]
    out = persistence.score(pred, _gt([1, 2, 3, 4]))
    assert out["per_video"] == [{"video_id": "v1", "visible": 4, "detected": 3,
                                 "longest_run": 2, "gaps": 1}]
    assert out["frame_recall"] == 0.75
    assert out["gaps_buckets"] == {"0": 0.0, "1-2": 1.0, "3+": 0.0}
    assert out["multi_frame_ready"] == {2: 1.0, 3: 1.0, 5: 0.0}
    assert "SPARSE_FRAMES" in out["coverage"]


def test_score_without_gt_is_null_not_zero():
    assert persistence.score([], None)["frame_recall"] is None


def _track1_source(tmp_path):
    src = tmp_path / "track1"
    video = "cam_a-20200101-000000-000.mp4"
    stem = video.removesuffix(".mp4")
    (src / "frames" / stem).mkdir(parents=True)
    lines = []
    for n in (30, 10, 20):
        (src / "frames" / stem / f"{n}.jpg").write_bytes(f"img-{n}".encode())
        lines.append(json.dumps({"video_name": video, "frame_no": n,
                                 "car_bbox": [[1, 2], [11, 22]], "plate_bbox": None}))
    lines.append(json.dumps({"video_name": "other.mp4", "frame_no": 1,
                             "car_bbox": [[0, 0], [1, 1]]}))
    (src / "frames.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (src / "sample_frames.json").write_text(json.dumps({"videos": [video]}), encoding="utf-8")
    return src, stem


@pytest.fixture
def private_root(tmp_path, monkeypatch):
    root = tmp_path / "private"
    monkeypatch.setattr(paths, "private_root", lambda: str(root))
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path / "repo_predictions"))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path / "repo_results"))
    return root


def test_track1_builder_orders_frames_and_converts_boxes(tmp_path, private_root):
    src, stem = _track1_source(tmp_path)
    assert build_private_aihub172.main(["--track", "1", "--source", str(src)]) == 0
    base = private_root / "manifests" / "private_aihub172_track1"
    samples = json.loads((base / "samples.json").read_text(encoding="utf-8"))
    assert [v["video_id"] for v in samples["videos"]] == [stem]
    assert [f["frame_no"] for f in samples["videos"][0]["frames"]] == [10, 20, 30]
    gt = json.loads((base / "gt" / "gt_persistence.json").read_text(encoding="utf-8"))
    assert gt["items"][0]["frames"][0]["car_bboxes_xywh"] == [[1, 2, 10, 20]]


def test_run_and_score_persistence_under_private_root(tmp_path, private_root, monkeypatch):
    src, _ = _track1_source(tmp_path)
    build_private_aihub172.main(["--track", "1", "--source", str(src)])
    calls = iter([[{"bbox_xywh": [1, 2, 10, 20], "conf": 0.8, "cls": "car"}], [],
                  [{"bbox_xywh": [1, 2, 10, 20], "conf": 0.8, "cls": "car"}]])
    monkeypatch.setattr(yolo_persistence, "_load_model", lambda: object())
    monkeypatch.setattr(yolo_persistence, "_detect", lambda model, image: next(calls))
    monkeypatch.setattr("cv2.imdecode", lambda buf, flag: "image")

    assert run.main(["--impl", "readout-exp:yolo11n", "--manifest", "private_aihub172_track1",
                     "--stage", "persistence", "--run-id", "track1_t"]) == 0
    assert score.main(["--prediction", "track1_t"]) == 0

    assert not (tmp_path / "repo_predictions").exists()
    result_path = next((private_root / "results").glob("track1_t.at1.t1-*.json"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["persistence"]["per_video"][0] == {
        "video_id": "cam_a-20200101-000000-000", "visible": 3, "detected": 2,
        "longest_run": 1, "gaps": 1}
    assert result["plate"]["coverage"].startswith("NOT_RUN")
