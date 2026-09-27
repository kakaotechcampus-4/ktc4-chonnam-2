"""번호판 OCR 전처리 ablation — 위치는 GT seed로 고정, 판독 방식만 바꾼다.

    D:/paddle-env/Scripts/python.exe ocr_eval2.py gt_plates.json sheets/picks.json <videos_dir> out.json

방법
  A    seed 프레임 1장 (지금과 같은 단일 프레임)
  B    CSRT로 ±1.5초 추적 → 7프레임 각각 OCR → 자리별 투표
  B+R  B + 기울기 보정
  B+RS B+R + 2줄 번호판이면 위·아래를 나눠 따로 읽기
  B+RSV B+RS + 전처리 두 가지(원본·흑백 대비)를 투표에 함께 넣기

최종 판독은 **한국 번호판 형식을 통과할 때만** 낸다. 못 통과하면 보류(abstain).
"""
import collections
import json
import re
import sys
from pathlib import Path

import cv2
import numpy as np

gt_path, picks_path, videos, out_path = (Path(a) for a in sys.argv[1:5])
K = 7
SPAN_SEC = 1.5
TARGET_H = 120
PLATE_FORMAT = re.compile(r"^(?:[가-힣]{2}\d{2}[가-힣]\d{4}|\d{2,3}[가-힣]\d{4})$")
"""1줄 신형·구형(`12가3456`, `123가4567`)과 2줄 영업용(`전남82바5215`)."""


def norm(text):
    return re.sub(r"[^0-9가-힣]", "", text)


