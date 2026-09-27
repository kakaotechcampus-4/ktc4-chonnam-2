"""predictions + judge verdicts -> results/summary.md.

    python aggregate.py --predictions ../predictions --judge-run-id <run_id> --out ../results/summary.md

judge 호출이 실패한 케이스는 분모에서 제외한다(조용히 0으로 세지 않는다) — README의
에러 처리 정책과 동일.

hallucinated/missed를 correct/partial과 분리해서 집계하는 이유, 카테고리별로도
따로 보는 이유는 README.md "채점 방식 — 1차 가설, 실측 전 잠정" 참고.

`--judge-run-id`는 필수다(2026-09-20, 멘토 피드백으로 judge.py가 채점 결과를
run_id별로 분리 저장하게 바뀌면서 같이 바뀜) — predictions 폴더 하나에 채점 결과가
여러 run 쌓일 수 있어서, "어느 채점을 집계할지"를 이 스크립트가 알아서 고르지 않는다
(judge.py 실행 끝에 찍히는 run_id를 그대로 넘긴다).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from schema import FIELDS

JUDGE_FIELDS = [f for f in FIELDS]  # notes 필드는 집계 대상 아님

# `decisions/intent-llm-eval-target-thresholds.md` §1의 "애매 3종은 정확도 대신
# null/confidence:low로 떨어지는 비율로 별도 관리"를 실제로 계산한다. dataset.py의
# scenario_tag 값과 정확히 일치해야 한다(datasets/intent-hint-eval-v1.jsonl 참고).
AMBIGUOUS_TAGS = frozenset({"전부_모호", "차량_애매", "위치_애매"})


def aggregate_model(model_dir: Path, judge_run_id: str) -> dict:
    total_cases = 0
    schema_valid_count = 0
    errored_cases = 0
    latencies: list[float] = []
    costs: list[float] = []
    judge_errors = 0

    field_correct = {f: 0 for f in JUDGE_FIELDS}
    field_judged = {f: 0 for f in JUDGE_FIELDS}

    hallucinated_count = 0
    missed_count = 0
    total_judged_fields = 0

    scenario_correct: dict[str, int] = {}
    scenario_judged: dict[str, int] = {}

    ambiguous_total = 0
    ambiguous_low_confidence = 0

    for pred_path in sorted(model_dir.glob("*.json")):
        if ".judge." in pred_path.name:
            continue
        total_cases += 1
        prediction = json.loads(pred_path.read_text(encoding="utf-8"))
        scenario_tag = prediction.get("scenario_tag", "unknown")

        if prediction.get("error"):
            errored_cases += 1
        if prediction.get("schema_valid"):
            schema_valid_count += 1
        if prediction.get("latency_ms") is not None:
            latencies.append(prediction["latency_ms"])
        if prediction.get("cost_krw") is not None:
            costs.append(prediction["cost_krw"])

        # 애매 3종은 judge 판정이 아니라 후보가 실제로 뱉은 confidence 값 자체를 본다 —
        # "정답을 맞혔는가"가 아니라 "애매함을 스스로 인정했는가"를 재는 지표라 다르다.
        if scenario_tag in AMBIGUOUS_TAGS and prediction.get("parsed") is not None:
            ambiguous_total += 1
            if prediction["parsed"].get("confidence") == "low":
                ambiguous_low_confidence += 1

        judge_path = pred_path.parent / f"{prediction['case_id']}.judge.{judge_run_id}.json"
        if not judge_path.exists():
            continue
        verdict = json.loads(judge_path.read_text(encoding="utf-8"))
        if verdict.get("error") or verdict.get("parsed") is None:
            judge_errors += 1
            continue
        parsed = verdict["parsed"]

        for f in JUDGE_FIELDS:
            if f not in parsed:
                continue
            field_judged[f] += 1
            total_judged_fields += 1
            scenario_judged[scenario_tag] = scenario_judged.get(scenario_tag, 0) + 1

            # parsed[f]는 FieldVerdict(verdict+reason) 딕셔너리다(2026-09-20부터,
            # 멘토 피드백으로 필드별 근거를 남기게 되면서 구조가 바뀜) — 판정값만 집계한다.
            outcome = parsed[f]["verdict"]
            if outcome == "correct":
                field_correct[f] += 1
                scenario_correct[scenario_tag] = scenario_correct.get(scenario_tag, 0) + 1
            elif outcome == "hallucinated":
                hallucinated_count += 1
            elif outcome == "missed":
                missed_count += 1

    total_correct = sum(field_correct.values())

    return {
        "total_cases": total_cases,
        "schema_compliance_rate": (schema_valid_count / total_cases) if total_cases else 0.0,
        "field_accuracy_rate": (total_correct / total_judged_fields) if total_judged_fields else None,
        "hallucination_rate": (hallucinated_count / total_judged_fields) if total_judged_fields else None,
        "missed_rate": (missed_count / total_judged_fields) if total_judged_fields else None,
        "avg_latency_ms": (sum(latencies) / len(latencies)) if latencies else None,
        "total_cost_krw": sum(costs) if costs else None,
        "errored_cases": errored_cases,
        "judge_errors": judge_errors,
        "per_field_accuracy": {
            f: (field_correct[f] / field_judged[f]) if field_judged[f] else None
            for f in JUDGE_FIELDS
        },
        "per_scenario_accuracy": {
            tag: (scenario_correct.get(tag, 0) / judged) if judged else None
            for tag, judged in scenario_judged.items()
        },
        "ambiguous_low_confidence_rate": (
            (ambiguous_low_confidence / ambiguous_total) if ambiguous_total else None
        ),
        "ambiguous_total": ambiguous_total,
    }


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.0%}"


def render_markdown(results: dict[str, dict], judge_run_id: str) -> str:
    lines = [
        "# Intent LLM 비교 결과",
        "",
        f"judge_run_id: `{judge_run_id}` — 이 채점 결과의 raw 파일은 "
        f"`predictions/<model>/<case_id>.judge.{judge_run_id}.json`에 있다"
        "(필드별 판정 근거는 여기서 직접 읽는다).",
        "",
        "| model | schema 준수율 | field 정확도 | hallucination rate | missed rate | "
        "평균 latency(ms) | 총 비용(KRW) | 실패 케이스 | judge 실패 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for model, r in results.items():
        latency = "-" if r["avg_latency_ms"] is None else f"{r['avg_latency_ms']:.0f}"
        cost = "-" if r["total_cost_krw"] is None else f"{r['total_cost_krw']:.2f}"
        lines.append(
            f"| {model} | {_pct(r['schema_compliance_rate'])} | {_pct(r['field_accuracy_rate'])} | "
            f"{_pct(r['hallucination_rate'])} | {_pct(r['missed_rate'])} | "
            f"{latency} | {cost} | {r['errored_cases']}/{r['total_cases']} | {r['judge_errors']} |"
        )

    lines.append("")
    lines.append("## 필드별 정확도")
    lines.append("")
    lines.append("| model | " + " | ".join(FIELDS) + " |")
    lines.append("| --- | " + " | ".join(["---"] * len(FIELDS)) + " |")
    for model, r in results.items():
        cells = [_pct(r["per_field_accuracy"][f]) for f in FIELDS]
        lines.append(f"| {model} | " + " | ".join(cells) + " |")

    all_tags: list[str] = []
    for r in results.values():
        for tag in r["per_scenario_accuracy"]:
            if tag not in all_tags:
                all_tags.append(tag)

    lines.append("")
    lines.append("## 카테고리별 정확도")
    lines.append("")
    lines.append("(애매 표현 3종·correction 카테고리가 여기서 따로 보임 — README 「채점 방식 — 1차 가설, 실측 전 잠정」)")
    lines.append("")
    lines.append("| model | " + " | ".join(all_tags) + " |")
    lines.append("| --- | " + " | ".join(["---"] * len(all_tags)) + " |")
    for model, r in results.items():
        cells = [_pct(r["per_scenario_accuracy"].get(tag)) for tag in all_tags]
        lines.append(f"| {model} | " + " | ".join(cells) + " |")

    lines.append("")
    lines.append("## 애매 3종 — confidence:low 인정 비율")
    lines.append("")
    lines.append(
        "(정답을 맞혔는가가 아니라 애매함을 스스로 인정했는가. "
        "`decisions/intent-llm-eval-target-thresholds.md` §1 참고 — n이 3뿐이라 "
        "퍼센트보다 옆의 원본 건수를 우선 본다.)"
    )
    lines.append("")
    lines.append("| model | confidence:low 인정 비율 | (건수) |")
    lines.append("| --- | --- | --- |")
    for model, r in results.items():
        rate = _pct(r["ambiguous_low_confidence_rate"])
        n = r["ambiguous_total"]
        low_n = (
            "-"
            if r["ambiguous_low_confidence_rate"] is None
            else round(r["ambiguous_low_confidence_rate"] * n)
        )
        lines.append(f"| {model} | {rate} | {low_n}/{n} |")

    return "\n".join(lines) + "\n"


def run(predictions_dir: Path, out_path: Path, judge_run_id: str) -> None:
    results = {
        model_dir.name: aggregate_model(model_dir, judge_run_id)
        for model_dir in sorted(p for p in predictions_dir.iterdir() if p.is_dir())
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_markdown(results, judge_run_id), encoding="utf-8")
    print(f"결과({judge_run_id}) -> {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--judge-run-id", required=True, help="judge.py 실행 끝에 찍힌 run_id."
    )
    args = parser.parse_args()
    run(args.predictions, args.out, args.judge_run_id)


if __name__ == "__main__":
    main()
