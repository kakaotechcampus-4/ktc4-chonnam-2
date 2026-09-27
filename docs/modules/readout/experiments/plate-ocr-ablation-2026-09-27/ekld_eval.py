"""번호판 전용 학습 인식기(EasyKoreanLpDetector `best_acc`, AI Hub 172 약 8만 장)를 같은 GT로 평가한다.

    <detector venv python> ekld_eval.py gt_plates.json picks_all.json <videos_dir> ekld_eval.json <model_dir> <user_network_dir>

원본 앱과 같은 입력: 여백 없는 번호판 crop → 224×128 → 흑백 → `reader.recognize`.
  K1  seed 프레임 1장
  K2  CSRT 추적 7프레임 각각 → 자리별 투표 (`ocr_eval2.vote`)
라이선스가 명시되지 않은 가중치다 — 평가용으로만 쓴다.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

model_dir, net_dir = sys.argv[5], sys.argv[6]
sys.argv = sys.argv[:5]
import ocr_eval2 as base  # noqa: E402

PLATE_SIZE = (224, 128)


def tight(cap, frame_no, box):
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
    ok, img = cap.read()
    if not ok:
        return None
    H, W = img.shape[:2]
    x, y, w, h = box
    part = img[max(0, y):min(H, y + h), max(0, x):min(W, x + w)]
    if part.size == 0:
        return None
    return cv2.cvtColor(cv2.resize(part, PLATE_SIZE), cv2.COLOR_BGR2GRAY)


def main():
    import easyocr
    reader = easyocr.Reader(["en"], gpu=False, verbose=False, recog_network="best_acc",
                            user_network_directory=net_dir, model_storage_directory=model_dir,
                            download_enabled=False)

    def read(gray):
        res = reader.recognize(gray)
        return (base.norm(res[0][1]), float(res[0][2])) if res else ("", 0.0)

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
        fps = info["fps"]
        seed_frame = round(seed_t * fps)
        tracked = base.track_frames(cap, fps, seed_frame, seed_box)
        idx = np.linspace(0, len(tracked) - 1, min(base.K, len(tracked))).round().astype(int)
        crops = [c for c in (tight(cap, *tracked[i]) for i in sorted(set(idx))) if c is not None]
        seed = tight(cap, seed_frame, seed_box)
        cap.release()
        results = {"K1": read(seed), "K2": base.vote([read(c) for c in crops])}
        row = {"video": item["video"], "gt": item["gt"], "kind": item["kind"]}
        for m, (text, conf) in results.items():
            row[m] = {"text": text, "conf": round(conf, 3), **base.verdict(text, item["gt"], item["kind"])}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    base.out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
