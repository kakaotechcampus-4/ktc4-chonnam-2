"""predictions/<model>/<case_id>.json x judge 모델 -> predictions/<model>/<case_id>.judge.<run_id>.json.

    python judge.py --dataset ../datasets/intent-hint-eval-v1.jsonl --predictions ../predictions

predictions/*.json 자체(candidate raw 출력)는 건드리지 않는다 — 불변으로 둔다.

채점 결과는 `<run_id>`별로 파일을 분리하고 절대 덮어쓰지 않는다(멘토 피드백 2026-09-20 —
"채점 결과도 덮어쓰지 말고 각각 저장해두시길 바랍니다. 채점 프로세스도 바뀔 수 있으니까요").
같은 predictions에 rubric(JUDGE_SYSTEM_PROMPT)이나 JUDGE_MODEL을 바꿔 다시 채점해도
이전 채점 결과가 그대로 남아 서로 비교할 수 있다. `--run-id`를 안 주면 실행 시각으로
자동 생성한다 — `aggregate.py`를 돌릴 때 그 run_id를 그대로 넘겨야 한다(출력에 찍힘).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from candidates import MODEL_IDS, JudgeAdapter
from dataset import load_dataset


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run(dataset_path: Path, predictions_dir: Path, run_id: str) -> None:
    cases = {c.id: c for c in load_dataset(dataset_path)}

    judge_model = os.environ["JUDGE_MODEL"]
    if judge_model in MODEL_IDS.values():
        raise ValueError(
            f"JUDGE_MODEL={judge_model!r}은 비교 대상 후보 중 하나다 — "
            "자기 채점 편향을 피하려면 후보 3개 밖의 모델을 써야 한다(README 참고)."
        )
    judge = JudgeAdapter(judge_model)

    written = 0
    for model_dir in sorted(p for p in predictions_dir.iterdir() if p.is_dir()):
        for pred_path in sorted(model_dir.glob("*.json")):
            # ".judge."가 들어간 파일은 이전 채점 결과다(버전마다 파일명이 다르므로
            # 고정 접미사 ".judge.json"이 아니라 부분 문자열로 확인해야 전부 걸러진다).
            if ".judge." in pred_path.name:
                continue
            prediction = json.loads(pred_path.read_text(encoding="utf-8"))
            case = cases[prediction["case_id"]]

            verdict = judge.judge(
                input_sentence=case.input_sentence,
                prior_hints=case.prior_hints,
                expected_notes=case.expected_notes,
                candidate_output=prediction.get("parsed"),
            )

            record = {
                "run_id": run_id,
                "judge_model": judge_model,
                "case_id": case.id,
                **dataclasses.asdict(verdict),
            }
            out_path = model_dir / f"{case.id}.judge.{run_id}.json"
            out_path.write_text(
                json.dumps(record, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            written += 1
            print(f"[{model_dir.name}] {case.id} judged -> {out_path.name} "
                  f"(error={verdict.error})")

    print(f"\njudge run_id={run_id!r} — {written}개 파일 기록. "
          f"aggregate.py --judge-run-id {run_id} 로 집계한다.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument(
        "--run-id",
        default=None,
        help="생략하면 실행 시각(UTC)으로 자동 생성한다. 같은 predictions를 다른 rubric/"
        "judge 모델로 다시 채점할 때 이전 결과를 덮어쓰지 않으려면 매번 새 값이어야 한다.",
    )
    args = parser.parse_args()
    run(args.dataset, args.predictions, args.run_id or _default_run_id())


if __name__ == "__main__":
    main()
