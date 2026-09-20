"""`aihub71555_detect.py`가 낸 JSON을 조건별 표로 접는다. 마크다운으로 뱉는다.

    python scripts/aihub71555_report.py --detections detections.json > RESULTS.md

**신뢰구간을 내지 않는다.** 한 클립이 25프레임이라 프레임이 서로 독립이 아니고,
독립 가정 CI는 실제보다 좁게 나온다. 대신 층마다 프레임 수와 서로 다른 클립 수를
같이 적어 유효 표본이 얼마인지 읽는 쪽이 판단하게 둔다.
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
from pathlib import Path

BINS = [(0, 30), (30, 50), (50, 100), (100, 200), (200, 10 ** 9)]


def bin_of(h: float) -> str:
    for lo, hi in BINS:
        if lo <= h < hi:
            return f"{lo}–{hi}" if hi < 10 ** 9 else f"{lo}+"
    return "?"


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.1f}%" if b else "—"


class Tally:
    """한 슬라이스의 집계. GT는 검출 여부, 검출은 어느 GT에 붙었는지를 센다."""

    def __init__(self):
        self.frames = 0
        self.clips = set()
        self.gt = collections.Counter()          # kind -> GT 수
        self.hit = collections.Counter()         # kind -> 검출된 GT 수
        self.det = 0
        self.det_on = collections.Counter()      # kind -> 그 kind GT에 붙은 검출 수
        self.fp = 0

    def add(self, frame: dict) -> None:
        self.frames += 1
        self.clips.add(frame.get("clip"))
        for g in frame["gts"]:
            self.gt[g["kind"]] += 1
            if g["matched"]:
                self.hit[g["kind"]] += 1
        for d in frame["dets"]:
            self.det += 1
            if d["matched_gt"]:
                self.det_on[d["matched_gt"]] += 1
            else:
                self.fp += 1

    def row(self, label: str) -> str:
        v, n = self.gt["위반"], self.gt["정상"]
        return (f"| {label} | {self.frames} | {len(self.clips)} | {v} | "
                f"{pct(self.hit['위반'], v)} | {n} | {pct(self.hit['정상'], n)} | "
                f"{self.det} | {pct(self.fp, self.det)} | "
                f"{self.fp / self.frames:.2f} |" if self.frames else "")


HEAD = ("| 구분 | 프레임 | 클립 | 위반 GT | 위반 검출률 | 정상 GT | 정상 검출률 | "
        "검출 수 | 무매칭 비율 | 무매칭/프레임 |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")


def group(frames: list[dict], key) -> str:
    tallies = collections.defaultdict(Tally)
    for f in frames:
        tallies[key(f)].add(f)
    lines = [HEAD]
    for k in sorted(tallies, key=lambda k: -tallies[k].frames):
        lines.append(tallies[k].row(str(k)))
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--detections", default="detections.json")
    d = json.loads(Path(ap.parse_args().detections).read_text(encoding="utf-8"))
    run, frames = d["run"], d["frames"]

    overall = Tally()
    for f in frames:
        overall.add(f)

    print("## 전체\n")
    print(HEAD)
    print(overall.row("전체"))

    print("\n### 검출이 어디에 붙었나\n")
    print("| | 수 | 전체 검출 대비 |\n| --- | ---: | ---: |")
    print(f"| 위반 차량 GT에 매칭 | {overall.det_on['위반']} | {pct(overall.det_on['위반'], overall.det)} |")
    print(f"| 정상 차량 GT에 매칭 | {overall.det_on['정상']} | {pct(overall.det_on['정상'], overall.det)} |")
    print(f"| 어느 차량 GT에도 안 붙음 | {overall.fp} | {pct(overall.fp, overall.det)} |")

    for title, key in [
        ("주야간", lambda f: f["daynight"]),
        ("날씨", lambda f: f["weather"]),
        ("위반 대분류", lambda f: f["major"]),
        ("세부유형", lambda f: f["minor"]),
        ("화면 방향", lambda f: f"{f['orientation']} {f['image_wh'][0]}x{f['image_wh'][1]}"),
        ("도로유형", lambda f: f["road"]),
    ]:
        print(f"\n## {title}\n")
        print(group(frames, key))

    # GT 크기 구간별 검출률 — 검출기가 어디서 무너지는지는 이 축이 가장 크게 가른다.
    print("\n## GT bbox 높이 구간 (검출률만)\n")
    print("| 높이(px) | 위반 GT | 위반 검출률 | 정상 GT | 정상 검출률 |\n"
          "| --- | ---: | ---: | ---: | ---: |")
    by_bin = collections.defaultdict(lambda: collections.Counter())
    for f in frames:
        for g in f["gts"]:
            b = bin_of(g["bbox"][3])
            by_bin[b][g["kind"]] += 1
            if g["matched"]:
                by_bin[b][g["kind"] + "_hit"] += 1
    for lo, hi in BINS:
        b = f"{lo}–{hi}" if hi < 10 ** 9 else f"{lo}+"
        c = by_bin[b]
        print(f"| {b} | {c['위반']} | {pct(c['위반_hit'], c['위반'])} | "
              f"{c['정상']} | {pct(c['정상_hit'], c['정상'])} |")

    # 무매칭 검출이 진짜 오검출인지 라벨 누락인지는 이 표만으로 못 가린다.
    # conf·크기 분포를 남겨 두고 판단은 육안 검수로 미룬다.
    un = [d for f in frames for d in f["dets"] if not d["matched_gt"]]
    hit = [d for f in frames for d in f["dets"] if d["matched_gt"]]
    print("\n## 무매칭 검출의 생김새\n")
    print("| | 수 | conf p10 / 중앙 / p90 | 높이(px) p10 / 중앙 / p90 | 클래스 |\n"
          "| --- | ---: | --- | --- | --- |")
    for lab, group_ in (("차량 GT에 매칭된 검출", hit), ("무매칭 검출", un)):
        if not group_:
            continue
        cs = sorted(d["conf"] for d in group_)
        hs = sorted(d["bbox"][3] for d in group_)
        q = lambda xs, f: xs[min(len(xs) - 1, int(f * len(xs)))]
        cls = collections.Counter(d["cls"] for d in group_)
        print(f"| {lab} | {len(group_)} | "
              f"{q(cs, .1):.2f} / {q(cs, .5):.2f} / {q(cs, .9):.2f} | "
              f"{q(hs, .1):.0f} / {q(hs, .5):.0f} / {q(hs, .9):.0f} | "
              f"{' · '.join(f'{k} {v}' for k, v in cls.most_common())} |")

    heights = [g["bbox"][3] for f in frames for g in f["gts"] if g["kind"] == "위반"]
    if heights:
        q = statistics.quantiles(heights, n=10)
        print(f"\n표본 내 위반 차량 bbox 높이 (n={len(heights):,}): "
              f"p10 {q[0]:.0f} · 중앙 {statistics.median(heights):.0f} · p90 {q[-1]:.0f} px")

    print(f"\n## 실행\n\n```json\n{json.dumps(run, ensure_ascii=False, indent=1)}\n```")


if __name__ == "__main__":
    main()
