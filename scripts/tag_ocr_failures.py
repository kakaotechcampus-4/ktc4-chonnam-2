#!/usr/bin/env python3
"""실제 OCR 실행 결과에 readout 실패 분류를 붙인다 — 2026-09-15 PaddleOCR 기준선.

무엇을 하는 스크립트인가
------------------------
2026-09-15에 돌린 두 실행의 **원본 출력**을 읽어, 각 사례에 `decisions/failure-taxonomy.md`의
**등재값만** 붙인 tagging JSON을 만든다. 손으로 쓴 표가 아니라 원본에서 계산한 값이다.

  ① 블랙박스 AVI 3개 pilot   : 대표 15프레임의 검출·인식 결과 (`paddle_results.json`)
  ② AI Hub Validation 500장  : recognition 단독 기준선 (`paddleocr_500_results.json`)

이 스크립트가 정하지 않는 것
----------------------------
- **새 분류값을 만들지 않는다.** taxonomy에 없는 상황은 `kind: null` + `open_question`으로
  남긴다 (CLAUDE.md 4 「미결을 완성도를 위해 채우지 않는다」).
- **런타임 kind와 사후 분류를 섞지 않는다.** 두 실행 모두 readout 공개 함수를 통과하지 않은
  provider 단독 측정이므로, 여기 붙는 kind는 실제로 기록된 `ReadoutRun.failure.kind`가 아니라
  「같은 상황이 readout을 통과했다면 붙었을 분류」다. 필드 이름에 `would_be_`를 붙여 구분한다.
- **목표치를 정하지 않는다.** 기준선 측정이다.

사용:
    python scripts/tag_ocr_failures.py
    python scripts/tag_ocr_failures.py --pilot <경로> --dataset <경로> --out <경로>
"""
import argparse
import hashlib
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAMP = "2026-09-15"
DEFAULT_OUT = os.path.join(
    ROOT, "docs", "modules", "readout", "experiments", "ocr-baseline-" + STAMP)

# 원본은 레포 밖이다 — 크기 때문에 옮기지 않는다. 대신 sha256을 결과에 박아
# 어느 파일에서 나온 수치인지 고정한다.
EXT = os.path.join(os.path.expanduser("~"), "Documents", "카테캠")
DEFAULT_PILOT = os.path.join(EXT, "ocr-test", "paddle_results.json")
DEFAULT_DATASET = os.path.join(EXT, "ocr-dataset-eval", "paddleocr_500_results.json")

# 번호판 용도문자 40자. 형식 검사(자릿수·배치)와 별개로 **문자 집합**을 닫는다 —
# 500장 평가의 형식 검사는 배치만 보고 `년`·`시`·`는`을 통과시켰다.
PLATE_LETTERS = set("가나다라마거너더러머버서어저고노도로모보소오조구누두루무부수우주아바사자배하허호")
REGION = re.compile(
    r"^(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)")
HANGUL = re.compile(r"[가-힣]")

