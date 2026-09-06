import json
import os
from eval import run, paths
from eval.runners import registry


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


def test_envelope_raw_matches_impl_output_exactly():
    # 얕은 길이 비교만으로는 raw 의 중첩 dict 를 손대는 회귀를 못 잡는다 —
    # impl 을 직접 호출한 결과와 깊이 비교해서 raw 가 진짜 원문인지 확인한다.
    scope = {"manifest": "b_youtube", "stage": "candidate"}
    direct = registry.get("fake:always_correct")(scope)
    env = run.build_envelope("fake:always_correct", "b_youtube", "candidate", "run_test_004")
    assert env["raw"] == direct


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
