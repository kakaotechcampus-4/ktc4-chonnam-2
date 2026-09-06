"""AI-Hub A tier 아카이브에서 평가용 시퀀스를 뽑는다.

51.4GB 아카이브를 풀지 않는다. 라벨 zip 만 읽어 GT 를 만들고,
이미지는 필요할 때 sequence 의 archive_path 로 꺼낸다.

샘플링 규칙은 GT 의 일부다 — seed 와 rule_version 을 meta 에 남긴다.
"""
import argparse
import collections
import json
import os
import random
import sys
import zipfile

from eval import paths

RULE_VERSION = "s1"

TYPE_MAP = {
    "신호위반": "SIGNAL",
    "중앙선침범": "CENTER_LINE_CROSSING",
    "진로변경위반": "SOLID_LINE_LANE_CHANGE",
    "안전모미착용": "MOTORCYCLE_HELMET_NON_USE",
}

# 위반 차량 bbox 를 가진 객체 이름. 확인된 목록 그대로다.
TARGET_OBJECTS = (
    "신호 위반 차량(이륜차 포함)",
    "중앙선침범 위반 차량(이륜차 포함)",
    "진로변경 위반 차량(이륜차 포함)",
    "안전모 미착용 이륜차",
)
NORMAL_OBJECT_PREFIX = "정상 차량"


def _index(zf):
    """{(top, sub, sequence_id): [entry, ...]}"""
    idx = collections.defaultdict(list)
    for name in zf.namelist():
        if not name.endswith(".json"):
            continue
        parts = name.split("/")
        if len(parts) < 4:
            continue
        idx[(parts[0], parts[1], parts[2])].append(name)
    return idx


def sample(zip_path, per_type, seed):
    zf = zipfile.ZipFile(zip_path)
    idx = _index(zf)

    by_type = collections.defaultdict(list)
    for key in sorted(idx):
        top = key[0]
        if top in TYPE_MAP:
            by_type[TYPE_MAP[top]].append(key)

    rng = random.Random(seed)
    sequences = []
    gt_items = []
    for vtype in sorted(by_type):
        keys = sorted(by_type[vtype])
        picked = rng.sample(keys, min(per_type, len(keys)))
        for top, sub, seq_id in sorted(picked):
            frames = sorted(idx[(top, sub, seq_id)])
            first = json.loads(zf.read(frames[0]).decode("utf-8"))
            cond = first.get("condition", {})

            target_bbox = None
            target_frame = None
            distractors = 0
            for fname in frames:
                d = json.loads(zf.read(fname).decode("utf-8"))
                anns = d["Annotation"]["annotations"]
                for a in anns:
                    if a["Object Name"] in TARGET_OBJECTS and "Bbox Cordinate" in a:
                        if target_bbox is None:
                            target_bbox = a["Bbox Cordinate"]
                            target_frame = os.path.basename(fname).replace(".json", ".jpg")
                if target_bbox is not None:
                    distractors = sum(
                        1 for a in anns if a["Object Name"].startswith(NORMAL_OBJECT_PREFIX)
                    )
                    break

            sequences.append({
                "sequence_id": seq_id,
                "violation_type": vtype,
                "sub_type": sub,
                "frame_count": len(frames),
                "condition": {
                    "weather": cond.get("Weather"),
                    "day_night": cond.get("DayNights"),
                    "road_type": cond.get("roadType"),
                },
                "archive": os.path.basename(zip_path).replace("VL", "VS"),
                "archive_path": "%s/%s/%s" % (top, sub, seq_id),
                "split": "DEV",
            })
            gt_items.append({
                "sequence_id": seq_id,
                "label": vtype,
                "target_bbox": target_bbox,
                "target_frame": target_frame,
                "distractor_count": distractors,
                # scorer 는 (normalized, gt) 두 개만 받는다. 조건별 지표를
                # 내려면 GT 가 자족적이어야 하므로 sequences 와 같은 값을
                # 여기에도 싣는다 (Task 8 classification.score 가 읽는다).
                "condition": {
                    "weather": cond.get("Weather"),
                    "day_night": cond.get("DayNights"),
                    "road_type": cond.get("roadType"),
                },
                "source_tier": "A",
            })

    seqs = {
        "meta": {
            "manifest_version": "m1",
            "tier": "A",
            "source": "aihub",
            "sampling": {
                "rule_version": RULE_VERSION,
                "seed": seed,
                "per_type": per_type,
                "strategy": "type-stratified, sequence-level",
            },
        },
        "sequences": sequences,
    }
    gt = {
        "meta": {"gt_version": "g1", "tier": "A", "stage": "classification",
                 "coverage": {"sequences_total": len(gt_items),
                              "sampling_rule_version": RULE_VERSION,
                              "sampling_seed": seed}},
        "items": gt_items,
    }
    return seqs, gt


def main(argv=None):
    ap = argparse.ArgumentParser(prog="eval.tools.sample_aihub")
    ap.add_argument("--zip", default=os.path.join(
        paths.REPO_ROOT, "eval", "manifests", "02.라벨링데이터", "VL.zip"))
    ap.add_argument("--per-type", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260906)
    args = ap.parse_args(argv)

    if not os.path.exists(args.zip):
        print("실패: %s 가 없다" % args.zip, file=sys.stderr)
        return 2

    seqs, gt = sample(args.zip, args.per_type, args.seed)
    outdir = paths.manifest_dir("a_aihub")
    os.makedirs(os.path.join(outdir, "gt"), exist_ok=True)
    with open(os.path.join(outdir, "sequences.json"), "w", encoding="utf-8") as f:
        json.dump(seqs, f, ensure_ascii=False, indent=2)
    with open(os.path.join(outdir, "gt", "gt_classification.json"), "w", encoding="utf-8") as f:
        json.dump(gt, f, ensure_ascii=False, indent=2)
    print("시퀀스 %d개 / GT %d건" % (len(seqs["sequences"]), len(gt["items"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
