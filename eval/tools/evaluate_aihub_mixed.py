"""Build and evaluate a small, explicitly synthetic AI-Hub-in-dashcam probe.

Eight Validation videos (two per type) are inserted into reviewed negative C2
clips at 20 seconds. A re-encoded background-only control is paired with each.
"""

import argparse
import datetime as dt
import json
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from daesingo.common import load_env_file
from daesingo.search import search_candidates
from eval import manifests_io, paths
from eval.gemini_preflight import PreparedClip, PreparedEval
from eval.runners.impls import search_pipeline


NAME = "aihub_mixed_pilot_mp2"
INSERT_AT = 20.0
BACKGROUND_END = 60.0
SOURCE = Path("D:/카테캠/데이터/AIHub_traffic_videos_best_100_each")
VIDEO_DIR = Path(paths.datasets_dir()) / "aihub_mixed_pilot"
MANIFEST_PATH = Path(paths.manifest_dir(NAME)) / "samples.json"
FILTER = "fps=10,scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2,setsar=1"


def _ffmpeg(args):
    result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-2000:])


def _duration(path):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)], text=True).strip())


def build(source=SOURCE):
    if MANIFEST_PATH.exists():
        raise FileExistsError(MANIFEST_PATH)
    selected = manifests_io.load_sequences("a_aihub_best100_val")["sequences"]
    by_type = defaultdict(list)
    for item in selected:
        by_type[item["violation_type"]].append(item)
    # Longer videos keep the injected interval visible at 2 fps; helmet clips
    # still last only about one second in this source collection.
    inserts = [item for label in sorted(by_type)
               for item in sorted(by_type[label], key=lambda x: -x["duration_sec"])[:2]]
    c2 = {item["clip_id"]: item for item in manifests_io.load_gt("ctier2", "candidate")["items"]}
    backgrounds = [item for item in manifests_io.load_clips("ctier2")["clips"]
                   if not c2[item["clip_id"]]["targets"]][:8]
    if len(inserts) != 8 or len(backgrounds) != 8:
        raise ValueError("expected eight injected videos and eight reviewed negative backgrounds")
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    samples = []
    for index, (insert, background) in enumerate(zip(inserts, backgrounds), 1):
        base_path = Path(paths.REPO_ROOT) / background["file_path"]
        insert_path = Path(source) / insert["file_path"]
        if manifests_io.sha256_file(base_path) != background["sha256"]:
            raise ValueError(f"background hash mismatch: {base_path}")
        if manifests_io.sha256_file(insert_path) != insert["sha256"]:
            raise ValueError(f"insert hash mismatch: {insert_path}")
        positive = VIDEO_DIR / f"mix_{index:02d}.mp4"
        control = VIDEO_DIR / f"control_{index:02d}.mp4"
        _ffmpeg(["-i", str(base_path), "-i", str(insert_path), "-filter_complex",
                 f"[0:v]trim=start=0:end={INSERT_AT},setpts=PTS-STARTPTS,{FILTER}[a];"
                 f"[1:v]setpts=PTS-STARTPTS,{FILTER}[b];"
                 f"[0:v]trim=start={INSERT_AT}:end={BACKGROUND_END},setpts=PTS-STARTPTS,{FILTER}[c];"
                 "[a][b][c]concat=n=3:v=1:a=0[out]",
                 "-map", "[out]", "-an", "-c:v", "libx264", "-preset", "veryfast",
                 "-crf", "26", str(positive)])
        _ffmpeg(["-i", str(base_path), "-t", str(BACKGROUND_END), "-vf", FILTER,
                 "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
                 str(control)])
        insert_end = INSERT_AT + insert["duration_sec"]
        for kind, path in (("injected", positive), ("control", control)):
            samples.append({"sample_id": f"{kind}_{index:02d}", "kind": kind,
                            "file_path": str(path.relative_to(Path(paths.REPO_ROOT))).replace("\\", "/"),
                            "sha256": manifests_io.sha256_file(path),
                            "duration_sec": _duration(path),
                            "background_id": background["clip_id"],
                            "insert_sequence_id": insert["sequence_id"] if kind == "injected" else None,
                            "label": insert["violation_type"] if kind == "injected" else "NONE",
                            "insert_start_sec": INSERT_AT if kind == "injected" else None,
                            "insert_end_sec": insert_end if kind == "injected" else None})
        print(f"built pair {index}/8", flush=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"meta": {"manifest_version": "mp2", "source": "synthetic",
                            "selection": "two longest Validation videos per class; first eight reviewed negative ctier2 clips",
                            "insert_at_sec": INSERT_AT, "background_end_sec": BACKGROUND_END,
                            "render": "H.264 CRF26, 640x360, 10fps, no audio; both arms re-encoded",
                            "note": "insertion boundary and source appearance may cue the model"},
                   "samples": samples}, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return samples


def _predict(service, sample):
    path = Path(paths.REPO_ROOT) / sample["file_path"]
    clip = PreparedClip(sample["sample_id"], path, sample["duration_sec"], sample["sha256"])
    try:
        result = search_candidates(search_pipeline._scope_for(clip), service=service)
        return {"sample_id": sample["sample_id"], "outcome": result.analysis_run.outcome.value,
                "issues": [issue.code for issue in result.analysis_run.issues],
                "candidates": [{"rank": c.rank,
                                "event_type": c.event_type_hint.value if c.event_type_hint else None,
                                "representative_sec": c.span.representative_ms / 1000,
                                "score": c.ranking_score}
                               for c in result.candidates]}
    except Exception as error:
        return {"sample_id": sample["sample_id"], "outcome": "ERROR",
                "issues": [type(error).__name__], "candidates": []}


