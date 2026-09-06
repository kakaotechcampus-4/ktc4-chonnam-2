from eval import manifests_io
from eval.runners import registry, normalize
from eval.scorers import candidate


def _run(impl_name):
    raw = registry.get(impl_name)({"manifest": "b_youtube", "stage": "candidate"})
    return normalize.normalize_candidate(raw)


def test_always_correct_gets_perfect_recall():
    gt = manifests_io.load_gt("b_youtube", "candidate")
    r = candidate.score(_run("fake:always_correct"), gt)
    assert r["recall_at"]["1"] == 1.0
    assert r["recall_at"]["3"] == 1.0
    assert r["fp_per_clip"] == 0.0


def test_always_wrong_gets_zero_recall_and_positive_fp():
    gt = manifests_io.load_gt("b_youtube", "candidate")
    r = candidate.score(_run("fake:always_wrong"), gt)
    assert r["recall_at"]["3"] == 0.0
    assert r["fp_per_clip"] > 0.0


def test_boundary_excluded_targets_are_not_counted():
    gt = manifests_io.load_gt("b_youtube", "candidate")
    n_included = sum(1 for i in gt["items"] for t in i["targets"]
                     if t.get("scoring") != "BOUNDARY_EXCLUDED")
    r = candidate.score(_run("fake:always_correct"), gt)
    assert r["n_events"] == n_included


def test_by_type_breakdown_lists_only_present_types():
    gt = manifests_io.load_gt("b_youtube", "candidate")
    r = candidate.score(_run("fake:always_correct"), gt)
    assert set(r["by_type"]) == {"SIGNAL", "SOLID_LINE_LANE_CHANGE"}


def test_zero_span_predictions_report_null_span_error():
    gt = {"meta": {"coverage": {}},
          "items": [{"clip_id": "C0", "source_video_id": "V", "targets": [
              {"event_id": "E", "violation_type": "SIGNAL", "t_start_sec": 1.0,
               "t_end_sec": 2.0, "t_onset_sec": 1.5, "scoring": "INCLUDED"}]}]}
    norm = [{"clip_id": "C0", "candidates": [
        {"rank": 1, "t_start_sec": 0.0, "t_end_sec": 0.0,
         "event_type": "SIGNAL", "score": 1.0}]}]
    r = candidate.score(norm, gt)
    assert r["span_error_sec"]["mean"] is None
