#!/usr/bin/env python3
"""Merge 전 셀프 체크 증빙 생성 — readout 공개 함수를 실제로 불러 출력을 파일로 남긴다.

테스트는 통과/실패만 말한다. 이 스크립트는 **출력이 어떻게 생겼는지**를 남긴다 — 회의에서
계약 문서의 예시 JSON과 나란히 놓고 필드가 같은지 눈으로 보기 위한 것이다.

무엇을 증명하려는지는 1차 체크리스트 「Merge 전 셀프 체크 증빙」과 「Merge 중단 기준」이 정한다.
이 스크립트는 규칙을 새로 만들지 않는다.

  중단 기준 2  abstained=true인데 확정 번호판 값이 함께 나옴      → 06
  중단 기준 3  완전 실패인데 결과 객체가 생성됨                    → 08
  중단 기준 4  overlay 4갈래 중 둘 이상이 한 값으로 합쳐짐         → 02~05

생성물은 `docs/modules/readout/experiments/merge-evidence-<날짜>/`에 떨어진다.
같은 폴더의 README.md도 같이 쓴다.

사용:
    python scripts/dump_readout_evidence.py
    python scripts/dump_readout_evidence.py --out <경로>
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from daesingo.readout import api, invariants, providers  # noqa: E402
from daesingo.readout.contracts import InputRef, ReadoutFixture  # noqa: E402

STAMP = "2026-09-14"
DEFAULT_OUT = os.path.join(
    ROOT, "docs", "modules", "readout", "experiments", "merge-evidence-" + STAMP)

DERIVED = "SOURCE_DERIVED_INCIDENT_CLIP"


def request(clip, case, candidate, profile="readout-native"):
    return api.ReadRequest(
        case_id=case,
        candidate_id=candidate,
        input_ref=InputRef(incident_clip_ref=clip, source_profile=profile, provenance=DERIVED),
    )


def write_json(out_dir, name, payload):
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)

    # 대본 진행(`clip_x001` overlay 2회차)을 보려면 provider 인스턴스를 하나로 유지해야 한다.
    provider = providers.FixtureOcrProvider()
    hint = api.TargetHint(track_ref="track_h001")

    runs, plates, overlays = [], [], []
    written = []

    def plate(clip, case, candidate, profile="readout-native", with_hint=True):
        run, result = api.read_plate(
            request(clip, case, candidate, profile),
            hint if with_hint else None,
            provider=provider,
        )
        runs.append(run)
        if result is not None:
            plates.append(result)
        return run, result

    def overlay(clip, case, candidate):
        run, result = api.read_overlay_time(request(clip, case, candidate), provider=provider)
        runs.append(run)
        if result is not None:
            overlays.append(result)
        return run, result

    def pair(run, result):
        return {"readout_run": run.to_dict(), "result": result.to_dict()}

    # ① 정상 판독 — 확인 질문 1번의 답
    run, happy = plate("clip_h001", "case_h001", "candidate_h001")
    written.append(write_json(args.out, "01-plate-happy.json", pair(run, happy)))

    # ②~⑤ overlay 4갈래. 체크리스트는 값이 안 나오는 3갈래를 요구하지만, 비교 대상인
    #     「읽음」을 같이 둬야 4갈래가 다르다는 것이 보인다.
    run, result = overlay("clip_h001", "case_h001", "candidate_h001")
    written.append(write_json(args.out, "02-overlay-ok.json", pair(run, result)))

    run, result = overlay("clip_u001", "case_u001", "candidate_u001")
    written.append(write_json(args.out, "03-overlay-not-present.json", pair(run, result)))

    # clip_x001의 overlay는 대본이 2회분이다 — 1회차 「있는지 못 봄」, 2회차 「못 알아봄」.
    run, result = overlay("clip_x001", "case_x001", "candidate_x001")
    written.append(write_json(args.out, "04-overlay-presence-undetermined.json", pair(run, result)))

    run, result = overlay("clip_x001", "case_x001", "candidate_x001")
    written.append(write_json(args.out, "05-overlay-ocr-failed.json", pair(run, result)))

    # ⑥⑦ abstain → 재판독. 두 파일을 나란히 놓는 것이 핵심이다 — 앞 판독이 그대로 남는다.
    run, first = plate("clip_p001", "case_p001", "candidate_p001")
    written.append(write_json(args.out, "06-plate-abstain.json", pair(run, first)))

    run, second = plate("clip_p001", "case_p001", "candidate_p001", "readout-native-hires")
    written.append(write_json(args.out, "07-plate-reread.json", pair(run, second)))

    # ⑧ 완전 실패. 「없음」은 JSON으로 못 보여준다 — 빈 파일은 만들다 만 것과 구분되지 않는다.
    run, missing = plate("clip_x001", "case_x001", "candidate_x001")
    lines = [
        "# 완전 실패 — 결과 객체가 생성되지 않는다는 증빙",
        "",
        "입력: scenario_infra_failure_001 / clip_x001 / PLATE_READ",
        "",
        ">>> run, plate = read_plate(request, target_hint)",
        "",
        "run   = " + json.dumps(run.to_dict(), ensure_ascii=False),
        "plate = " + repr(missing) + "        <- 결과 객체가 없는 것이 정상이다",
        "",
        "근거: decisions/failure-taxonomy.md 「code」 — INFRA 3종은 완전 실패이므로",
        "      결과 객체를 생성하지 않는다. 실패 사실과 원인은 ReadoutRun만 갖는다.",
        "      contract-readout-run.md §5 — ReadoutRun 1건 : 결과 0~1건.",
        "",
        "확인: run.outcome == FAILED / run.failure == {kind: INFRA, code: READOUT_PROVIDER_TIMEOUT}",
        "      plate is None / run.ended_at 존재(UsageRecord 발행 근거)",
    ]
    name = "08-plate-total-failure.log"
    with open(os.path.join(args.out, name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    written.append(name)

    # 만든 출력 전부에 불변조건 18개를 건다. 증빙이 중단 기준을 스스로 통과해야 한다.
    generated = ReadoutFixture("merge-evidence", "readout", runs, plates, overlays)
    violations = invariants.check_all([generated])

    write_readme(args.out, written, violations, happy, first, second)

    print("생성 위치: " + os.path.relpath(args.out, ROOT).replace(os.sep, "/"))
    for name in written:
        print("  " + name)
    print("")
    print("불변조건 18개 — 위반 %d건" % len(violations))
    for violation in violations:
        print("  " + str(violation))
    return 1 if violations else 0


def write_readme(out_dir, written, violations, happy, abstained, reread):
    body = """# Merge 전 셀프 체크 증빙 — readout (%(stamp)s)

