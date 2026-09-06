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


def load_sequences(manifest_name):
    """A tier 의 시퀀스 manifest. B tier 의 clips.json 에 대응한다."""
    return _read_json(os.path.join(paths.manifest_dir(manifest_name), "sequences.json"))


def load_manifest_meta(manifest_name):
    """manifest 의 meta 블록. clips.json 이 없으면 sequences.json 에서 읽는다.

    B tier 는 clip 단위(clips.json), A tier 는 시퀀스 단위(sequences.json)라
    파일 이름이 다르다. 없는 필드는 여기서 지어내지 않는다 — sequences.json
    에는 clip 개념 자체가 없어 clip_rule_version 이 없고, 호출부에서 null 이
    된다. 그것이 「clip 규칙 버전이 c1 이다」라고 거짓말하는 것보다 낫다.
    """
    clips_path = os.path.join(paths.manifest_dir(manifest_name), "clips.json")
    if os.path.exists(clips_path):
        return _read_json(clips_path)["meta"]
    return load_sequences(manifest_name)["meta"]


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
        # 아래 sha256 검사부의 경로 조립과 비슷해 보이지만 같지 않다 — 여기는
        # cwd 기준 상대경로도 존재로 인정하고(두 번째 or), 저쪽은 REPO_ROOT
        # 기준만 본다. 합치면 한쪽의 허용 범위가 조용히 넓어진다.
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
