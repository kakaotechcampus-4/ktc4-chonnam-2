"""A tier 시퀀스 + B tier negative 클립을 한 manifest 로 잇는다 (F12).

5×5 confusion 의 `NONE` 행·열은 A tier 만으로는 채울 수 없다 — AI-Hub 시퀀스는
전부 4종 중 하나여서 「아무 위반도 아닌 것」이 없다. `NONE` 은 B tier 의
「사람이 검토해서 사건 없음을 확인한」 클립에서 온다 (harness-v1-design.md §4-2).

**항목마다 `source_tier` 를 남긴다.** A tier 는 AI-Hub 원본 프레임, B tier 는
YouTube 재인코딩 영상이라 해상도·압축 특성이 다르다. 그 차이를 지운 채
한 숫자로 뭉치면 결과가 거짓말을 하게 된다.

**두 tier 의 항목은 모양이 다르다.** A tier 는 정지 프레임 열이고 B tier 는
60초 영상이다. `sequences.json` 이라는 한 이름으로 묶지만 같은 것이 아니며,
필드를 억지로 맞추지 않는다 — B tier 항목에는 `condition`·`target_bbox` 가
없고 `null` 로 남는다. 없는 라벨을 지어내는 것보다 낫다.

실행:

    python -m eval.tools.build_ab_mixed --n-none 30 --seed 20260916
"""
import argparse
import json
import os
import random

from eval import manifests_io, paths

MANIFEST_NAME = "ab_mixed"
MANIFEST_VERSION = "am1"
GT_VERSION = "ag1"
SAMPLING_RULE_VERSION = "abs2"   # 2026-09-16 random() 스트림만 쓰는 선택으로 교체


def _negative_clip_ids(b_gt):
    """검토를 마친 negative 클립만. not_applicable 은 negative 가 아니다."""
    return sorted(
        item["clip_id"] for item in b_gt["items"]
        if not item.get("not_applicable") and not item["targets"]
    )


def build(a_sequences, a_gt, b_clips, b_gt, n_none, seed):
    """섞인 manifest 와 정답지를 만든다. 반환은 (sequences, gt)."""
    cov = b_gt["meta"].get("coverage") or {}
    if cov.get("clips_reviewed", 0) < cov.get("clips_total", 0) \
            or not cov.get("negatives_confirmed"):
        raise ValueError(
            "B tier 정답지의 검토가 끝나지 않았다 — 「사건 없음」을 NONE 정답으로 "
            "쓸 수 없다 (clips_reviewed=%s / clips_total=%s / negatives_confirmed=%s)"
            % (cov.get("clips_reviewed"), cov.get("clips_total"),
               cov.get("negatives_confirmed")))

    available = _negative_clip_ids(b_gt)
    if n_none > len(available):
        raise ValueError(
            "negative 클립이 %d개뿐인데 %d개를 요청했다. 분모를 조용히 줄이지 않는다."
            % (len(available), n_none))
    # random.sample 을 쓰지 않는다. CPython 이 버전 간 보장하는 것은 random()
    # 스트림뿐이고 sample() 의 알고리즘은 구현 세부다 — 파이썬을 올리면
    # 뽑히는 클립이 조용히 달라질 수 있고, 그러면 「샘플링이 GT 의 일부다」가
    # 거짓이 된다. 정렬된 후보에 난수 키를 붙여 정렬하는 방식은 random()
    # 만으로 선다.
    rng = random.Random(seed)
    keyed = sorted((rng.random(), clip_id) for clip_id in available)
    picked = sorted(clip_id for _, clip_id in keyed[:n_none])

    clip_by_id = {c["clip_id"]: c for c in b_clips["clips"]}

    sequences = [dict(s, source_tier="A") for s in a_sequences["sequences"]]
    items = [dict(i, source_tier="A") for i in a_gt["items"]]

    for clip_id in picked:
        c = clip_by_id[clip_id]
        sequences.append({
            "sequence_id": clip_id,
            "source_tier": "B",
            "violation_type": None,
            "source_video_id": c.get("source_video_id"),
            "duration_sec": c.get("duration_sec"),
            "file_path": c.get("file_path"),
            "sha256": c.get("sha256"),
            "split": c.get("split"),
        })
        items.append({
            "sequence_id": clip_id,
            "label": "NONE",
            # B tier 에는 이 라벨들이 없다. 지어내지 않는다.
            "target_bbox": None,
            "target_frame": None,
            "distractor_count": None,
            "condition": None,
            "source_tier": "B",
        })

    seq_ids = [s["sequence_id"] for s in sequences]
    if len(seq_ids) != len(set(seq_ids)):
        raise ValueError("sequence_id 가 두 tier 사이에서 겹친다")

    meta_seq = {
        "manifest_version": MANIFEST_VERSION,
        "tier": "AB",
        "source": "aihub+youtube",
        "composition": {
            "a_aihub": a_sequences["meta"].get("manifest_version"),
            "b_youtube": b_clips["meta"].get("manifest_version"),
        },
    }
    meta_gt = {
        "gt_version": GT_VERSION,
        "tier": "AB",
        "stage": "classification",
        "coverage": {
            "sequences_total": len(items),
            "a_tier_sequences": len(a_gt["items"]),
            "b_tier_negative_clips": len(picked),
            "negatives_available": len(available),
            "sampling": {
                "rule_version": SAMPLING_RULE_VERSION,
                "seed": seed,
                "strategy": "B tier 의 검토 완료 negative 클립에서 단순 무작위 추출",
            },
            "source_gt_versions": {
                "a_aihub": a_gt["meta"].get("gt_version"),
                "b_youtube": b_gt["meta"].get("gt_version"),
            },
            "note": ("A tier 는 AI-Hub 원본 프레임, B tier 는 YouTube 재인코딩 "
                     "영상이다. source_tier 로 구분해 읽는다."),
        },
    }
    return {"meta": meta_seq, "sequences": sequences}, {"meta": meta_gt, "items": items}


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(prog="eval.tools.build_ab_mixed")
    ap.add_argument("--n-none", type=int, default=30,
                    help="NONE 으로 들여올 B tier negative 클립 수 (기본 30 — A tier 유형별 수와 맞춘다)")
    ap.add_argument("--seed", type=int, default=20260916)
    args = ap.parse_args(argv)

    sequences, gt = build(
        manifests_io.load_sequences("a_aihub"),
        manifests_io.load_gt("a_aihub", "classification"),
        manifests_io.load_clips("b_youtube"),
        manifests_io.load_gt("b_youtube", "candidate"),
        n_none=args.n_none, seed=args.seed,
    )
    out = paths.manifest_dir(MANIFEST_NAME)
    print(_write(os.path.join(out, "sequences.json"), sequences))
    print(_write(os.path.join(out, "gt", "gt_classification.json"), gt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
