"""dataset x candidates -> predictions/*.json (불변 저장).

    python runner.py --dataset ../datasets/intent-hint-eval-v1.jsonl --out ../predictions

candidates.py의 TODO가 채워지기 전까지는 각 케이스가 error로 기록된다 — 그 자체로
"아직 실행 불가" 상태를 파일로 남기는 것이므로 정상이다.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path

from candidates import ALL_CANDIDATES
from dataset import load_dataset
from schema import validate_schema


def run(dataset_path: Path, out_dir: Path) -> None:
    cases = load_dataset(dataset_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    for adapter_cls in ALL_CANDIDATES:
        adapter = adapter_cls()
        model_dir = out_dir / adapter.model_name
        model_dir.mkdir(parents=True, exist_ok=True)

        for case in cases:
            result = adapter.extract(case.input_sentence, case.prior_hints)

            schema_valid = False
            schema_errors: list[str] = []
            if result.parsed is not None:
                schema_valid, schema_errors = validate_schema(result.parsed)

            record = {
                "case_id": case.id,
                "scenario_tag": case.scenario_tag,
                **dataclasses.asdict(result),
                "schema_valid": schema_valid,
                "schema_errors": schema_errors,
            }

            out_path = model_dir / f"{case.id}.json"
            out_path.write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"[{adapter.model_name}] {case.id} -> {out_path.name} "
                  f"(schema_valid={schema_valid}, error={result.error})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    run(args.dataset, args.out)


if __name__ == "__main__":
    main()
