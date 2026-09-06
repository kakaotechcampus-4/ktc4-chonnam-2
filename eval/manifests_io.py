"""manifest·GT 로드와 불변식 검증.

지표 정의는 여기 없다. 이 모듈은 「정답지가 스스로 모순되지 않는가」만 본다.
"""
import hashlib
import json
import os

from eval import paths
from eval.enums import VIOLATION_TYPES


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_clips(manifest_name):
    return _read_json(os.path.join(paths.manifest_dir(manifest_name), "clips.json"))


def load_gt(manifest_name, stage):
    return _read_json(
        os.path.join(paths.manifest_dir(manifest_name), "gt", "gt_%s.json" % stage)
    )


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate(clips, gt, verify_hashes=0):
    """위반 메시지 목록을 돌려준다. 빈 리스트면 정상."""
    problems = []
    by_id = {c["clip_id"]: c for c in clips["clips"]}
    items = gt["items"]
    cov = gt["meta"].get("coverage")

    if cov is None:
        problems.append("meta.coverage 가 없다 — 검토 실적을 확인할 수 없다")
    else:
        if cov["clips_total"] != len(items):
            problems.append(
                "meta.coverage.clips_total=%d 인데 items=%d" % (cov["clips_total"], len(items))
            )
        n_with = len([i for i in items if i["targets"]])
        if cov["clips_with_events"] != n_with:
            problems.append(
                "meta.coverage.clips_with_events=%d 인데 실제=%d"
                % (cov["clips_with_events"], n_with)
            )
        if cov["clips_reviewed"] < cov["clips_total"]:
            problems.append(
                "미검토 클립 %d개 — negative 를 정답으로 쓸 수 없다"
                % (cov["clips_total"] - cov["clips_reviewed"])
            )

    for item in items:
        clip = by_id.get(item["clip_id"])
        if clip is None:
            problems.append("%s: GT 항목이 clips.json 에 없다" % item["clip_id"])
            continue
        for t in item["targets"]:
            if t["violation_type"] not in VIOLATION_TYPES:
                problems.append(
                    "%s: %r 는 baseline 4종이 아니다" % (item["clip_id"], t["violation_type"])
                )
            if not t["t_start_sec"] < t["t_end_sec"]:
                problems.append(
                    "%s: t_start_sec >= t_end_sec (%s, %s)"
                    % (item["clip_id"], t["t_start_sec"], t["t_end_sec"])
                )
            if t["t_start_sec"] < 0 or t["t_end_sec"] > clip["duration_sec"]:
                problems.append(
                    "%s: span [%s, %s] 이 클립 길이 %s 를 벗어난다"
                    % (item["clip_id"], t["t_start_sec"], t["t_end_sec"], clip["duration_sec"])
                )

    for c in clips["clips"]:
        if not os.path.exists(os.path.join(paths.REPO_ROOT, c["file_path"])) \
                and not os.path.exists(c["file_path"]):
            problems.append("%s: file_path 가 존재하지 않는다 (%s)" % (c["clip_id"], c["file_path"]))

    for c in clips["clips"][:verify_hashes]:
        p = os.path.join(paths.REPO_ROOT, c["file_path"])
        if os.path.exists(p) and c.get("sha256"):
            if _sha256(p) != c["sha256"]:
                problems.append("%s: sha256 불일치" % c["clip_id"])

    return problems


def check_invariants(manifest_name, stage, verify_hashes=0):
    return validate(load_clips(manifest_name), load_gt(manifest_name, stage), verify_hashes)
