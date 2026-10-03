"""AI Hub 172 번호판OCR(Validation) → PaddleOCR 인식기 전체 미세조정 데이터. 번들 폴더 안에서만 읽고 쓴다.

    .venv/Scripts/python.exe prep_desktop.py

**인식기 입력을 판독 경로와 똑같이 만든다(detline-v2).** 판독 경로에서 인식기는 번호판 crop이 아니라, PaddleOCR 검출기가
그 crop에서 잘라 낸 **여백 없는 글자 줄**을 받는다. 여백 crop으로 학습한 첫 데스크톱 모델은 이 경로에서 1/13로 무너졌다.
  - train: 판독 경로 줄(아래) + 여백 없는 KLPD crop(노트북 1회차에서 7/13 · 오답 0)
  - val · test_aihub: 판독 경로 줄만
판독 경로 줄 = `ocr_eval2.crop`(여백 가로 20% · 높이 120) → 2줄이면 `Reader.read(split=True)`처럼 나눔 → PaddleOCR
`predict` → 파이프라인이 자르는 줄(`CropByPolys`를 가로챔). 줄이 하나면 그 부위 라벨, 둘이면 번호판 빈칸(한글 | 일련번호
4자리)에서 라벨을 나눈다. 그 밖은 버리고 센다.
번호판 단위 분할: test = 09-15 기준선 500장(seed 20260915)의 번호, val = 나머지 번호의 5%, train = 나머지.
2줄 판정(라벨이 지역명으로 시작 · 비율 < 2.6 · 윗줄 숫자 없음 또는 줄 사이 빈 띠)은 노트북과 같다.
출력: data/{train,val,test_aihub}/ · *_list.txt · prep_stats.json · PREP_VERSION · korean_plate_rec_gpu.yml
"""
import collections
import json
import os
import random
import re
import sys
import zipfile
from pathlib import Path

B = Path(__file__).resolve().parent
os.environ["HF_MODEL_CACHE"] = str(B)          # models/plate_detect_v1/weights/best.onnx
sys.path.insert(0, str(B))

# PaddleOCR(→ pandas)를 cv2·onnxruntime보다 먼저 불러온다. 거꾸로면 Windows에서 먼저 뜬 런타임 DLL 때문에
# `DLL load failed while importing join`(pandas)로 죽었다(데스크톱, 2026-09-29).
import paddleocr  # noqa: E402,F401
import pandas  # noqa: E402,F401
import cv2  # noqa: E402
import numpy as np  # noqa: E402
import yaml  # noqa: E402
from klpd.models.loader import ONNXModel, get_model_path  # noqa: E402

for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):  # klpd loader가 1로 묶는다
    os.environ.pop(k, None)

CANVAS, MIN_CONF, TWO_LINE_ASPECT, ROW_GAP, VAL_SHARE = 2, 0.3, 2.6, 0.25, 0.05
REGION_LINE = re.compile(r"^([가-힣]{2,}\d{0,2})([가-힣]\d{4})$")
DATA = B / "data"


def norm(s):
    return re.sub(r"\s+", "", s)


def detect(model, img):
    h, w = img.shape[:2]
    oy, ox = h * (CANVAS - 1) // 2, w * (CANVAS - 1) // 2
    can = np.full((h * CANVAS, w * CANVAS, 3), 114, np.uint8)
    can[oy:oy + h, ox:ox + w] = img
    bs = [b for b in model(can)[0].boxes if float(b.conf) >= MIN_CONF]
    if not bs:
        return None
    x1, y1, x2, y2 = max(bs, key=lambda b: float(b.conf)).xyxy.tolist()[0]
    x1, x2 = max(0, round(x1) - ox), min(w, round(x2) - ox)
    y1, y2 = max(0, round(y1) - oy), min(h, round(y2) - oy)
    return (x1, y1, x2, y2) if x2 - x1 > 8 and y2 - y1 > 4 else None


def row_gap(plate):
    g = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)
    g = g[:, int(g.shape[1] * .08): int(g.shape[1] * .92)]
    best = 1.0
    for mode in (cv2.THRESH_BINARY_INV, cv2.THRESH_BINARY):
        prof = cv2.threshold(g, 0, 255, mode + cv2.THRESH_OTSU)[1].mean(1) / 255
        h = len(prof)
        top, mid, bot = prof[int(h * .08): int(h * .40)], prof[int(h * .30): int(h * .60)], prof[int(h * .50): int(h * .92)]
        if len(top) and len(mid) and len(bot):
            best = min(best, float(mid.min() / max(1e-6, min(top.max(), bot.max()))))
    return best


