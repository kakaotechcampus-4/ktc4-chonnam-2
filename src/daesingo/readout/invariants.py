"""readout 출력의 불변조건 — 「형식이 맞다」 다음에 오는 「의미가 맞다」.

라운드트립(contracts.py)은 필드가 제자리에 있는지만 본다. 여기는 **값 사이의 관계**를 본다 —
abstain인데 확정값이 함께 나오는지, 완전 실패인데 결과 객체가 생겼는지 같은 것들이다.
체크리스트의 Merge 중단 기준 4개가 전부 여기에 들어 있다.

규칙 원문의 소유자:
  - contract-readout-run.md §4            R1 · R2
  - contract-plate-overlay-readout.md §3  R16 (crop_ref identity)
  - 같은 문서 §5                          R10~R14 (abstain)
  - 같은 문서 §7 · §10                    R17 · R18 (overlay 갈래 · validation)
  - contract-observation.md 불변조건      R8 · R9
  - decisions/failure-taxonomy.md         R2 · R17

fixture 검수용이자 **구현 자체의 자기검사용**이다 — 공개 함수가 만든 출력에도 같은 함수를 건다.
"""
from __future__ import annotations

from dataclasses import dataclass

NULL_VALUE_STATUSES = frozenset({"UNKNOWN", "NOT_APPLICABLE", "ERROR"})
ASSOCIATION_BLOCKING = frozenset({"AMBIGUOUS", "FAILED"})

# overlay 4갈래 — (status, reason.code) → (samples가 있어야 하나, format_ok 기대값)
OVERLAY_BRANCHES = {
    ("OK", None): ("있음", True),
    ("NOT_APPLICABLE", "readout.overlay.not_present"): ("없음", None),
    ("UNKNOWN", "readout.overlay.presence_undetermined"): ("없음", None),
    ("UNKNOWN", "readout.overlay.ocr_failed"): ("있음", False),
}


@dataclass
class Violation:
    rule: str
    obj: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.rule}] {self.obj} — {self.detail}"


def _question_positions(text) -> list:
    return [i for i, ch in enumerate(text or "") if ch == "?"]


def check_runs(fixture) -> list:
    out = []
    for run in fixture.readout_runs:
        if run.outcome == "SUCCEEDED" and run.failure is not None:
            out.append(Violation("R1", run.run_id, "outcome=SUCCEEDED인데 failure가 있다"))
        if run.outcome in ("PARTIAL", "FAILED") and run.failure is None:
            out.append(Violation("R1", run.run_id, f"outcome={run.outcome}인데 failure가 없다"))
        if run.failure and run.failure.kind == "OVERLAY_VALIDATION" and run.outcome == "FAILED":
            out.append(Violation(
                "R2", run.run_id,
                "OVERLAY_VALIDATION은 run 실패가 아니다 — outcome=FAILED로 만들지 않는다",
            ))
    return out


def check_run_links(fixture) -> list:
    """결과 객체와 ReadoutRun의 연결 — 참조 해소 · 1 run 1 결과 · operation 대응 · 완전 실패."""
    out = []
    runs = {r.run_id: r for r in fixture.readout_runs}
    attached = {}
    expected_op = {"plate": "PLATE_READ", "overlay": "OVERLAY_TIME_READ"}

    for label, results in (("plate", fixture.plate_readouts),
                           ("overlay", fixture.overlay_time_readouts)):
        for res in results:
            ref = res.run_ref.ref
            run = runs.get(ref)
            if run is None:
                out.append(Violation("R4", res.readout_id, f"run_ref가 가리키는 run이 없다: {ref}"))
                continue
            attached.setdefault(ref, []).append(res.readout_id)
            if run.operation != expected_op[label]:
                out.append(Violation(
                    "R7", res.readout_id,
                    f"run.operation={run.operation}인데 {label} 결과가 붙었다",
                ))
            if run.outcome == "FAILED":
                out.append(Violation(
                    "R3", res.readout_id,
                    f"완전 실패(run {ref}, outcome=FAILED)인데 결과 객체가 생성됐다",
                ))
            produced = res.observation.produced_by.run_ref.ref
            if produced != ref:
                out.append(Violation(
                    "R6", res.readout_id,
                    f"produced_by.run_ref({produced})가 최상위 run_ref({ref})와 다르다",
                ))

    for ref, ids in attached.items():
        if len(ids) > 1:
            out.append(Violation("R5", ref, f"한 run에 결과 객체가 여럿 붙었다: {ids}"))
    return out


def check_observation(readout_id, observation) -> list:
    out = []
    if observation.status in NULL_VALUE_STATUSES and observation.value is not None:
        out.append(Violation(
            "R8", readout_id,
            f"status={observation.status}인데 value가 null이 아니다: {observation.value!r}",
        ))
    if observation.support_refs:
        out.append(Violation(
            "R9", readout_id,
            "readout의 support_refs는 빈 배열이다 — 근거 ref는 best_frame·frame_results가 갖는다",
        ))
    return out


