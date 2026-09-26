"""기존 Recording Benchmark를 반복 실행해 덮어쓰지 않는 Baseline bundle을 만든다."""

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
from statistics import median
from uuid import uuid4


_spec = importlib.util.spec_from_file_location("recording_benchmark", Path(__file__).with_name("recording_benchmark.py"))
benchmark = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(benchmark)


class BaselineError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def statistics(values):
    return {"count": len(values), "min": min(values) if values else None,
            "median": median(values) if values else None, "max": max(values) if values else None}


def summarize(reports):
    """SKIPPED는 0초로 바꾸지 않고 제외하며, 실패 시간은 성공 시간과 별도로 요약한다."""
    stages = {}
    names = benchmark.SPLIT_STAGES if reports[0].get("schema_version") == "recording-benchmark/v2" else benchmark.STAGES
    for name in names:
        entries = [s for r in reports for s in r["stages"] if s["name"] == name]
        stages[name] = {
            "status_counts": dict(Counter(s["status"] for s in entries)),
            "elapsed_sec": statistics([s["elapsed_sec"] for s in entries
                                       if s["status"] in {"SUCCESS", "FALLBACK"}]),
            "failed_elapsed_sec": statistics([s["elapsed_sec"] for s in entries if s["status"] == "FAILED"]),
        }
    return {"status_counts": dict(Counter(r["status"] for r in reports)), "stages": stages,
            "total_elapsed_sec": statistics([r["total_elapsed_sec"] for r in reports]),
            "timing_policy": "stage_success_and_fallback_only; failed_separate; skipped_excluded"}


def _write_json(path, value):
    data = (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")
    # 새 bundle 내에서만 사용한다. 기존 파일은 절대 덮어쓰지 않는다.
    with path.open("xb") as stream:
        stream.write(data)
    return hashlib.sha256(data).hexdigest()


def _freeze_checks(reports, repeats):
    first = reports[0]
    return {
        "all_repeats_completed": len(reports) == repeats,
        "all_runs_usable": all(r["status"] in {"SUCCESS", "FALLBACK"} for r in reports),
        "original_unchanged": all(r["original_unchanged"] is True
                                  and r["input_before"] == r["input_after"] for r in reports),
        "same_fingerprint": first["input_before"] is not None and all(
            r["input_before"] == first["input_before"] for r in reports),
        "same_settings": bool(first["settings"]) and all(
            (r["schema_version"], r["settings"], r.get("requested_range"), r.get("requested_ranges"))
            == (first["schema_version"], first["settings"], first.get("requested_range"), first.get("requested_ranges"))
            for r in reports),
        "same_versions": set(first["tools"]) == {"python", "ffmpeg", "ffprobe"}
            and all(v != "unparsed" for v in first["tools"].values())
            and all(r["tools"] == first["tools"] for r in reports),
        "same_technical_metadata": first["results"].get("input") is not None and all(
            r["results"].get("input") == first["results"].get("input") for r in reports),
    }


def run_baseline(video, *, dataset_id, output, repeats, video_index, start_sec=None, end_sec=None, height=480,
                 analysis_start=None, analysis_end=None, incident_start=None, incident_end=None):
    """기존 단일 실행 결과는 수정하지 않는다. 생성된 bundle.json을 반환한다."""
    # 자유로운 설명·파일명·경로를 ID에 복사하지 못하도록 opaque UUID 표기만 받는다.
    if not isinstance(dataset_id, str) or re.fullmatch(r"ds_[0-9a-f]{32}", dataset_id) is None:
        raise BaselineError("INVALID_DATASET_ID")
    if (not isinstance(video, (str, os.PathLike)) or not str(video)
            or type(repeats) is not int or repeats < 1
            or type(video_index) is not int or video_index < 0
            or type(height) is not int or height <= 0 or height % 2):
        raise BaselineError("INVALID_INPUT")
    try:
        ranges = benchmark.requested_ranges(start_sec, end_sec, analysis_start, analysis_end, incident_start, incident_end)
    except ValueError:
        raise BaselineError("INVALID_INPUT") from None
    destination = Path(output)
    try:
        destination.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise BaselineError("OUTPUT_EXISTS") from None
    (destination / "runs").mkdir()
    reports, artifacts = [], []
    for index in range(1, repeats + 1):
        report = benchmark.run_benchmark(video, video_index=video_index, start_sec=start_sec,
                                         end_sec=end_sec, height=height, analysis_start=analysis_start,
                                         analysis_end=analysis_end, incident_start=incident_start, incident_end=incident_end)
        filename = f"runs/{index:04d}.json"
        digest = _write_json(destination / filename, report)
        reports.append(report)
        artifacts.append({"index": index, "file": filename, "sha256": digest, "status": report["status"]})
        # 원본 변경·조사 불가 시 추가 실행을 멈추되 이미 나온 보고서는 보존한다.
        if report["original_unchanged"] is not True:
            break
    first = reports[0]
    checks = _freeze_checks(reports, repeats)
    bundle = {
        "schema_version": "recording-baseline/v1", "bundle_id": f"baseline_{uuid4().hex}",
        "status": "FROZEN" if all(checks.values()) else "INCOMPLETE", "freeze_checks": checks,
        "dataset": {"dataset_id": dataset_id, "fingerprint": first["input_before"],
                    "technical_metadata": first["results"].get("input")},
        "execution": {"requested_repeats": repeats, "completed_repeats": len(reports),
                      "settings": first["settings"],
                      "service_lifetime": "fresh_per_run", "warmup_runs": 0},
        "tools": first["tools"], "runs": artifacts, "summary": summarize(reports),
    }
    if "shared" in ranges:
        bundle["execution"]["requested_range"] = first["requested_range"]
    else:
        bundle["schema_version"] = "recording-baseline/v2"
        bundle["execution"]["requested_ranges"] = first["requested_ranges"]
    # manifest는 마지막에 발행한다. 중단된 디렉터리를 FROZEN으로 취급하지 않는다.
    temporary = destination / "bundle.pending.json"
    _write_json(temporary, bundle)
    temporary.rename(destination / "bundle.json")
    return bundle


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", nargs="?", default=os.environ.get("DAESINGO_RECORDING_VIDEO"))
    parser.add_argument("--dataset-id", required=True, help="ds_ + UUID hex 형식의 익명 identity")
    parser.add_argument("--output", required=True, help="존재하지 않는 새 bundle 디렉터리")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--video-index", type=int, required=True)
    benchmark.add_range_arguments(parser)
    args = parser.parse_args(argv)
    try:
        bundle = run_baseline(args.video, dataset_id=args.dataset_id, output=args.output, repeats=args.repeats,
                              video_index=args.video_index, start_sec=args.start, end_sec=args.end,
                              analysis_start=args.analysis_start, analysis_end=args.analysis_end,
                              incident_start=args.incident_start, incident_end=args.incident_end)
    except Exception as error:
        print(json.dumps({"status": "FAILED", "failure": {"code": error.code if isinstance(error, BaselineError)
                                                           else "BUNDLE_WRITE_OR_RUN_FAILED"}}))
        return 1
    print(json.dumps(bundle, ensure_ascii=False, allow_nan=False, indent=2))
    return 0 if bundle["status"] == "FROZEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
