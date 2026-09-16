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
from eval.scorers import candidate, classification, cost, plate


def _load_prediction(run_id):
    with open(os.path.join(paths.predictions_dir(), run_id + ".json"), encoding="utf-8") as f:
        return json.load(f)


def _prediction_ref(run_id):
    path = os.path.join(paths.predictions_dir(), run_id + ".json")
    return {"path": os.path.relpath(path, paths.REPO_ROOT).replace("\\", "/"),
            "sha256": manifests_io.sha256_file(path)}


class ContractMismatch(Exception):
    pass


# stage 가 실제로 돌린 scorer 의 버전. candidate.SCORER_VERSION 을 모든
# stage 에 무조건 쓰면 plate 결과가 candidate 지표 정의("IoU -> onset point
# error")를 자기 것인 양 적어 낸다 (FIX5).
_SCORER_VERSIONS = {
    "candidate": candidate.SCORER_VERSION,
    "classification": classification.SCORER_VERSION,
    "plate": plate.SCORER_VERSION,
}


def _load_gt(manifest, stage):
    """GT 를 읽는다. plate 는 정답지가 없어도 None 으로 계속 진행한다.

    plate.score 는 gt=None 을 이미 다룬다(NO_GT). A tier 처럼 plate 정답지가
    없는 manifest 로 --stage plate 를 돌리면 FileNotFoundError 로 죽이지
    않는다 — 크래시 대신 결과 파일이 「이 manifest 엔 plate 정답지가 없다」를
    말하는 쪽이 더 쓸모 있다. candidate·classification 은 gt=None 을 다루지
    않으므로(가정이 다르다) 여기서 다른 stage 의 동작은 바꾸지 않는다.
    """
    if stage == "plate":
        try:
            return manifests_io.load_gt(manifest, stage)
        except OSError:
            return None
    return manifests_io.load_gt(manifest, stage)


def build_result(env):
    stage = env["meta"]["stage"]
    manifest = env["meta"]["manifest"]
    gt = _load_gt(manifest, stage)
    norm = env["normalized"]

    gt_contract = (gt or {}).get("meta", {}).get("contract_version")
    env_contract = env["meta"].get("contract_version")
    if gt_contract and env_contract and gt_contract != env_contract:
        raise ContractMismatch(
            "계약 버전이 다르면 비교하지 않는다 (v4 §9-2 규칙 5): "
            "정답지=%s · 예측=%s" % (gt_contract, env_contract))

    result = {
        "meta": {
            "run_id": env["meta"]["run_id"],
            "impl": env["meta"]["impl"],
            "stage": stage,
            "manifest": manifest,
            "gt_version": (gt or {}).get("meta", {}).get("gt_version") or "nogt",
            "normalizer_version": env["meta"]["normalizer_version"],
            "code_commit": env["meta"]["code_commit"],
            "scorer_version": _SCORER_VERSIONS.get(stage, candidate.SCORER_VERSION),
            "prediction_ref": _prediction_ref(env["meta"]["run_id"]),
        },
        "candidate": None,
        "classification": None,
        "plate": None,
        "cost": cost.score(
            (env.get("facts") or {}).get("usage_records", []),
            env["meta"].get("processed_duration_sec"),
            (env.get("facts") or {}).get("scenarios", []),
        ),
    }
    if stage == "candidate":
        result["candidate"] = candidate.score(norm, gt)
        result["classification"] = classification.not_run(
            "NOT_RUN — stage=candidate 실행이다")
        result["plate"] = plate.not_run("NOT_RUN — stage=candidate 실행이다")
    elif stage == "classification":
        result["classification"] = classification.score(norm, gt)
        result["candidate"] = candidate.not_run("NOT_RUN — stage=classification 실행이다")
        result["plate"] = plate.not_run("NOT_RUN — stage=classification 실행이다")
    elif stage == "plate":
        result["plate"] = plate.score(norm, gt)
        result["candidate"] = candidate.not_run("NOT_RUN — stage=plate 실행이다")
        result["classification"] = classification.not_run("NOT_RUN — stage=plate 실행이다")
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
    except ContractMismatch as e:
        print("실패: %s" % e, file=sys.stderr)
        return 4
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
