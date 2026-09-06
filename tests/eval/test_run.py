import json
import os
from eval import run, paths


def test_envelope_has_meta_raw_normalized():
    env = run.build_envelope("fake:always_correct", "b_youtube", "candidate", "run_test_001")
    assert set(env) == {"meta", "raw", "normalized"}
    assert env["meta"]["impl"] == "fake:always_correct"
    assert env["meta"]["stage"] == "candidate"
    assert env["meta"]["manifest"] == "b_youtube"
    assert env["meta"]["normalizer_version"] == "n1"
    assert env["meta"]["manifest_version"] == "m1"


def test_envelope_raw_is_preserved_not_replaced_by_normalized():
    env = run.build_envelope("fake:always_correct", "b_youtube", "candidate", "run_test_002")
    assert env["raw"] is not env["normalized"]
    assert len(env["raw"]) == 55


def test_main_writes_prediction_file(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path))
    rc = run.main(["--impl", "fake:always_correct", "--manifest", "b_youtube",
                   "--stage", "candidate", "--run-id", "run_test_003"])
    assert rc == 0
    p = os.path.join(str(tmp_path), "run_test_003.json")
    with open(p, encoding="utf-8") as f:
        env = json.load(f)
    assert env["meta"]["run_id"] == "run_test_003"


def test_unknown_impl_returns_nonzero(capsys):
    rc = run.main(["--impl", "nope", "--manifest", "b_youtube", "--stage", "candidate"])
    assert rc != 0
