"""경로 해석. 다른 모듈은 경로를 직접 조립하지 않는다."""
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_ROOT = os.path.join(REPO_ROOT, "eval")


def manifest_dir(name):
    """tier 단위 manifest 폴더. 예: 'b_youtube', 'a_aihub'."""
    return os.path.join(EVAL_ROOT, "manifests", name)


def predictions_dir():
    return os.path.join(EVAL_ROOT, "predictions")


def results_dir():
    return os.path.join(EVAL_ROOT, "results")


def datasets_dir():
    return os.path.join(EVAL_ROOT, "datasets")
