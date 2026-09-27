import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:\tmp\ocr-tools")
import cv2
import numpy as np

INPUTS = [
    Path(r"C:\Users\ymshin\Downloads\20260806_061434_EVT_1.avi"),
    Path(r"C:\Users\ymshin\Downloads\20260806_192353_EVT_1.avi"),
    Path(r"C:\Users\ymshin\Downloads\20260810_175721_EVT_1.avi"),
]
OUT = Path("ocr-test")
OUT.mkdir(exist_ok=True)

report = []
for src in INPUTS:
    cap = cv2.VideoCapture(str(src))
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frames / fps if fps else 0
    sample_dir = OUT / src.stem
    sample_dir.mkdir(exist_ok=True)
    tiles = []
    samples = []
    for i, sec in enumerate(np.linspace(0, max(duration - 0.05, 0), 24)):
        cap.set(cv2.CAP_PROP_POS_MSEC, float(sec * 1000))
        ok, frame = cap.read()
        if not ok:
            continue
        path = sample_dir / f"frame_{i:02d}_{sec:06.2f}s.jpg"
        cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        small = cv2.resize(frame, (480, round(480 * height / width)))
        cv2.putText(small, f"{sec:.2f}s", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, .8, (0, 255, 255), 2)
        tiles.append(small)
        samples.append(str(path))
    cap.release()
    if tiles:
        cols = 4
        rows = []
        for j in range(0, len(tiles), cols):
            row = tiles[j:j+cols]
            while len(row) < cols:
                row.append(np.zeros_like(tiles[0]))
            rows.append(cv2.hconcat(row))
        sheet = cv2.vconcat(rows)
        sheet_path = OUT / f"{src.stem}_contact.jpg"
        cv2.imwrite(str(sheet_path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 92])
    report.append({"file": str(src), "frames": frames, "fps": fps, "width": width, "height": height,
                   "duration_sec": duration, "sample_count": len(samples), "samples": samples})

(OUT / "metadata.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