def deskew(img):
    """글자 줄의 기울기를 찾아 수평으로 돌린다. ±15°를 넘으면 오검출로 보고 건드리지 않는다."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(g, 60, 160)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 40, minLineLength=img.shape[1] // 3, maxLineGap=8)
    if lines is None:
        return img
    angles = [np.degrees(np.arctan2(y2 - y1, x2 - x1)) for x1, y1, x2, y2 in lines[:, 0]]
    angles = [a for a in angles if abs(a) < 15]
    if not angles:
        return img
    a = float(np.median(angles))
    m = cv2.getRotationMatrix2D((img.shape[1] / 2, img.shape[0] / 2), a, 1.0)
    return cv2.warpAffine(img, m, (img.shape[1], img.shape[0]), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)


def gray_contrast(img):
    g = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4)).apply(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)


class Reader:
    def __init__(self):
        from paddleocr import PaddleOCR
        self.engine = PaddleOCR(lang="korean", text_detection_model_name="PP-OCRv5_mobile_det",
                                text_recognition_model_name="korean_PP-OCRv5_mobile_rec",
                                enable_mkldnn=False, use_doc_orientation_classify=False,
                                use_doc_unwarping=False, use_textline_orientation=False)

    def lines(self, img):
        res = next(iter(self.engine.predict(img))).json["res"]
        return sorted(zip(res["rec_texts"], res["rec_scores"], res["rec_boxes"]),
                      key=lambda r: (round(r[2][1] / 25), r[2][0]))

    def read(self, img, split=False):
        if split:
            # 2줄: 윗줄은 글자가 작아 한 번에 읽으면 검출기가 놓친다 — 나눠서 윗줄은 더 키운다
            h = img.shape[0]
            top = cv2.resize(img[: int(h * 0.45)], None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            bottom = img[int(h * 0.35):]
            parts = [self.lines(top), self.lines(bottom)]
            text = "".join(norm("".join(t for t, _, _ in p)) for p in parts)
            scores = [s for p in parts for _, s, _ in p]
        else:
            ls = self.lines(img)
            text = norm("".join(t for t, _, _ in ls))
            scores = [s for _, s, _ in ls]
        return text, float(np.mean(scores)) if scores else 0.0


def vote(readings):
    readings = [(t, c) for t, c in readings if t]
    if not readings:
        return "", 0.0
    length = collections.Counter(len(t) for t, _ in readings).most_common(1)[0][0]
    same = [(t, c) for t, c in readings if len(t) == length]
    out, agree = [], []
    for i in range(length):
        w = collections.Counter()
        for t, c in same:
            w[t[i]] += c
        ch, top = w.most_common(1)[0]
        share = top / sum(w.values())
        out.append(ch if share > 0.5 else "?")
        agree.append(share)
    return "".join(out), float(np.mean(agree))


def verdict(pred, gt, kind):
    """accept(형식 통과) 여부와 정오. '?' 자리는 채점하지 않는다."""
    accepted = bool(PLATE_FORMAT.match(pred))
    if gt is None:
        return {"accepted": accepted, "correct": None, "wrong_accept": accepted}
    if not accepted:
        return {"accepted": False, "correct": False, "wrong_accept": False}
    ok = len(pred) == len(gt) and all(g == "?" or p == g for p, g in zip(pred, gt))
    return {"accepted": True, "correct": ok, "wrong_accept": not ok}


def track_frames(cap, fps, seed_frame, seed_box):
    """seed에서 앞뒤로 CSRT 추적. 반환은 [(frame_no, box)]."""
    out = {seed_frame: tuple(seed_box)}
    step = 3
    for direction in (1, -1):
        cap.set(cv2.CAP_PROP_POS_FRAMES, seed_frame)
        ok, img = cap.read()
        tracker = cv2.TrackerCSRT_create()
        tracker.init(img, tuple(int(v) for v in seed_box))
        f = seed_frame
        while abs(f - seed_frame) < SPAN_SEC * fps:
            f += direction * step
            if f < 0:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, f)
            ok, img = cap.read()
            if not ok:
                break
            found, box = tracker.update(img)
            if not found or box[2] < 8 or box[3] < 5:
                break
            out[f] = tuple(int(v) for v in box)
    return sorted(out.items())


def crop(cap, frame_no, box):
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
    ok, img = cap.read()
    if not ok:
        return None
    H, W = img.shape[:2]
    x, y, w, h = box
    pad = max(6, round(w * 0.2))
    part = img[max(0, y - pad):min(H, y + h + pad), max(0, x - pad):min(W, x + w + pad)]
    s = TARGET_H / max(h, 1)
    return cv2.resize(part, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)


def main():
    reader = Reader()
    items = json.loads(gt_path.read_text(encoding="utf-8"))["items"]
    picks = json.loads(picks_path.read_text(encoding="utf-8"))
    rows = []
    for item in items:
        info = picks[item["video"]]
        seed_t, seed_box = item["seed_t"], item["seed_plate"]
        if seed_box is None:
            top = max(info["picks"], key=lambda p: p["plate"][3] * p["conf"])
            seed_t, seed_box = top["t"], top["plate"]
        cap = cv2.VideoCapture(str(next(videos.glob(f"{item['video']}.*"))))
        fps = info["fps"]
        seed_frame = round(seed_t * fps)
        tracked = track_frames(cap, fps, seed_frame, seed_box)
        # 추적 구간에서 K장을 고르게 — 큰 것만 고르면 같은 순간이 몰린다
        idx = np.linspace(0, len(tracked) - 1, min(K, len(tracked))).round().astype(int)
        frames = [tracked[i] for i in sorted(set(idx))]
        crops = [c for c in (crop(cap, f, b) for f, b in frames) if c is not None]
        seed_crop = crop(cap, seed_frame, seed_box)
        cap.release()
        two_line = seed_box[2] / seed_box[3] < 2.6

        results = {}
        results["A"] = reader.read(seed_crop)
        results["B"] = vote([reader.read(c) for c in crops])
        rot = [deskew(c) for c in crops]
        results["B+R"] = vote([reader.read(c) for c in rot])
        results["B+RS"] = vote([reader.read(c, split=two_line) for c in rot])
        results["B+RSV"] = vote([reader.read(v, split=two_line) for c in rot for v in (c, gray_contrast(c))])

        row = {"video": item["video"], "gt": item["gt"], "kind": item["kind"],
               "tracked": len(tracked), "used": len(crops), "two_line": two_line}
        for m, (text, conf) in results.items():
            row[m] = {"text": text, "conf": round(conf, 3), **verdict(text, item["gt"], item["kind"])}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
