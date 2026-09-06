import json
import os
from eval import run, score, paths
from eval.scorers import classification


def test_score_cli_writes_results_with_coverage(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path))
    run.main(["--impl", "fake:always_correct", "--manifest", "b_youtube",
              "--stage", "candidate", "--run-id", "run_cli_001"])
    rc = score.main(["--prediction", "run_cli_001"])
    assert rc == 0
    out = os.path.join(str(tmp_path), "run_cli_001.g1.json")
    with open(out, encoding="utf-8") as f:
        res = json.load(f)
    assert res["candidate"]["recall_at"]["1"] == 1.0
    assert res["plate"]["exact_accuracy"] is None
    assert res["meta"]["impl"] == "fake:always_correct"


def test_score_cli_returns_rc2_when_gt_missing_not_a_traceback(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path))
    run.main(["--impl", "fake:always_correct", "--manifest", "b_youtube",
              "--stage", "candidate", "--run-id", "run_missing_gt"])
    # prediction이 가리키는 manifest를 GT가 없는 이름으로 바꿔치기한다.
    p = os.path.join(str(tmp_path), "run_missing_gt.json")
    with open(p, encoding="utf-8") as f:
        env = json.load(f)
    env["meta"]["manifest"] = "does_not_exist"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(env, f)
    rc = score.main(["--prediction", "run_missing_gt"])
    assert rc == 2


def _score_classification(run_id, impl, tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path))
    assert run.main(["--impl", impl, "--manifest", "a_aihub",
                     "--stage", "classification", "--run-id", run_id]) == 0
    assert score.main(["--prediction", run_id]) == 0
    with open(os.path.join(str(tmp_path), run_id + ".g1.json"), encoding="utf-8") as f:
        return json.load(f)


def test_classification_runs_end_to_end_and_fakes_contrast(tmp_path, monkeypatch):
    """치트 두 개의 점수 차이가 classification 지표 계산의 검증이다 (§6)."""
    ok = _score_classification("run_cls_ok", "fake:always_correct", tmp_path, monkeypatch)
    ng = _score_classification("run_cls_ng", "fake:always_wrong", tmp_path, monkeypatch)

    assert ok["classification"]["recall_macro"] == 1.0
    assert ok["classification"]["precision_macro"] == 1.0
    assert ok["classification"]["target_correctness"] == 1.0
    assert ng["classification"]["recall_macro"] == 0.0
    assert ng["classification"]["target_correctness"] == 0.0
    assert ok["classification"]["n"] == 120


def test_not_run_classification_block_keeps_every_metric_key(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path))
    run.main(["--impl", "fake:always_correct", "--manifest", "b_youtube",
              "--stage", "candidate", "--run-id", "run_cli_notrun"])
    assert score.main(["--prediction", "run_cli_notrun"]) == 0
    path = os.path.join(str(tmp_path), "run_cli_notrun.g1.json")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    res = json.loads(text)
    blank = res["classification"]
    assert blank["recall_macro"] is None and blank["confusion"] is None
    assert blank["coverage"].startswith("NOT_RUN")
    # 채점된 블록과 키 집합이 같아야 한다 (plate 무데이터 블록과 같은 규칙).
    assert set(blank) == set(classification.not_run("x"))
    # 결과 파일은 개행으로 끝난다 — 텍스트 도구로 이어 붙이기 위해서다.
    assert text.endswith("}\n")
