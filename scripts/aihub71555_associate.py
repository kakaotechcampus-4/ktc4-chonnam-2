"""대상 차량 association 기준선 — `aihub71555_detect.py`가 낸 JSON을 다시 접는다.

    python scripts/aihub71555_associate.py --detections detections.json > ASSOCIATION.md

## 이게 readout의 지표다

`module-architecture.md` 모듈 3 ②의 첫 책임이 **대상 차량 association**이고, ③은
`target_hint`가 없어도 **자체 association을 시도해야 한다**고 못박는다(§696 · §1155).
이 스크립트는 그 「hint 없을 때」의 기준선을 잰다.

검출기가 **위반 차량을 찾아내는가**는 `search`의 지표지 readout의 것이 아니다.
여기서 검출률은 association의 **상한**으로만 쓴다 — 후보에 대상이 없으면 무엇을
고르든 틀리기 때문이다.

## 한계 두 가지 (수치를 읽기 전에)

1. **readout이 받는 것은 프레임이 아니라 span이다.** 프레임 단위 선택은 근사다.
   span 전체에서 한 대상을 고르는 문제는 클립 단위 표본이 있어야 잴 수 있다.
2. **`condition.DayNights` 기준 slice를 내지 않는다.** 이 필드가 실제 화면과 어긋나는
   사례가 확인됐다(overlay 타임스탬프 대조). 감사 전까지는 이 축으로 자르지 않는다.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path


def area(b) -> float:
    return b[2] * b[3]


def center(b) -> tuple[float, float]:
    return b[0] + b[2] / 2, b[1] + b[3] / 2


def dist2(p, q) -> float:
    return (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2


# hint 없이 후보 하나를 고르는 규칙들. 전부 「검출 결과만 보고」 고른다 —
# 라벨도, 위반 여부도 쓰지 않는다. 그게 실제 readout이 놓인 상황이다.
HEURISTICS = {
    "최대 면적": lambda dets, wh: max(dets, key=lambda d: area(d["bbox"])),
    "최대 높이": lambda dets, wh: max(dets, key=lambda d: d["bbox"][3]),
    "conf 최고": lambda dets, wh: max(dets, key=lambda d: d["conf"]),
    "화면 중앙 최근접": lambda dets, wh: min(
        dets, key=lambda d: dist2(center(d["bbox"]), (wh[0] / 2, wh[1] / 2))),
    "하단 중앙 최근접": lambda dets, wh: min(
        dets, key=lambda d: dist2(center(d["bbox"]), (wh[0] / 2, wh[1]))),
}


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.1f}%" if b else "—"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--detections", default="detections.json")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        return demo()

    d = json.loads(Path(args.detections).read_text(encoding="utf-8"))
    frames = d["frames"]

    # 분모를 셋으로 나눈다. 섞으면 「못 찾은 것」과 「찾고도 잘못 고른 것」이 합쳐진다.
    with_gt = [f for f in frames if any(g["kind"] == "위반" for g in f["gts"])]
    scorable = [f for f in with_gt if f["dets"]]                       # 고를 후보가 있다
    reachable = [f for f in scorable                                    # 후보에 대상이 있다
                 if any(x["matched_gt"] == "위반" for x in f["dets"])]

    print("## 분모\n")
    print("| | 프레임 | 비고 |\n| --- | ---: | --- |")
    print(f"| 표본 전체 | {len(frames)} | |")
    print(f"| 위반 차량 GT가 있는 프레임 | {len(with_gt)} | 없는 프레임은 대상이 없다 |")
    print(f"| + 검출 후보가 1개 이상 | {len(scorable)} | 고를 것이 있다 |")
    print(f"| + 후보 안에 대상이 있다 (**상한**) | {len(reachable)} | "
          f"{pct(len(reachable), len(scorable))} — 여기가 천장이다 |")

    print("\n## 후보가 몇 개인가 — association이 필요한 상황인가\n")
    n_dets = collections.Counter(min(len(f["dets"]), 10) for f in scorable)
    print("| 후보 수 | 프레임 | 비율 |\n| --- | ---: | ---: |")
    for k in sorted(n_dets):
        label = "10+" if k == 10 else str(k)
        print(f"| {label} | {n_dets[k]} | {pct(n_dets[k], len(scorable))} |")
    solo = sum(v for k, v in n_dets.items() if k <= 1)
    print(f"\n후보가 1개뿐이라 고민이 없는 프레임: **{pct(solo, len(scorable))}**. "
          f"나머지 {pct(len(scorable) - solo, len(scorable))}에서 실제로 골라야 한다.")

    multi = sum(1 for f in with_gt if sum(g["kind"] == "위반" for g in f["gts"]) > 1)
    print(f"\n위반 차량 GT가 **2개 이상**인 프레임: {multi} "
          f"({pct(multi, len(with_gt))}) — 「하나 고르기」가 정의부터 성립하지 않는다.")

    print("\n## hint 없는 선택 규칙별 정확도\n")
    print("| 규칙 | 상한 대비 (후보에 대상이 있을 때) | 전체 대비 (후보가 있을 때) |\n"
          "| --- | ---: | ---: |")
    hits = {}
    for name, pick in HEURISTICS.items():
        h_reach = sum(1 for f in reachable if pick(f["dets"], f["image_wh"])["matched_gt"] == "위반")
        h_all = sum(1 for f in scorable if pick(f["dets"], f["image_wh"])["matched_gt"] == "위반")
        hits[name] = (h_reach, h_all)
        print(f"| {name} | {pct(h_reach, len(reachable))} | {pct(h_all, len(scorable))} |")
    print(f"| *(상한 — 후보에 대상이 있기만 하면 맞다고 칠 때)* | 100.0% | "
          f"**{pct(len(reachable), len(scorable))}** |")

    print("\n### 틀릴 때 무엇을 고르나\n")
    print("| 규칙 | 정상 차량을 고름 | 어느 GT에도 없는 검출을 고름 |\n| --- | ---: | ---: |")
    for name, pick in HEURISTICS.items():
        picks = [pick(f["dets"], f["image_wh"]) for f in reachable]
        normal = sum(1 for p in picks if p["matched_gt"] == "정상")
        none_ = sum(1 for p in picks if p["matched_gt"] is None)
        print(f"| {name} | {normal} ({pct(normal, len(reachable))}) | "
              f"{none_} ({pct(none_, len(reachable))}) |")

    print("\n## 위반 대분류별 (최대 면적 규칙)\n")
    print("| 대분류 | 상한 대비 | 전체 대비 | 상한 |\n| --- | ---: | ---: | ---: |")
    pick = HEURISTICS["최대 면적"]
    for major in sorted({f["major"] for f in scorable}):
        sc = [f for f in scorable if f["major"] == major]
        re_ = [f for f in reachable if f["major"] == major]
        h = sum(1 for f in re_ if pick(f["dets"], f["image_wh"])["matched_gt"] == "위반")
        print(f"| {major} | {pct(h, len(re_))} | {pct(h, len(sc))} | {pct(len(re_), len(sc))} |")

    # 같은 클립의 프레임이 몇 장씩 뽑혔는지 — 시간축 안정성을 잴 수 있는지의 판정이다.
    per_clip = collections.Counter(f["clip"] for f in frames)
    multi_clip = sum(1 for v in per_clip.values() if v > 1)
    print(f"\n## 시간축 안정성 — 이 표본으로는 못 잰다\n")
    print(f"표본 {len(frames)}프레임은 클립 {len(per_clip)}개에 흩어져 있고, "
          f"2프레임 이상 뽑힌 클립은 {multi_clip}개다. "
          f"게다가 층 안에서 무작위로 뽑아 **연속 프레임이 아니다.** "
          f"같은 대상을 계속 고르는지는 **클립 단위 표본이 있어야 잴 수 있다** — 미결로 남긴다.")


def demo() -> None:
    """python scripts/aihub71555_associate.py --selfcheck"""
    wh = (100, 100)
    dets = [
        {"bbox": (0, 0, 10, 10), "conf": 0.9, "matched_gt": "정상"},    # 작고 conf 높음
        {"bbox": (40, 40, 30, 30), "conf": 0.5, "matched_gt": "위반"},  # 크고 중앙
        {"bbox": (80, 0, 5, 40), "conf": 0.3, "matched_gt": None},      # 높지만 좁음
    ]
    assert HEURISTICS["최대 면적"](dets, wh)["matched_gt"] == "위반"
    assert HEURISTICS["최대 높이"](dets, wh)["matched_gt"] is None       # 30 < 40
    assert HEURISTICS["conf 최고"](dets, wh)["matched_gt"] == "정상"
    assert HEURISTICS["화면 중앙 최근접"](dets, wh)["matched_gt"] == "위반"
    # 하단 중앙(50,100)에 가장 가까운 것은 중앙 (55,55) 박스다
    assert HEURISTICS["하단 중앙 최근접"](dets, wh)["matched_gt"] == "위반"
    assert pct(1, 4) == "25.0%" and pct(0, 0) == "—"
    print("selfcheck ok")


if __name__ == "__main__":
    main()