def split_label(label, aspect, gap):
    m = REGION_LINE.match(label)
    if m and aspect < TWO_LINE_ASPECT and (not any(c.isdigit() for c in m.group(1)) or gap < ROW_GAP):
        return [("top", m.group(1)), ("bottom", m.group(2))]
    return [("full", label)]


def padded(img, box, frac):
    """`ocr_eval2.crop`과 같은 모양 — 네 변에 가로 × frac 픽셀(최소 6), 원본 밖은 잘린다."""
    x1, y1, x2, y2 = box
    H, W = img.shape[:2]
    p = max(6, round((x2 - x1) * frac))
    return img[max(0, y1 - p):min(H, y2 + p), max(0, x1 - p):min(W, x2 + p)]


def cut(img, part):
    h = img.shape[0]
    return {"full": img, "top": img[: int(h * 0.45)], "bottom": img[int(h * 0.35):]}[part]


def selfcheck():
    assert split_label("경기71아1234", 2.0, 0.0) == [("top", "경기71"), ("bottom", "아1234")]
    assert split_label("경기37바1234", 2.3, 0.4) == [("full", "경기37바1234")]
    assert split_label("경기부천가1234", 1.8, 0.4)[0] == ("top", "경기부천")
    assert split_label("12가3456", 2.0, 0.0) == [("full", "12가3456")]
    assert split_at_gap("150소1234") == ["150소", "1234"] and split_at_gap("경기71") is None


class PipelineLines:
    """판독 경로(`ocr_eval2.Reader`)와 같은 PaddleOCR을 돌려, 인식기에 들어가는 줄 이미지를 그대로 받아 온다.
    PaddleX OCR 파이프라인이 검출 박스를 자르는 `CropByPolys`를 가로챈다 — 자르는 방식을 따로 흉내 내지 않는다."""

    def __init__(self):
        from paddleocr import PaddleOCR
        from paddlex.inference.pipelines.components.common import crop_image_regions as cir
        self.last = []
        orig = cir.CropByPolys.__call__

        def grab(op, img, polys, *a, **k):
            out = orig(op, img, polys, *a, **k)
            crops = [o["img"] if isinstance(o, dict) else o for o in out]
            xs = [float(np.min(np.asarray(p)[:, 0])) for p in polys]
            self.last = [c for _, c in sorted(zip(xs, crops), key=lambda t: t[0])]  # 왼쪽부터
            return out
        cir.CropByPolys.__call__ = grab
        self.engine = PaddleOCR(lang="korean", text_detection_model_name="PP-OCRv5_mobile_det",
                                text_recognition_model_name="korean_PP-OCRv5_mobile_rec", enable_mkldnn=False,
                                use_doc_orientation_classify=False, use_doc_unwarping=False,
                                use_textline_orientation=False)

    def __call__(self, img):
        self.last = []
        next(iter(self.engine.predict(img)))
        return self.last


def split_at_gap(text):
    """검출기가 한 줄을 둘로 나누면 번호판의 빈칸 — 한글과 일련번호 4자리 사이 — 에서 나뉜다(`150소 | 1234`).
    그 자리로 라벨을 나눈다. 그 모양이 아니면 None(버린다)."""
    m = re.fullmatch(r"(.*[가-힣])(\d{4})", text)
    return [m.group(1), m.group(2)] if m else None


