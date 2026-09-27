"""번호판 crop 보정 비교 — 같은 프레임, 같은 bbox, 보정만 바꿔 PaddleOCR로 읽는다.

    D:/paddle-env/Scripts/python.exe plate_enhance.py <video> <at_sec> <x,y,w,h> <GT> <out_dir>
"""
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

video, at_sec, bbox, gt, out = sys.argv[1], float(sys.argv[2]), sys.argv[3], sys.argv[4], Path(sys.argv[5])
x, y, w, h = map(int, bbox.split(","))
out.mkdir(parents=True, exist_ok=True)

cap = cv2.VideoCapture(video)
fps = cap.get(cv2.CAP_PROP_FPS)
center = round(at_sec * fps)
frames = {}
for k in range(-4, 5):                           # 앞뒤 4프레임 — fusion 재료
    cap.set(cv2.CAP_PROP_POS_FRAMES, center + k)
    ok, img = cap.read()
    if ok:
        frames[k] = img
cap.release()
H, W = frames[0].shape[:2]

pad = round(max(w, h) * 0.25)                    # 번호판 주변 여백 — OCR detector가 경계를 잡게
x1, y1, x2, y2 = max(0, x - pad), max(0, y - pad), min(W, x + w + pad), min(H, y + h + pad)
crop = lambda img: img[y1:y2, x1:x2].copy()      # noqa: E731
base = crop(frames[0])


def up(img, s=3, interp=cv2.INTER_CUBIC):
    return cv2.resize(img, None, fx=s, fy=s, interpolation=interp)


def clahe(img):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    lab[..., 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4)).apply(lab[..., 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def unsharp(img, amount=1.0, sigma=1.5):
    blur = cv2.GaussianBlur(img, (0, 0), sigma)
    return cv2.addWeighted(img, 1 + amount, blur, -amount, 0)


def denoise(img):
    return cv2.fastNlMeansDenoisingColored(img, None, 5, 5, 7, 21)


def fuse(scale=3):
    """앞뒤 프레임을 ECC로 기준 프레임에 정렬해 평균 — 영상이라 가능한 보정.

    프레임마다 다른 센서 노이즈·압축 블록이 평균되며 줄고, 확대 전에 합치면 글자 가장자리가
    덜 뭉개진다. 정렬에 실패한 프레임은 뺀다(흔들린 프레임을 섞으면 오히려 번진다).
    """
    ref = cv2.cvtColor(up(base, scale), cv2.COLOR_BGR2GRAY).astype(np.float32)
    stack, used = [up(base, scale).astype(np.float32)], [0]
    for k, img in frames.items():
        if k == 0:
            continue
        cand = up(crop(img), scale)
        warp = np.eye(2, 3, dtype=np.float32)
        try:
            _, warp = cv2.findTransformECC(ref, cv2.cvtColor(cand, cv2.COLOR_BGR2GRAY).astype(np.float32),
                                           warp, cv2.MOTION_AFFINE,
                                           (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 1e-5), None, 5)
        except cv2.error:
            continue
        aligned = cv2.warpAffine(cand, warp, (ref.shape[1], ref.shape[0]),
                                 flags=cv2.INTER_CUBIC + cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
        stack.append(aligned.astype(np.float32))
        used.append(k)
    return np.clip(np.mean(stack, axis=0), 0, 255).astype(np.uint8), used


fused, used = fuse()
variants = {
    "00_원본(1x)": base,
    "01_3x_cubic(현재)": up(base),
    "02_3x_lanczos": up(base, interp=cv2.INTER_LANCZOS4),
    "03_3x+CLAHE": clahe(up(base)),
    "04_3x+unsharp": unsharp(up(base)),
    "05_3x+denoise+unsharp": unsharp(denoise(up(base))),
    "06_fusion(9프레임)": fused,
    "07_fusion+unsharp": unsharp(fused),
    "08_fusion+CLAHE+unsharp": unsharp(clahe(fused)),
    "09_5x_cubic": up(base, 5),
}

from paddleocr import PaddleOCR  # noqa: E402

engine = PaddleOCR(lang="korean", text_detection_model_name="PP-OCRv5_mobile_det",
                   text_recognition_model_name="korean_PP-OCRv5_mobile_rec", enable_mkldnn=False,
                   use_doc_orientation_classify=False, use_doc_unwarping=False,
                   use_textline_orientation=False)

rows = []
for name, img in variants.items():
    cv2.imwrite(str(out / f"{name}.png"), img)
    t = time.time()
    res = next(iter(engine.predict(img))).json["res"]
    texts = [(t_, round(float(s), 3)) for t_, s in zip(res["rec_texts"], res["rec_scores"])]
    joined = "".join(t_ for t_, _ in texts).replace(" ", "")
    rows.append({"variant": name, "size": f"{img.shape[1]}x{img.shape[0]}", "texts": texts,
                 "exact": joined == gt, "has_hangul": any("가" <= c <= "힣" for c in joined),
                 "sec": round(time.time() - t, 2)})
    print(json.dumps(rows[-1], ensure_ascii=False), flush=True)

# 한눈에 보는 비교 그림 — 모두 같은 높이로 맞추지 않는다. 실제 크기 차이를 보여주는 게 목적이다
canvas_w = max(v.shape[1] for v in variants.values()) + 20
blocks = []
for name in ("00_원본(1x)", "01_3x_cubic(현재)", "09_5x_cubic", "06_fusion(9프레임)", "08_fusion+CLAHE+unsharp"):
    img = variants[name]
    block = np.full((img.shape[0] + 40, canvas_w, 3), 255, np.uint8)
    block[30:30 + img.shape[0], 10:10 + img.shape[1]] = img
    cv2.putText(block, f"{name.split('_', 1)[1].encode('ascii', 'ignore').decode() or name[:2]} "
                       f"{img.shape[1]}x{img.shape[0]}px", (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
    blocks.append(block)
cv2.imwrite(str(out / "compare.png"), np.vstack(blocks))
(out / "results.json").write_text(json.dumps({"video": Path(video).name, "at_sec": at_sec, "fps": fps,
                                              "frame_wh": [W, H], "plate_bbox": [x, y, w, h],
                                              "crop_box": [x1, y1, x2 - x1, y2 - y1], "gt": gt,
                                              "fusion_frames_used": used, "rows": rows},
                                             ensure_ascii=False, indent=2), encoding="utf-8")
