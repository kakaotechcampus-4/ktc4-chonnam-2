"""AI Hub 71555 트랙 ① — 표본 프레임에서 차량을 검출하고 라벨 bbox와 대조한다.

`aihub71555_labels.py sample`이 만든 manifest만 읽는다. **VS.zip은 풀지 않는다** —
manifest에 적힌 `image_entry`만 `zipfile`로 꺼내 메모리에서 디코드한다.

    python scripts/aihub71555_detect.py --manifest track1-sample.json --out results.json

## 이 스크립트가 재는 것 / 못 재는 것

COCO 사전학습 검출기는 **차량을 찾을 뿐 위반 여부를 모른다.** 한 프레임만 보고
「이 차가 신호를 위반했는가」를 판정할 수 없다 — 위반은 시간축·문맥 판정이다.
그래서 여기서 나오는 것은 **차량 위치 검출의 기준선**이지 위반 판정 성능이 아니다.

| 잰다 | 못 잰다 |
| --- | --- |
| 위반 차량 라벨 bbox를 검출기가 찾아내는 비율 | 「정상 차량을 위반으로 분류」 — 검출기에 위반 클래스가 없다 |
| 정상 차량 라벨 bbox 검출 비율 | |
| 어느 차량 라벨에도 안 붙는 검출(FP) | |
| 검출 중 위반/정상 라벨에 붙은 비율 (대상 특정 부담) | |
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
import time
import zipfile
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from aihub71555_labels import SRC_ZIP, annotations_of, bbox_of, load, open_zip  # noqa: E402

# COCO 클래스 중 차량. 라벨의 '차량(이륜차 포함)'에 이륜차가 들어 있어 motorcycle을 뺄 수 없다.
VEHICLE_COCO = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
IOU_THR = 0.5
HEIGHT_BINS = [(0, 30), (30, 50), (50, 100), (100, 10 ** 9)]


def iou(a, b) -> float:
    """(x, y, w, h) 두 개의 IoU."""
    ax2, ay2 = a[0] + a[2], a[1] + a[3]
    bx2, by2 = b[0] + b[2], b[1] + b[3]
    iw = min(ax2, bx2) - max(a[0], b[0])
    ih = min(ay2, by2) - max(a[1], b[1])
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    return inter / (a[2] * a[3] + b[2] * b[3] - inter)


# 차량 GT로 셀 `Object Name`과 그 위반 여부. 전수 19종 중 탈것만 골랐다.
# 안전모미착용 구획에는 `~ 차량` 객체가 아예 없고 이륜차로만 라벨돼 있어,
# 「차량」 문자열로 거르면 그 구획 전체가 GT 0건이 된다.
# `안전모 (미)착용 머리`는 탈것이 아니라 제외한다.
VEHICLE_GT = {
    "정상 차량(이륜차 포함)": "정상",
    "신호 위반 차량(이륜차 포함)": "위반",
    "중앙선침범 위반 차량(이륜차 포함)": "위반",
    "진로변경 위반 차량(이륜차 포함)": "위반",
    "안전모 미착용 이륜차": "위반",
    "안전모 착용 이륜차": "정상",
}


def gt_vehicles(label: dict) -> list[dict]:
    """차량 라벨만 골라 (kind, bbox)로. 불량 박스(w나 h가 0)는 버린다."""
    out = []
    for ann in annotations_of(label):
        kind = VEHICLE_GT.get(ann.get("Object Name") or "")
        if kind is None:
            continue
        box = bbox_of(ann)
        if not box or box[2] <= 0 or box[3] <= 0:
            continue
        out.append({"kind": kind, "name": ann["Object Name"],
                    "bbox": [float(v) for v in box]})
    return out


def image_size(label: dict) -> tuple[int | None, int | None]:
    """`Meta.Resolution`은 전부 'FHD'인데 실제와 다르다. Image information을 쓴다."""
    info = label.get("Annotation", {}).get("Image information") or {}
    return info.get("Image File Width"), info.get("Image File Height")


def height_bin(h: float) -> str:
    for lo, hi in HEIGHT_BINS:
        if lo <= h < hi:
            return f"{lo}-{hi}px" if hi < 10 ** 9 else f"{lo}px+"
    return "?"


def match(dets: list[dict], gts: list[dict]) -> None:
    """conf 내림차순 greedy 매칭. dets에 `matched_gt`, gts에 `matched` 를 채운다."""
    for gt in gts:
        gt["matched"] = False
    for det in sorted(dets, key=lambda d: -d["conf"]):
        best, best_iou = None, IOU_THR
        for gt in gts:
            if gt["matched"]:
                continue
            v = iou(det["bbox"], gt["bbox"])
            if v >= best_iou:
                best, best_iou = gt, v
        det["matched_gt"] = best["kind"] if best else None
        det["iou"] = round(best_iou, 3) if best else None
        if best:
            best["matched"] = True


def run(args) -> None:
    from ultralytics import YOLO

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    items = manifest["items"][: args.limit] if args.limit else manifest["items"]

    model = YOLO(args.model)
    zs = open_zip(SRC_ZIP)
    zl = open_zip(Path(manifest["label_zip"]))

    frames, missing_image, unreadable = [], [], []
    t0 = time.time()
    for i, item in enumerate(items, 1):
        if i % 100 == 0:
            print(f"  … {i:,}/{len(items):,}  ({time.time() - t0:.0f}s)", file=sys.stderr)
        try:
            blob = zs.read(item["image_entry"])
        except KeyError:
            missing_image.append(item["image_entry"])
            continue
        img = cv2.imdecode(np.frombuffer(blob, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            unreadable.append(item["image_entry"])
            continue

        label = load(zl, item["label_entry"])
        gts = gt_vehicles(label)
        lw, lh = image_size(label)
        ih, iw = img.shape[:2]

        res = model.predict(img, conf=args.conf, imgsz=args.imgsz, classes=list(VEHICLE_COCO),
                            verbose=False)[0]
        dets = []
        for box in res.boxes:
            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
            dets.append({"bbox": [x1, y1, x2 - x1, y2 - y1],
                         "conf": float(box.conf[0]), "cls": VEHICLE_COCO[int(box.cls[0])]})
        match(dets, gts)

        cond = label.get("condition") or {}
        frames.append({
            "label_entry": item["label_entry"], "clip": item.get("clip"),
            "major": item["major"], "minor": item["minor"],
            "daynight": cond.get("DayNights", "(없음)"),
            "weather": cond.get("Weather", "(없음)"),
            "road": cond.get("roadType", "(없음)"),
            "image_wh": [iw, ih], "label_wh": [lw, lh],
            "orientation": "세로" if ih > iw else "가로",
            "gts": gts, "dets": dets,
        })

    elapsed = time.time() - t0
    out = {
        "run": {
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": args.model, "conf": args.conf, "imgsz": args.imgsz,
            "iou_threshold": IOU_THR, "coco_classes": VEHICLE_COCO,
            "manifest": str(Path(args.manifest).resolve()), "seed": manifest.get("seed"),
            "frames_requested": len(items), "frames_scored": len(frames),
            "missing_image": missing_image, "unreadable": unreadable,
            "elapsed_sec": round(elapsed, 1),
            "sec_per_frame": round(elapsed / max(1, len(frames)), 3),
        },
        "frames": frames,
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(frames):,}프레임 · {elapsed:.0f}s ({elapsed / max(1, len(frames)):.2f}s/장) → {args.out}")
    if missing_image or unreadable:
        print(f"  이미지 없음 {len(missing_image)} · 디코드 실패 {len(unreadable)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default="track1-sample.json")
    ap.add_argument("--out", default="track1-detect.json")
    ap.add_argument("--model", default="yolo11n.pt")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--selfcheck", action="store_true", help="IoU·매칭 자체 점검만 하고 끝낸다")
    args = ap.parse_args()
    demo() if args.selfcheck else run(args)




def demo() -> None:
    """python scripts/aihub71555_detect.py --selfcheck — IoU와 greedy 매칭 자체 점검."""
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert iou((0, 0, 10, 10), (20, 20, 5, 5)) == 0.0
    assert abs(iou((0, 0, 10, 10), (5, 0, 10, 10)) - 50 / 150) < 1e-9
    # 맞닿기만 한 박스는 겹침이 아니다
    assert iou((0, 0, 10, 10), (10, 0, 10, 10)) == 0.0

    # conf 높은 검출이 먼저 가져간다. 낮은 쪽은 남은 GT에 붙거나 FP가 된다.
    gts = [{"kind": "위반", "bbox": (0, 0, 10, 10)}, {"kind": "정상", "bbox": (100, 0, 10, 10)}]
    dets = [{"bbox": (1, 1, 10, 10), "conf": 0.9}, {"bbox": (0, 0, 10, 10), "conf": 0.3}]
    match(dets, gts)
    assert dets[0]["matched_gt"] == "위반", dets
    assert dets[1]["matched_gt"] is None, dets      # 같은 GT를 두 번 세지 않는다
    assert gts[0]["matched"] and not gts[1]["matched"]
    print("selfcheck ok")

if __name__ == "__main__":
    main()
