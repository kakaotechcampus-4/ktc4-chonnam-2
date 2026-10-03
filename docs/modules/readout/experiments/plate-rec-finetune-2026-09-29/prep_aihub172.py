"""AI Hub 172 번호판OCR(Validation)을 PaddleOCR 인식기 미세조정 데이터로 바꾼다.

    <detector venv python> prep_aihub172.py <aihub_validation_dir> <out_dir>

제품이 인식기에 넣는 입력과 같게 만든다.
  1. 번호판 검출(KLPD ONNX)로 딱 맞게 다시 자른다. AI Hub crop은 범퍼까지 들어 있고, 검출기는 번호판이 작게
     보이는 차량 crop에 맞춰져 있어 원본 그대로는 200장 중 18장만 잡혔다 — 2배 캔버스에 올리면 163장.
     못 잡은 crop은 버린다(제품에서도 인식기까지 오지 않는다).
  2. 2줄 번호판은 줄을 나눈다 — 라벨이 지역명으로 시작하고 가로/세로 < 2.6이며, **윗줄에 숫자가 없거나(이륜차)
     가로 투영에 두 글자 줄 사이 빈 띠가 있을 때만**. 비율만 보면 기울어진 1줄 영업용(`경기37바1234`)이 2.6 아래로
     떨어져 반으로 잘렸다. 나누는 자리는 `ocr_eval2.Reader.read(split=True)`와 같다(윗줄 0~45%, 아랫줄 35~100%).
  3. 09-15 기준선 500장(`ocr-baseline-2026-09-15`, seed 20260915)은 학습에서 빼 `test_aihub`로 둔다.
     원 스크립트(`evaluate_500.py`)와 같은 순서(라벨 파일 이름순 → 이미지 있는 것만 → shuffle)로 다시 뽑는다.

출력(`<out_dir>`): `{train,val,test_aihub}/<id>_{0,1,2}.jpg` · `{train,val,test_aihub}_list.txt`(경로<TAB>라벨) · `prep_stats.json`.
AI Hub 이용정책상 이 출력은 레포에 넣지 않는다.
"""
import collections
import json
import os
import random
import re
import sys
import zipfile
from pathlib import Path