# 육안 대조값. pilot 보고서에 적힌 것만 옮긴다 — 없는 정답을 지어내지 않는다.
VISUAL_TRUTH = {
    "20260806_061434_EVT_1": None,      # 원거리·주행. 육안으로도 문자 판독 불가
    "20260806_192353_EVT_1": "23두4874",
    "20260810_175721_EVT_1": None,      # 2줄 황색. 아랫줄 바5215만 육안 확인, 윗줄 미확정
}
CONDITION = {
    "20260806_061434_EVT_1": "주행 · 원거리 · 횡방향 · 터널 진입",
    "20260806_192353_EVT_1": "정지 · 정면 · 백색 1줄",
    "20260810_175721_EVT_1": "정지 · 근거리 · 황색 2줄",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def illegal_letters(text):
    """번호판 용도문자 집합을 벗어난 한글."""
    return sorted({c for c in HANGUL.findall(text or "") if c not in PLATE_LETTERS})


# -- (1) 영상 pilot ------------------------------------------------

def tag_pilot(rows):
    by_video = {}
    for r in rows:
        by_video.setdefault(r["video"], []).append(r)

    out = []
    for video, frames in by_video.items():
        truth = VISUAL_TRUTH[video]
        tagged = []
        for fr in frames:
            # plate 후보 = 가장 높은 confidence. api.py의 _best_index()가 쓰는 기준과 같다.
            cands = sorted(fr["candidates"], key=lambda c: -c["score"])
            top = cands[0] if cands else None
            if top is None:
                verdict = "NOT_DETECTED"
            elif truth is None:
                verdict = "TRUTH_UNKNOWN"
            else:
                verdict = "EXACT" if top["text"] == truth else "MISMATCH"
            tagged.append({
                "frame": fr["frame"],
                "candidates": len(fr["candidates"]),
                "text": top["text"] if top else None,
                "confidence": round(top["score"], 4) if top else None,
                # box는 [x0,y0,x1,y1]이다. 계약 §4 plate_bbox_xywh와 맞추려면 xywh로 옮긴다.
                "bbox_xywh": ([top["box"][0], top["box"][1], top["width"], top["height"]]
                              if top else None),
                "plate_px_height": top["height"] if top else None,
                "illegal_letters": illegal_letters(top["text"]) if top else [],
                "verdict": verdict,
            })

        detected = [t for t in tagged if t["text"]]
        texts = {t["text"] for t in detected}
        entry = {
            "video": video,
            "condition": CONDITION[video],
            "visual_truth": truth,
            "frames_ocr": len(tagged),
            "frames_detected": len(detected),
            "distinct_texts": sorted(texts),
            "unanimous": len(texts) == 1 and len(detected) == len(tagged),
            "exact_frames": len([t for t in tagged if t["verdict"] == "EXACT"]),
            "frames": tagged,
        }
        entry["tagging"] = pilot_tagging(entry)
        out.append(entry)
    return sorted(out, key=lambda e: e["video"])


def pilot_tagging(e):
    """등재값만 붙인다. 등재값이 없으면 null + open_question."""
    if e["frames_detected"] == 0:
        return {
            "would_be_runtime_kind": "PLATE_DETECTION",
            "kind_registered": True,
            "would_be_failure_code": None,
            "code_registered": False,
            "post_hoc": None,
            "would_be_abstain_reason": None,
            "open_question": (
                "PLATE_DETECTION에 대응하는 failure.code가 taxonomy 「code」 표에 없다. "
                "등재된 code는 INFRA 3종뿐인데 contract-readout-run.md §4 예시는 "
                "NO_PLATE_REGION_FOUND를 쓴다 — 미등재 값이다. Owner 결정 필요."),
            "note": "검출 0/5. 거리·해상도 문제인지 detector 문제인지는 이 실행으로 분리되지 않는다.",
        }
    if e["unanimous"] and e["visual_truth"] is None:
        return {
            "would_be_runtime_kind": None,
            "kind_registered": None,
            "would_be_failure_code": None,
            "code_registered": None,
            "post_hoc": "OVERCONFIDENT",
            "would_be_abstain_reason": None,
            "open_question": (
                "2줄 번호판의 아랫줄만 만장일치·고신뢰로 읽었다. 영역을 못 찾은 것도"
                "(PLATE_DETECTION) 문자를 잘못 읽은 것도(PLATE_RECOGNITION) 아닌 "
                "「영역을 부분만 잡음」이며 taxonomy에 해당 값이 없다. Owner 결정 필요."),
            "note": ("현재 api.py는 만장일치 + 고신뢰이므로 abstained=false · status=OK로 "
                     "확정한다. 완전성 검사가 없어 막히지 않는다."),
        }
    mism = [f for f in e["frames"] if f["verdict"] == "MISMATCH"]
    return {
        "would_be_runtime_kind": "PLATE_RECOGNITION" if mism else None,
        "kind_registered": bool(mism),
        "would_be_failure_code": None,
        "code_registered": False,
        "post_hoc": None,
        "would_be_abstain_reason": "FRAME_DISAGREEMENT" if len(e["distinct_texts"]) > 1 else None,
        "open_question": None,
        "note": ("프레임 간 불일치가 있어 현재 구현의 만장일치 consensus가 abstain으로 막는다. "
                 "PLATE_RECOGNITION은 프레임 단위 분류이고 run 단위 결과는 정상 보류다."),
    }


# -- (2) AI Hub 500장 ----------------------------------------------

def _subsequence(p, t):
    it = iter(t)
    return all(c in it for c in p)


def tag_dataset(rows):
    empty = [r for r in rows if not r["prediction"]]
    nonempty = [r for r in rows if r["prediction"]]
    exact = [r for r in nonempty if r["exact"]]
    wrong = [r for r in nonempty if not r["exact"]]
    region = [r for r in rows if REGION.match(r["truth"])]
    fmt_wrong = [r for r in wrong if r["format_valid"]]

    gates = []
    for th in (0.8, 0.9, 0.95):
        acc = [r for r in nonempty if r["score"] >= th]
        bad = [r for r in acc if not r["exact"]]
        leak = [r for r in bad if r["format_valid"]]        # 형식 gate까지 통과한 오답
        illegal = [r for r in leak if illegal_letters(r["prediction"])]
        rest = [r for r in leak if not illegal_letters(r["prediction"])]
        gates.append({
            "confidence": th,
            "accepted": len(acc),
            "wrong_accepts": len(bad),
            # 아래는 형식 gate까지 통과한 오답(leak)의 내역이다.
            "wrong_accepts_passing_format": len(leak),
            "of_which_illegal_letter": len(illegal),
            "of_which_region_dropped": len([r for r in rest if REGION.match(r["truth"])]),
            "of_which_unexplained": len([r for r in rest if not REGION.match(r["truth"])]),
        })

    return {
        "n": len(rows),
        "exact": len(exact),
        "empty_predictions": {
            "n": len(empty),
            "max_confidence": max((r["score"] for r in empty), default=None),
            "would_be_runtime_kind": None,
            "post_hoc": None,
            "note": ("confidence가 전부 정확히 0.0이다 — 고신뢰로 위장하지 않는다. "
                     "readout을 통과하면 읽어낸 글자가 없는 경우이므로 "
                     "observation.status=UNKNOWN · value=null이고 실패가 아니다."),
        },
        "wrong_nonempty": {
            "n": len(wrong),
            "would_be_runtime_kind": "PLATE_RECOGNITION",
            "kind_registered": True,
            "subsequence_of_truth": len([r for r in wrong
                                         if _subsequence(r["prediction"], r["truth"])]),
            "with_illegal_letter": len([r for r in wrong if illegal_letters(r["prediction"])]),
        },
        "region_plates": {
            "n": len(region),
            "exact": len([r for r in region if r["exact"]]),
            "region_dropped_exactly": len([
                r for r in region
                if r["prediction"] and REGION.sub("", r["truth"]) == r["prediction"]]),
            "note": "지역명이 붙는 번호판 = 2줄 계열. 영상 pilot의 바5215와 같은 실패다.",
        },
        "format_gate_leaks": {
            "n": len(fmt_wrong),
            "max_confidence": round(max((r["score"] for r in fmt_wrong), default=0), 4),
            "caught_by_letter_set": len([r for r in fmt_wrong if illegal_letters(r["prediction"])]),
            "region_drop": len([r for r in fmt_wrong if REGION.match(r["truth"])]),
            "cases": [{
                "truth": r["truth"], "prediction": r["prediction"],
                "confidence": round(r["score"], 4),
                "illegal_letters": illegal_letters(r["prediction"]),
                "region_drop": bool(REGION.match(r["truth"])),
            } for r in sorted(fmt_wrong, key=lambda r: -r["score"])],
        },
        "gates": gates,
        "post_hoc_note": (
            "confidence 단독 gate를 통과한 오답이 OVERCONFIDENT 후보다. 실제 분류는 "
            "정답지 대조로 eval이 붙인다 — readout이 런타임에 붙일 수 있는 값이 아니다."),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", default=DEFAULT_PILOT)
    ap.add_argument("--dataset", default=DEFAULT_DATASET)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    for src, name, fn in (
        (args.pilot, "tagged-video-pilot.json", tag_pilot),
        (args.dataset, "tagged-dataset-500.json", tag_dataset),
    ):
        with open(src, encoding="utf-8") as f:
            rows = json.load(f)
        payload = {
            "source_file": os.path.basename(src),
            "source_sha256": sha256(src),
            "source_note": "레포 밖 원본. 경로는 같은 폴더 README.md 참조",
            "executed_at": STAMP,
            "taxonomy": "docs/modules/readout/decisions/failure-taxonomy.md",
            "tagging": fn(rows),
        }
        path = os.path.join(args.out, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("wrote", os.path.relpath(path, ROOT))


if __name__ == "__main__":
    main()
