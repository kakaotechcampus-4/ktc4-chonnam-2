"""Build 100 synthetic AI-Hub insertions into distinct reviewed C2 dashcams.

This is a development diagnostic. Source videos are inserted as whole scenes;
their boundaries and appearance can give away the answer.
"""

import argparse
import json
import subprocess
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from eval import manifests_io, paths


NAME = "aihub_mixed_100_v1"
SOURCE = Path("D:/카테캠/데이터/AIHub_traffic_videos_best_100_each")
VIDEO_DIR = Path(paths.datasets_dir()) / NAME
MANIFEST = Path(paths.manifest_dir(NAME)) / "samples.json"
FILTER = "fps=10,scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2,setsar=1"
INSERT_TIMES = (10.0, 20.0, 30.0)


def _probe(path):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)], text=True).strip())


def _encode(args, output):
    temporary = output.with_name(output.stem + ".partial.mp4")
    result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                             *args, str(temporary)], capture_output=True, text=True)
    if result.returncode:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"{output}: {result.stderr[-2000:]}")
    temporary.replace(output)


def _choose():
    valid_ids = {s["sequence_id"] for s in
                 manifests_io.load_sequences("a_aihub_best100_val")["sequences"]}
    by_type = defaultdict(list)
    for item in manifests_io.load_sequences("a_aihub_best100_all")["sequences"]:
        by_type[item["violation_type"]].append(item)
    inserts = []
    for label in sorted(by_type):
        # Prefer nonoverlapping Validation; use Training only to fill a class.
        ranked = sorted(by_type[label], key=lambda s: (
            s["sequence_id"] not in valid_ids, -s["duration_sec"], s["sequence_id"]))
        inserts.extend(ranked[:25])
    gt = {item["clip_id"]: item for item in
          manifests_io.load_gt("ctier2", "candidate")["items"]}
    old = json.loads((Path(paths.manifest_dir("aihub_mixed_pilot_mp2")) / "samples.json")
                     .read_text(encoding="utf-8"))
    old_backgrounds = {s["background_id"] for s in old["samples"]}
    backgrounds = [item for item in manifests_io.load_clips("ctier2")["clips"]
                   if not gt[item["clip_id"]]["targets"]
                   and item["clip_id"] not in old_backgrounds][:100]
    if len(inserts) != 100 or len(backgrounds) != 100:
        raise ValueError("100 unique insert and background sources required")
    # Interleave classes, so a partial build remains balanced and useful to inspect.
    ordered = [inserts[25 * cls + n] for n in range(25) for cls in range(4)]
    return list(zip(ordered, backgrounds))


def _pair(index, insert, background, source):
    base_path = Path(paths.REPO_ROOT) / background["file_path"]
    insert_path = source / insert["file_path"]
    if manifests_io.sha256_file(base_path) != background["sha256"]:
        raise ValueError(f"background hash mismatch: {base_path}")
    if manifests_io.sha256_file(insert_path) != insert["sha256"]:
        raise ValueError(f"insert hash mismatch: {insert_path}")
    start = INSERT_TIMES[(index - 1) % len(INSERT_TIMES)]
    positive = VIDEO_DIR / f"injected_{index:03d}.mp4"
    control = VIDEO_DIR / f"control_{index:03d}.mp4"
    if not positive.exists():
        _encode(["-i", str(base_path), "-i", str(insert_path), "-filter_complex",
                 f"[0:v]trim=start=0:end={start},setpts=PTS-STARTPTS,{FILTER}[a];"
                 f"[1:v]setpts=PTS-STARTPTS,{FILTER}[b];"
                 f"[0:v]trim=start={start}:end=60,setpts=PTS-STARTPTS,{FILTER}[c];"
                 "[a][b][c]concat=n=3:v=1:a=0[out]",
                 "-map", "[out]", "-an", "-c:v", "libx264", "-preset", "veryfast",
                 "-crf", "26"], positive)
    if not control.exists():
        _encode(["-i", str(base_path), "-t", "60", "-vf", FILTER,
                 "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26"], control)
    samples = []
    for kind, path in (("injected", positive), ("control", control)):
        samples.append({
            "sample_id": f"{kind}_{index:03d}", "kind": kind,
            "file_path": str(path.relative_to(paths.REPO_ROOT)).replace("\\", "/"),
            "sha256": manifests_io.sha256_file(path), "duration_sec": _probe(path),
            "background_id": background["clip_id"],
            "insert_sequence_id": insert["sequence_id"] if kind == "injected" else None,
            "insert_source_split": insert["source_split"] if kind == "injected" else None,
            "label": insert["violation_type"] if kind == "injected" else "NONE",
            "insert_start_sec": start if kind == "injected" else None,
            "insert_end_sec": start + insert["duration_sec"] if kind == "injected" else None,
        })
    return samples


def build(source=SOURCE, workers=4):
    if MANIFEST.exists():
        raise FileExistsError(MANIFEST)
    if not source.is_dir():
        raise FileNotFoundError(source)
    pairs = _choose()
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    grouped = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_pair, i, insert, background, source): i
                   for i, (insert, background) in enumerate(pairs, 1)}
        for future in as_completed(futures):
            i = futures[future]
            grouped[i] = future.result()
            print(f"built {len(grouped)}/100 pairs", flush=True)
    samples = [item for i in range(1, 101) for item in grouped[i]]
    counts = Counter(s["insert_source_split"] for s in samples if s["kind"] == "injected")
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"meta": {"manifest_version": "mv1", "source": "synthetic",
                            "selection": "25 per type; Validation nonoverlap first, then Training; 100 distinct reviewed C2 negative backgrounds excluding 8 pilot backgrounds",
                            "source_split_counts": dict(counts),
                            "insert_at_sec_cycle": INSERT_TIMES,
                            "background_end_sec": 60.0,
                            "render": "H.264 CRF26, 640x360, 10fps, no audio; both arms re-encoded",
                            "note": "source scene and insertion boundary may cue the model; pseudo 10fps playback time"},
                   "samples": samples}, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(MANIFEST)
    return samples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    build(args.source, args.workers)


if __name__ == "__main__":
    main()
