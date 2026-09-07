"""이름표 → 호출 가능 객체.

entry_points·동적 로딩을 쓰지 않는다 (harness-v1-design.md §2-3).
가짜 구현은 `fake:` 접두어로 격리한다.
"""
from eval.runners.impls import fake_always_correct, fake_always_wrong, mock_pack

_REGISTRY = {
    "fake:always_correct": fake_always_correct.run,
    "fake:always_wrong": fake_always_wrong.run,
    # 팀 공용 Mock Pack 산출물을 읽는다. 정답지를 보지 않으므로 fake: 가 아니다.
    "mock_pack:contracts": mock_pack.run,
}


def get(name):
    if name not in _REGISTRY:
        raise KeyError(
            "알 수 없는 impl 이름표: %r (등록된 것: %s)" % (name, ", ".join(names()))
        )
    return _REGISTRY[name]


def names():
    return sorted(_REGISTRY)
