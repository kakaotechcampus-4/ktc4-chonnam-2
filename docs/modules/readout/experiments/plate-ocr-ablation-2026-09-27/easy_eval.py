"""EasyOCR과 PaddleOCR을 같은 입력으로 비교한다 — ablation F.

    <detector venv python> easy_eval.py gt_plates.json sheets/picks.json <videos_dir> easy_eval.json

입력(추적·crop·기울기 보정·2줄 분할)은 `ocr_eval2.py`의 함수를 그대로 쓴다. 인식기만 바뀐다.

  E    EasyOCR 한국어, seed 1장
  EL   E + 허용 글자 제한(숫자 + 번호판에 쓰이는 한글)
  ELB  EL + 7프레임 투표 + 기울기 보정 + 2줄 분할 (Paddle `B+RS`와 같은 입력)
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.argv = [sys.argv[0], *sys.argv[1:]]
import ocr_eval2 as base  # noqa: E402  같은 폴더. argv를 모듈 수준에서 읽는다

PLATE_HANGUL = ("가나다라마거너더러머버서어저고노도로모보소오조구누두루무부수우주"
                "아바사자배하허호" "서울부산대구인천광주대전울산세종경기강원충북남전제")
"""번호판 용도 기호(자가용·영업용·렌터카·택배)와 2줄 영업용 지역명 글자. 없는 글자를 못 내게 한다."""
ALLOW = "0123456789" + "".join(sorted(set(PLATE_HANGUL)))


class Easy:
    def __init__(self, allow=None):
        import easyocr
        self.reader = easyocr.Reader(["ko"], gpu=False, verbose=False)
        self.allow = allow

    def lines(self, img):
        res = self.reader.readtext(img, detail=1, allowlist=self.allow)
        return sorted(((t, float(c), b) for b, t, c in res),
                      key=lambda r: (round(min(p[1] for p in r[2]) / 25), min(p[0] for p in r[2])))

    def read(self, img, split=False):
        if split:
            h = img.shape[0]
            top = cv2.resize(img[: int(h * 0.45)], None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            parts = [self.lines(top), self.lines(img[int(h * 0.35):])]
            text = "".join(base.norm("".join(t for t, _, _ in p)) for p in parts)
            scores = [s for p in parts for _, s, _ in p]
        else:
            ls = self.lines(img)
            text = base.norm("".join(t for t, _, _ in ls))
            scores = [s for _, s, _ in ls]
        return text, float(np.mean(scores)) if scores else 0.0


def main():
    plain, limited = Easy(), Easy(ALLOW)
    items = json.loads(base.gt_path.read_text(encoding="utf-8"))["items"]
    picks = json.loads(base.picks_path.read_text(encoding="utf-8"))
    rows = []
    for item in items:
        info = picks[item["video"]]
        seed_t, seed_box = item["seed_t"], item["seed_plate"]
        if seed_box is None:
            top = max(info["picks"], key=lambda p: p["plate"][3] * p["conf"])
            seed_t, seed_box = top["t"], top["plate"]
        cap = cv2.VideoCapture(str(base.videos / f"{item['video']}.avi"))
        fps = info["fps"]
        seed_frame = round(seed_t * fps)
        tracked = base.track_frames(cap, fps, seed_frame, seed_box)
        idx = np.linspace(0, len(tracked) - 1, min(base.K, len(tracked))).round().astype(int)
        crops = [c for c in (base.crop(cap, *tracked[i]) for i in sorted(set(idx))) if c is not None]
        seed_crop = base.crop(cap, seed_frame, seed_box)
        cap.release()
        two_line = seed_box[2] / seed_box[3] < 2.6
        rot = [base.deskew(c) for c in crops]
        results = {
            "E": plain.read(seed_crop),
            "EL": limited.read(seed_crop),
            "ELB": base.vote([limited.read(c, split=two_line) for c in rot]),
        }
        row = {"video": item["video"], "gt": item["gt"], "kind": item["kind"], "used": len(crops)}
        for m, (text, conf) in results.items():
            row[m] = {"text": text, "conf": round(conf, 3), **base.verdict(text, item["gt"], item["kind"])}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    base.out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