def product_parts(img, box, two_line):
    """`ocr_eval2.crop`(여백 가로 20% · 높이 120으로 확대) + `Reader.read(split=True)`(윗줄 0~45% ×2, 아랫줄 35~)."""
    x1, y1, x2, y2 = box
    c = padded(img, box, 0.20)
    s = 120 / max(y2 - y1, 1)
    c = cv2.resize(c, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
    if not two_line:
        return [c]
    h = c.shape[0]
    top = cv2.resize(c[: int(h * 0.45)], None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    return [top, c[int(h * 0.35):]]


def write_config(stats):
    c = yaml.safe_load(open(B / "korean_plate_rec_gpu.template.yml", encoding="utf-8"))
    c["Global"]["pretrained_model"] = str(B / "pretrained" / "korean_PP-OCRv5_mobile_rec_pretrained")
    c["Global"]["save_model_dir"] = str(B / "output" / "full_ft")
    c["Global"]["save_res_path"] = str(B / "output" / "full_ft" / "predicts.txt")
    for part, lst in (("Train", "train_list.txt"), ("Eval", "val_list.txt")):
        c[part]["dataset"]["data_dir"] = str(DATA) + os.sep
        c[part]["dataset"]["label_file_list"] = [str(DATA / lst)]
    open(B / "korean_plate_rec_gpu.yml", "w", encoding="utf-8").write(yaml.safe_dump(c, allow_unicode=True, sort_keys=False))


def main():
    selfcheck()
    img_dir = B / "aihub172" / "images"
    labels = []
    with zipfile.ZipFile(B / "aihub172" / "labels.zip") as z:
        for name in sorted(n for n in z.namelist() if n.endswith(".json")):
            o = json.loads(z.read(name).decode("utf-8"))
            ip = img_dir / o["imagePath"]
            if ip.exists():
                labels.append((ip, norm(o["value"]), o["id"]))
    random.Random(20260915).shuffle(labels)                 # 09-15 기준선과 같은 순서
    limit = int(os.environ.get("PREP_LIMIT", "0"))          # 점검용: 앞 N장만 (분할은 전체 번호로 정한다)
    test_plates = {lab for _, lab, _ in labels[:500]}
    rest = sorted({lab for _, lab, _ in labels} - test_plates)
    random.Random(20260928).shuffle(rest)
    val_plates = set(rest[:round(len(rest) * VAL_SHARE)])
    split_of = lambda lab: "test_aihub" if lab in test_plates else "val" if lab in val_plates else "train"

    model = ONNXModel(get_model_path("plate_detect_v1"))
    det_lines = PipelineLines()
    lines = collections.defaultdict(list)
    stats = collections.defaultdict(collections.Counter)
    for n, (ip, label, rid) in enumerate(labels[:limit] if limit else labels):
        split = split_of(label)
        img = cv2.imdecode(np.fromfile(str(ip), np.uint8), cv2.IMREAD_COLOR)
        box = detect(model, img) if img is not None else None
        if box is None:
            stats[split]["no_plate"] += 1
            continue
        x1, y1, x2, y2 = box
        parts = split_label(label, (x2 - x1) / (y2 - y1), row_gap(img[y1:y2, x1:x2]))
        stats[split]["two_line" if len(parts) == 2 else "one_line"] += 1
        (DATA / split).mkdir(parents=True, exist_ok=True)

        def save(name, image, text):
            rel = f"{split}/{name}.jpg"
            cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tofile(str(DATA / rel))
            lines[split].append(f"{rel}\t{text}")

        if split == "train":  # 노트북 1회차에서 통한 여백 없는 crop도 함께
            tight = img[y1:y2, x1:x2]
            for i, (part, text) in enumerate(parts):
                save(f"{rid}_t{i}", cut(tight, part), text)
        # 판독 경로가 인식기에 넣는 줄 — 부위마다 검출된 줄이 정확히 하나일 때만 라벨을 붙일 수 있다
        for i, ((part, text), image) in enumerate(zip(parts, product_parts(img, box, len(parts) == 2))):
            got = det_lines(image)
            pieces = [text] if len(got) == 1 else split_at_gap(text) if len(got) == 2 else None
            if not pieces:
                stats[split][f"det_lines_{min(len(got), 3)}_skipped"] += 1
                continue
            stats[split][f"det_lines_{len(got)}"] += 1
            for j, (g, t) in enumerate(zip(got, pieces)):
                save(f"{rid}_d{i}{j}", g, t)
        if n % 500 == 0:
            print(f"{n}/{len(labels)}", flush=True)
    for split, ls in lines.items():
        (DATA / f"{split}_list.txt").write_text("\n".join(ls) + "\n", encoding="utf-8")
        stats[split]["line_images"] = len(ls)
    plates = {s: {lab for _, lab, _ in labels if split_of(lab) == s} for s in ("train", "val", "test_aihub")}
    assert not (plates["train"] & plates["val"]) and not (plates["train"] & plates["test_aihub"])
    (DATA / "PREP_VERSION").write_text("detline-v2", encoding="utf-8")
    (DATA / "prep_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    write_config(stats)
    print(json.dumps(stats, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
