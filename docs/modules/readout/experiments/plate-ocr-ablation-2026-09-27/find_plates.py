"""영상마다 번호판이 가장 크게 잡힌 프레임을 찾아 사람이 읽을 수 있게 잘라 둔다.

    <detector venv python> find_plates.py <out_dir> <video> [<video> ...]

차량(yolo11n) → 차량 crop 안에서 번호판(KLPD ONNX) 순서다. 결과는 GT를 만드는 재료이지
판독이 아니다 — OCR은 돌리지 않는다.
"""
import json
import os
import sys
from pathlib import Path

DET = Path(os.environ["READOUT_DETECTOR_DIR"])
"""`yolo11n.pt`와 `korean-license-plate-detector/`(KLPD ONNX)가 있는 폴더. 레포에 넣지 않는다."""
os.environ.setdefault("HF_MODEL_CACHE", str(DET / ".cache" / "sauce_onnx" / "hf"))
sys.path.insert(0, str(DET / "korean-license-plate-detector" / "src"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from klpd.models.loader import ONNXModel, get_model_path  # noqa: E402
from ultralytics import YOLO  # noqa: E402

STEP_SEC = 0.5
TOP = 6
MIN_GAP_SEC = 1.0
VEHICLES = [2, 3, 5, 7]

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
car_model = YOLO(str(DET / "yolo11n.pt"))
plate_model = ONNXModel(get_model_path("plate_detect_v1"))


def put(img, text, org, scale=0.6):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 3)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 1)


summary = {}
for video in sys.argv[2:]:
    name = Path(video).stem
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    found = []
    for frame_no in range(0, n, max(1, round(fps * STEP_SEC))):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        ok, img = cap.read()
        if not ok:
            continue
        H, W = img.shape[:2]
        cars = car_model.predict(img, conf=0.3, classes=VEHICLES, verbose=False)[0].boxes
        for box in cars:
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            if (x2 - x1) < 80:                      # 너무 작은 차는 번호판도 못 읽는다
                continue
            crop = img[y1:y2, x1:x2]
            for p in plate_model(crop)[0].boxes:
                px1, py1, px2, py2 = p.xyxy.tolist()[0]
                conf = float(p.conf)
                if conf < 0.3:
                    continue
                plate = [round(px1 + x1), round(py1 + y1), round(px2 - px1), round(py2 - py1)]
                # 번호판 비율만 받는다 — 1줄 약 4.7:1, 2줄 약 2:1. 차 전체·세로 박스 오탐을 거른다
                if plate[3] <= 0 or not 1.5 <= plate[2] / plate[3] <= 6.0:
                    continue
                found.append({"t": round(frame_no / fps, 2), "frame": frame_no, "conf": round(conf, 3),
                              "vehicle": [x1, y1, x2 - x1, y2 - y1], "plate": plate})
    # 번호판 높이 순, 시간이 1초 이상 떨어진 것만 — 같은 장면 반복을 피한다
    picks = []
    for f in sorted(found, key=lambda f: (-f["plate"][3], -f["conf"])):
        if all(abs(f["t"] - p["t"]) >= MIN_GAP_SEC for p in picks):
            picks.append(f)
        if len(picks) == TOP:
            break
    picks.sort(key=lambda f: f["t"])

    tiles = []
    for i, f in enumerate(picks, 1):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f["frame"])
        ok, img = cap.read()
        H, W = img.shape[:2]
        x, y, w, h = f["plate"]
        pad = max(10, round(w * 0.35))
        c = img[max(0, y - pad):min(H, y + h + pad), max(0, x - pad):min(W, x + w + pad)]
        zoom = cv2.resize(c, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        ctx = img.copy()
        vx, vy, vw, vh = f["vehicle"]
        cv2.rectangle(ctx, (vx, vy), (vx + vw, vy + vh), (0, 255, 255), 4)
        cv2.rectangle(ctx, (x, y), (x + w, y + h), (0, 0, 255), 3)
        ctx = cv2.resize(ctx, (480, round(480 * H / W)))
        th = max(zoom.shape[0], ctx.shape[0])
        tile = np.full((th + 30, zoom.shape[1] + ctx.shape[1] + 10, 3), 40, np.uint8)
        tile[30:30 + ctx.shape[0], :ctx.shape[1]] = ctx
        tile[30:30 + zoom.shape[0], ctx.shape[1] + 10:] = zoom
        put(tile, f"#{i}  t={f['t']:.1f}s  plate {w}x{h}px  conf {f['conf']:.2f}", (8, 22))
        tiles.append(tile)
    cap.release()
    summary[name] = {"fps": fps, "frames": n, "candidates": found, "picks": picks}
    if tiles:
        width = max(t.shape[1] for t in tiles)
        sheet = np.vstack([np.pad(t, ((0, 6), (0, width - t.shape[1]), (0, 0))) for t in tiles])
        cv2.imencode(".jpg", sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tofile(str(out / f"{name}.jpg"))
    print(f"{name}: candidates={len(found)} picks={len(picks)} "
          f"max_plate_h={picks and max(p['plate'][3] for p in picks)}", flush=True)

(out / "picks.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