DET = Path(r"C:\Users\tlsdb\Documents\카테캠\readout_plate_detection")
os.environ.setdefault("HF_MODEL_CACHE", str(DET / ".cache" / "sauce_onnx" / "hf"))
sys.path.insert(0, str(DET / "korean-license-plate-detector" / "src"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from klpd.models.loader import ONNXModel, get_model_path  # noqa: E402

CANVAS = 2
MIN_CONF = 0.3
TWO_LINE_ASPECT = 2.6
REGION_LINE = re.compile(r"^([가-힣]{2,}\d{0,2})([가-힣]\d{4})$")  # 경기71|아1234 · 경기부천|가1234
VAL_SHARE = 0.05
ROW_GAP = 0.25  # 표본 24장: 2줄 ≤ 0.16(글자 밝은 판은 반대 극성으로), 기울어진 1줄 ≥ 0.33


def norm(s):
    return re.sub(r"\s+", "", s)


def row_gap(plate):
    """두 글자 줄 사이 빈 띠의 깊이 — 가로 투영에서 30~60% 구간 최소 / 위·아래 최대. 작을수록 2줄."""
    g = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)
    g = g[:, int(g.shape[1] * .08): int(g.shape[1] * .92)]
    best = 1.0
    for mode in (cv2.THRESH_BINARY_INV, cv2.THRESH_BINARY):  # 어두운 글자 · 밝은 글자
        prof = cv2.threshold(g, 0, 255, mode + cv2.THRESH_OTSU)[1].mean(1) / 255
        h = len(prof)
        top, mid, bot = prof[int(h * .08): int(h * .40)], prof[int(h * .30): int(h * .60)], prof[int(h * .50): int(h * .92)]
        if len(top) and len(mid) and len(bot):
            best = min(best, float(mid.min() / max(1e-6, min(top.max(), bot.max()))))
    return best


def split_label(label, aspect, gap=0.0):
    """[(부위, 라벨)] — 2줄이면 윗줄·아랫줄, 아니면 한 줄."""
    m = REGION_LINE.match(label)
    if m and aspect < TWO_LINE_ASPECT and (not any(ch.isdigit() for ch in m.group(1)) or gap < ROW_GAP):
        return [("top", m.group(1)), ("bottom", m.group(2))]
    return [("full", label)]


def cut(img, part):
    h = img.shape[0]
    return {"full": img, "top": img[: int(h * 0.45)], "bottom": img[int(h * 0.35):]}[part]


def detect(model, img):
    h, w = img.shape[:2]
    H, W = h * CANVAS, w * CANVAS
    oy, ox = (H - h) // 2, (W - w) // 2
    can = np.full((H, W, 3), 114, np.uint8)
    can[oy:oy + h, ox:ox + w] = img
    bs = [b for b in model(can)[0].boxes if float(b.conf) >= MIN_CONF]
    if not bs:
        return None
    x1, y1, x2, y2 = max(bs, key=lambda b: float(b.conf)).xyxy.tolist()[0]
    x1, x2 = max(0, round(x1) - ox), min(w, round(x2) - ox)
    y1, y2 = max(0, round(y1) - oy), min(h, round(y2) - oy)
    return (x1, y1, x2, y2) if x2 - x1 > 8 and y2 - y1 > 4 else None


def selfcheck():
    assert split_label("경기71아1234", 2.0) == [("top", "경기71"), ("bottom", "아1234")]
    assert split_label("경기부천가1234", 1.8) == [("top", "경기부천"), ("bottom", "가1234")]
    assert split_label("경기37바1234", 4.5) == [("full", "경기37바1234")]
    assert split_label("경기37바1234", 2.3, gap=0.4) == [("full", "경기37바1234")]
    assert split_label("경기부천가1234", 1.8, gap=0.4)[0] == ("top", "경기부천")
    assert split_label("12가3456", 2.0) == [("full", "12가3456")]


def main():
    selfcheck()
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    img_dir = src / "[원천]자동차번호판OCR데이터"
    labels = []
    with zipfile.ZipFile(src / "[라벨]자동차번호판OCR_valid.zip") as z:
        for name in sorted(n for n in z.namelist() if n.endswith(".json")):
            o = json.loads(z.read(name).decode("utf-8"))
            ip = img_dir / o["imagePath"]
            if ip.exists():
                labels.append((ip, norm(o["value"]), o["id"]))
    random.Random(20260915).shuffle(labels)
    baseline, rest = labels[:500], labels[500:]
    random.Random(20260928).shuffle(rest)
    n_val = round(len(rest) * VAL_SHARE)
    splits = {"test_aihub": baseline, "val": rest[:n_val], "train": rest[n_val:]}

    model = ONNXModel(get_model_path("plate_detect_v1"))
    stats = {"labels": len(labels), "canvas": CANVAS}
    for split, items in splits.items():
        (out / split).mkdir(parents=True, exist_ok=True)
        lines, c = [], collections.Counter()
        for ip, label, rid in items:
            img = cv2.imdecode(np.fromfile(str(ip), np.uint8), cv2.IMREAD_COLOR)
            box = detect(model, img) if img is not None else None
            if box is None:
                c["no_plate"] += 1
                continue
            x1, y1, x2, y2 = box
            plate = img[y1:y2, x1:x2]
            parts = split_label(label, (x2 - x1) / (y2 - y1), row_gap(plate))
            c["two_line" if len(parts) == 2 else "one_line"] += 1
            for i, (part, text) in enumerate(parts):
                rel = f"{split}/{rid}_{i}.jpg"
                cv2.imencode(".jpg", cut(plate, part), [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tofile(str(out / rel))
                lines.append(f"{rel}\t{text}")
        (out / f"{split}_list.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        stats[split] = {"plates": len(items), **c, "line_images": len(lines)}
        print(split, stats[split], flush=True)
    (out / "prep_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
