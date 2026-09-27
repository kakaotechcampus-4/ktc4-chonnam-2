"""클립(span) 단위 분석 — 검출 지속성 · multi-frame 성립 · Best Frame 전략.

    python scripts/aihub71555_clips.py --detections clip-detections.json > CLIPS.md

`--by-clip`으로 뽑은 manifest로 돌린 `aihub71555_detect.py` 결과를 받는다.
프레임 단위 표본으로 돌리면 연속 프레임이 아니라 지속성 수치가 거짓이 된다.

## 이 스크립트가 답하는 것

readout이 받는 것은 프레임이 아니라 **span**이다. 「데이터 전처리 설계」의
**프레임 선택 전략(Best Frame / Multi-frame 적용 여부와 기준)**이 여기서 갈린다.

| 질문 | 지표 |
| --- | --- |
| 대상이 span 안에서 몇 프레임이나 잡히나 | `frames_detected / frames_visible` |
| 툭툭 끊기나 (tracker가 필요한가) | `longest_run` · `gaps` |
| multi-frame 합의가 성립하나 | `frames_detected >= 2` 인 클립 비율 |
| 한 프레임만 고르면 되나, 여러 장이 필요한가 | per-frame vs Best Frame vs oracle |

## 한계 — 인스턴스 ID가 없다

라벨에 추적 ID가 없어 **클립 단위**로만 센다(「이 프레임에 대상이 보였나 / 잡혔나」).
위반 차량이 2대 이상인 클립에서는 서로 다른 차가 한 축으로 합쳐진다. 인스턴스 단위로
가르려면 IoU 체이닝 추적기를 붙여야 하고, **그 추적기 자체가 검증 안 된 휴리스틱**이라
여기서는 쓰지 않는다. 다중 대상 클립 비율을 같이 찍어 둔다.
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
from pathlib import Path


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.1f}%" if b else "—"


def runs(flags: list[bool]) -> tuple[int, int]:
    """(최장 연속 True 길이, 끊긴 횟수). 앞뒤의 False는 끊김으로 세지 않는다 —
    대상이 화면에 들어오기 전/나간 뒤는 「끊김」이 아니다."""
    longest = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        longest = max(longest, cur)
    try:
        first, last = flags.index(True), len(flags) - 1 - flags[::-1].index(True)
    except ValueError:
        return 0, 0
    gaps, inside = 0, flags[first:last + 1]
    for i, f in enumerate(inside):
        if not f and (i == 0 or inside[i - 1]):
            gaps += 1
    return longest, gaps


def pick_top_conf(dets):
    return max(dets, key=lambda d: d["conf"])


def build(frames: list[dict]) -> dict:
    """클립별로 프레임을 시간순으로 모은다."""
    clips = collections.defaultdict(list)
    for f in frames:
        clips[f["clip"]].append(f)
    for fs in clips.values():
        fs.sort(key=lambda f: f.get("clip_pos", f.get("frame_index", 0)))
    return clips


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--detections", default="clip-detections.json")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        return demo()

    d = json.loads(Path(args.detections).read_text(encoding="utf-8"))
    clips = build(d["frames"])

    rows = []
    for name, fs in clips.items():
        visible = [any(g["kind"] == "위반" for g in f["gts"]) for f in fs]
        detected = [any(x["matched_gt"] == "위반" for x in f["dets"]) for f in fs]
        n_vis = sum(visible)
        if not n_vis:
            continue
        longest, gaps = runs(detected)
        # hint 없는 규칙(conf 최고)을 프레임마다 독립으로 적용했을 때
        picks = [pick_top_conf(f["dets"])["matched_gt"] if f["dets"] else None for f in fs]
        # Best Frame — 검출 박스가 가장 큰 프레임 하나만 본다 (GT를 쓰지 않는다)
        sized = [(max((x["bbox"][2] * x["bbox"][3] for x in f["dets"]), default=0), i)
                 for i, f in enumerate(fs)]
        best_i = max(sized)[1]
        rows.append({
            "clip": name, "major": fs[0]["major"], "minor": fs[0]["minor"],
            "frames": len(fs), "visible": n_vis, "detected": sum(detected),
            "longest_run": longest, "gaps": gaps,
            "multi_target": max(sum(g["kind"] == "위반" for g in f["gts"]) for f in fs) > 1,
            "per_frame_hits": sum(p == "위반" for p in picks),
            "per_frame_n": len(fs),
            "best_frame_hit": picks[best_i] == "위반",
            "any_frame_hit": any(p == "위반" for p in picks),
            "picked_normal_frames": sum(p == "정상" for p in picks),
        })

    print(f"## 표본\n")
    run = d["run"]
    print("| | 값 |\n| --- | ---: |")
    print(f"| 클립 | {len(clips)} |")
    print(f"| 대상이 한 번이라도 보이는 클립 | {len(rows)} |")
    print(f"| 프레임 | {run['frames_scored']:,} |")
    print(f"| 클립당 프레임 | 중앙 {statistics.median(r['frames'] for r in rows):.0f} · "
          f"최소 {min(r['frames'] for r in rows)} · 최대 {max(r['frames'] for r in rows)} |")
    print(f"| 위반 차량이 2대 이상인 클립 | {sum(r['multi_target'] for r in rows)} "
          f"({pct(sum(r['multi_target'] for r in rows), len(rows))}) — 인스턴스가 합쳐진다 |")
    print(f"| 실행 | {run['elapsed_sec']}s · {run['sec_per_frame']}s/프레임 |")

    print("\n## ① 검출 지속성 — 대상이 span 안에서 얼마나 붙어 있나\n")
    ratio = [r["detected"] / r["visible"] for r in rows]
    print("| 지표 | 중앙 | p10 | p90 |\n| --- | ---: | ---: | ---: |")
    for label, vals in (("보이는 프레임 수", [r["visible"] for r in rows]),
                        ("그중 검출된 프레임 수", [r["detected"] for r in rows]),
                        ("검출 비율", ratio),
                        ("최장 연속 검출", [r["longest_run"] for r in rows]),
                        ("끊긴 횟수", [r["gaps"] for r in rows])):
        q = statistics.quantiles(vals, n=10) if len(vals) > 1 else [vals[0]] * 9
        fmt = (lambda v: f"{v:.2f}") if label == "검출 비율" else (lambda v: f"{v:.0f}")
        print(f"| {label} | {fmt(statistics.median(vals))} | {fmt(q[0])} | {fmt(q[-1])} |")

    print("\n### tracker가 필요한가\n")
    print("| | 클립 | 비율 |\n| --- | ---: | ---: |")
    for label, cond in (
        ("한 번도 안 끊김 (gaps = 0)", lambda r: r["gaps"] == 0),
        ("1~2회 끊김", lambda r: 1 <= r["gaps"] <= 2),
        ("3회 이상 끊김", lambda r: r["gaps"] >= 3),
    ):
        n = sum(1 for r in rows if cond(r))
        print(f"| {label} | {n} | {pct(n, len(rows))} |")

    print("\n## ② multi-frame 합의가 성립하나\n")
    print("| 조건 | 클립 | 비율 |\n| --- | ---: | ---: |")
    for label, k in (("검출 0프레임 — 합의 불가", 0), ("1프레임만 — `MULTI_FRAME` 불가", 1)):
        n = sum(1 for r in rows if r["detected"] == k)
        print(f"| {label} | {n} | {pct(n, len(rows))} |")
    for k in (2, 3, 5):
        n = sum(1 for r in rows if r["detected"] >= k)
        print(f"| **{k}프레임 이상 — 합의 가능** | {n} | **{pct(n, len(rows))}** |")

    print("\n## ③ 프레임 선택 전략 — 한 장이면 되나, 여러 장이 필요한가\n")
    print("`target_hint` 없이 `conf 최고`로 고른다. 분모는 대상이 보이는 클립 "
          f"{len(rows)}개다.\n")
    print("| 전략 | 맞은 클립 | 비율 |\n| --- | ---: | ---: |")
    tot_f = sum(r["per_frame_n"] for r in rows)
    tot_h = sum(r["per_frame_hits"] for r in rows)
    print(f"| (참고) 프레임 단위 정확도 | {tot_h}/{tot_f} | {pct(tot_h, tot_f)} |")
    bf = sum(r["best_frame_hit"] for r in rows)
    print(f"| **Best Frame — 검출 박스가 가장 큰 프레임 1장** | {bf} | **{pct(bf, len(rows))}** |")
    anyf = sum(r["any_frame_hit"] for r in rows)
    print(f"| *(oracle)* 어느 프레임에서든 한 번이라도 맞음 | {anyf} | {pct(anyf, len(rows))} |")
    print(f"\noracle은 **어떤 프레임 선택 전략도 넘을 수 없는 천장**이다. "
          f"Best Frame이 {pct(bf, len(rows))}, 천장이 {pct(anyf, len(rows))}.")

    print("\n## ④ 클립 안에서 선택이 흔들리나\n")
    stable = sum(1 for r in rows if r["per_frame_hits"] in (0, r["per_frame_n"]))
    print(f"프레임마다 독립으로 고를 때, 클립 내내 **한결같이 맞거나 한결같이 틀린** 클립은 "
          f"{stable}개({pct(stable, len(rows))})다. 나머지 {pct(len(rows) - stable, len(rows))}는 "
          f"**같은 span 안에서 답이 바뀐다** — 프레임을 아무거나 고르면 안 된다는 뜻이다.")

    print("\n## ⑤ 위반 대분류별\n")
    print("| 대분류 | 클립 | 검출 비율 중앙 | 합의 가능(≥2) | Best Frame | oracle |\n"
          "| --- | ---: | ---: | ---: | ---: | ---: |")
    for major in sorted({r["major"] for r in rows}):
        sel = [r for r in rows if r["major"] == major]
        print(f"| {major} | {len(sel)} | "
              f"{statistics.median(r['detected'] / r['visible'] for r in sel):.2f} | "
              f"{pct(sum(r['detected'] >= 2 for r in sel), len(sel))} | "
              f"{pct(sum(r['best_frame_hit'] for r in sel), len(sel))} | "
              f"{pct(sum(r['any_frame_hit'] for r in sel), len(sel))} |")

    print("\n## 클립별 원자료\n")
    print("| clip | 세부유형 | 프레임 | 보임 | 검출 | 최장연속 | 끊김 | BestFrame |\n"
          "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |")
    for r in sorted(rows, key=lambda r: (r["minor"], r["clip"])):
        print(f"| `{r['clip']}` | {r['minor']} | {r['frames']} | {r['visible']} | "
              f"{r['detected']} | {r['longest_run']} | {r['gaps']} | "
              f"{'✅' if r['best_frame_hit'] else '❌'} |")


def demo() -> None:
    """python scripts/aihub71555_clips.py --selfcheck"""
    assert runs([True, True, False, True]) == (2, 1)
    assert runs([False, True, True, False]) == (2, 0)      # 앞뒤 False는 끊김이 아니다
    assert runs([True, False, False, True]) == (1, 1)      # 연속된 공백은 1회
    assert runs([True, False, True, False, True]) == (1, 2)
    assert runs([False, False]) == (0, 0)
    assert runs([True]) == (1, 0)

    fs = [{"clip": "c", "clip_pos": 1, "major": "m", "minor": "n",
           "gts": [{"kind": "위반"}], "dets": [{"conf": 0.9, "matched_gt": "정상",
                                                "bbox": (0, 0, 9, 9)}]},
          {"clip": "c", "clip_pos": 0, "major": "m", "minor": "n",
           "gts": [{"kind": "위반"}], "dets": [{"conf": 0.5, "matched_gt": "위반",
                                                "bbox": (0, 0, 20, 20)}]}]
    clips = build(fs)
    assert [f["clip_pos"] for f in clips["c"]] == [0, 1]   # 시간순으로 정렬된다
    assert pct(1, 4) == "25.0%" and pct(0, 0) == "—"
    print("selfcheck ok")


if __name__ == "__main__":
    main()
