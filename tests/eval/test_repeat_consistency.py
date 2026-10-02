import json
import os

import pytest

from eval import paths, repeat, run
from eval.scorers import consistency


def _gt():
    return {"items": [
        {"clip_id": "c1", "targets": [
            {"event_id": "E1", "scoring": "INCLUDED",
             "violation_type": "SIGNAL", "t_onset_sec": 10.0},
            {"event_id": "E2", "scoring": "INCLUDED",
             "violation_type": "SIGNAL", "t_onset_sec": 50.0},
        ]},
        {"clip_id": "c2", "targets": [
            {"event_id": "E3", "scoring": "INCLUDED",
             "violation_type": "CENTER_LINE_CROSSING", "t_onset_sec": 5.0},
            {"event_id": "X", "scoring": "EXCLUDED",
             "violation_type": "SIGNAL", "t_onset_sec": 30.0},
        ]},
        {"clip_id": "neg", "targets": []},
    ]}


def _cand(rank, rep, event_type):
    return {"rank": rank, "t_start_sec": rep - 1, "t_end_sec": rep + 1,
            "representative_sec": rep, "timeline_revision": 1,
            "event_type": event_type, "score": 0.9}


def _run(hit_e2, n_fp):
    """E1 은 매번 맞히고, E3 는 매번 놓치고, E2 는 hit_e2 일 때만 맞힌다."""
    c1 = [_cand(1, 10.0, "SIGNAL")]
    if hit_e2:
        c1.append(_cand(2, 50.0, "SIGNAL"))
    return [
        {"clip_id": "c1", "candidates": c1},
        {"clip_id": "c2", "candidates": [_cand(1, 5.0, "SIGNAL")]},   # 유형 틀림
        {"clip_id": "neg", "candidates": [_cand(i + 1, 3.0, "SIGNAL")
                                          for i in range(n_fp)]},
    ]


def test_counts_always_flaky_never_per_event():
    out = consistency.score([_run(True, 0), _run(False, 2), _run(True, 1)], _gt())
    assert out["n_runs"] == 3
    assert out["n_events"] == 3                 # EXCLUDED 는 빠진다
    assert (out["always_hit"], out["flaky"], out["never_hit"]) == (1, 1, 1)
    assert out["hit_count_histogram"] == {"0": 1, "1": 0, "2": 1, "3": 1}
    assert {e["event_id"]: e["hits"] for e in out["per_event"]} == {
        "E1": 3, "E2": 2, "E3": 0}
    assert out["recall_at_k_by_run"] == pytest.approx([2 / 3, 1 / 3, 2 / 3])
    assert out["fp_per_negative_clip_by_run"] == [0.0, 2.0, 1.0]
    assert out["always_hit_ratio_ci95"] is not None
    assert out["coverage"] is None


def test_single_run_is_flagged_not_scored_as_consistent():
    out = consistency.score([_run(True, 0)], _gt())
    assert "SINGLE_RUN" in out["coverage"]


def test_hit_definition_matches_candidate_scorer_top_k():
    """k 밖의 후보는 적중이 아니다 — candidate.recall_at 과 같은 잣대."""
    out = consistency.score([_run(True, 0)] * 2, _gt(), k=1)
    assert {e["event_id"]: e["hits"] for e in out["per_event"]}["E2"] == 0


def _prepare_two_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path / "results"))
    for r in ("rep_r1", "rep_r2"):
        assert run.main(["--impl", "fake:always_correct", "--manifest", "b_youtube",
                         "--stage", "candidate", "--run-id", r]) == 0


def test_cli_writes_grouped_result_and_flaky_events(tmp_path, monkeypatch):
    _prepare_two_runs(tmp_path, monkeypatch)
    # 2회차는 아무것도 못 찾았다고 바꿔, 모든 사건이 1/2 로 흔들리게 한다.
    p = tmp_path / "rep_r2.json"
    env = json.loads(p.read_text(encoding="utf-8"))
    for n in env["normalized"]:
        n["candidates"] = []
    p.write_text(json.dumps(env), encoding="utf-8")

    assert repeat.main(["--name", "rep", "--predictions", "rep_r1", "rep_r2"]) == 0
    out_dir = tmp_path / "results"
    (name,) = os.listdir(out_dir)
    res = json.loads((out_dir / name).read_text(encoding="utf-8"))
    c = res["consistency"]
    assert c["n_runs"] == 2
    assert c["flaky"] == c["n_events"] > 0
    assert c["recall_at_k_by_run"] == [1.0, 0.0]
    assert len(res["meta"]["prediction_refs"]) == 2

    # 같은 묶음 이름으로 다시 쓰지 않는다.
    assert repeat.main(["--name", "rep", "--predictions", "rep_r1", "rep_r2"]) == 3


def test_cli_refuses_runs_with_different_settings(tmp_path, monkeypatch, capsys):
    _prepare_two_runs(tmp_path, monkeypatch)
    p = tmp_path / "rep_r2.json"
    env = json.loads(p.read_text(encoding="utf-8"))
    env.setdefault("facts", {})["prompt_fingerprint"] = "other"
    p.write_text(json.dumps(env), encoding="utf-8")

    assert repeat.main(["--name", "rep", "--predictions", "rep_r1", "rep_r2"]) == 4
    assert "facts.prompt_fingerprint" in capsys.readouterr().err


def test_cli_rejects_duplicate_or_single_run(tmp_path, monkeypatch):
    _prepare_two_runs(tmp_path, monkeypatch)
    assert repeat.main(["--name", "rep", "--predictions", "rep_r1", "rep_r1"]) == 2
    assert repeat.main(["--name", "rep", "--predictions", "rep_r1"]) == 2
