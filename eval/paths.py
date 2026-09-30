"""경로 해석. 다른 모듈은 경로를 직접 조립하지 않는다."""
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_ROOT = os.path.join(REPO_ROOT, "eval")


PRIVATE_PREFIX = "private_"


def is_private(name):
    """차량번호처럼 공개 레포에 둘 수 없는 정답·예측을 가진 manifest 인가.

    이름이 `private_` 로 시작하면 manifest·prediction·result 가 전부 레포 밖
    (`.env` 의 DAESINGO_EVAL_PRIVATE_ROOT)에 산다. 레포에는 집계 수치만 남긴다.
    """
    return name.startswith(PRIVATE_PREFIX)


def private_root():
    from daesingo.common import load_env_file

    root = load_env_file().get("DAESINGO_EVAL_PRIVATE_ROOT", "").strip()
    if not root:
        raise OSError("DAESINGO_EVAL_PRIVATE_ROOT is not set (.env) — "
                      "private_ manifest 는 레포 밖에만 둔다")
    return root


def manifest_dir(name):
    """tier 단위 manifest 폴더. 예: 'b_youtube', 'a_aihub'."""
    if is_private(name):
        return os.path.join(private_root(), "manifests", name)
    return os.path.join(EVAL_ROOT, "manifests", name)


def predictions_dir():
    return os.path.join(EVAL_ROOT, "predictions")


def results_dir():
    return os.path.join(EVAL_ROOT, "results")


def private_predictions_dir():
    return os.path.join(private_root(), "predictions")


def private_results_dir():
    return os.path.join(private_root(), "results")


def datasets_dir():
    return os.path.join(EVAL_ROOT, "datasets")
