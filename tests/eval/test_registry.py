import pytest

from eval import run
from eval.runners import registry


def test_both_fakes_are_registered_under_fake_prefix():
    names = registry.names()
    assert "fake:always_correct" in names
    assert "fake:always_wrong" in names
    assert all(n.startswith("fake:") for n in names)


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
