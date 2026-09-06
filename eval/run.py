"""runner CLI.

    python -m eval.run --impl fake:always_correct --manifest b_youtube --stage candidate

prediction 은 immutable 이다. 같은 run_id 로 덮어쓰지 않는다.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

from eval import manifests_io, paths
from eval.runners import normalize, registry

_NORMALIZERS = {
    "candidate": normalize.normalize_candidate,
    "classification": normalize.normalize_classification,
}


def _git_commit():
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=paths.REPO_ROOT, capture_output=True, text=True)
        return out.stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def _new_run_id():
    return "run_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def build_envelope(impl_name, manifest, stage, run_id):
    impl = registry.get(impl_name)
    scope = {"manifest": manifest, "stage": stage}
    raw = impl(scope)
    normalized = _NORMALIZERS[stage](raw)
    manifest_meta = manifests_io.load_manifest_meta(manifest)
    # 버전은 impl 코드와 함께 움직여야 하므로 runner 가 값을 정하지 않고
    # impl 이 속한 모듈에서 읽는다 (없으면 "v1"으로 취급한다).
    impl_module = sys.modules[impl.__module__]
    impl_version = getattr(impl_module, "IMPL_VERSION", "v1")
    return {
        "meta": {
            "run_id": run_id,
            "impl": impl_name,
            "impl_version": impl_version,
            "stage": stage,
            "manifest": manifest,
            "manifest_version": manifest_meta.get("manifest_version"),
            # A tier 시퀀스 manifest 에는 clip 개념이 없어 null 이 된다.
            "clip_rule_version": manifest_meta.get("clip_rule_version"),
            "normalizer_version": normalize.NORMALIZER_VERSION,
            "code_commit": _git_commit(),
            "created_at": datetime.datetime.now().astimezone().isoformat(),
        },
        "raw": raw,
        "normalized": normalized,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(prog="eval.run")
    ap.add_argument("--impl", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--stage", required=True, choices=sorted(_NORMALIZERS))
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args(argv)

    run_id = args.run_id or _new_run_id()
    # 이름표 확인만 여기서 감싼다. build_envelope 전체를 except KeyError 로
    # 감싸면 impl 내부의 KeyError 가 「알 수 없는 impl」로 둔갑해 진짜 버그가
    # 숨는다 (classification stage 미구현이 그렇게 숨어 있었다).
    try:
        registry.get(args.impl)
    except KeyError as e:
        print("실패: %s" % e, file=sys.stderr)
        return 2
    env = build_envelope(args.impl, args.manifest, args.stage, run_id)

    outdir = paths.predictions_dir()
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, run_id + ".json")
    if os.path.exists(out):
        print("실패: %s 가 이미 있다. prediction 은 덮어쓰지 않는다." % out, file=sys.stderr)
        return 3
    with open(out, "w", encoding="utf-8") as f:
        json.dump(env, f, ensure_ascii=False, indent=2)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
