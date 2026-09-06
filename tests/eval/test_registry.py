import pytest
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


def test_always_correct_does_not_receive_gt_from_caller():
    # scope 에 GT 를 넣지 않아도 동작해야 한다 — impl 이 스스로 읽는다.
    impl = registry.get("fake:always_correct")
    scope = {"manifest": "b_youtube", "stage": "candidate"}
    assert "gt" not in scope
    assert impl(scope)
