"""검출 지속성 지표 — 대상 차량이 영상 안에서 얼마나 끊기지 않고 잡히나.

정의는 readout 의 `track1-vehicle-2026-09-19` 실험(`scripts/aihub71555_clips.py`)과
같다. 같은 숫자를 다른 데이터에서 다시 재려고 옮겨 왔다 — 정의가 어긋나면 그쪽이 이긴다.

- 매칭: 검출과 정답 박스의 IoU >= 0.5 (conf 내림차순 greedy)
- 프레임이 「보인다」: 정답 차량 박스가 1개 이상 있다
- 프레임이 「검출됐다」: 정답 차량 중 하나라도 검출과 매칭됐다
- `longest_run`: 최장 연속 검출 · `gaps`: 첫 검출과 마지막 검출 사이에서 끊긴 횟수.
  앞뒤의 미검출은 끊김이 아니다 (대상이 화면에 들어오기 전·나간 뒤)

프레임 순서는 frame_no 순이다. 라벨 프레임이 연속 프레임이 아니면 「끊김」도 라벨 프레임
사이의 끊김이다 — 결과의 coverage 가 그렇게 말한다.

라벨이 전수가 아니면 라벨 없는 차량의 검출이 전부 FP 가 되므로 FP 는 세지 않는다.
"""
import statistics

SCORER_VERSION = "t1"
IOU_THRESHOLD = 0.5
SPARSE = ("SPARSE_FRAMES — 라벨 프레임이 연속이 아니다. gaps 는 라벨 프레임 순서 기준이며 "
          "연속 영상의 끊김과 같지 않다")
NO_FP = "NO_FP — 라벨이 전수가 아니라 오검출은 재지 않는다"


def not_run(reason):
    return {"n_videos": None, "detected_ratio": None, "longest_run": None, "gaps": None,
            "gaps_buckets": None, "multi_frame_ready": None, "frame_recall": None,
            "per_video": None, "coverage": reason}


def iou(a, b):
    """(x, y, w, h) 두 개의 IoU."""
    ax2, ay2 = a[0] + a[2], a[1] + a[3]
    bx2, by2 = b[0] + b[2], b[1] + b[3]
    iw = min(ax2, bx2) - max(a[0], b[0])
    ih = min(ay2, by2) - max(a[1], b[1])
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    return inter / (a[2] * a[3] + b[2] * b[3] - inter)


def _frame_detected(dets, gts):
    taken = set()
    for det in sorted(dets, key=lambda d: -d["conf"]):
        best, best_iou = None, IOU_THRESHOLD
        for i, gt in enumerate(gts):
            if i in taken:
                continue
            v = iou(det["bbox_xywh"], gt)
            if v >= best_iou:
                best, best_iou = i, v
        if best is not None:
            taken.add(best)
    return bool(taken)


def runs(flags):
    """(최장 연속 True 길이, 끊긴 횟수). 앞뒤의 False 는 끊김으로 세지 않는다."""
    longest = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        longest = max(longest, cur)
    if True not in flags:
        return 0, 0
    first, last = flags.index(True), len(flags) - 1 - flags[::-1].index(True)
    inside = flags[first:last + 1]
    gaps = sum(1 for i, f in enumerate(inside) if not f and (i == 0 or inside[i - 1]))
    return longest, gaps


def _quantiles(values):
    ordered = sorted(values)

    def at(q):
        return ordered[min(len(ordered) - 1, int(q * len(ordered)))]
    return {"median": statistics.median(ordered), "p10": at(0.10), "p90": at(0.90)}


def score(normalized, gt):
    if gt is None:
        return not_run("NO_PERSISTENCE_GT — 이 manifest 에 차량 박스 정답지가 없다")
    preds = {(v["video_id"], f["frame_no"]): f["detections"]
             for v in normalized for f in v["frames"]}
    rows = []
    n_visible = n_detected = 0
    for item in gt["items"]:
        frames = sorted(item["frames"], key=lambda f: f["frame_no"])
        visible = [f for f in frames if f["car_bboxes_xywh"]]
        flags = [_frame_detected(preds.get((item["video_id"], f["frame_no"]), []),
                                 f["car_bboxes_xywh"]) for f in visible]
        if not visible:
            continue
        longest, gaps = runs(flags)
        rows.append({"video_id": item["video_id"], "visible": len(visible),
                     "detected": sum(flags), "longest_run": longest, "gaps": gaps})
        n_visible += len(visible)
        n_detected += sum(flags)
    if not rows:
        return not_run("NO_VISIBLE_FRAMES — 정답 차량이 있는 프레임이 없다")

    n = len(rows)
    return {
        "n_videos": n,
        "detected_ratio": _quantiles([r["detected"] / r["visible"] for r in rows]),
        "longest_run": _quantiles([r["longest_run"] for r in rows]),
        "gaps": _quantiles([r["gaps"] for r in rows]),
        "gaps_buckets": {
            "0": sum(r["gaps"] == 0 for r in rows) / n,
            "1-2": sum(1 <= r["gaps"] <= 2 for r in rows) / n,
            "3+": sum(r["gaps"] >= 3 for r in rows) / n,
        },
        "multi_frame_ready": {k: sum(r["detected"] >= k for r in rows) / n for k in (2, 3, 5)},
        "frame_recall": n_detected / n_visible,
        "per_video": rows,
        "coverage": f"{SPARSE}; {NO_FP}",
    }
