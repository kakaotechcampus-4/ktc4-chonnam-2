"""Evaluate video-level labels on the selected AI-Hub Validation videos.

The prediction is the top-ranked Coarse candidate's type. This measures the
Search pipeline's ability to return the right type from an entire positive
video; it is not a standalone classifier or a temporal-localization score.
"""

import argparse
import csv
import datetime as dt
import json
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from daesingo.common import load_env_file
from daesingo.search import search_candidates
from eval import manifests_io, paths
from eval.runners import normalize
from eval.runners.impls import search_pipeline
from eval.runners.errors import RunnerPreflightError


VALIDATION_MANIFEST = "a_aihub_best100_val"
ALL_MANIFEST = "a_aihub_best100_all"
SOURCE = Path("D:/카테캠/데이터/AIHub_traffic_videos_best_100_each")
TYPE_MAP = {
    "신호위반": "SIGNAL",
    "실선_차선변경": "SOLID_LINE_LANE_CHANGE",
    "오토바이_헬멧_미착용": "MOTORCYCLE_HELMET_NON_USE",
    "중앙선_침범": "CENTER_LINE_CROSSING",
}


def _write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def build_manifest(source=SOURCE, *, include_training=False):
    source = Path(source)
    with (source / "manifest.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 400 or Counter(row["category_folder"] for row in rows) != dict.fromkeys(TYPE_MAP, 100):
        raise ValueError("source manifest must contain exactly 100 videos for each of four types")
    old_ids = {
        item["sequence_id"]
        for name in ("a_aihub", "a_aihub_extra")
        for item in manifests_io.load_sequences(name)["sequences"]
    }
    chosen = (rows if include_training else
              [row for row in rows if row["source_split"] == "Validation"
               and row["sequence_id"] not in old_ids])
    expected = 400 if include_training else 117
    if len(chosen) != expected:
        raise ValueError(f"expected {expected} videos, got {len(chosen)}")
    sequences, truth = [], []
    for row in chosen:
        relative = f"{row['category_folder']}/{row['filename']}"
        video = source / relative
        if not video.is_file():
            raise FileNotFoundError(video)
        label = TYPE_MAP[row["category_folder"]]
        sequences.append({
            "sequence_id": row["sequence_id"], "violation_type": label,
            "sub_type": row["subtype"], "frame_count": int(row["frames"]),
            "duration_sec": float(row["duration_seconds"]), "playback_fps": 10,
            "file_path": relative, "source_split": row["source_split"],
            "method": row["method"], "sha256": manifests_io.sha256_file(video),
        })
        truth.append({"sequence_id": row["sequence_id"], "label": label,
                      "target_bbox": None, "target_frame": None,
                      "distractor_count": None, "source_tier": "A"})
    manifest = {"meta": {"manifest_version": "bm1", "tier": "A",
                         "source": "aihub_traffic_videos_best_100_each",
                         "sampling": {"rule_version": ("all-selected-v1" if include_training else
                                                       "validation-no-prior-sequences-v1"),
                                      "source_total": 400, "validation_total": 129,
                                      "prior_overlap_excluded": 0 if include_training else 12,
                                      "contains_training": include_training,
                                      "selected": len(chosen)}},
                "sequences": sequences}
    gt = {"meta": {"gt_version": "bg1", "tier": "A", "stage": "classification",
                   "coverage": {"sequences_total": len(truth), "label_source": "manifest.csv category_folder",
                                "target_bbox": "not provided", "negative_examples": 0}},
          "items": truth}
    directory = Path(paths.manifest_dir(ALL_MANIFEST if include_training else VALIDATION_MANIFEST))
    if directory.exists():
        raise FileExistsError(directory)
    _write_new(directory / "sequences.json", manifest)
    _write_new(directory / "gt" / "gt_classification.json", gt)
    return len(chosen)


def _classify(service, item, source):
    from eval.gemini_preflight import PreparedClip

    video = source / item["file_path"]
    clip = PreparedClip(item["sequence_id"], video, item["duration_sec"], item["sha256"])
    try:
        result = search_candidates(search_pipeline._scope_for(clip), service=service)
        ordered = sorted(result.candidates, key=lambda c: (-c.ranking_score, c.rank))
        top = ordered[0] if ordered else None
        return {"sequence_id": item["sequence_id"],
                "predicted": top.event_type_hint.value if top and top.event_type_hint else "NONE",
                "outcome": result.analysis_run.outcome.value,
                "issues": [issue.code for issue in result.analysis_run.issues],
                "candidates": [{"rank": c.rank, "event_type": c.event_type_hint.value
                                if c.event_type_hint else None, "score": c.ranking_score}
                               for c in ordered]}
    except Exception as error:
        return {"sequence_id": item["sequence_id"], "predicted": "NONE",
                "outcome": "ERROR", "issues": [type(error).__name__], "candidates": []}


def evaluate(source=SOURCE, *, manifest_name=VALIDATION_MANIFEST, limit=None, workers=4,
             run_id=None, point="s3"):
    from eval.gemini_preflight import PreparedClip, PreparedEval

    source = Path(source)
    manifest = manifests_io.load_sequences(manifest_name)
    items = manifest["sequences"][:limit]
    if not items:
        raise ValueError("no videos selected")
    key = load_env_file().get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RunnerPreflightError("GEMINI_API_KEY is not set (.env)")
    for item in items:
        video = source / item["file_path"]
        if manifests_io.sha256_file(video) != item["sha256"]:
            raise ValueError(f"{item['sequence_id']}: SHA-256 mismatch ({video})")
    if point not in search_pipeline.POINTS:
        raise ValueError(f"unknown Search point: {point}")
    clips = tuple(PreparedClip(item["sequence_id"], source / item["file_path"],
                               float(item["duration_sec"]), item["sha256"])
                  for item in items)
    prepared = PreparedEval(key, "openai", clips)
    service = search_pipeline._build_service(prepared, search_pipeline.POINTS[point])
    run_id = run_id or dt.datetime.now().strftime("aihub_best100_%Y%m%d_%H%M%S")
    destination = Path(paths.predictions_dir()) / f"{run_id}.json"
    if destination.exists():
        raise FileExistsError(destination)
    raw = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_classify, service, item, source): item for item in items}
        for future in as_completed(futures):
            item = future.result()
            raw.append(item)
            print(f"{len(raw)}/{len(items)} {item['sequence_id']} {item['predicted']} {item['outcome']}", flush=True)
    raw.sort(key=lambda x: next(i for i, item in enumerate(items)
                                if item["sequence_id"] == x["sequence_id"]))
    records = service.ledger.records()
    envelope = {
        "meta": {"run_id": run_id, "impl": f"search:{point}-coarse-top1",
                 "impl_version": "v1", "stage": "classification", "manifest": manifest_name,
                 "manifest_version": manifest["meta"]["manifest_version"],
                 "clip_rule_version": None, "normalizer_version": normalize.NORMALIZER_VERSION,
                 "code_commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                               cwd=paths.REPO_ROOT, capture_output=True,
                                               text=True, check=False).stdout.strip(),
                 "created_at": dt.datetime.now().astimezone().isoformat(),
                 "contract_version": None,
                 "processed_duration_sec": sum(float(i["duration_sec"]) for i in items)},
        "raw": raw, "normalized": normalize.normalize_classification(raw),
        "facts": {"prediction_rule": "top-ranked coarse candidate event_type; no candidate => NONE",
                  "model": service.config.model, "point": point,
                  "config_version": service.config.version,
                  "config_fingerprint": service.config.fingerprint,
                  "usage_records": [record.as_eval_fact() for record in records],
                  "scenarios": [item["sequence_id"] for item in items],
                  "partial_run": limit is not None,
                  "n_errors": sum(item["outcome"] == "ERROR" for item in raw)},
    }
    _write_new(destination, envelope)
    print(destination)
    return destination