def check_plate(fixture) -> list:
    out = []
    for plate in fixture.plate_readouts:
        pid = plate.readout_id
        obs = plate.observation
        out += check_observation(pid, obs)

        if plate.abstained:
            if obs.status != "NEEDS_REVIEW":
                out.append(Violation("R10", pid, f"abstained=true인데 status={obs.status}"))
            if obs.value is not None and "?" not in obs.value:
                out.append(Violation(
                    "R11", pid,
                    f"abstained=true인데 확정 번호판 값이 나왔다: {obs.value!r}",
                ))
            if plate.abstain_reason is None:
                out.append(Violation("R12", pid, "abstained=true인데 abstain_reason이 없다"))
            if obs.reason is not None:
                out.append(Violation(
                    "R12", pid,
                    "abstain_reason이 authoritative다 — abstained=true일 때 "
                    "observation.reason을 중복 채우지 않는다",
                ))
            if plate.target_association.status in ASSOCIATION_BLOCKING \
                    and plate.abstain_reason != "TARGET_AMBIGUOUS":
                out.append(Violation(
                    "R14", pid,
                    f"target_association={plate.target_association.status}이면 "
                    f"TARGET_AMBIGUOUS가 authoritative인데 {plate.abstain_reason}이다",
                ))
        elif plate.abstain_reason is not None:
            out.append(Violation(
                "R13", pid, f"abstained=false인데 abstain_reason={plate.abstain_reason}"))

        marked = sorted(plate.consensus.disagree_positions)
        if marked != _question_positions(obs.value):
            out.append(Violation(
                "R15", pid,
                f"disagree_positions={marked}가 value의 ? 위치 "
                f"{_question_positions(obs.value)}와 다르다",
            ))
        if marked != _question_positions(plate.consensus.text):
            out.append(Violation(
                "R15", pid,
                f"disagree_positions={marked}가 consensus.text의 ? 위치와 다르다",
            ))
    return out


def check_overlay(fixture) -> list:
    out = []
    for overlay in fixture.overlay_time_readouts:
        oid = overlay.readout_id
        obs = overlay.observation
        val = overlay.validation
        out += check_observation(oid, obs)

        branch = (obs.status, obs.reason.code if obs.reason else None)
        expected = OVERLAY_BRANCHES.get(branch)
        if expected is None:
            out.append(Violation(
                "R17", oid,
                f"등재된 overlay 4갈래에 없는 조합이다: status={branch[0]} reason={branch[1]}",
            ))
        else:
            want_samples, want_format_ok = expected
            has_samples = "있음" if overlay.samples else "없음"
            label = branch[1] or "OK"
            if has_samples != want_samples:
                out.append(Violation(
                    "R17", oid,
                    f"{label} 갈래는 samples가 {want_samples}이어야 하는데 {has_samples}이다",
                ))
            if val.format_ok != want_format_ok:
                out.append(Violation(
                    "R17", oid,
                    f"{label} 갈래는 format_ok={want_format_ok}이어야 하는데 {val.format_ok}이다",
                ))

        if val.sample_count != len(overlay.samples):
            out.append(Violation(
                "R18", oid,
                f"sample_count={val.sample_count}인데 samples는 {len(overlay.samples)}건이다",
            ))
    return out


def check_crop_identity(fixtures) -> list:
    """crop_ref는 (frame_ref, bbox, source_profile) 기준 발급이고 재사용하지 않는다.

    기계로 볼 수 있는 것은 두 가지다 — 같은 crop_ref가 다른 frame_ref에 붙지 않는지,
    서로 다른 ReadoutRun이 같은 crop_ref를 공유하지 않는지. 한 결과 객체 안에서
    best_frame과 frame_results가 같은 crop_ref를 가리키는 것은 같은 crop이라 정상이다.
    """
    out = []
    owner = {}  # crop_ref -> (frame_ref, run_ref)
    for fixture in fixtures:
        for plate in fixture.plate_readouts:
            run = plate.run_ref.ref
            pairs = []
            if plate.best_frame:
                pairs.append((plate.best_frame.crop_ref, plate.best_frame.frame_ref))
            pairs += [(f.crop_ref, f.frame_ref) for f in plate.frame_results]
            for crop_ref, frame_ref in pairs:
                prev = owner.get(crop_ref)
                if prev is None:
                    owner[crop_ref] = (frame_ref, run)
                    continue
                if prev[0] != frame_ref:
                    out.append(Violation(
                        "R16", crop_ref,
                        f"같은 crop_ref가 다른 frame_ref에 붙었다: {prev[0]} vs {frame_ref}",
                    ))
                if prev[1] != run:
                    out.append(Violation(
                        "R16", crop_ref,
                        f"다른 run이 같은 crop_ref를 재사용했다: {prev[1]} vs {run}",
                    ))
    return out


def check_fixture(fixture) -> list:
    """한 시나리오 안에서 볼 수 있는 불변조건 전부."""
    return (
        check_runs(fixture)
        + check_run_links(fixture)
        + check_plate(fixture)
        + check_overlay(fixture)
    )


def check_all(fixtures) -> list:
    """여러 시나리오. crop_ref는 시나리오를 가로질러야 보이므로 여기서만 검사한다."""
    out = []
    for fixture in fixtures:
        out += check_fixture(fixture)
    out += check_crop_identity(fixtures)
    return out
