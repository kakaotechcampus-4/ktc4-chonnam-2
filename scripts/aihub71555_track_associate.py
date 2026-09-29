"""hint 없는 대상 차량 association — 프레임이 아니라 **트랙**을 고른다.

    python scripts/aihub71555_track_associate.py --selfcheck
    python scripts/aihub71555_track_associate.py \
        --dev clip-detections.json --holdout holdout-detections.json > TRACKS.md

`aihub71555_detect.py`가 `--by-clip` manifest로 만든 검출 결과를 받는다.

## 무엇을 바꾸나

track1(2026-09-19)은 프레임마다 검출 박스 하나를 독립으로 골랐다. 최고 규칙(conf 최고)이
프레임 단위 35.1%, 클립 단위 Best Frame 25.8%였다. 이 스크립트는

1. 연속 프레임의 검출을 IoU로 이어 **트랙**을 만들고
2. 트랙마다 **클립 안에서만 알 수 있는 특징**(지속 · 크기 · 위치 · 움직임)을 뽑아
3. 클립당 트랙 하나를 고른다.

## readout 입력 경계를 지킨다

특징은 **incident clip의 픽셀에서 나오는 것만** 쓴다(`contract-readout-run.md` —
`read_plate(span, target_hint?)`). 위반 유형(`visual_event_type`)은 readout 입력이 아니므로
**선택에 쓰지 않는다.** 표의 유형별 행은 채점용 분류일 뿐이다. GT(`matched_gt`)는 채점에만 쓴다.

## 채점

트랙의 정답 = 그 트랙 프레임들의 `matched_gt` 다수결. 클립 정답 = 고른 트랙이 「위반」.
분모는 **위반 차량이 한 번이라도 보이고 검출 트랙이 1개 이상인 클립**이다.
천장(oracle) = 위반 트랙이 하나라도 있는 클립 비율.

## 학습 규칙의 과적합 방지

학습 규칙(conditional logit)은 **dev에서 클립 단위 5-fold CV**로 먼저 재고, dev 전체로
학습한 가중치를 **다른 seed로 뽑은 holdout**에 한 번만 적용한다. dev와 겹치는 holdout
클립은 뺀다.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import random
from pathlib import Path

import numpy as np

LINK_IOU = 0.3
"""트랙을 잇는 최소 IoU. 클립 표본은 프레임 간격이 넓어 0.5면 빠른 차가 끊긴다."""
MAX_GAP = 1
"""검출이 이만큼 빠져도 같은 트랙으로 잇는다 — track1 §3-①에서 끊김 1~2회가 14.6%였다."""


def iou(a, b) -> float:
    ax2, ay2, bx2, by2 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    iw = max(0.0, min(ax2, bx2) - max(a[0], b[0]))
    ih = max(0.0, min(ay2, by2) - max(a[1], b[1]))
    inter = iw * ih
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def build_tracks(frames: list[dict]) -> list[list[tuple[int, dict]]]:
    """greedy IoU 체이닝. 반환은 트랙마다 `[(frame_pos, det), ...]`."""
    tracks: list[list[tuple[int, dict]]] = []
    for pos, f in enumerate(frames):
        alive = [t for t in tracks if pos - t[-1][0] <= MAX_GAP + 1]
        pairs = sorted(((iou(t[-1][1]["bbox"], d["bbox"]), ti, di)
                        for ti, t in enumerate(alive) for di, d in enumerate(f["dets"])),
                       reverse=True)
        used_t, used_d = set(), set()
        for score, ti, di in pairs:
            if score < LINK_IOU or ti in used_t or di in used_d:
                continue
            alive[ti].append((pos, f["dets"][di]))
            used_t.add(ti)
            used_d.add(di)
        for di, d in enumerate(f["dets"]):
            if di not in used_d:
                tracks.append([(pos, d)])
    return tracks


BASE_FEATURES = ("cover", "conf_mean", "area_mean", "area_max", "cx_off", "cy_mean",
                 "dx_net", "dx_path", "growth", "is_moto", "conf_top_votes")
REL_FEATURES = ("dx_rel", "crosses_center", "rank_cover", "rank_conf", "rank_area")
"""클립 안에서의 상대 특징. 위반 차량은 「크다」보다 「다른 차와 다르게 움직인다」일 수 있다 —
진로변경·중앙선침범은 옆 이동이, 신호위반은 교차로를 가로지르는 이동이 특징이다."""
FEATURES = BASE_FEATURES + REL_FEATURES


def track_features(track, n_frames: int, wh, top_conf_votes: int) -> dict:
    w, h = wh
    boxes = [d["bbox"] for _, d in track]
    cx = [(b[0] + b[2] / 2) / w for b in boxes]
    cy = [(b[1] + b[3] / 2) / h for b in boxes]
    area = [b[2] * b[3] / (w * h) for b in boxes]
    return {
        "crosses_center": float(min(cx) < 0.5 < max(cx)),
        "cover": len(track) / n_frames,
        "conf_mean": sum(d["conf"] for _, d in track) / len(track),
        "area_mean": math.sqrt(sum(area) / len(area)),      # 한 변 길이 비율로 편다
        "area_max": math.sqrt(max(area)),
        "cx_off": abs(sum(cx) / len(cx) - 0.5),
        "cy_mean": sum(cy) / len(cy),
        "dx_net": abs(cx[-1] - cx[0]),
        "dx_path": sum(abs(b - a) for a, b in zip(cx, cx[1:])),
        "growth": math.log(max(area[-1], 1e-6) / max(area[0], 1e-6)),
        "is_moto": float(any(d["cls"] == "motorcycle" for _, d in track)),
        "conf_top_votes": top_conf_votes / n_frames,
    }


def track_label(track) -> str | None:
    votes = collections.Counter(d["matched_gt"] for _, d in track)
    return votes.most_common(1)[0][0] if votes else None


def load_clips(path: Path, exclude: set[str] = frozenset()) -> list[dict]:
    """클립마다 `{clip, major, tracks: [{feat, label, frames}], ...}`."""
    frames = json.loads(path.read_text(encoding="utf-8"))["frames"]
    by_clip = collections.defaultdict(list)
    for f in frames:
        by_clip[f["clip"]].append(f)
    out = []
    for name, fs in by_clip.items():
        if name in exclude:
            continue
        fs.sort(key=lambda f: f.get("clip_pos", f.get("frame_index", 0)))
        if not any(g["kind"] == "위반" for f in fs for g in f["gts"]):
            continue
        tracks = build_tracks(fs)
        if not tracks:
            continue
        # 프레임마다 conf 최고 박스가 어느 트랙에 속했나 — 기존 규칙을 트랙으로 올린 것
        owner = {id(d): ti for ti, t in enumerate(tracks) for _, d in t}
        votes = collections.Counter(owner[id(max(f["dets"], key=lambda d: d["conf"]))]
                                    for f in fs if f["dets"])
        wh = fs[0]["image_wh"]
        rows = [{"feat": track_features(t, len(fs), wh, votes[ti]),
                 "label": track_label(t), "len": len(t)}
                for ti, t in enumerate(tracks)]
        add_relative([r["feat"] for r in rows])
        out.append({"clip": name, "major": fs[0]["major"], "n_frames": len(fs), "tracks": rows})
    return out


def add_relative(feats: list[dict]) -> None:
    """같은 클립 트랙끼리 비교한 값을 채운다. 순위는 0(최하)~1(최고)."""
    dx = sorted(f["dx_path"] for f in feats)
    median_dx = dx[len(dx) // 2]
    for key, src in (("rank_cover", "cover"), ("rank_conf", "conf_mean"), ("rank_area", "area_mean")):
        order = sorted(range(len(feats)), key=lambda i: feats[i][src])
        for r, i in enumerate(order):
            feats[i][key] = r / (len(feats) - 1) if len(feats) > 1 else 1.0
    for f in feats:
        f["dx_rel"] = f["dx_path"] - median_dx


# ── 선택 규칙 ────────────────────────────────────────────────

def rule(key):
    return lambda clip: max(range(len(clip["tracks"])), key=lambda i: clip["tracks"][i]["feat"][key])


RULES = {
    "트랙 conf-최고 득표 (기존 규칙을 트랙으로)": rule("conf_top_votes"),
    "가장 오래 보인 트랙": rule("cover"),
    "평균 크기 최대 트랙": rule("area_mean"),
    "옆으로 가장 많이 움직인 트랙": rule("dx_path"),
    "지속×conf": lambda c: max(range(len(c["tracks"])),
                              key=lambda i: c["tracks"][i]["feat"]["cover"] * c["tracks"][i]["feat"]["conf_mean"]),
}


def matrix(clip, mean=None, std=None, feats=FEATURES):
    x = np.array([[t["feat"][k] for k in feats] for t in clip["tracks"]], dtype=float)
    return x if mean is None else (x - mean) / std


def fit_logit(clips, feats=FEATURES, l2=0.05, steps=800, lr=0.3):
    """conditional logit — 클립 안에서 softmax로 정답 트랙의 확률을 올린다.

    클립마다 트랙 수가 달라 일반 분류기보다 이쪽이 맞다: 「이 트랙이 위반인가」가 아니라
    「이 클립에서 어느 트랙인가」를 배운다. 정답 트랙이 없는 클립은 학습에서 뺀다.
    """
    usable = [c for c in clips if any(t["label"] == "위반" for t in c["tracks"])]
    allx = np.vstack([matrix(c, feats=feats) for c in usable])
    mean, std = allx.mean(0), allx.std(0) + 1e-9
    xs = [matrix(c, mean, std, feats) for c in usable]
    ys = [np.array([t["label"] == "위반" for t in c["tracks"]], dtype=float) for c in usable]
    ys = [y / y.sum() for y in ys]
    wgt = np.zeros(len(feats))
    for _ in range(steps):
        grad = l2 * wgt
        for x, y in zip(xs, ys):
            s = x @ wgt
            p = np.exp(s - s.max())
            p /= p.sum()
            grad += x.T @ (p - y) / len(xs)
        wgt -= lr * grad
    return wgt, mean, std, feats


def logit_rule(model):
    wgt, mean, std, feats = model
    return lambda clip: int(np.argmax(matrix(clip, mean, std, feats) @ wgt))


# ── 채점 ────────────────────────────────────────────────────

def score(clips, pick) -> dict:
    hit = normal = 0
    for c in clips:
        label = c["tracks"][pick(c)]["label"]
        hit += label == "위반"
        normal += label == "정상"
    oracle = sum(any(t["label"] == "위반" for t in c["tracks"]) for c in clips)
    return {"n": len(clips), "hit": hit, "normal": normal, "oracle": oracle}


def cv_logit(clips, feats=FEATURES, folds=5, seed=20260927) -> dict:
    idx = list(range(len(clips)))
    random.Random(seed).shuffle(idx)
    total = collections.Counter()
    for k in range(folds):
        test = [clips[i] for i in idx[k::folds]]
        train = [clips[i] for i in idx if i not in set(idx[k::folds])]
        total.update(score(test, logit_rule(fit_logit(train, feats))))
    return dict(total)


def pct(a, b) -> str:
    return f"{100 * a / b:.1f}%" if b else "—"


def row(name, s) -> str:
    wrong = s["n"] - s["hit"]
    return (f"| {name} | {s['hit']}/{s['n']} | **{pct(s['hit'], s['n'])}** | "
            f"{pct(s['hit'], s['oracle'])} | {pct(s['normal'], wrong)} |")


HEAD = ("| 규칙 | 맞은 클립 | 정확도 | 천장 대비 | 틀릴 때 정상 차량 |\n"
        "| --- | ---: | ---: | ---: | ---: |")


def by_major(clips, pick) -> list[str]:
    lines = ["| 대분류 | 클립 | 정확도 | 천장 |", "| --- | ---: | ---: | ---: |"]
    for major in sorted({c["major"] for c in clips}):
        sel = [c for c in clips if c["major"] == major]
        s = score(sel, pick)
        lines.append(f"| {major} | {s['n']} | {pct(s['hit'], s['n'])} | {pct(s['oracle'], s['n'])} |")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dev")
    ap.add_argument("--holdout")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        return demo()

    dev = load_clips(Path(args.dev))
    dev_names = {c["clip"] for c in dev}
    hold = load_clips(Path(args.holdout), exclude=dev_names) if args.holdout else []

    print(f"## 표본\n\n| | dev | holdout |\n| --- | ---: | ---: |")
    print(f"| 클립 (위반 보임 · 트랙 ≥1) | {len(dev)} | {len(hold)} |")
    print(f"| 클립당 트랙 수 중앙 | {np.median([len(c['tracks']) for c in dev]):.0f} | "
          f"{np.median([len(c['tracks']) for c in hold]) if hold else 0:.0f} |")
    print(f"| 천장 (위반 트랙이 있는 클립) | {pct(score(dev, rule('cover'))['oracle'], len(dev))} | "
          f"{pct(score(hold, rule('cover'))['oracle'], len(hold)) if hold else '—'} |")

    for name, clips in (("dev", dev), ("holdout", hold)):
        if not clips:
            continue
        print(f"\n## 고정 규칙 — {name}\n\n{HEAD}")
        for rname, pick in RULES.items():
            print(row(rname, score(clips, pick)))

    print(f"\n## 학습 규칙 (conditional logit)\n\n{HEAD}")
    no_moto = tuple(k for k in BASE_FEATURES if k != "is_moto")
    for fname, feats in (("기본 11종", BASE_FEATURES), ("기본+상대 16종", FEATURES),
                         ("기본 − 오토바이 여부", no_moto)):
        print(row(f"{fname} · dev 5-fold CV", cv_logit(dev, feats)))
        if hold:
            print(row(f"**{fname} · dev 학습 → holdout 1회**",
                      score(hold, logit_rule(fit_logit(dev, feats)))))
    model = fit_logit(dev, BASE_FEATURES)
    print("\n### 가중치 (표준화 특징 기준, dev 전체 학습)\n")
    print("| 특징 | 가중치 |\n| --- | ---: |")
    for k, v in sorted(zip(model[3], model[0]), key=lambda kv: -abs(kv[1])):
        print(f"| `{k}` | {v:+.2f} |")

    target = hold or dev
    print(f"\n## 대분류별 — 학습 규칙 ({'holdout' if hold else 'dev'})\n")
    print("\n".join(by_major(target, logit_rule(model))))


def demo() -> None:
    """python scripts/aihub71555_track_associate.py --selfcheck"""
    assert iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0
    assert iou([0, 0, 10, 10], [20, 20, 5, 5]) == 0.0
    det = lambda x, gt, conf=0.5: {"bbox": [x, 0, 10, 10], "conf": conf, "cls": "car", "matched_gt": gt}  # noqa: E731
    frames = [{"dets": [det(0, "위반"), det(100, "정상")]},
              {"dets": [det(2, "위반"), det(101, "정상")]},
              {"dets": []},                                  # 한 프레임 빠져도 이어진다
              {"dets": [det(4, "위반")]}]
    tracks = build_tracks(frames)
    assert sorted(len(t) for t in tracks) == [2, 3], tracks
    assert track_label(max(tracks, key=len)) == "위반"
    # 두 프레임 넘게 빠지면 새 트랙이다
    far = [{"dets": [det(0, "위반")]}, {"dets": []}, {"dets": []}, {"dets": [det(0, "위반")]}]
    assert len(build_tracks(far)) == 2
    # conditional logit이 분리 가능한 장난감 문제를 푼다 — 위반 트랙이 항상 더 오래 보인다
    toy = []
    for i in range(20):
        mk = lambda cover, label: {"feat": {k: 0.0 for k in FEATURES} | {"cover": cover, "conf_mean": 0.5},  # noqa: E731
                                   "label": label, "len": 1}
        toy.append({"clip": str(i), "major": "x", "n_frames": 5,
                    "tracks": [mk(0.9, "위반"), mk(0.2 + i * 0.01, "정상")]})
    assert score(toy, logit_rule(fit_logit(toy)))["hit"] == 20
    print("selfcheck ok")


if __name__ == "__main__":
    main()
