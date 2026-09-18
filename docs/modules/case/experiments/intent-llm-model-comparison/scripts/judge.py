"""predictions/<model>/<case_id>.json x judge 모델 -> <case_id>.judge.json.

    python judge.py --dataset ../datasets/intent-hint-eval-v1.jsonl --predictions ../predictions

predictions/*.json 자체(candidate raw 출력)는 건드리지 않는다 — 불변으로 둔다.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path

from candidates import JudgeAdapter
from dataset import load_dataset


def run(dataset_path: Path, predictions_dir: Path) -> None:
    cases = {c.id: c for c in load_dataset(dataset_path)}
    judge = JudgeAdapter()

    for model_dir in sorted(p for p in predictions_dir.iterdir() if p.is_dir()):
        for pred_path in sorted(model_dir.glob("*.json")):
            if pred_path.name.endswith(".judge.json"):
                continue
            prediction = json.loads(pred_path.read_text(encoding="utf-8"))
            case = cases[prediction["case_id"]]

            verdict = judge.judge(
                input_sentence=case.input_sentence,
                prior_hints=case.prior_hints,
                expected_notes=case.expected_notes,
                candidate_output=prediction.get("parsed"),
            )

            out_path = pred_path.with_suffix("").with_suffix(".judge.json")
            out_path.write_text(
                json.dumps(dataclasses.asdict(verdict), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[{model_dir.name}] {case.id} judged -> {out_path.name} "
                  f"(error={verdict.error})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    args = parser.parse_args()
    run(args.dataset, args.predictions)


if __name__ == "__main__":
    main()
