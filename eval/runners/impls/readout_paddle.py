"""readout:paddle-crop — 번호판 crop 이미지를 readout 공개 함수 `read_plate`로 판독한다.

crop 한 장을 「프레임 한 장짜리 사건 클립」으로 공급한다. `PaddleOcrProvider`는
`frames(clip_ref)`만 있는 공급자를 받으므로(`case/real_e2e.py`와 같은 경로) 판정
(consensus·abstain·association)은 제품과 같은 코드가 한다. 프레임이 한 장이라
consensus 는 항상 `SINGLE_FRAME`이다 — 같은 crop 을 두 번 넣어 합의를 지어내지 않는다.

**crop 입력이라 검출 단계가 빠져 있다.** 이 impl 이 재는 것은 인식(recognition)이다.

`private_` manifest 전용이다. 정답·예측에 실제 차량번호가 들어가므로 manifest·crop·
prediction 이 전부 `DAESINGO_EVAL_PRIVATE_ROOT` 아래에 있다(`eval/paths.py`).
"""
import hashlib
import json
import os
from importlib.metadata import PackageNotFoundError, version

from daesingo.readout import (
    InputRef,
    ProviderError,
    ReadRequest,
    paddle_provider,
    read_plate,
)
from eval import paths
from eval.runners.errors import RunnerPreflightError

IMPL_VERSION = "v1"
CONTRACT_VERSION = "plate-readout/v1.3"
SOURCE_PROFILE = "readout-native"
PROVENANCE = "SOURCE_DERIVED_INCIDENT_CLIP"
_last_facts = {}


class CropFrameSource:
    """`PaddleOcrProvider`가 기대하는 `frames(clip_ref)` 모양. crop 한 장 = 프레임 한 장."""

    def __init__(self, paths_by_ref):
        self._paths = dict(paths_by_ref)

    def frames(self, clip_ref):
        import cv2
        import numpy as np

        path = self._paths.get(clip_ref)
        if path is None:
            raise ProviderError("INFRA", "READOUT_FRAME_ACCESS_FAILED",
                                f"crop 이 없다: {clip_ref!r}")
        # cv2.imread 는 Windows 에서 비ASCII 경로를 못 연다.
        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ProviderError("INFRA", "READOUT_FRAME_ACCESS_FAILED",
                                f"crop 을 decode 하지 못했다: {clip_ref!r}")
        return [paddle_provider.SourceFrame(frame_ref="crop_" + clip_ref, offset_sec=0.0,
                                            image=image)]


def _sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _prepare(scope):
    problems = []
    manifest = scope.get("manifest", "")
    if not paths.is_private(manifest):
        problems.append("readout:paddle-crop 은 private_ manifest 만 받는다 (차량번호)")
    if scope.get("stage") != "plate":
        problems.append("readout:paddle-crop 은 stage=plate 만 지원한다")
    try:
        paddle_version = version("paddleocr")
    except PackageNotFoundError:
        paddle_version = None
        problems.append("paddleocr 가 없다 — readout-paddle extra 를 sync 할 것")
    samples = []
    if not problems:
        try:
            base = paths.manifest_dir(manifest)
            # 표본 목록만 읽는다. 정답지(gt/)는 impl 이 보지 않는다.
            with open(os.path.join(base, "samples.json"), encoding="utf-8") as f:
                samples = json.load(f)["samples"]
        except OSError as e:
            problems.append(str(e))
    by_ref = {}
    for s in samples:
        path = os.path.join(base, s["file_path"])
        if not os.path.isfile(path):
            problems.append(f"{s['sample_id']}: crop 이 없다")
        elif _sha256(path) != s["sha256"]:
            problems.append(f"{s['sample_id']}: sha256 불일치")
        else:
            by_ref[s["sample_id"]] = path
    if problems:
        raise RunnerPreflightError("readout 평가 사전 점검 실패:\n" + "\n".join(
            "- " + p for p in problems[:30]))
    return by_ref, paddle_version


def run(scope):
    by_ref, paddle_version = _prepare(scope)
    provider = paddle_provider.PaddleOcrProvider(CropFrameSource(by_ref))
    raw, failed = [], []
    for sample_id in sorted(by_ref):
        request = ReadRequest(case_id="eval", candidate_id=sample_id,
                              input_ref=InputRef(sample_id, SOURCE_PROFILE, PROVENANCE))
        readout_run, plate = read_plate(request, provider=provider)
        if plate is None:
            # 완전 실패는 PlateReadout 이 없어 채점 대상에서 빠진다 — 여기 남긴다.
            failure = readout_run.failure
            failed.append({"sample_id": sample_id,
                           "code": failure.code if failure else None})
            continue
        item = plate.to_dict()
        item["scenario_id"] = sample_id
        raw.append(item)

    global _last_facts
    _last_facts = {
        "contract_version": CONTRACT_VERSION,
        "provider": provider.label,
        "paddleocr_version": paddle_version,
        "processed_duration_sec": None,
        "n_samples": len(by_ref),
        "n_failed_runs": len(failed),
        "failed_runs": failed,
        "usage_records": [],
        "scenarios": [],
    }
    return raw


def run_facts(scope):
    del scope
    return dict(_last_facts)
