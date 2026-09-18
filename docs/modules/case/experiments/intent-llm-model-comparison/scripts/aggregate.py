"""predictions + judge verdicts -> results/summary.md.

    python aggregate.py --predictions ../predictions --out ../results/summary.md

judge 호출이 실패한 케이스는 분모에서 제외한다(조용히 0으로 세지 않는다) — README의
에러 처리 정책과 동일.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from schema import FIELDS

JUDGE_FIELDS = [f for f in FIELDS]  # notes 필드는 집계 대상 아님


def aggregate_model(model_dir: Path) -> dict:
    total_cases = 0
    schema_valid_count = 0
    errored_cases = 0
    latencies: list[float] = []
    costs: list[float] = []

    field_correct = {f: 0 for f in JUDGE_FIELDS}
    field_judged = {f: 0 for f in JUDGE_FIELDS}
    judge_errors = 0

    for pred_path in sorted(model_dir.glob("*.json")):
        if pred_path.name.endswith(".judge.json"):
            continue
        total_cases += 1
        prediction = json.loads(pred_path.read_text(encoding="utf-8"))

        if prediction.get("error"):
            errored_cases += 1
        if prediction.get("schema_valid"):
            schema_valid_count += 1
        if prediction.get("latency_ms") is not None:
            latencies.append(prediction["latency_ms"])
        if prediction.get("cost_usd") is not None:
            costs.append(prediction["cost_usd"])

        judge_path = pred_path.with_suffix("").with_suffix(".judge.json")
        if not judge_path.exists():
            continue
        verdict = json.loads(judge_path.read_text(encoding="utf-8"))
        if verdict.get("error") or verdict.get("parsed") is None:
            judge_errors += 1
            continue
        parsed = verdict["parsed"]
        for f in JUDGE_FIELDS:
            if f in parsed:
                field_judged[f] += 1
                if parsed[f] == "correct":
                    field_correct[f] += 1

    total_judged = sum(field_judged.values())
    total_correct = sum(field_correct.values())

    return {
        "total_cases": total_cases,
        "schema_compliance_rate": (schema_valid_count / total_cases) if total_cases else 0.0,
        "field_accuracy_rate": (total_correct / total_judged) if total_judged else None,
        "avg_latency_ms": (sum(latencies) / len(latencies)) if latencies else None,
        "total_cost_usd": sum(costs) if costs else None,
        "errored_cases": errored_cases,
        "judge_errors": judge_errors,
        "per_field_accuracy": {
            f: (field_correct[f] / field_judged[f]) if field_judged[f] else None
            for f in JUDGE_FIELDS
        },
    }


def render_markdown(results: dict[str, dict]) -> str:
    lines = [
        "# Intent LLM 비교 결과",
        "",
        "| model | schema 준수율 | field 정확도 | 평균 latency(ms) | 총 비용(USD) | 실패 케이스 | judge 실패 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for model, r in results.items():
        field_acc = "-" if r["field_accuracy_rate"] is None else f"{r['field_accuracy_rate']:.0%}"
        latency = "-" if r["avg_latency_ms"] is None else f"{r['avg_latency_ms']:.0f}"
        cost = "-" if r["total_cost_usd"] is None else f"{r['total_cost_usd']:.4f}"
        lines.append(
            f"| {model} | {r['schema_compliance_rate']:.0%} | {field_acc} | "
            f"{latency} | {cost} | {r['errored_cases']}/{r['total_cases']} | {r['judge_errors']} |"
        )

    lines.append("")
    lines.append("## 필드별 정확도")
    lines.append("")
    lines.append("| model | " + " | ".join(FIELDS) + " |")
    lines.append("| --- | " + " | ".join(["---"] * len(FIELDS)) + " |")
    for model, r in results.items():
        cells = [
            "-" if r["per_field_accuracy"][f] is None else f"{r['per_field_accuracy'][f]:.0%}"
            for f in FIELDS
        ]
        lines.append(f"| {model} | " + " | ".join(cells) + " |")

    return "\n".join(lines) + "\n"


def run(predictions_dir: Path, out_path: Path) -> None:
    results = {
        model_dir.name: aggregate_model(model_dir)
        for model_dir in sorted(p for p in predictions_dir.iterdir() if p.is_dir())
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_markdown(results), encoding="utf-8")
    print(f"결과 -> {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    run(args.predictions, args.out)


if __name__ == "__main__":
    main()
