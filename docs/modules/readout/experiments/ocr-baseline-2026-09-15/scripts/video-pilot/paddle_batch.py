import json
import re
import sys
from pathlib import Path

sys.path.insert(0, r"C:\tmp\paddle-ocr")
from paddleocr import PaddleOCR

ROOT = Path(r"C:\Users\ymshin\Documents\카테캠\ocr-test")
SETS = {
    "20260806_061434_EVT_1": [4, 8, 11, 14, 17],
    "20260806_192353_EVT_1": [2, 7, 12, 17, 22],
    "20260810_175721_EVT_1": [2, 7, 12, 17, 22],
}

ocr = PaddleOCR(
    text_detection_model_name="PP-OCRv5_mobile_det",
    text_recognition_model_name="korean_PP-OCRv5_mobile_rec",
    enable_mkldnn=False,
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
)

out = []
for stem, indexes in SETS.items():
    paths = sorted((ROOT / stem).glob("frame_*.jpg"))
    for i in indexes:
        path = paths[i]
        result = next(iter(ocr.predict(str(path)))).json["res"]
        rows = []
        for text, score, box in zip(result["rec_texts"], result["rec_scores"], result["rec_boxes"]):
            x1, y1, x2, y2 = map(int, box)
            w, h = x2 - x1, y2 - y1
            digits = len(re.findall(r"\d", text))
            if digits >= 3 and w / max(h, 1) >= 2.2 and y1 < 1020:
                rows.append({"text": text, "score": round(float(score), 6), "box": [x1,y1,x2,y2],
                             "width": w, "height": h})
        out.append({"video": stem, "frame": path.name, "candidates": rows})
        print(stem, path.name, rows, flush=True)

(ROOT / "paddle_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
