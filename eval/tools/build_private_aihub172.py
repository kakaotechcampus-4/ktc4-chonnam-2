"""AI-Hub 172 번호판 crop 표본 → private manifest `private_aihub172_plate`.

    python -m eval.tools.build_private_aihub172 --source D:/카테캠/데이터/_derived/aihub172/track2_recognition

입력은 `데이터셋 생성/scripts/aihub172.py sample` 의 산출물이다(manifest.json ·
gt_plate.LOCAL_ONLY.json · crops/). 출력은 전부 `.env` 의 DAESINGO_EVAL_PRIVATE_ROOT
아래다 — 정답지와 crop 에 실제 차량번호가 있어 공개 레포에 둘 수 없다.

**legibility 는 전부 READABLE 이다.** AI-Hub 가 모든 crop 에 value 문자열을 달았고,
판독불가 라벨은 원천에 없다. 그래서 wrong_accept_rate · abstention_recall 은 분모가
0 이라 null 이 된다 — 성능이 좋아서가 아니다.
"""
import argparse
import json
import os
import shutil
import sys

from eval import paths

MANIFEST = "private_aihub172_plate"
MANIFEST_VERSION = "m1"
GT_VERSION = "ap1"
CONTRACT_VERSION = "plate-readout/v1.3"


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


def main(argv=None):
    ap = argparse.ArgumentParser(prog="eval.tools.build_private_aihub172")
    ap.add_argument("--source", required=True)
    args = ap.parse_args(argv)
    try:
        out_dir = paths.manifest_dir(MANIFEST)
    except OSError as e:
        print(f"실패: {e}", file=sys.stderr)
        return 2
    if os.path.exists(os.path.join(out_dir, "samples.json")):
        print(f"실패: {out_dir} 가 이미 있다. manifest 는 덮어쓰지 않는다.", file=sys.stderr)
        return 3
    n = build(args.source, out_dir)
    print(f"{out_dir} — 표본 {n}장")
    return 0


if __name__ == "__main__":
    sys.exit(main())
