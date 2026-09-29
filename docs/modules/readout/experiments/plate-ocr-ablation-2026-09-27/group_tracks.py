"""`find_plates.py` 후보를 번호판 트랙(= 차 한 대)으로 묶고, 트랙마다 가장 크게 찍힌 한 장을 고른다.

    python group_tracks.py <picks.json> <out picks.json>

크기 순으로만 고르면 한 차가 시트를 다 차지한다. 여기서는 차마다 한 장이다.
화면 맨 아래 띠(세로 88% 아래)는 블랙박스 시각 overlay 자리라 후보에서 뺀다 — MDR 영상에서
overlay 글자가 번호판으로 검출됐다.
"""
import json
import sys

OVERLAY_BAND = 0.88
MAX_TRACKS = 12


def center(b):
    return b[0] + b[2] / 2, b[1] + b[3] / 2


def same_track(last, c):
    """0.5초 간격 표본에서 IoU는 자주 0이 된다 — 거리와 크기 비로 잇는다."""
    if c["t"] - last["t"] > 1.0:
        return False
    (x1, y1), (x2, y2) = center(last["plate"]), center(c["plate"])
    dist = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
    ratio = c["plate"][3] / max(last["plate"][3], 1)
    return dist < 1.5 * max(last["plate"][2], c["plate"][2]) and 0.5 < ratio < 2.0


src, dst = sys.argv[1], sys.argv[2]
data = json.load(open(src, encoding="utf-8"))
out = {}
for name, info in data.items():
    H = 1080  # 이 표본은 전부 1080p다
    cands = [c for c in info["candidates"] if center(c["plate"])[1] < OVERLAY_BAND * H]
    tracks = []
    for c in sorted(cands, key=lambda c: c["t"]):
        live = [t for t in tracks if same_track(t[-1], c)]
        if live:
            max(live, key=len).append(c)
        else:
            tracks.append([c])
    # 두 번 이상 잡혔거나 충분히 큰 트랙만 — 한 번 스친 작은 박스는 사람도 못 읽는다
    tracks = [t for t in tracks if len(t) >= 2 or max(c["plate"][3] for c in t) >= 30]
    tracks.sort(key=lambda t: -max(c["plate"][3] for c in t))
    seeds = []
    for t in tracks[:MAX_TRACKS]:
        best = max(t, key=lambda c: (c["plate"][3], c["conf"]))
        seeds.append({**best, "track_len": len(t), "track_span": [t[0]["t"], t[-1]["t"]],
                      "track_h_range": [min(c["plate"][3] for c in t), max(c["plate"][3] for c in t)]})
    out[name] = {"fps": info["fps"], "frames": info["frames"], "candidates": cands,
                 "picks": sorted(seeds, key=lambda s: s["t"])}
    print(name, f"kept {len(cands)}/{len(info['candidates'])} candidates -> {len(tracks)} tracks")
    for s in out[name]["picks"]:
        print(f"   t={s['t']:>5}  plate {s['plate'][2]}x{s['plate'][3]}  track n={s['track_len']} "
              f"span={s['track_span']} h={s['track_h_range']}")
json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
