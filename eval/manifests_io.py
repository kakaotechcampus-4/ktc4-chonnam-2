"""manifest·GT 로드와 불변식 검증.

지표 정의는 여기 없다. 이 모듈은 「정답지가 스스로 모순되지 않는가」만 본다.
"""
import hashlib
import json
import os

from eval import paths
from eval.enums import CLASS_LABELS, VIOLATION_TYPES


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


def sha256_file(path):
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
            if sha256_file(p) != c["sha256"]:
                problems.append("%s: sha256 불일치" % c["clip_id"])

    return problems


def check_invariants(manifest_name, stage, verify_hashes=0):
    return validate(load_clips(manifest_name), load_gt(manifest_name, stage), verify_hashes)


_SOURCE_TIERS = ("A", "B", "C")


def validate_sequences(sequences, gt):
    """시퀀스 manifest 와 classification 정답지의 불변식. 위반 메시지 목록.

    validate() 는 clip 과 span 을 전제해 A tier·ab_mixed 에서 돌지 않는다 —
    시퀀스 manifest 에는 clip 도 span 도 없다 (F13). 이 함수는 시퀀스 쪽
    불변식만 본다.

    라벨 공간은 4종이 아니라 CLASS_LABELS(4종 + NONE)다. ab_mixed 의 NONE
    항목이 baseline enum 밖이라고 거부당하면 안 되기 때문이다.
    """
    problems = []
    items = gt["items"]
    # 키가 없는 입력에 KeyError 를 던지면 「위반 메시지 목록을 돌려준다」는
    # 계약이 깨진다. 없는 것도 위반으로 적고 계속 본다.
    for where, rows in (("sequences.json", sequences["sequences"]), ("GT", items)):
        for n, row in enumerate(rows):
            if "sequence_id" not in row:
                problems.append("%s[%d]: sequence_id 가 없다" % (where, n))
    seq_ids = [s["sequence_id"] for s in sequences["sequences"] if "sequence_id" in s]
    gt_ids = [i["sequence_id"] for i in items if "sequence_id" in i]

    for ids, where in ((seq_ids, "sequences.json"), (gt_ids, "GT")):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        for d in dupes:
            problems.append("%s: sequence_id 중복 (%s)" % (where, d))

    for sid in sorted(set(gt_ids) - set(seq_ids)):
        problems.append("%s: GT 항목이 sequences.json 에 없다" % sid)
    for sid in sorted(set(seq_ids) - set(gt_ids)):
        problems.append("%s: sequences.json 항목이 GT 에 없다 — 채점되지 않는다" % sid)

    cov = (gt.get("meta") or {}).get("coverage")
    if "meta" not in gt:
        problems.append("GT 에 meta 가 없다 — gt_version 도 검토 실적도 확인할 수 없다")
    if cov is None:
        problems.append("meta.coverage 가 없다 — 검토 실적을 확인할 수 없다")
    elif cov.get("sequences_total") != len(items):
        problems.append(
            "meta.coverage.sequences_total=%s 인데 items=%d"
            % (cov.get("sequences_total"), len(items)))

    seq_by_id = {s["sequence_id"]: s for s in sequences["sequences"] if "sequence_id" in s}
    for item in items:
        if "sequence_id" not in item:
            continue                      # 위에서 이미 적었다
        sid = item["sequence_id"]
        if "label" not in item:
            problems.append("%s: label 이 없다" % sid)
            continue
        # A tier 는 위반유형을 sequences.json 과 GT 양쪽에 싣는다 — 이 레포에서
        # 같은 사실이 두 파일에 중복 저장되는 유일한 지점이라 드리프트가 가능하다.
        # B tier 항목은 violation_type 이 없고(None) 라벨이 NONE 이므로 건너뛴다.
        seq_type = (seq_by_id.get(sid) or {}).get("violation_type")
        if seq_type is not None and seq_type != item["label"]:
            problems.append(
                "%s: sequences.json 의 violation_type(%r)과 GT label(%r)이 다르다"
                % (sid, seq_type, item["label"]))
        if item["label"] not in CLASS_LABELS:
            problems.append("%s: %r 는 5클래스(4종 + NONE)가 아니다" % (sid, item["label"]))
        if item.get("source_tier") not in _SOURCE_TIERS:
            problems.append(
                "%s: 알 수 없는 source_tier %r — 해상도·압축 특성이 다른 tier 를 "
                "구분할 수 없다" % (sid, item.get("source_tier")))

        box = item.get("target_bbox")
        if box is None:
            # bbox 가 없으면 그에 딸린 사실도 전부 null 이어야 한다 —
            # 하나만 남으면 「무엇을 모르는지」가 흐려진다.
            for key in ("target_frame", "distractor_count"):
                if item.get(key) is not None:
                    problems.append(
                        "%s: target_bbox 가 없는데 %s 가 남아 있다" % (sid, key))
        elif len(box) != 4:
            problems.append("%s: target_bbox 의 길이가 4가 아니다 (%r)" % (sid, box))
        elif not (box[0] < box[2] and box[1] < box[3]):
            problems.append(
                "%s: target_bbox 의 넓이가 0 이하다 (%r) — IoU 가 영원히 0 이 된다"
                % (sid, box))

    return problems


def check_sequence_invariants(manifest_name, stage="classification"):
    return validate_sequences(load_sequences(manifest_name), load_gt(manifest_name, stage))