`scripts/dump_readout_evidence.py`가 **공개 함수를 실제로 불러** 만든 출력이다. 손으로 쓴 예시가
아니다. 1차 체크리스트 「Merge 전 셀프 체크 증빙」 항목에 그대로 대응한다.

재생성:

```
python scripts/dump_readout_evidence.py
```

## 파일

| 파일 | 무엇을 보여주나 | 체크리스트 |
| --- | --- | --- |
| `01-plate-happy.json` | 정상 판독 — `value` `%(happy)s` · `status=OK` · `abstained=false` | 증빙 ① · 확인 질문 1 |
| `02-overlay-ok.json` | overlay 읽음 — `OK`, `validation` 3종 전부 `true` | 4갈래 비교 기준 |
| `03-overlay-not-present.json` | 「없음」(사실) — `NOT_APPLICABLE` + `readout.overlay.not_present` | 증빙 ② |
| `04-overlay-presence-undetermined.json` | 「있는지 못 봄」(모름) — `UNKNOWN` + `...presence_undetermined` | 증빙 ② |
| `05-overlay-ocr-failed.json` | 「읽었으나 못 알아봄」(모름) — `UNKNOWN` + `...ocr_failed`, `format_ok=false` | 증빙 ② |
| `06-plate-abstain.json` | 보류 — `abstained=true` · `NEEDS_REVIEW` · `value` `%(abstain)s` | 증빙 ③ |
| `07-plate-reread.json` | 재판독 성공 — `value` `%(reread)s` · `OK`. `06`을 고치지 않은 **새 run·새 결과** | 증빙 ③ |
| `08-plate-total-failure.log` | 완전 실패 — `outcome=FAILED`이고 **결과 객체가 없다** | 증빙 ④ |

## Merge 중단 기준과의 대응

- **abstain인데 확정값이 함께 나옴** → `06`. `value`에 `?`가 남아 있고 `abstain_reason`은 단일 값 하나다
- **완전 실패인데 결과 객체가 생성됨** → `08`. 결과가 `None`이다
- **overlay 4갈래 중 둘 이상이 합쳐짐** → `02`~`05`. `status`와 `reason.code` 조합이 넷 다 다르다
- **미등재 값 사용** → 전 파일. `failure.kind`·`code`·`abstain_reason`·`reason.code`가 등재값뿐이다

## 자기검사

이 폴더의 출력 전부에 `invariants.check_all`(R1~R18)을 걸었다 — **위반 %(violations)d건.**
fixture가 아니라 구현이 만든 값에 건 것이다.

## 다시 돌리면 달라지는 것

`run_id` · `readout_id` · `crop_ref` · `started_at` · `ended_at`은 **실행마다 바뀐다.** 오류가
아니라 규칙이다 — `run_id`는 1회성 식별자이고(`contract-readout-run.md` §4), `crop_ref`는
프레임을 다시 떠서 읽으면 새로 발급한다(`contract-plate-overlay-readout.md` §3). 이 폴더의
파일은 %(stamp)s 실행분 스냅샷이다. 값의 **의미**가 바뀌면 그때는 구현이 움직인 것이다.
""" % {
        "stamp": STAMP,
        "happy": happy.observation.value,
        "abstain": abstained.observation.value,
        "reread": reread.observation.value,
        "violations": len(violations),
    }
    with open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    written.append("README.md")


if __name__ == "__main__":
    sys.exit(main())
