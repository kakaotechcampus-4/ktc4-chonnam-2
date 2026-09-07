import inspect
import sys

import pytest

from eval import manifests_io, run
from eval.enums import VIOLATION_TYPES
from eval.runners import registry


def test_gt_reading_cheats_stay_isolated_under_the_fake_prefix():
    """`fake:` 는 정답지를 몰래 읽는 치트의 표시다.

    「등록된 전부가 fake: 다」를 단언하던 테스트였으나 그것은 가짜 2종만
    있던 때 우연히 참이었을 뿐이다. 지켜야 하는 불변식은 방향이 반대다 —
    **정답지를 읽는 구현은 반드시 fake: 아래에 있어야 한다.** 접두어 없는
    구현이 정답지를 읽으면 치트를 실제 구현으로 착각하게 된다.
    """
    names = registry.names()
    assert "fake:always_correct" in names
    assert "fake:always_wrong" in names

    # fake: 가 아닌 구현은 정답지 로더를 참조하지 않는다.
    for name in names:
        if name.startswith("fake:"):
            continue
        module = sys.modules[registry.get(name).__module__]
        src = inspect.getsource(module)
        assert "load_gt" not in src, "%s 가 정답지를 읽는다 — fake: 로 격리해야 한다" % name
        assert "manifests_io" not in src, "%s 가 manifests_io 를 참조한다" % name


def test_unknown_impl_raises():
    with pytest.raises(KeyError):
        registry.get("does_not_exist")


def test_always_correct_reproduces_gt_spans():
    impl = registry.get("fake:always_correct")
    raw = impl({"manifest": "b_youtube", "stage": "candidate"})
    by_clip = {r["clip_id"]: r for r in raw}
    # GT 에 사건이 있는 클립은 후보를 돌려주고, 없는 클립은 빈 목록이다.
    assert by_clip["YT_0001_C08"]["candidates"][0]["event_type"] == "SIGNAL"
    assert by_clip["YT_0001_C00"]["candidates"] == []


def test_always_wrong_never_matches_gt_type():
    impl = registry.get("fake:always_wrong")
    raw = impl({"manifest": "b_youtube", "stage": "candidate"})
    by_clip = {r["clip_id"]: r for r in raw}
    assert by_clip["YT_0001_C08"]["candidates"][0]["event_type"] != "SIGNAL"


def test_run_hands_impl_only_manifest_and_stage(monkeypatch):
    """runner 가 impl 에 넘기는 scope 를 실제로 붙잡아 키 집합을 본다.

    §2-5「runner 는 GT 를 모른다」를 지키는 실물은 eval/run.py 의 scope
    조립부 한 줄이다. 여기서 그 줄이 만든 dict 를 그대로 받아 집합 비교를
    하므로, "gt" 든 다른 이름이든 키가 하나라도 늘면 이 테스트가 깨진다.
    """
    seen = []

    def probe(scope):
        seen.append(scope)
        return []

    monkeypatch.setitem(registry._REGISTRY, "fake:probe", probe)
    run.build_envelope("fake:probe", "b_youtube", "candidate", "run_probe_001")

    assert len(seen) == 1
    assert set(seen[0]) == {"manifest", "stage"}
    assert seen[0] == {"manifest": "b_youtube", "stage": "candidate"}


def test_always_correct_reproduces_gt_labels_and_boxes():
    impl = registry.get("fake:always_correct")
    raw = impl({"manifest": "a_aihub", "stage": "classification"})
    gt = manifests_io.load_gt("a_aihub", "classification")
    by_id = {r["sequence_id"]: r for r in raw}
    assert len(by_id) == len(gt["items"])
    for item in gt["items"]:
        p = by_id[item["sequence_id"]]
        assert p["predicted"] == item["label"]
        assert p["target_bbox"] == item.get("target_bbox")


def test_always_wrong_misses_every_label_and_box():
    impl = registry.get("fake:always_wrong")
    raw = impl({"manifest": "a_aihub", "stage": "classification"})
    gt = manifests_io.load_gt("a_aihub", "classification")
    by_id = {r["sequence_id"]: r for r in raw}
    for item in gt["items"]:
        p = by_id[item["sequence_id"]]
        assert p["predicted"] != item["label"]
        assert p["predicted"] in VIOLATION_TYPES  # 구조적으로 틀렸을 뿐 enum 안이다
        box = item.get("target_bbox")
        if box is not None:
            # 완전히 밀어냈으므로 GT bbox 와 겹치는 좌표가 없다.
            assert p["target_bbox"][0] > box[2] and p["target_bbox"][1] > box[3]


def test_unsupported_stage_raises_value_error_not_key_error():
    # 다루지 않는 stage 는 「알 수 없는 impl」과 구분돼야 한다 (run.main 의
    # except KeyError 에 잡히면 미구현이 그 오류로 둔갑한다).
    impl = registry.get("fake:always_correct")
    with pytest.raises(ValueError):
        impl({"manifest": "b_youtube", "stage": "plate"})
