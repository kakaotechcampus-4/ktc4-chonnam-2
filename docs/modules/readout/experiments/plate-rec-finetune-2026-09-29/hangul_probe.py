"""PaddleOCR 인식기가 한글 자리에서 정답 한글을 몇 위로 보는지 — CTC 확률을 직접 연다.

    TRACKS=tracks_verified.json D:/paddle-env/Scripts/python.exe hangul_probe.py gt_plates.json picks_all.json <videos_dir> hangul_probe.json

`ocr_eval2.py`와 같은 입력(seed 1장 + 검증된 추적 프레임, 기울기 보정)을 같은 PaddleOCR로 읽되, `CTCLabelDecode`에
들어가는 확률 행렬([시간, 글자])을 가로챈다. 전체 판독 GT만 본다.

한 번 읽을 때마다
  greedy      지금 제품이 내는 글자열
  g_rank      모든 시간 칸 중 정답 한글 확률이 가장 높은 칸에서, 정답 한글의 순위(전체 글자 중)
  g_prob      그 확률
  plate_top   번호판 용도 한글 40자로만 좁혔을 때 확률이 가장 높은 (한글, 확률) — 시간 칸 전체에서
「40자로 좁히면 맞는가」는 plate_top의 한글 == 정답 한글이다.
"""
import json
import os

import numpy as np

import ocr_eval2 as base
from paddlex.inference.models.text_recognition.processors import CTCLabelDecode

PLATE_HANGUL = list("가나다라마거너더러머버서어저고노도로모보소오조구누두루무부수우주아바사자배하허호")
assert len(PLATE_HANGUL) == 40 and len(set(PLATE_HANGUL)) == 40

CAPTURED = []
_orig = CTCLabelDecode.__call__


def _capture(self, pred, *a, **k):
    for row in np.array(pred[0]):
        CAPTURED.append((row, self.character))
    return _orig(self, pred, *a, **k)


CTCLabelDecode.__call__ = _capture


def analyse(rows, g):
    """한 번 읽은 결과(여러 줄)의 확률 행렬들에서 정답 한글 g의 자리를 본다."""
    best = None      # (prob, rank)
    top = ("", 0.0)
    for probs, chars in rows:
        idx = {c: i for i, c in enumerate(chars)}
        if g in idx:
            t = int(probs[:, idx[g]].argmax())
            p = float(probs[t, idx[g]])
            rank = int((probs[t] > p).sum()) + 1
            if best is None or p > best[0]:
                best = (p, rank)
        present = [h for h in PLATE_HANGUL if h in idx]
        sub = probs[:, [idx[h] for h in present]]
        t, j = np.unravel_index(sub.argmax(), sub.shape)
        if sub[t, j] > top[1]:
            top = (present[j], float(sub[t, j]))
    return best, top


def greedy(rows):
    out = []
    for probs, chars in rows:
        prev = 0
        for i in probs.argmax(-1):
            if i != prev and i != 0:
                out.append(chars[i])
            prev = i
    return base.norm("".join(out))


def main():
    reader = base.Reader()
    import cv2
    items = json.loads(base.gt_path.read_text(encoding="utf-8"))["items"]
    picks = json.loads(base.picks_path.read_text(encoding="utf-8"))
    out = []
    for n, item in enumerate(items):
        if item["kind"] != "full":
            continue
        g = [c for c in item["gt"] if "가" <= c <= "힣"][-1]      # 용도 한글(2줄이면 지역명 뒤)
        info = picks[item["video"]]
        seed_t, seed_box = item["seed_t"], item["seed_plate"]
        if seed_box is None:
            top = max(info["picks"], key=lambda p: p["plate"][3] * p["conf"])
            seed_t, seed_box = top["t"], top["plate"]
        cap = cv2.VideoCapture(str(next(base.videos.glob(f"{item['video']}.*"))))
        seed_frame = round(seed_t * info["fps"])
        frames = base.frames_for(n, cap, info["fps"], seed_frame, seed_box)
        idx = np.linspace(0, len(frames) - 1, min(base.K, len(frames))).round().astype(int)
        crops = [base.crop(cap, *frames[i]) for i in sorted(set(idx))]
        cap.release()
        two_line = seed_box[2] / seed_box[3] < 2.6
        reads = []
        for c in crops:
            if c is None:
                continue
            CAPTURED.clear()
            reader.read(base.deskew(c), split=two_line)
            (best, top) = analyse(list(CAPTURED), g)
            reads.append({"greedy": greedy(CAPTURED), "g_prob": best and round(best[0], 4),
                          "g_rank": best and best[1], "plate_top": [top[0], round(top[1], 4)]})
        row = {"video": item["video"], "gt": item["gt"], "g": g, "reads": reads}
        out.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    base.out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
