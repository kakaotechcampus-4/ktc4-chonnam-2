"""AI-Hub 172 파생 표본 → private manifest.

    python -m eval.tools.build_private_aihub172 --source .../aihub172/track2_recognition
    python -m eval.tools.build_private_aihub172 --track 1 --source .../aihub172/track1_association

트랙② (기본) → `private_aihub172_plate` — 번호판 crop 인식.
트랙① → `private_aihub172_track1` — CCTV 프레임의 차량 검출 지속성. 아래 `build_track1`.

입력은 `데이터셋 생성/scripts/aihub172.py sample` 의 산출물이다(manifest.json ·
gt_plate.LOCAL_ONLY.json · crops/). 출력은 전부 `.env` 의 DAESINGO_EVAL_PRIVATE_ROOT
아래다 — 정답지와 crop 에 실제 차량번호가 있어 공개 레포에 둘 수 없다.

**legibility 는 전부 READABLE 이다.** AI-Hub 가 모든 crop 에 value 문자열을 달았고,
판독불가 라벨은 원천에 없다. 그래서 wrong_accept_rate · abstention_recall 은 분모가
0 이라 null 이 된다 — 성능이 좋아서가 아니다.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys

from eval import paths

MANIFEST = "private_aihub172_plate"
MANIFEST_VERSION = "m1"
GT_VERSION = "ap1"
CONTRACT_VERSION = "plate-readout/v1.3"

TRACK1_MANIFEST = "private_aihub172_track1"
TRACK1_GT_VERSION = "at1"


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")


def build(source, out_dir):
    src_manifest = _read(os.path.join(source, "manifest.json"))
    src_gt = _read(os.path.join(source, "gt_plate.LOCAL_ONLY.json"))
    truth = {g["sample_id"]: g["gt_plate_text"] for g in src_gt["items"]}
    items = src_manifest["items"]
    missing = [i["sample_id"] for i in items if i["sample_id"] not in truth]
    if missing:
        raise ValueError(f"정답이 없는 표본 {len(missing)}건: {missing[:5]}")

    crops = os.path.join(out_dir, "crops")
    os.makedirs(crops, exist_ok=True)
    for item in items:
        shutil.copyfile(os.path.join(source, item["file_path"]),
                        os.path.join(out_dir, item["file_path"]))

    src_meta = src_manifest["meta"]
    meta = {"manifest_version": MANIFEST_VERSION, "tier": "AIHUB172",
            "source": src_meta.get("source"), "section": src_meta.get("section"),
            "split": src_meta.get("split"), "sampling": src_meta.get("sampling"),
            "track": src_meta.get("track"), "readout_taken": src_meta.get("readout_taken"),
            "note": "crop 입력이라 검출 단계가 빠져 있다 — 인식(recognition)만 잰다"}
    _write(os.path.join(out_dir, "samples.json"), {
        "meta": meta,
        "samples": [{k: item[k] for k in ("sample_id", "file_path", "width", "height",
                                           "sha256")} for item in items],
    })
    _write(os.path.join(out_dir, "gt", "gt_plate.json"), {
        "meta": {"gt_version": GT_VERSION, "tier": "AIHUB172", "stage": "plate",
                 "contract_version": CONTRACT_VERSION,
                 "coverage": {"readouts_total": len(items), "readable": len(items),
                              "unreadable": 0, "independent_ground_truth": True,
                              "legibility_rule": "AI-Hub value 가 있는 crop 은 전부 READABLE"}},
        "items": [{"scenario_id": item["sample_id"], "legibility": "READABLE",
                   "true_text": truth[item["sample_id"]]} for item in items],
    })
    return len(items)


def _xyxy_to_xywh(box):
    (x1, y1), (x2, y2) = box
    return [round(x1, 1), round(y1, 1), round(x2 - x1, 1), round(y2 - y1, 1)]


def build_track1(source, out_dir):
    """`aihub172.py index` + `frames` 산출물 → 영상별 프레임 목록과 차량 박스 정답지.

    **라벨 프레임은 연속 프레임이 아니다** (frameNo 가 띄엄띄엄이다). 지속성은
    frame_no 순으로 늘어놓은 라벨 프레임 사이에서 센다.

    원천에 위반 여부가 없어 라벨된 차량 전부가 대상이다(프레임당 평균 1.01대).
    """
    sample = _read(os.path.join(source, "sample_frames.json"))
    picked = set(sample["videos"])
    boxes = {}                                    # (video, frame_no) -> [xywh, ...]
    with open(os.path.join(source, "frames.jsonl"), encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec["video_name"] in picked and rec.get("car_bbox"):
                boxes.setdefault((rec["video_name"], rec["frame_no"]), []).append(
                    _xyxy_to_xywh(rec["car_bbox"]))

    videos, items = [], []
    for video in sorted(picked):
        stem = video.removesuffix(".mp4")
        frame_nos = sorted(n for v, n in boxes if v == video)
        frames = []
        for n in frame_nos:
            rel = f"frames/{stem}/{n}.jpg"
            src = os.path.join(source, rel)
            if not os.path.isfile(src):
                continue
            dst = os.path.join(out_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
            with open(dst, "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
            frames.append({"frame_no": n, "file_path": rel, "sha256": digest})
        videos.append({"video_id": stem, "frames": frames})
        items.append({"video_id": stem, "frames": [
            {"frame_no": fr["frame_no"], "car_bboxes_xywh": boxes[(video, fr["frame_no"])]}
            for fr in frames]})

    n_frames = sum(len(v["frames"]) for v in videos)
    _write(os.path.join(out_dir, "samples.json"), {
        "meta": {"manifest_version": MANIFEST_VERSION, "tier": "AIHUB172",
                 "source": "aihub_172", "section": "원본이미지(merged)",
                 "track": "1_association", "sampling": sample.get("sampling"),
                 "note": "라벨 프레임은 연속이 아니다. 번호판 자리가 회색으로 마스킹돼 있다"},
        "videos": videos,
    })
    _write(os.path.join(out_dir, "gt", "gt_persistence.json"), {
        "meta": {"gt_version": TRACK1_GT_VERSION, "tier": "AIHUB172", "stage": "persistence",
                 "coverage": {"videos": len(videos), "frames": n_frames,
                              "labeling": "전수 아님 — 프레임당 평균 1.01대. FP 는 셀 수 없다"}},
        "items": items,
    })
    return n_frames


def main(argv=None):
    ap = argparse.ArgumentParser(prog="eval.tools.build_private_aihub172")
    ap.add_argument("--source", required=True)
    ap.add_argument("--track", choices=["1", "2"], default="2")
    args = ap.parse_args(argv)
    try:
        out_dir = paths.manifest_dir(TRACK1_MANIFEST if args.track == "1" else MANIFEST)
    except OSError as e:
        print(f"실패: {e}", file=sys.stderr)
        return 2
    if os.path.exists(os.path.join(out_dir, "samples.json")):
        print(f"실패: {out_dir} 가 이미 있다. manifest 는 덮어쓰지 않는다.", file=sys.stderr)
        return 3
    n = (build_track1 if args.track == "1" else build)(args.source, out_dir)
    print(f"{out_dir} — 표본 {n}장")
    return 0


if __name__ == "__main__":
    sys.exit(main())
