"""반복 실행 일관성 CLI.

    python -m eval.repeat --name gemini_v3_rep_20261002 \
        --predictions gemini_v3_rep_20261002_r1 ... gemini_v3_rep_20261002_r5

같은 설정으로 돌린 예측 여러 개를 묶어 사건별 적중 횟수를 낸다. 회차마다
예측은 eval.run 으로 따로 만든다 — 예측을 덮어쓰지 않는 규칙은 그대로다.
"""
import argparse
import json
import os
import sys

from eval import manifests_io, paths, score
from eval.scorers import consistency

# 이 값이 회차 사이에 다르면 「같은 testcase 반복」이 아니라 다른 실험이다.
_SAME_META = ("impl", "impl_version", "stage", "manifest", "manifest_version",
              "normalizer_version", "code_commit", "contract_version")
_SAME_FACTS = ("model", "prompt_fingerprint", "config_version", "config_fingerprint")


class NotComparable(Exception):
    pass


def _check_same(envs):
    diffs = []
    for key in _SAME_META:
        values = {json.dumps(e["meta"].get(key)) for e in envs}
        if len(values) > 1:
            diffs.append(f"meta.{key}")
    for key in _SAME_FACTS:
        values = {json.dumps((e.get("facts") or {}).get(key)) for e in envs}
        if len(values) > 1:
            diffs.append(f"facts.{key}")
    if diffs:
        raise NotComparable(f"회차 사이에 설정이 다르다: {', '.join(diffs)}")
    stage = envs[0]["meta"]["stage"]
    if stage != "candidate":
        raise NotComparable(f"반복 일관성은 지금 candidate stage 만 잰다 (stage={stage})")


def build_result(name, run_ids):
    envs = [score._load_prediction(r) for r in run_ids]
    _check_same(envs)
    meta = envs[0]["meta"]
    manifest = meta["manifest"]
    gt = manifests_io.load_gt(manifest, "candidate")
    private = paths.is_private(manifest)
    return {
        "meta": {
            "name": name,
            "impl": meta["impl"],
            "stage": meta["stage"],
            "manifest": manifest,
            "gt_version": (gt.get("meta") or {}).get("gt_version") or "nogt",
            "code_commit": meta["code_commit"],
            "consistency_scorer_version": consistency.SCORER_VERSION,
            "prediction_refs": [score._prediction_ref(r, private) for r in run_ids],
            # 실패한 클립은 「놓침」과 다르다. 회차별로 남겨 구분할 수 있게 한다.
            "n_not_succeeded_clips_by_run": [
                (e.get("facts") or {}).get("n_not_succeeded_clips") for e in envs],
        },
        "consistency": consistency.score([e["normalized"] for e in envs], gt),
    }


def result_filename(name, meta):
    return f"{name}.{meta['gt_version']}.{meta['consistency_scorer_version']}.json"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="eval.repeat")
    ap.add_argument("--name", required=True, help="묶음 결과 이름")
    ap.add_argument("--predictions", required=True, nargs="+", help="run_id 들")
    args = ap.parse_args(argv)

    if len(set(args.predictions)) != len(args.predictions):
        print("실패: 같은 run_id 가 두 번 들어왔다", file=sys.stderr)
        return 2
    if len(args.predictions) < 2:
        print("실패: 회차가 2개 이상이어야 일관성을 잴 수 있다", file=sys.stderr)
        return 2
    try:
        result = build_result(args.name, args.predictions)
    except OSError as e:
        print(f"실패: {e}", file=sys.stderr)
        return 2
    except NotComparable as e:
        print(f"실패: {e}", file=sys.stderr)
        return 4
    outdir = (paths.private_results_dir() if paths.is_private(result["meta"]["manifest"])
              else paths.results_dir())
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, result_filename(args.name, result["meta"]))
    if os.path.exists(out):
        print(f"실패: {out} 가 이미 있다. 채점 결과는 덮어쓰지 않는다.",
              file=sys.stderr)
        return 3
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