def derive_validation_prediction(all_run_id, run_id):
    """Score the Validation subset from the *same* 400-video model run."""
    source_path = Path(paths.predictions_dir()) / f"{all_run_id}.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if source["meta"]["manifest"] != ALL_MANIFEST or source["facts"].get("partial_run"):
        raise ValueError("source must be a complete a_aihub_best100_all run")
    selected = manifests_io.load_sequences(VALIDATION_MANIFEST)["sequences"]
    by_id = {item["sequence_id"]: item for item in source["raw"]}
    if len(by_id) != 400 or any(item["sequence_id"] not in by_id for item in selected):
        raise ValueError("source predictions do not cover the Validation subset")
    ids = {item["sequence_id"] for item in selected}
    raw = [by_id[item["sequence_id"]] for item in selected]
    meta = {**source["meta"], "run_id": run_id, "manifest": VALIDATION_MANIFEST,
            "processed_duration_sec": sum(item["duration_sec"] for item in selected),
            "derived_from_run_id": all_run_id}
    facts = {**source["facts"],
             "usage_records": [record for record in source["facts"]["usage_records"]
                               if record["case_id"] in ids],
             "scenarios": [item["sequence_id"] for item in selected],
             "n_errors": sum(item["outcome"] == "ERROR" for item in raw)}
    destination = Path(paths.predictions_dir()) / f"{run_id}.json"
    _write_new(destination, {"meta": meta, "raw": raw,
                             "normalized": normalize.normalize_classification(raw),
                             "facts": facts})
    print(destination)
    return destination


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build", "run", "derive-val"))
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--run-id")
    parser.add_argument("--set", choices=("validation", "all"), default="validation")
    parser.add_argument("--point", choices=tuple(search_pipeline.POINTS), default="s3")
    parser.add_argument("--from-run-id")
    args = parser.parse_args()
    if args.command == "build":
        print(f"built {build_manifest(args.source, include_training=args.set == 'all')} videos")
    elif args.command == "run":
        evaluate(args.source, manifest_name=(ALL_MANIFEST if args.set == "all" else VALIDATION_MANIFEST),
                 limit=args.limit, workers=args.workers, run_id=args.run_id,
                 point=args.point)
    else:
        if not args.from_run_id or not args.run_id:
            parser.error("derive-val requires --from-run-id and --run-id")
        derive_validation_prediction(args.from_run_id, args.run_id)


if __name__ == "__main__":
    main()
