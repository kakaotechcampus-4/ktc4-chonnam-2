"""scorer CLI.

    python -m eval.score --prediction run_20260906_001

prediction 을 읽어 stage 에 맞는 scorer 를 돌리고 results 를 쓴다.
데이터가 없는 stage 는 null + 사유로 채운다.
"""
import argparse
import json
import os
import sys

from eval import manifests_io, paths
from eval.scorers import candidate, classification, plate


def _load_prediction(run_id):
    with open(os.path.join(paths.predictions_dir(), run_id + ".json"), encoding="utf-8") as f:
        return json.load(f)


def build_result(env):
    stage = env["meta"]["stage"]
    manifest = env["meta"]["manifest"]
    gt = manifests_io.load_gt(manifest, stage)
    norm = env["normalized"]

    result = {
        "meta": {
            "run_id": env["meta"]["run_id"],
            "impl": env["meta"]["impl"],
            "stage": stage,
            "manifest": manifest,
            "gt_version": gt["meta"]["gt_version"],
            "normalizer_version": env["meta"]["normalizer_version"],
            "code_commit": env["meta"]["code_commit"],
        },
        "candidate": None,
        "classification": None,
        "plate": plate.score(norm, None),
    }
    if stage == "candidate":
        result["candidate"] = candidate.score(norm, gt)
        result["classification"] = classification.not_run(
            "NOT_RUN — stage=candidate 실행이다")
    elif stage == "classification":
        result["classification"] = classification.score(norm, gt)
        result["candidate"] = candidate.not_run("NOT_RUN — stage=classification 실행이다")
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(prog="eval.score")
    ap.add_argument("--prediction", required=True, help="run_id")
    args = ap.parse_args(argv)

    try:
        env = _load_prediction(args.prediction)
        result = build_result(env)
    except OSError as e:
        print("실패: %s" % e, file=sys.stderr)
        return 2
    outdir = paths.results_dir()
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, "%s.%s.json" % (args.prediction, result["meta"]["gt_version"]))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
