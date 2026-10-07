"""readout-exp:yolo11n — readout 대상 차량 실험의 검출기를 다른 데이터에서 다시 돌린다.

**제품 코드가 아니다.** readout 에는 아직 차량 검출 공개 함수가 없다. 이 impl 은
readout 의 `track1-vehicle-2026-09-19` 실험 설정(`scripts/aihub71555_detect.py`)을
그대로 옮긴 것이다 — Ultralytics `yolo11n.pt`(COCO 사전학습) · conf 0.25 · imgsz 640 ·
COCO 차량 4클래스. 설정이 어긋나면 그쪽이 이긴다. 제품에 검출이 들어오면 그 공개 함수를
부르는 impl 로 바꾼다.

정답지를 보지 않는다. 프레임마다 검출 결과만 내고 매칭은 scorer(`persistence`)가 한다.
가중치는 `DAESINGO_EVAL_PRIVATE_ROOT/models/` 에 둔다 — 레포에 받지 않는다.
"""
import hashlib
import json
import os
from importlib.metadata import PackageNotFoundError, version

from eval import paths
from eval.runners.errors import RunnerPreflightError

IMPL_VERSION = "v1"
MODEL = "yolo11n.pt"
CONF = 0.25
IMGSZ = 640
# 라벨의 차량에 이륜차가 들어 있어 motorcycle 을 뺄 수 없다 (readout 실험과 같다).
VEHICLE_COCO = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
_last_facts = {}


def _sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _prepare(scope):
    problems = []
    manifest = scope.get("manifest", "")
    if not paths.is_private(manifest):
        problems.append("readout-exp:yolo11n 은 private_ manifest 만 받는다 (AI-Hub 재배포 금지)")
    if scope.get("stage") != "persistence":
        problems.append("readout-exp:yolo11n 은 stage=persistence 만 지원한다")
    try:
        ultralytics_version = version("ultralytics")
    except PackageNotFoundError:
        ultralytics_version = None
        problems.append("ultralytics 가 없다 — eval-yolo extra 를 sync 할 것")
    videos, base = [], None
    if not problems:
        try:
            base = paths.manifest_dir(manifest)
            # 표본 목록만 읽는다. 정답지(gt/)는 impl 이 보지 않는다.
            with open(os.path.join(base, "samples.json"), encoding="utf-8") as f:
                videos = json.load(f)["videos"]
        except OSError as e:
            problems.append(str(e))
    for video in videos:
        for frame in video["frames"]:
            path = os.path.join(base, frame["file_path"])
            if not os.path.isfile(path):
                problems.append(f"{video['video_id']}/{frame['frame_no']}: 프레임이 없다")
            elif _sha256(path) != frame["sha256"]:
                problems.append(f"{video['video_id']}/{frame['frame_no']}: sha256 불일치")
    if problems:
        raise RunnerPreflightError("검출 지속성 평가 사전 점검 실패:\n" + "\n".join(
            "- " + p for p in problems[:30]))
    return base, videos, ultralytics_version


def _load_model():
    from ultralytics import YOLO

    models = os.path.join(paths.private_root(), "models")
    os.makedirs(models, exist_ok=True)
    return YOLO(os.path.join(models, MODEL))


def _detect(model, image):
    res = model.predict(image, conf=CONF, imgsz=IMGSZ, classes=list(VEHICLE_COCO),
                        verbose=False)[0]
    dets = []
    for box in res.boxes:
        x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
        dets.append({"bbox_xywh": [x1, y1, x2 - x1, y2 - y1],
                     "conf": float(box.conf[0]), "cls": VEHICLE_COCO[int(box.cls[0])]})
    return dets


def _read_image(path):
    import cv2
    import numpy as np

    # cv2.imread 는 Windows 에서 비ASCII 경로를 못 연다.
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)


def run(scope):
    base, videos, ultralytics_version = _prepare(scope)
    model = _load_model()
    raw, unreadable = [], []
    for video in videos:
        frames = []
        for frame in video["frames"]:
            path = os.path.join(base, frame["file_path"])
            image = _read_image(path)
            if image is None:
                unreadable.append(f"{video['video_id']}/{frame['frame_no']}")
                continue
            frames.append({"frame_no": frame["frame_no"], "detections": _detect(model, image)})
        raw.append({"video_id": video["video_id"], "frames": frames})

    global _last_facts
    _last_facts = {
        "contract_version": None,
        "model": MODEL, "conf": CONF, "imgsz": IMGSZ, "coco_classes": VEHICLE_COCO,
        "ultralytics_version": ultralytics_version,
        "reference": "docs/modules/readout/experiments/track1-vehicle-2026-09-19/ENVIRONMENT.md",
        "processed_duration_sec": None,
        "n_frames": sum(len(v["frames"]) for v in raw),
        "unreadable_frames": unreadable,
        "usage_records": [],
        "scenarios": [],
    }
    return raw


def run_facts(scope):
    del scope
    return dict(_last_facts)
