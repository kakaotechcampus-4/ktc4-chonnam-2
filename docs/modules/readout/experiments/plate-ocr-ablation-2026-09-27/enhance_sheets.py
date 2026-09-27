"""사람이 번호판을 읽도록 보정한 시트를 만든다 — 생성형 복원은 쓰지 않는다.

    python enhance_sheets.py <picks.json> <videos_dir> <out_dir>

picks마다 한 줄: [원본 확대] [다중 프레임 합성] [합성+선명화] [흑백 대비+선명화]
합성은 ±0.5초 프레임을 기준 crop에 ECC로 정렬해 **중앙값**을 낸다(평균보다 튀는 프레임에 강하다).
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

picks_path, videos, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
data = json.loads(picks_path.read_text(encoding="utf-8"))
TOP = 3
WINDOW_SEC = 0.5
TARGET_W = 420          # 표시 폭 — 작은 번호판도 같은 크기로 보이게 키운다


def label(img, text):
    bar = np.full((26, img.shape[1], 3), 30, np.uint8)
    cv2.putText(bar, text, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    return np.vstack([bar, img])


def sharpen(img):
    return cv2.addWeighted(img, 1.8, cv2.GaussianBlur(img, (0, 0), 1.2), -0.8, 0)


def gray_contrast(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(3, 3)).apply(g)
    return cv2.cvtColor(sharpen(g), cv2.COLOR_GRAY2BGR)


for name, info in data.items():
    picks = sorted(info["picks"], key=lambda p: -(p["plate"][3] * p["conf"]))[:TOP]
    if not picks:
        continue
    cap = cv2.VideoCapture(str(videos / f"{name}.avi"))
    fps = info["fps"]
    rows = []
    for p in sorted(picks, key=lambda p: p["t"]):
        x, y, w, h = p["plate"]
        pad = max(6, round(w * 0.25))
        scale = TARGET_W / (w + 2 * pad)

        def crop_at(frame_no, extra=0):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ok, img = cap.read()
            if not ok:
                return None
            H, W = img.shape[:2]
            e = pad + extra
            c = img[max(0, y - e):min(H, y + h + e), max(0, x - e):min(W, x + w + e)]
            return cv2.resize(c, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)

        ref = crop_at(p["frame"])
        ref_g = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY).astype(np.float32)
        stack = [ref.astype(np.float32)]
        half = round(fps * WINDOW_SEC)
        for k in range(-half, half + 1, 2):
            if k == 0:
                continue
            cand = crop_at(p["frame"] + k)
            if cand is None or cand.shape != ref.shape:
                continue
            warp = np.eye(2, 3, dtype=np.float32)
            try:
                cc, warp = cv2.findTransformECC(ref_g, cv2.cvtColor(cand, cv2.COLOR_BGR2GRAY).astype(np.float32),
                                                warp, cv2.MOTION_AFFINE,
                                                (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 80, 1e-5), None, 5)
            except cv2.error:
                continue
            if cc < 0.8:                     # 정렬이 안 맞은 프레임은 섞지 않는다 — 번진다
                continue
            stack.append(cv2.warpAffine(cand, warp, (ref.shape[1], ref.shape[0]),
                                        flags=cv2.INTER_LANCZOS4 + cv2.WARP_INVERSE_MAP,
                                        borderMode=cv2.BORDER_REPLICATE).astype(np.float32))
        fused = np.median(np.stack(stack), axis=0).astype(np.uint8)
        panels = [label(ref, f"t={p['t']:.1f}s  original {w}x{h}px"),
                  label(fused, f"fusion {len(stack)} frames"),
                  label(sharpen(fused), "fusion + sharpen"),
                  label(gray_contrast(fused), "fusion + gray contrast")]
        hmax = max(q.shape[0] for q in panels)
        panels = [np.pad(q, ((0, hmax - q.shape[0]), (0, 8), (0, 0))) for q in panels]
        rows.append(np.hstack(panels))
    cap.release()
    wmax = max(r.shape[1] for r in rows)
    sheet = np.vstack([np.pad(r, ((0, 10), (0, wmax - r.shape[1]), (0, 0))) for r in rows])
    cv2.imencode(".jpg", sheet, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tofile(str(out / f"{name}.jpg"))
    print(name, [len(r) for r in rows], flush=True)
