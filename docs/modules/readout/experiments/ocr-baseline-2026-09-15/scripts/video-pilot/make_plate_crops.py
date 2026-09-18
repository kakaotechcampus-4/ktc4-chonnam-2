import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:\tmp\paddle-ocr")
import cv2
import numpy as np

root = Path(r"C:\Users\ymshin\Documents\카테캠\ocr-test")
data = json.loads((root / "paddle_results.json").read_text(encoding="utf-8"))
tiles = []
for row in data:
    for c in row["candidates"]:
        text = c["text"]
        if not ("4874" in text or "5215" in text):
            continue
        img = cv2.imdecode(np.fromfile(root / row["video"] / row["frame"], dtype=np.uint8), cv2.IMREAD_COLOR)
        x1,y1,x2,y2 = c["box"]
        pad_x, pad_y = 25, 15
        crop = img[max(0,y1-pad_y):min(img.shape[0],y2+pad_y), max(0,x1-pad_x):min(img.shape[1],x2+pad_x)]
        crop = cv2.resize(crop, (600, 180), interpolation=cv2.INTER_CUBIC)
        cv2.putText(crop, row["frame"].split("_")[-1].replace(".jpg",""), (8,28),
                    cv2.FONT_HERSHEY_SIMPLEX, .75, (0,255,255), 2)
        tiles.append(crop)
sheet = cv2.vconcat(tiles)
ok, encoded = cv2.imencode(".jpg", sheet, [cv2.IMWRITE_JPEG_QUALITY, 96])
if ok:
    encoded.tofile(root / "plate_crops_contact.jpg")