def _predict_fine(service, sample):
    path = Path(paths.REPO_ROOT) / sample["file_path"]
    clip = PreparedClip(sample["sample_id"], path, sample["duration_sec"], sample["sha256"])
    try:
        record = search_pipeline._run_clip(service, clip)
        return {"sample_id": sample["sample_id"], "outcome": record["outcome"],
                "issues": record["issues"],
                "candidates": [{"rank": c["rank"], "event_type": c["event_type"],
                                "representative_sec": c["representative_sec"],
                                "score": c["score"], "verification": c["verification"],
                                "fine_error": c.get("fine_error")}
                               for c in record["candidates"]]}
    except Exception as error:
        return {"sample_id": sample["sample_id"], "outcome": "ERROR",
                "issues": [type(error).__name__], "candidates": []}


def evaluate(*, workers=4, run_id=None, fine=False, dataset=NAME, point="s3"):
    manifest_path = Path(paths.manifest_dir(dataset)) / "samples.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    samples = manifest["samples"]
    for sample in samples:
        path = Path(paths.REPO_ROOT) / sample["file_path"]
        if manifests_io.sha256_file(path) != sample["sha256"]:
            raise ValueError(f"hash mismatch: {path}")
    key = load_env_file().get("GEMINI_API_KEY", "").strip()
    if not key:
        raise ValueError("GEMINI_API_KEY is not set (.env)")
    clips = tuple(PreparedClip(s["sample_id"], Path(paths.REPO_ROOT) / s["file_path"],
                               s["duration_sec"], s["sha256"]) for s in samples)
    if point not in search_pipeline.POINTS:
        raise ValueError(f"unknown Search point: {point}")
    service = search_pipeline._build_service(PreparedEval(key, "openai", clips),
                                             search_pipeline.POINTS[point])
    run_id = run_id or dt.datetime.now().strftime("aihub_mixed_%Y%m%d_%H%M%S")
    destination = Path(paths.predictions_dir()) / f"{run_id}.json"
    if destination.exists():
        raise FileExistsError(destination)
    predictions = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        predict = _predict_fine if fine else _predict
        futures = {pool.submit(predict, service, s): s for s in samples}
        for future in as_completed(futures):
            pred = future.result()
            predictions.append(pred)
            print(f"{len(predictions)}/{len(samples)} {pred['sample_id']} {pred['outcome']}", flush=True)
    predictions.sort(key=lambda p: next(i for i,s in enumerate(samples) if s["sample_id"] == p["sample_id"]))
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"meta": {"run_id": run_id, "manifest": dataset,
                            "model": service.config.model, "point": point,
                            "config_version": service.config.version,
                            "fine": fine,
                            "created_at": dt.datetime.now().astimezone().isoformat()},
                   "predictions": predictions,
                   "usage_records": [r.as_eval_fact() for r in service.ledger.records()]},
                  stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    summary = score(samples, predictions, fine=fine, dataset=dataset)
    summary["meta"]["point"] = point
    result = Path(paths.results_dir()) / f"{run_id}.mixed{'-fine' if fine else ''}.json"
    with result.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(result)
    return summary


def score(samples, predictions, *, fine=False, dataset=NAME):
    by_id = {p["sample_id"]: p for p in predictions}
    details = []
    for s in samples:
        pred = by_id[s["sample_id"]]
        candidates = sorted(pred["candidates"], key=lambda c: c["rank"])[:3]
        inside = [c for c in candidates if s["kind"] == "injected" and
                  s["insert_start_sec"] <= c["representative_sec"] <= s["insert_end_sec"]]
        matched = [c for c in inside if c["event_type"] == s["label"]]
        observed = [c for c in candidates if c.get("verification") == "OBSERVED"]
        confirmed = [c for c in matched if c.get("verification") == "OBSERVED"]
        details.append({"sample_id": s["sample_id"], "kind": s["kind"],
                        "label": s["label"], "outcome": pred["outcome"],
                        "localized_top3": bool(inside), "typed_top3": bool(matched),
                        "confirmed_top3": bool(confirmed) if fine else None,
                        "n_observed_top3": len(observed) if fine else None,
                        "n_candidates_top3": len(candidates),
                        "n_outside_candidates_top3": len(candidates) - len(inside),
                        "top1_type": candidates[0]["event_type"] if candidates else "NONE"})
    injected = [d for d in details if d["kind"] == "injected"]
    controls = [d for d in details if d["kind"] == "control"]
    return {"meta": {"dataset": dataset,
                     "metric": "candidate representative inside entire inserted segment; type matches",
                     "top_k": 3, "fine": fine,
                     "note": "synthetic development diagnostic, not real long-dashcam performance"},
            "n_injected": len(injected), "n_controls": len(controls),
            "localized_top3": sum(d["localized_top3"] for d in injected),
            "typed_top3": sum(d["typed_top3"] for d in injected),
            "control_candidates_top3": sum(d["n_candidates_top3"] for d in controls),
            "control_clips_with_candidate": sum(d["n_candidates_top3"] > 0 for d in controls),
            "confirmed_top3": sum(d["confirmed_top3"] for d in injected) if fine else None,
            "control_observed_top3": sum(d["n_observed_top3"] for d in controls) if fine else None,
            "control_clips_with_observed": (sum(d["n_observed_top3"] > 0 for d in controls)
                                            if fine else None),
            "details": details}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build", "run"))
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--run-id")
    parser.add_argument("--fine", action="store_true")
    parser.add_argument("--dataset", default=NAME)
    parser.add_argument("--point", choices=tuple(search_pipeline.POINTS), default="s3")
    args = parser.parse_args()
    if args.command == "build":
        build(args.source)
    else:
        evaluate(workers=args.workers, run_id=args.run_id, fine=args.fine,
                 dataset=args.dataset, point=args.point)


if __name__ == "__main__":
    main()
