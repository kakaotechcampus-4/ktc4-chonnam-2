"""추적 검증 — CSRT로 추적한 프레임마다 번호판을 다시 검출해, 맞는 프레임만 투표에 넘긴다.

    <detector venv python> verify_tracks.py gt_plates.json picks_all.json <videos_dir> tracks_verified.json

`find_plates.py`와 같은 순서 — 차량(yolo11n) → 추적 박스 중심을 품은 차량 crop 안 번호판(KLPD ONNX) — 로
검출하고, 다음 둘을 모두 만족하는 검출이 있으면 그 **검출 박스로 바꿔** 받는다. 없으면 그 프레임은 버린다.
(번호판 둘레 창만 잘라 검출하면 seed 프레임에서도 27개 중 6~7개를 놓쳤다 — 검출기가 차량 crop 입력에 맞춰져 있다.)
  ① 추적 박스와 IoU ≥ 0.3          — 추적기가 가리키는 자리에 실제로 번호판이 있다
  ② 직전에 받은 박스에서 중심 이동 ≤ 그 박스 가로 1배 — 옆 차 번호판으로 건너뛰지 않았다
seed 프레임은 GT seed(원래 검출 결과)를 그대로 쓴다.

`CHAIN=1`이면 CSRT를 쓰지 않는다 — 같은 프레임 구간에서 추적 박스 자리에 **직전에 받은 박스**를 넣어,
검출끼리 이어 붙인다. ①은 「직전 박스와 가로 크기 0.5~2배」로 바꾼다 — 3프레임에 번호판이 반 폭 넘게
움직이면 IoU로는 끊긴다. CSRT가 몇 프레임 만에 배경으로 흘러서 넣었다.

결과는 GT 항목 순서의 리스트다. `ocr_eval2.py`·`ekld_eval.py`는 `TRACKS=<이 파일>`이면 CSRT 대신 이것을 쓴다.
"""
import json
import os
import sys
from pathlib import Path

import ocr_eval2 as base  # argv[1:5]를 그대로 받는다

CHAIN = os.environ.get("CHAIN") == "1"

DET = Path(r"C:\Users\tlsdb\Documents\카테캠\readout_plate_detection")
os.environ.setdefault("HF_MODEL_CACHE", str(DET / ".cache" / "sauce_onnx" / "hf"))
sys.path.insert(0, str(DET / "korean-license-plate-detector" / "src"))

import cv2  # noqa: E402
from klpd.models.loader import ONNXModel, get_model_path  # noqa: E402
from ultralytics import YOLO  # noqa: E402

MIN_IOU = 0.3
MAX_JUMP = 1.0  # 직전 박스 가로 대비
MIN_CONF = 0.3
VEHICLES = [2, 3, 5, 7]


def iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    iw = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    ih = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = iw * ih
    return inter / (aw * ah + bw * bh - inter) if inter else 0.0


def center(b):
    return b[0] + b[2] / 2, b[1] + b[3] / 2


def detect_near(models, img, box):
    """추적 박스 중심을 품은 차량마다 그 crop에서 번호판을 검출해 프레임 좌표로 돌려준다."""
    car_model, plate_model = models
    cx, cy = center(box)
    out = []
    for v in car_model.predict(img, conf=0.3, classes=VEHICLES, verbose=False)[0].boxes:
        x1, y1, x2, y2 = (int(t) for t in v.xyxy[0].tolist())
        if not (x1 <= cx <= x2 and y1 <= cy <= y2):
            continue
        for p in plate_model(img[y1:y2, x1:x2])[0].boxes:
            if float(p.conf) < MIN_CONF:
                continue
            px1, py1, px2, py2 = p.xyxy.tolist()[0]
            out.append((round(px1 + x1), round(py1 + y1), round(px2 - px1), round(py2 - py1)))
    return out


def check(model, cap, seed_frame, tracked):
    """seed에서 바깥쪽으로 걸어가며 검증한다 — ②의 「직전」이 시간상 이웃이 되도록."""
    kept = {seed_frame: dict(tracked)[seed_frame]}
    dropped = []
    before = [ft for ft in tracked if ft[0] < seed_frame][::-1]
    after = [ft for ft in tracked if ft[0] > seed_frame]
    for side in (before, after):
        prev = kept[seed_frame]
        for f, tbox in side:
            cap.set(cv2.CAP_PROP_POS_FRAMES, f)
            ok, img = cap.read()
            if not ok:
                dropped.append([f, "read_fail"])
                continue
            if CHAIN:
                cands = [d for d in detect_near(model, img, prev) if 0.5 <= d[2] / prev[2] <= 2]
            else:
                cands = [d for d in detect_near(model, img, tbox) if iou(d, tbox) >= MIN_IOU]
            if not cands:
                dropped.append([f, "no_plate_at_track"])
                continue
            (px, py), limit = center(prev), MAX_JUMP * prev[2]
            near = [d for d in cands if abs(center(d)[0] - px) <= limit and abs(center(d)[1] - py) <= limit]
            if not near:
                dropped.append([f, "jumped"])
                continue
            if CHAIN:
                prev = min(near, key=lambda d: abs(center(d)[0] - px) + abs(center(d)[1] - py))
            else:
                prev = max(near, key=lambda d: iou(d, tbox))
            kept[f] = prev
    return sorted(kept.items()), sorted(dropped)


def selfcheck():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert iou((0, 0, 10, 10), (20, 20, 5, 5)) == 0.0
    assert abs(iou((0, 0, 10, 10), (5, 0, 10, 10)) - 50 / 150) < 1e-9


def main():
    selfcheck()
    model = (YOLO(str(DET / "yolo11n.pt")), ONNXModel(get_model_path("plate_detect_v1")))
    items = json.loads(base.gt_path.read_text(encoding="utf-8"))["items"]
    picks = json.loads(base.picks_path.read_text(encoding="utf-8"))
    rows = []
    for item in items:
        info = picks[item["video"]]
        seed_t, seed_box = item["seed_t"], item["seed_plate"]
        if seed_box is None:
            top = max(info["picks"], key=lambda p: p["plate"][3] * p["conf"])
            seed_t, seed_box = top["t"], top["plate"]
        cap = cv2.VideoCapture(str(next(base.videos.glob(f"{item['video']}.*"))))
        seed_frame = round(seed_t * info["fps"])
        if CHAIN:
            span = round(base.SPAN_SEC * info["fps"])
            tracked = [(seed_frame + d, tuple(seed_box)) for d in range(-(span // 3) * 3, span + 1, 3)
                       if seed_frame + d >= 0]
        else:
            tracked = base.track_frames(cap, info["fps"], seed_frame, seed_box)
        kept, dropped = check(model, cap, seed_frame, tracked)
        cap.release()
        row = {"video": item["video"], "kind": item["kind"], "seed_frame": seed_frame,
               "tracked": len(tracked), "kept": len(kept), "dropped": dropped,
               "verified": [[f, list(b)] for f, b in kept]}
        rows.append(row)
        print(json.dumps({k: v for k, v in row.items() if k != "verified"}, ensure_ascii=False), flush=True)
    base.out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
