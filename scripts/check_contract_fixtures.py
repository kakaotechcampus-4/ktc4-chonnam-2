#!/usr/bin/env python3
"""계약 예시·fixture 의미 검사 — 2026-09-07 접합부 종결 ADR의 검증 조건 V0~V6 + 2026-09-08 후속 ADR의 V8~V15.

규칙은 여기서 정하지 않는다. 각 검사가 옮겨 온 규칙의 원문은 함수 docstring이 가리킨다.
  - 결정 원장  → docs/architecture/contracts/adr/adr-data-contract-call-closure-2026-09-07.md §7
                 docs/architecture/contracts/adr/adr-data-contract-call-closure-2026-09-08.md §7
  - fixture    → docs/architecture/contracts/fixtures/call-closure-2026-09-07/
                 docs/architecture/contracts/fixtures/call-closure-2026-09-08/

이 스크립트의 PASS는 「계약 규칙을 코드로 옮겼을 때 fixture가 그 규칙을 만족한다」는 뜻이다.
구현 통합·E2E·Owner 수락을 증명하지 않는다.

사용:
    python scripts/check_contract_fixtures.py
"""
import json
import os
import re
import sys
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CDIR = os.path.join(ROOT, "docs", "architecture", "contracts")
FDIR = os.path.join(CDIR, "fixtures", "call-closure-2026-09-07")
FDIR2 = os.path.join(CDIR, "fixtures", "call-closure-2026-09-08")

# 세 회차에 수정·추가한 문서. V0(JSON 파싱)·V6(링크) 대상.
TOUCHED = [
    "adr/adr-plate-overlay-readout.md",
    "adr/adr-evidence-record-needs.md",
    "contract-source-asset-media-stream.md",
    "contract-analysis-source-derived.md",
    "adr/adr-data-contract-call-closure-2026-09-08.md",
    "adr/adr-source-asset-media-stream.md",
    "adr/adr-analysis-source-derived.md",
    "adr/adr-analysis-scope.md",
    "adr/adr-recording-timeline-asset-span.md",
    "contract-job-record-case-view.md",
    "contract-evidence-record-needs.md",
    "contract-time-resolution.md",
    "contract-requirement-report-package.md",
    "contract-plate-overlay-readout.md",
    "contract-readout-run.md",
    "contract-observation.md",
    "contract-usage-record.md",
    "contract-job-execution.md",
    "contract-analysis-run-candidate-event.md",
    "contract-recording-timeline-asset-span.md",
    "contract-analysis-scope.md",
    "README.md",
    "adr/adr-data-contract-call-closure-2026-09-07.md",
    "adr/adr-consistency-followup-2026-09-06.md",
]

results = {"structure": [], "json": [], "semantic": []}


def rec(bucket, ok, name, detail=""):
    results[bucket].append((ok, name, detail))


def read(rel):
    with open(os.path.join(CDIR, rel), encoding="utf-8") as fh:
        return fh.read()


def load_fixture(name, fdir=FDIR):
    with open(os.path.join(fdir, name), encoding="utf-8") as fh:
        return json.load(fh)


# ══ V0. 계약 본문의 JSON 예시가 파싱되는가 ══════════════════════
FENCE = re.compile(r"```(\w*)\n(.*?)```", re.S)


def json_blocks(rel):
    """```json 펜스는 반드시 파싱돼야 한다. 언어 표시 없는 펜스는 첫 글자가 '{'일 때만 시도한다
    (recording 계약 §8.1·§24가 그 형식이다)."""
    out = []
    for lang, body in FENCE.findall(read(rel)):
        body = body.strip()
        if lang == "json":
            out.append(("json", body))
        elif lang == "" and body.startswith("{"):
            out.append(("bare", body))
    return out


def check_v0():
    parsed = {}
    for rel in TOUCHED:
        if not rel.startswith("contract-"):
            continue
        objs = []
        for kind, body in json_blocks(rel):
            try:
                objs.append(json.loads(body))
            except json.JSONDecodeError as exc:
                if kind == "json":
                    rec("json", False, "V0 %s" % rel, "```json 파싱 실패: %s" % exc)
                # bare 펜스는 pseudo-schema일 수 있어 실패를 세지 않는다
        parsed[rel] = objs
        rec("json", True, "V0 %s" % rel, "%d개 JSON 파싱" % len(objs))
    return parsed


# ══ V1. B01 — info_state 파생 ═══════════════════════════════════
INFO = ("INFO_AI_ESTIMATED", "INFO_SOURCE_VERIFIED", "INFO_USER_CONFIRMED",
        "INFO_NEEDS_REVIEW", "INFO_UNKNOWN")


def check_evidence_value_invariants(ev, where):
    """contract-evidence-record-needs.md §10-12·§10-13."""
    errs = []
    if ev is None:
        return errs
    if ev.get("user_corrected") and ev.get("needs_review"):
        errs.append("%s: user_corrected=true ∧ needs_review=true" % where)
    if ev.get("value") is None and ev.get("needs_review"):
        errs.append("%s: value=null ∧ needs_review=true" % where)
    return errs


def derive_from_evidence_value(ev):
    """contract-job-record-case-view.md B절 §7 (1) — 5단계 순서 그대로."""
    if ev is None or ev.get("value") is None:
        return "INFO_UNKNOWN"
    if ev.get("user_corrected"):
        return "INFO_USER_CONFIRMED"
    if ev.get("needs_review"):
        return "INFO_NEEDS_REVIEW"
    if ev["source"].get("observability") == "OBSERVED":
        return "INFO_SOURCE_VERIFIED"
    return "INFO_AI_ESTIMATED"


def derive_event_time(occ):
    """contract-job-record-case-view.md B절 §7 (2) — 4단계 표."""
    if occ is None:
        return "INFO_UNKNOWN"
    if occ.get("user_corrected"):
        return "INFO_USER_CONFIRMED"
    if occ["resolution_status"] == "NEEDS_REVIEW":
        return "INFO_NEEDS_REVIEW"
    if occ["resolution_status"] == "OK":
        return "INFO_SOURCE_VERIFIED"
    raise ValueError("resolution_status must be OK|NEEDS_REVIEW (§10-8)")


def project_display(ev):
    return {
        "value": None if ev is None else ev.get("value"),
        "needs_review": bool(ev and ev.get("needs_review")),
        "info_state": derive_from_evidence_value(ev),
        "source_label_key": None if ev is None else ev["source"].get("label_key"),
    }


def project_case_view_evidence(record):
    """contract-job-record-case-view.md B절 §7 (1)~(3)."""
    out = {}
    out["plate_display"] = project_display(record.get("vehicle_number"))

    occ = record.get("occurred_at")
    out["event_time_display"] = {
        "value": None if occ is None else occ["value"],
        "needs_review": bool(occ and occ["resolution_status"] == "NEEDS_REVIEW"),
        "info_state": derive_event_time(occ),
        "source_label_key": None if occ is None else occ["source"].get("label_key"),
    }

    loc = record.get("location") or {}
    rep_key = next((k for k in ("address", "place_name", "user_hint") if loc.get(k)), None)
    rep = loc.get(rep_key) if rep_key else None
    disp = project_display(rep)
    if rep_key == "user_hint":
        disp["info_state"] = "INFO_NEEDS_REVIEW"       # §7 (3) location 전용 규칙
    disp["coord"] = loc["coord"]["value"] if loc.get("coord") else None
    disp["search_keyword"] = loc["search_keyword"]["value"] if loc.get("search_keyword") else None
    out["location_display"] = disp
    return out


def check_v1(parsed):
    fx = load_fixture("v1-caseview-info-state.json")
    for case in fx["cases"]:
        rec_ = case["evidence_record"]
        errs = []
        errs += check_evidence_value_invariants(rec_.get("vehicle_number"), "vehicle_number")
        for k, v in (rec_.get("location") or {}).items():
            errs += check_evidence_value_invariants(v, "location." + k)
        got = project_case_view_evidence(rec_)
        for disp, exp in case["expected"].items():
            if got[disp] != exp:
                errs.append("%s 기대 %s ≠ 실제 %s" % (disp, json.dumps(exp, ensure_ascii=False),
                                                json.dumps(got[disp], ensure_ascii=False)))
        for disp in got.values():
            if disp["info_state"] not in INFO:
                errs.append("enum 밖 info_state %s" % disp["info_state"])
        rec("semantic", not errs, "V1 %s" % case["id"], "; ".join(errs))

    for bad in fx["evidence_invariant_violations"]:
        errs = check_evidence_value_invariants(bad["evidence_value"], bad["id"])
        rec("semantic", bool(errs), "V1 violation detected: %s" % bad["id"],
            "" if errs else "위반 fixture를 검사기가 통과시켰다")

    # CaseView §8 예시: thumb_ref는 fr_ opaque, requirements 두 객체, location_display 새 필드
    for obj in parsed.get("contract-job-record-case-view.md", []):
        if "candidates" not in obj or "case_id" not in obj or not isinstance(obj.get("case_rev"), int):
            continue   # §5 스키마 블록(값이 타입 문자열)은 예시가 아니다
        errs = []
        for c in obj.get("candidates") or []:
            t = c.get("thumb_ref")
            if t is not None and not (isinstance(t, str) and t.startswith("fr_") and "@" not in t and ":" not in t):
                errs.append("thumb_ref %r 는 fr_ opaque id가 아니다" % t)
        for key in ("requirements_evidence", "requirements_package"):
            if key not in obj:
                errs.append("%s 키 없음" % key)
        if "requirements" in obj:
            errs.append("옛 단일 requirements 잔존")
        ev = obj.get("evidence")
        if ev and "location_display" in ev:
            for key in ("coord", "search_keyword"):
                if key not in ev["location_display"]:
                    errs.append("location_display.%s 없음" % key)
        rec("semantic", not errs, "V1 CaseView 예시 case_id=%s" % obj["case_id"], "; ".join(errs))


# ══ V2. B02 — RequirementReport 선택 3단계 ═════════════════════
def select_report(reports, scope, current_record_ref):
    """contract-job-record-case-view.md B절 §7 표 「선택 규칙(3단계)」."""
    cands = [r for r in reports if r["scope"] == scope
             and r["basis"]["evidence_record_ref"]["ref"] == current_record_ref]      # 1
    superseded = {r["supersedes_ref"]["ref"] for r in cands if r.get("supersedes_ref")}
    heads = [r for r in cands if r["requirement_report_ref"]["ref"] not in superseded]  # 2
    if not heads:
        return None
    heads.sort(key=lambda r: r["evaluated_at"], reverse=True)                            # 3
    return heads[0]


def check_v2():
    fx = load_fixture("v2-requirements-selection.json")
    for sc in fx["scenarios"]:
        errs = []
        cur = sc["current_evidence_record_ref"]
        got_e = select_report(fx["reports"], "EVIDENCE", cur)
        got_p = select_report(fx["reports"], "FINAL_PACKAGE", cur)
        ge = got_e["requirement_report_ref"]["ref"] if got_e else None
        gp = got_p["requirement_report_ref"]["ref"] if got_p else None
        if ge != sc["expected"]["requirements_evidence"]:
            errs.append("requirements_evidence 기대 %s ≠ %s" % (sc["expected"]["requirements_evidence"], ge))
        if gp != sc["expected"]["requirements_package"]:
            errs.append("requirements_package 기대 %s ≠ %s" % (sc["expected"]["requirements_package"], gp))
        # §10-3: package non-null → requirements_package non-null ∧ readiness ∈ {PASS,WARN}
        if sc["package_exists"] and not (got_p and got_p["overall"] in ("PASS", "WARN")):
            errs.append("package 존재인데 requirements_package 조건 불충족")
        rec("semantic", not errs, "V2 %s" % sc["id"], "; ".join(errs))

    tb = fx["tie_break_scenario"]
    got = select_report(tb["reports"], "EVIDENCE", tb["current_evidence_record_ref"])
    g = got["requirement_report_ref"]["ref"] if got else None
    rec("semantic", g == tb["expected"]["requirements_evidence"], "V2 %s" % tb["id"],
        "" if g == tb["expected"]["requirements_evidence"] else "기대 %s ≠ %s" % (tb["expected"]["requirements_evidence"], g))


# ══ V3. B03·B05 — 결과 → run → usage → execution → job ══════════
def is_ref(x, kind=None):
    return isinstance(x, dict) and set(x.keys()) == {"kind", "ref"} and (kind is None or x["kind"] == kind)


def check_v3(parsed):
    fx = load_fixture("v3-readout-run-chain.json")
    runs = {r["run_id"]: r for r in fx["readout_runs"]}
    usages = {u["usage_id"]: u for u in fx["usage_records"]}
    execs = {e["execution_id"]: e for e in fx["job_executions"]}
    jobs = {j["job_id"]: j for j in fx["job_records"]}
    results_ = fx["plate_readouts"] + fx["overlay_time_readouts"]
    errs = []

    # 결과가 존재하면 run_ref 존재·유효 (plate-overlay §3), 최상위 == produced_by.run_ref (R-9-5)
    run_of_result = {}
    for r in results_:
        rr = r.get("run_ref")
        if not is_ref(rr, "readout_run") or rr["ref"] not in runs:
            errs.append("%s: run_ref 없음/무효" % r["readout_id"])
            continue
        if r["observation"].get("produced_by", {}).get("run_ref") != rr:
            errs.append("%s: 최상위 run_ref ≠ observation.produced_by.run_ref" % r["readout_id"])
        if r["observation"].get("contract_version") != "observation/v1":
            errs.append("%s: observation.contract_version 누락" % r["readout_id"])
        if "supersedes_ref" in r or "kind" in r["observation"] or "provenance" in r["observation"]:
            errs.append("%s: 금지 필드(supersedes_ref / observation.kind / observation.provenance)" % r["readout_id"])
        run_of_result.setdefault(rr["ref"], []).append(r["readout_id"])

    # run 1건 : 결과 0~1건. FAILED run은 결과 0건
    for rid, run in runs.items():
        n = len(run_of_result.get(rid, []))
        if n > 1:
            errs.append("%s: 결과 %d건 (0~1건이어야)" % (rid, n))
        if run["outcome"] == "FAILED" and n != 0:
            errs.append("%s: FAILED인데 결과 존재" % rid)
        if run["outcome"] == "SUCCEEDED" and run["failure"] is not None:
            errs.append("%s: SUCCEEDED인데 failure non-null" % rid)
        if run["outcome"] in ("PARTIAL", "FAILED") and not (run["failure"] and run["failure"].get("kind") and run["failure"].get("code")):
            errs.append("%s: %s인데 failure.kind/code 없음" % (rid, run["outcome"]))
    got_with = sorted(run_of_result)
    got_without = sorted(r for r in runs if r not in run_of_result)
    if got_with != sorted(fx["expected"]["runs_with_result"]):
        errs.append("결과 있는 run 기대 %s ≠ %s" % (fx["expected"]["runs_with_result"], got_with))
    if got_without != sorted(fx["expected"]["runs_without_result"]):
        errs.append("결과 없는 run 기대 %s ≠ %s" % (fx["expected"]["runs_without_result"], got_without))

    # UsageRecord.run_ref: ContractRef|null, kind ∈ {analysis_run, readout_run}, null은 직접 호출만 (§8-9·10)
    nulls = []
    for uid, u in usages.items():
        rr = u["run_ref"]
        if rr is None:
            nulls.append(uid)
            continue
        if not is_ref(rr) or rr["kind"] not in ("analysis_run", "readout_run"):
            errs.append("%s: run_ref 모양/kind 위반 %r" % (uid, rr))
        if rr["kind"] == "readout_run" and rr["ref"] not in runs:
            errs.append("%s: readout_run %s 없음" % (uid, rr["ref"]))
    if sorted(nulls) != sorted(fx["expected"]["usage_run_ref_null_only_for"]):
        errs.append("run_ref=null 기대 %s ≠ %s" % (fx["expected"]["usage_run_ref_null_only_for"], nulls))
    # Run에 속한 usage가 null로 기록되지 않았는가: run.usage_refs가 가리키는 row는 run_ref non-null
    for rid, run in runs.items():
        for uid in run["usage_refs"]:
            u = usages.get(uid)
            if u is None:
                errs.append("%s.usage_refs → %s 없음" % (rid, uid))
            elif u["run_ref"] is None:
                errs.append("%s에 속한 %s가 run_ref=null" % (rid, uid))
            elif u["run_ref"] != {"kind": "readout_run", "ref": rid}:
                # §8-11: 어긋나면 원장이 기준 — 위반은 아니지만 기록
                rec("semantic", True, "V3 NOTE %s" % uid, "ReadoutRun.usage_refs와 원장 run_ref 불일치 → 원장 기준")

    # JobExecution.produced의 readout_run ref 정확히 1개 (job-execution §9-9), 1 execution : 1 run, job.kind ↔ operation
    exec_to_run = {}
    for eid, e in execs.items():
        for p in e["produced"]:
            if not is_ref(p):
                errs.append("%s.produced 원소가 ContractRef가 아님 %r" % (eid, p))
        rrs = [p["ref"] for p in e["produced"] if is_ref(p, "readout_run")]
        if len(rrs) != 1:
            errs.append("%s: produced readout_run %d개 (정확히 1개)" % (eid, len(rrs)))
            continue
        exec_to_run[eid] = rrs[0]
        job = jobs[e["job_id"]]
        run = runs.get(rrs[0])
        if run is None:
            errs.append("%s → run %s 없음" % (eid, rrs[0]))
        elif run["operation"] != job["kind"]:
            errs.append("%s: JobRecord.kind %s ≠ ReadoutRun.operation %s" % (eid, job["kind"], run["operation"]))
        # usage 역방향: execution.usage_refs → usage.execution_ref == eid
        for uid in e["usage_refs"]:
            if usages[uid]["execution_ref"] != eid:
                errs.append("%s.usage_refs → %s.execution_ref=%s" % (eid, uid, usages[uid]["execution_ref"]))
    if exec_to_run != fx["expected"]["execution_to_run"]:
        errs.append("execution→run 기대 %s ≠ %s" % (fx["expected"]["execution_to_run"], exec_to_run))
    runs_by_exec = list(exec_to_run.values())
    if len(set(runs_by_exec)) != len(runs_by_exec):
        errs.append("한 run이 두 execution에 속함")
    if set(j["kind"] for j in jobs.values()) - {"COARSE_SEARCH", "PLATE_READ", "OVERLAY_TIME_READ"}:
        errs.append("등재되지 않은 JobRecord.kind")
    rec("semantic", not errs, "V3 readout run chain (fixture)", "; ".join(errs))

    # 계약 본문 예시 대조: plate/overlay 예시 run_ref, usage 예시 run_ref 모양, observation 등재
    errs = []
    for obj in parsed.get("contract-plate-overlay-readout.md", []):
        if "readout_id" in obj:
            if not is_ref(obj.get("run_ref"), "readout_run"):
                errs.append("%s 예시에 run_ref 없음" % obj["readout_id"])
            if obj["observation"].get("produced_by", {}).get("run_ref") != obj.get("run_ref"):
                errs.append("%s 예시 produced_by.run_ref 불일치" % obj["readout_id"])
    for obj in parsed.get("contract-usage-record.md", []):
        if "usage_id" in obj and "run_ref" in obj and not isinstance(obj["run_ref"], dict) and obj["run_ref"] is not None:
            errs.append("UsageRecord 예시 %s run_ref가 평문" % obj["usage_id"])
        if "usage_id" in obj and obj["usage_id"] == "usage_205" and obj["run_ref"] is None:
            errs.append("usage_205 예시가 여전히 null (B05 원인 예시)")
    for obj in parsed.get("contract-job-execution.md", []):
        if "execution_id" in obj and isinstance(obj.get("produced"), list):
            for p in obj["produced"]:
                if not is_ref(p):
                    errs.append("JobExecution 예시 produced 원소 %r" % p)
    if "readout_run" not in read("contract-observation.md"):
        errs.append("observation §6에 readout_run 미등재")
    rec("semantic", not errs, "V3 계약 본문 예시 대조", "; ".join(errs))


# ══ V4. B06 — SpanResolution 완전성 (+ V10. CALL-14 failure 직렬화) ══
REASONS_V1 = {"TIMELINE_GAP", "SOURCE_UNAVAILABLE", "STREAM_UNAVAILABLE"}
REASONS_V1_1 = REASONS_V1 | {"OUT_OF_TIMELINE_RANGE"}


def span_violations(sr):
    """contract-recording-timeline-asset-span.md §23 SpanResolution 1·6·7 (v1) + 9~12 (v1.1).
    `failure` 규칙은 contract_version이 span-resolution/v1.1 이상일 때만 적용한다 — v1 payload의
    재해석 규칙은 정해지지 않았다(2026-09-08 ADR §4.3). `source_ref` 규칙(§10.2 · §23-13·14)은
    v1.2에서만 적용한다."""
    errs = []
    ver = sr.get("contract_version")
    v11 = ver in ("span-resolution/v1.1", "span-resolution/v1.2")
    v12 = ver == "span-resolution/v1.2"
    st = sr["status"]
    req = (sr["requested_range"]["start_sec"], sr["requested_range"]["end_sec"])
    pieces = [(s["timeline_range"]["start_sec"], s["timeline_range"]["end_sec"]) for s in sr["spans"]]
    pieces += [(m["timeline_range"]["start_sec"], m["timeline_range"]["end_sec"]) for m in sr["missing_ranges"]]
    for a, b in pieces:
        if a < req[0] or b > req[1]:
            errs.append("range_outside_request")
    # reason enum (§10 · §23-12)
    allowed = REASONS_V1_1 if v11 else REASONS_V1
    for m in sr["missing_ranges"]:
        if m.get("reason") not in allowed:
            errs.append("reason_not_in_enum: %r" % m.get("reason"))
    # source_ref 규칙 (§10.1·§10.2 · §23-13·14) — v1.2만
    if v12:
        errs += source_ref_violations(sr["missing_ranges"])
    # failure 규칙 (§9 · §23-10·11) — v1.1만
    unlocatable_failed = False
    if v11:
        if "failure" not in sr:
            errs.append("failure_key_missing")
        else:
            f = sr["failure"]
            if st in ("COMPLETE", "PARTIAL") and f is not None:
                errs.append("failure_must_be_null")
            if st == "FAILED":
                if f is None:
                    errs.append("failure_required")
                elif not (isinstance(f, dict) and isinstance(f.get("kind"), str) and f["kind"]
                          and isinstance(f.get("code"), str) and f["code"]):
                    errs.append("failure_shape")
                elif not sr["missing_ranges"]:
                    unlocatable_failed = True      # §23-11 — 완전성 예외
    # coverage: 합집합 == 요청 범위 (§23-6) — 위치 특정 불가 FAILED는 예외
    if not unlocatable_failed:
        pts = sorted(set([req[0], req[1]] + [p for pr in pieces for p in pr]))
        for lo, hi in zip(pts, pts[1:]):
            if not any(a <= lo and hi <= b for a, b in pieces):
                errs.append("coverage: [%s,%s) 미설명" % (lo, hi))
    # 같은 stream 중복 금지
    by_stream = {}
    for s in sr["spans"]:
        by_stream.setdefault(s["media_stream_ref"], []).append((s["timeline_range"]["start_sec"], s["timeline_range"]["end_sec"]))
    for ms, rs in by_stream.items():
        rs.sort()
        for (a1, b1), (a2, b2) in zip(rs, rs[1:]):
            if a2 < b1:
                errs.append("same_stream_overlap: %s" % ms)
    # status ↔ 배열 (§9)
    if st == "COMPLETE" and (not sr["spans"] or sr["missing_ranges"]):
        errs.append("COMPLETE 조건 위반")
    if st == "PARTIAL" and (not sr["spans"] or not sr["missing_ranges"]):
        errs.append("PARTIAL 조건 위반")
    if st == "FAILED" and sr["spans"]:
        errs.append("FAILED인데 spans 존재")
    return errs


def check_v4(parsed):
    fx = load_fixture("v4-span-resolution.json")
    for v in fx["valid"]:
        errs = span_violations(v["span_resolution"])
        rec("semantic", not errs, "V4 %s" % v["id"], "; ".join(errs))
    for inv in fx["invalid"]:
        errs = span_violations(inv["span_resolution"])
        hit = any(inv["expect_violation"] in e for e in errs)
        rec("semantic", hit, "V4 violation detected: %s" % inv["id"],
            "" if hit else "기대 위반 %s 미검출 (%s)" % (inv["expect_violation"], errs))
    # 계약 본문 예시 (§8.1 · §24)
    n = 0
    for obj in parsed.get("contract-recording-timeline-asset-span.md", []):
        srs = []
        if obj.get("contract") == "SpanResolution":
            srs.append(obj)
        if "span_resolution" in obj:
            srs.append(obj["span_resolution"])
        for sr in srs:
            n += 1
            errs = span_violations(sr)
            rec("semantic", not errs, "V4 계약 예시 requested=[%s,%s)" % (sr["requested_range"]["start_sec"], sr["requested_range"]["end_sec"]), "; ".join(errs))
    if n == 0:
        rec("semantic", False, "V4 계약 예시", "recording 계약에서 SpanResolution 예시를 찾지 못함")
    if n < 4:
        rec("semantic", False, "V4 계약 예시 개수", "§8.1·§9 FAILED 2건·§24 = 최소 4건이어야 하는데 %d건" % n)


def check_v10():
    """CALL-14 fixture — contract-recording-timeline-asset-span.md §9·§10·§23 SpanResolution 9~12."""
    fx = load_fixture("v10-span-resolution-failure.json", FDIR2)
    for v in fx["valid"]:
        errs = span_violations(v["span_resolution"])
        rec("semantic", not errs, "V10 %s" % v["id"], "; ".join(errs))
    for inv in fx["invalid"]:
        errs = span_violations(inv["span_resolution"])
        hit = any(inv["expect_violation"] in e for e in errs)
        rec("semantic", hit, "V10 violation detected: %s" % inv["id"],
            "" if hit else "기대 위반 %s 미검출 (%s)" % (inv["expect_violation"], errs))
    # 계약 본문: v1.1 예시가 존재하고 §10 reason 표에 OUT_OF_TIMELINE_RANGE가 있다
    body = read("contract-recording-timeline-asset-span.md")
    errs = []
    if "span-resolution/v1.1" not in body:
        errs.append("헤더/예시에 span-resolution/v1.1 없음")
    if "`OUT_OF_TIMELINE_RANGE`" not in body:
        errs.append("§10에 OUT_OF_TIMELINE_RANGE 없음")
    if "span-resolution/v1.2" not in body:
        errs.append("헤더/예시에 span-resolution/v1.2 없음")
    if "CALL_REQUIRED" in body:
        errs.append("CALL_REQUIRED 표기가 남아 있음 (CALL-16 종결)")
    rec("semantic", not errs, "V10 계약 본문 표기", "; ".join(errs))


# ══ V5. B09 — timeline_revision ══════════════════════════════════
def check_v5(parsed):
    fx = load_fixture("v5-candidate-revision.json")
    errs = []
    cur = fx["current_timeline"]
    stale = {}
    for c in fx["candidates"]:
        sp = c["span"]
        if "timeline_revision" not in sp or not isinstance(sp["timeline_revision"], int) or sp["timeline_revision"] < 1:
            errs.append("%s: timeline_revision 누락/무효" % c["candidate_id"])
            continue
        if not (0 <= sp["start_ms"] < sp["end_ms"] and sp["start_ms"] <= sp["representative_ms"] <= sp["end_ms"]):
            errs.append("%s: span 좌표 불변조건 위반" % c["candidate_id"])
        if c["run_id"] != fx["analysis_run"]["run_id"]:
            errs.append("%s: run_id 불일치" % c["candidate_id"])
        stale[c["candidate_id"]] = (sp["timeline_id"] == cur["timeline_id"] and sp["timeline_revision"] != cur["revision"])
        t = c.get("thumbnail_ref")
        if t is not None and not t.startswith("fr_"):
            errs.append("%s: thumbnail_ref가 FrameRef가 아님" % c["candidate_id"])
    if stale != fx["expected"]["stale_by_candidate"]:
        errs.append("stale 기대 %s ≠ %s" % (fx["expected"]["stale_by_candidate"], stale))
    ns = fx["not_stale_case"]
    stale2 = {c["candidate_id"]: c["span"]["timeline_revision"] != ns["current_timeline"]["revision"] for c in fx["candidates"]}
    if stale2 != ns["expected_stale_by_candidate"]:
        errs.append("not-stale 기대 %s ≠ %s" % (ns["expected_stale_by_candidate"], stale2))
    if fx["analysis_run"]["contract_version"] != "analysis-run-candidate-event/v1.1":
        errs.append("contract_version v1.1 아님")
    rec("semantic", not errs, "V5 candidate timeline_revision (fixture)", "; ".join(errs))

    errs = []
    for obj in parsed.get("contract-analysis-run-candidate-event.md", []):
        for c in obj.get("candidates", []) if isinstance(obj, dict) else []:
            if "timeline_revision" not in c["span"]:
                errs.append("계약 §2 예시 candidate에 timeline_revision 없음")
        if "timeline_id" in obj and "start_ms" in obj and "timeline_revision" not in obj:
            errs.append("계약 §4-1 span 예시에 timeline_revision 없음")
    rec("semantic", not errs, "V5 계약 본문 예시", "; ".join(errs))


# ══ V8. CALL-12 — 재판독 발주 kind·force_rerun ══════════════════════
REGISTERED_KINDS = {"COARSE_SEARCH", "PLATE_READ", "OVERLAY_TIME_READ"}


def cache_decision(job, existing_success):
    """contract-job-record-case-view.md A절 §7 `force_rerun` — 동일 (case_id, kind, input_fingerprint) +
    force_rerun=false + 기존 SUCCEEDED → cache hit. force_rerun=true → 새 실행."""
    key = (job["case_id"], job["kind"], job["input_fingerprint"])
    if not job["force_rerun"] and key in existing_success:
        return "cache_hit"
    return "run"


def reread_violations(job, original_job, existing_success, used_job_ids):
    """A절 §7 「재판독 발주 규칙」 + §10-1."""
    errs = []
    if job["kind"] not in REGISTERED_KINDS:
        errs.append("kind_not_registered: %s" % job["kind"])
    if job["kind"] != "PLATE_READ":
        errs.append("reread_kind_must_be_PLATE_READ")
    if job["job_id"] in used_job_ids:
        errs.append("job_id_reused")
    if cache_decision(job, existing_success) == "cache_hit":
        errs.append("cache_hit: force_rerun=false with same tuple")
    if not job["force_rerun"]:
        errs.append("force_rerun_must_be_true")
    same_tuple = (job["case_id"], job["kind"], job["input_fingerprint"]) == \
                 (original_job["case_id"], original_job["kind"], original_job["input_fingerprint"])
    if job["kind"] == "PLATE_READ" and not same_tuple:
        errs.append("fixture: 재판독 입력이 원판독과 다름 — 기본값(동일 입력) 시나리오가 아님")
    return errs


def check_v8():
    fx = load_fixture("v8-reread-force-rerun.json", FDIR2)
    o, r = fx["original"], fx["reread"]
    existing_success = {(o["job_record"]["case_id"], o["job_record"]["kind"], o["job_record"]["input_fingerprint"])}
    used = {o["job_record"]["job_id"]}
    errs = []
    # 원판독: abstain인데 SUCCEEDED (readout §9-5) → 같은 kind 재발주는 cache hit
    if not (o["plate_readout"]["abstained"] and o["readout_run"]["outcome"] == "SUCCEEDED"):
        errs.append("원판독 fixture가 abstain+SUCCEEDED가 아님")
    if fx["evidence_need"]["kind"] != "PLATE_REREAD":
        errs.append("Need kind가 PLATE_REREAD가 아님")
    # 재판독 발주
    errs += reread_violations(r["job_record"], o["job_record"], existing_success, used)
    # 새 execution → 새 ReadoutRun 정확히 1건, operation ↔ kind, 원 run과 다른 run_id
    rrs = [p["ref"] for p in r["job_execution"]["produced"] if is_ref(p, "readout_run")]
    if len(rrs) != 1 or rrs[0] != r["readout_run"]["run_id"]:
        errs.append("재판독 execution의 produced readout_run이 정확히 1건이 아니거나 불일치")
    if r["job_execution"]["job_id"] != r["job_record"]["job_id"]:
        errs.append("재판독 execution.job_id ≠ 재판독 job_id")
    if r["job_execution"]["attempt"] != 1:
        errs.append("재판독은 새 job이므로 attempt=1이어야")
    if r["readout_run"]["run_id"] == o["readout_run"]["run_id"]:
        errs.append("재판독 run_id가 원판독과 같음")
    if r["readout_run"]["operation"] != r["job_record"]["kind"]:
        errs.append("kind ↔ operation 불일치")
    if r["plate_readout"]["run_ref"] != {"kind": "readout_run", "ref": r["readout_run"]["run_id"]}:
        errs.append("재판독 결과 run_ref 불일치")
    # 원판독 불변
    if fx["original_after_reread"]["readout_run"] != o["readout_run"] or fx["original_after_reread"]["plate_readout"] != o["plate_readout"]:
        errs.append("원판독 ReadoutRun/결과가 재판독 후 바뀜")
    # 인프라 재시도는 같은 job_id, attempt 증가, 다른 execution
    ir = fx["infra_retry"]["job_execution"]
    if not (ir["job_id"] == o["job_record"]["job_id"] and ir["attempt"] == o["job_execution"]["attempt"] + 1
            and ir["execution_id"] != o["job_execution"]["execution_id"]):
        errs.append("인프라 재시도 fixture가 같은 job_id·attempt+1·새 execution이 아님")
    rec("semantic", not errs, "V8 reread force_rerun (fixture)", "; ".join(errs))
    for inv in fx["invalid"]:
        got = reread_violations(inv["job_record"], o["job_record"], existing_success, used)
        hit = any(inv["expect_violation"] in e for e in got)
        rec("semantic", hit, "V8 violation detected: %s" % inv["id"],
            "" if hit else "기대 위반 %s 미검출 (%s)" % (inv["expect_violation"], got))
    # 계약 본문: A절 §7에 규칙 등재, §13 미결 종결
    body = read("contract-job-record-case-view.md")
    errs = []
    if "재판독 발주 규칙" not in body or "`force_rerun=true`를 조건 없이" not in body:
        errs.append("A절 §7 재판독 발주 규칙 미등재")
    if "case Owner 결정 대기(CALL-12)." in body and "~~" not in body.split("case Owner 결정 대기(CALL-12).")[0][-200:]:
        errs.append("§13 CALL-12 미결 문구가 종결 표시 없이 남아 있음")
    rec("semantic", not errs, "V8 계약 본문 표기", "; ".join(errs))


# ══ V9. CALL-13 — AnalysisRun.usage_refs 파생값 vs 원장 run_ref ══════
def check_v9():
    """contract-usage-record.md §8-11·§8-12 · contract-analysis-run-candidate-event.md §3 usage_refs·§3-4."""
    fx = load_fixture("v9-usage-refs-derived.json", FDIR2)
    run = fx["analysis_run"]
    usages = {u["usage_id"]: u for u in fx["usage_records"]}
    errs = []
    ledger = sorted(uid for uid, u in usages.items()
                    if u["run_ref"] == {"kind": "analysis_run", "ref": run["run_id"]})
    derived = sorted(run["usage_refs"])
    if ledger != sorted(fx["expected"]["ledger_members_of_run"]):
        errs.append("원장 기준 소속 기대 %s ≠ %s" % (fx["expected"]["ledger_members_of_run"], ledger))
    if derived != sorted(fx["expected"]["derived_members_of_run"]):
        errs.append("파생값 기대 %s ≠ %s" % (fx["expected"]["derived_members_of_run"], derived))
    if ledger == derived:
        errs.append("fixture가 어긋난 상태를 재현하지 않음(파생 == 원장)")
    ledger_cost = sum(Decimal(usages[u]["cost"]["amount"]) for u in ledger)
    derived_cost = sum(Decimal(usages[u]["cost"]["amount"]) for u in derived)
    if ledger_cost != Decimal(fx["expected"]["ledger_total_cost"]):
        errs.append("원장 기준 합 %s ≠ 기대 %s" % (ledger_cost, fx["expected"]["ledger_total_cost"]))
    if derived_cost != Decimal(fx["expected"]["derived_total_cost"]):
        errs.append("파생 기준 합 %s ≠ 기대 %s" % (derived_cost, fx["expected"]["derived_total_cost"]))
    # usage_summary는 원장 기준 aggregate와 정합 (§3-4 · UsageRecord §8-7·8-12)
    if Decimal(run["usage_summary"]["total_cost"]["amount"]) != ledger_cost:
        errs.append("usage_summary.total_cost %s ≠ 원장 기준 %s" % (run["usage_summary"]["total_cost"]["amount"], ledger_cost))
    if Decimal(run["usage_summary"]["total_cost"]["amount"]) == derived_cost:
        errs.append("usage_summary가 파생값 기준으로 집계됨")
    # run_ref 모양·null 규칙 (§8-9·10)
    nulls = sorted(uid for uid, u in usages.items() if u["run_ref"] is None)
    if nulls != sorted(fx["expected"]["run_ref_null_only_for"]):
        errs.append("run_ref=null 기대 %s ≠ %s" % (fx["expected"]["run_ref_null_only_for"], nulls))
    for uid, u in usages.items():
        if u["run_ref"] is not None and not (is_ref(u["run_ref"]) and u["run_ref"]["kind"] in ("analysis_run", "readout_run")):
            errs.append("%s run_ref 모양 위반" % uid)
    rec("semantic", not errs, "V9 usage_refs 파생 vs 원장 (fixture)", "; ".join(errs))
    body = read("contract-analysis-run-candidate-event.md")
    errs = []
    if "조회 편의용 파생값" not in body:
        errs.append("AnalysisRun §3 usage_refs에 파생값 표기 없음")
    if "analysis-run-candidate-event/v1.1" not in body:
        errs.append("버전이 v1.1이 아님(버전 유지 결정 위반)")
    ub = read("contract-usage-record.md")
    if "12. (2026-09-08" not in ub:
        errs.append("UsageRecord §8-12 없음")
    # 2026-09-10: usage-record/v1.2로 의도적으로 올랐다(이슈 #33 Required-5/Required-7,
    # run_ref_reason 필드 추가 + row 생성 규칙 명확화 — case 통합 주도). v1.1 고정은 그 이전의
    # "버전 유지" 결정이었고 이번 필드 추가로 더 이상 유효하지 않다. v1.2 미만으로 되돌아가면 실패시킨다.
    if "usage-record/v1.2" not in ub:
        errs.append("UsageRecord 버전이 v1.2가 아님(2026-09-10 run_ref_reason 추가 반영 안 됨)")
    rec("semantic", not errs, "V9 계약 본문 표기", "; ".join(errs))


# ══ V11. CALL-15 — AnalysisScope time_ranges[].kind ═══════════════
ISO_TZ = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")


def resolve_kind(r):
    """contract-analysis-scope.md §7 — kind 부재 + start/end 존재 = ABSOLUTE."""
    if "kind" in r:
        return r["kind"]
    if "start" in r and "end" in r:
        return "ABSOLUTE"
    return None


def scope_violations(scope, timeline_status=None):
    """contract-analysis-scope.md §6·§7·§10-2·§10-7."""
    errs = []
    ranges = scope["time_ranges"]
    if not ranges:
        errs.append("time_ranges_empty")
        return errs
    kinds = set()
    trefs = set()
    for r in ranges:
        k = resolve_kind(r)
        if k not in ("ABSOLUTE", "TIMELINE_RELATIVE"):
            errs.append("kind_unresolvable: %r" % k)
            continue
        kinds.add(k)
        if k == "ABSOLUTE":
            if not (isinstance(r.get("start"), str) and isinstance(r.get("end"), str)
                    and ISO_TZ.match(r["start"]) and ISO_TZ.match(r["end"])):
                errs.append("absolute_iso8601_tz_required")
            elif r["start"] > r["end"]:
                errs.append("range_order: start > end")
            if timeline_status == "USABLE_RELATIVE_ONLY":
                errs.append("fake_absolute: relative-only timeline에 ABSOLUTE range (§10-7)")
        else:
            tr = r.get("timeline_ref")
            if not (isinstance(tr, dict) and isinstance(tr.get("timeline_id"), str) and tr["timeline_id"]
                    and isinstance(tr.get("revision"), int) and tr["revision"] >= 1):
                errs.append("timeline_ref_required")
            else:
                trefs.add((tr["timeline_id"], tr["revision"]))
            if not (isinstance(r.get("start_ms"), int) and isinstance(r.get("end_ms"), int)):
                errs.append("relative_ms_required")
            elif r["start_ms"] > r["end_ms"]:
                errs.append("range_order: start_ms > end_ms")
    if len(kinds) > 1:
        errs.append("mixed_kinds")
    if len(trefs) > 1:
        errs.append("timeline_ref_mismatch")
    return errs


def check_v11(parsed):
    fx = load_fixture("v11-analysis-scope-relative.json", FDIR2)
    for v in fx["valid"]:
        errs = scope_violations(v["scope"])
        got_kinds = {resolve_kind(r) for r in v["scope"]["time_ranges"]}
        if got_kinds != {v["expected_kind"]}:
            errs.append("kind 해석 기대 %s ≠ %s" % (v["expected_kind"], got_kinds))
        rec("semantic", not errs, "V11 %s" % v["id"], "; ".join(errs))
    for inv in fx["invalid"]:
        errs = scope_violations(inv["scope"], inv.get("timeline_status"))
        hit = any(inv["expect_violation"] in e for e in errs)
        rec("semantic", hit, "V11 violation detected: %s" % inv["id"],
            "" if hit else "기대 위반 %s 미검출 (%s)" % (inv["expect_violation"], errs))
    # 계약 §8 예시: 두 건 모두 유효, 1.1.0, kind 각각 ABSOLUTE / TIMELINE_RELATIVE
    errs = []
    seen = []
    for obj in parsed.get("contract-analysis-scope.md", []):
        if "scope_id" in obj and isinstance(obj.get("time_ranges"), list) and obj["scope_id"] != "string":
            v = scope_violations(obj)
            if v:
                errs.append("%s: %s" % (obj["scope_id"], v))
            if obj.get("contract_version") != "1.1.0":
                errs.append("%s: contract_version %s" % (obj["scope_id"], obj.get("contract_version")))
            seen.append({resolve_kind(r) for r in obj["time_ranges"]})
    if {"ABSOLUTE"} not in seen or {"TIMELINE_RELATIVE"} not in seen:
        errs.append("§8에 ABSOLUTE·TIMELINE_RELATIVE 예시가 각 1건 이상 있어야 함 (%s)" % seen)
    body = read("contract-analysis-scope.md")
    if "analysis-scope/1.1.0" not in body:
        errs.append("헤더 버전이 1.1.0이 아님")
    if "`RELATIVE`" in body and "TIMELINE_RELATIVE" not in body:
        errs.append("축약 표기 RELATIVE만 등재됨")
    rec("semantic", not errs, "V11 계약 본문 예시", "; ".join(errs))


# ══ V13. MissingRange.source_ref (span-resolution/v1.2) ═════════
# 규칙: contract-recording-timeline-asset-span.md §10.1·§10.2 · §23 SpanResolution 13·14
SOURCE_REF_KIND_BY_REASON = {
    "SOURCE_UNAVAILABLE": "source_asset",
    "STREAM_UNAVAILABLE": "media_stream",
}
SOURCE_REF_NULL_REASONS = ("TIMELINE_GAP", "OUT_OF_TIMELINE_RANGE")


def source_ref_violations(missing_ranges):
    """`source_ref` 키는 항상 존재하고 타입은 ContractRef|null. reason별 non-null/null과
    kind 대응(§10.2 표)을 본다. kind 문자열 공간은 contract-source-asset-media-stream.md §2.1."""
    errs = []
    for i, m in enumerate(missing_ranges):
        if "source_ref" not in m:
            errs.append("source_ref_key_missing: missing_ranges[%d]" % i)
            continue
        sref = m["source_ref"]
        reason = m.get("reason")
        if sref is not None and not is_ref(sref):
            errs.append("source_ref_shape: missing_ranges[%d] = %r" % (i, sref))
            continue
        if reason in SOURCE_REF_KIND_BY_REASON:
            if sref is None:
                errs.append("source_ref_required: %s인데 null" % reason)
            elif sref["kind"] != SOURCE_REF_KIND_BY_REASON[reason]:
                errs.append("source_ref_kind_mismatch: %s → %r (기대 %r)"
                            % (reason, sref["kind"], SOURCE_REF_KIND_BY_REASON[reason]))
        elif reason in SOURCE_REF_NULL_REASONS and sref is not None:
            errs.append("source_ref_must_be_null: %s인데 %r" % (reason, sref))
    return errs


def check_v13():
    """CALL-16 fixture — source_ref 타입·nullable 규칙."""
    fx = load_fixture("v13-missing-range-source-ref.json", FDIR2)
    for v in fx["valid"]:
        errs = span_violations(v["span_resolution"])
        rec("semantic", not errs, "V13 %s" % v["id"], "; ".join(errs))
    for inv in fx["invalid"]:
        errs = span_violations(inv["span_resolution"])
        hit = any(inv["expect_violation"] in e for e in errs)
        rec("semantic", hit, "V13 violation detected: %s" % inv["id"],
            "" if hit else "기대 위반 %s 미검출 (%s)" % (inv["expect_violation"], errs))
    # 계약 본문: §10 예시가 ContractRef이고 평문이 남아 있지 않다
    body = read("contract-recording-timeline-asset-span.md")
    errs = []
    if re.search(r'"source_ref"\s*:\s*"', body):
        errs.append("§8.1/§9/§10 예시에 평문 source_ref 잔존")
    if '"source_ref": null' not in body:
        errs.append("§10.2에 source_ref: null 예시 없음")
    if "SpanResolution 13" not in body and "13. (2026-09-08 · v1.2)" not in body:
        errs.append("§23에 13·14 불변조건 없음")
    rec("semantic", not errs, "V13 계약 본문 표기", "; ".join(errs))


# ══ V14. 자산 계층 ContractRef.kind · canonical AssetFacts ═══════
# 규칙: contract-source-asset-media-stream.md §2.1·§2.2·§3.4·§3.5·§6.1~§6.4
AVAILABILITY = ("AVAILABLE", "UNAVAILABLE", "UNKNOWN")
ASSET_FACTS_KEYS = ("asset_ref", "asset_kind", "derived_role", "byte_size", "availability",
                    "checked_at", "lineage", "duration_sec", "timeline_ref", "timeline_range")
OFFSET_AWARE = re.compile(r"(Z|[+-]\d{2}:\d{2})$")


def asset_facts_violations(af, kind_space, kind_map):
    errs = []
    for key in ASSET_FACTS_KEYS:
        if key not in af:
            errs.append("key_missing: %s" % key)
    if errs:
        return errs
    ar = af["asset_ref"]
    if not is_ref(ar):
        errs.append("asset_ref_shape: %r" % ar)
    elif ar["kind"] not in kind_space:
        errs.append("kind_not_in_value_space: %r" % ar["kind"])
    ak = af["asset_kind"]
    if ak not in kind_map:
        errs.append("asset_kind_not_in_enum: %r" % ak)
    elif is_ref(ar) and kind_map[ak] != ar["kind"]:
        errs.append("asset_kind_map_mismatch: %s ↔ %r (기대 %r)" % (ak, ar["kind"], kind_map[ak]))
    av = af["availability"]
    if av not in AVAILABILITY:
        errs.append("availability_not_in_enum: %r" % av)
    bs = af["byte_size"]
    if av == "AVAILABLE" and bs is None:
        errs.append("available_requires_byte_size")
    if av != "AVAILABLE" and bs == 0:
        errs.append("byte_size_faked_zero")
    if bs is not None and (not isinstance(bs, int) or bs < 0):
        errs.append("byte_size_shape: %r" % bs)
    ca = af["checked_at"]
    if not isinstance(ca, str) or not OFFSET_AWARE.search(ca):
        errs.append("checked_at_not_offset_aware: %r" % ca)
    tr, tref = af["timeline_range"], af["timeline_ref"]
    if (tr is None) != (tref is None):
        errs.append("timeline_pair: range=%r ref=%r" % (tr, tref))
    if tref is not None:
        if "revision" not in tref:
            errs.append("timeline_revision_missing")
        if "timeline_id" not in tref:
            errs.append("timeline_id_missing")
    if tr is not None and not ("start_sec" in tr and "end_sec" in tr):
        errs.append("timeline_range_not_seconds: %r" % tr)
    lin = af["lineage"]
    if not isinstance(lin, list):
        errs.append("lineage_shape")
    else:
        for e in lin:
            if not is_ref(e):
                errs.append("lineage_entry_shape: %r" % e)
            elif e["kind"] not in kind_space:
                errs.append("kind_not_in_value_space: %r" % e["kind"])
        # §6.3 — 파생 자산은 원본 계열(source_asset/external_source)까지 평탄화
        if ak in ("ANALYSIS_SOURCE", "INCIDENT_CLIP", "DERIVED_ASSET"):
            if not any(is_ref(e) and e["kind"] in ("source_asset", "external_source") for e in lin):
                errs.append("lineage_missing_source_origin")
    return errs


def check_v14():
    """CALL-17 + Consumer Review fixture — kind 표기와 AssetFacts 불변조건."""
    fx = load_fixture("v14-asset-facts-kind.json", FDIR2)
    space = set(fx["kind_value_space"])
    kmap = fx["asset_kind_map"]
    for v in fx["valid"]:
        errs = asset_facts_violations(v["asset_facts"], space, kmap)
        rec("semantic", not errs, "V14 %s" % v["id"], "; ".join(errs))
    for inv in fx["invalid"]:
        errs = asset_facts_violations(inv["asset_facts"], space, kmap)
        hit = any(inv["expect_violation"] in e for e in errs)
        rec("semantic", hit, "V14 violation detected: %s" % inv["id"],
            "" if hit else "기대 위반 %s 미검출 (%s)" % (inv["expect_violation"], errs))
    # 계약 본문: 값 공간·대응표가 §2.1·§6.2에 있고 대문자 자산 kind가 남아 있지 않다
    errs = []
    doc1 = read("contract-source-asset-media-stream.md")
    for k in sorted(space):
        if "`%s`" % k not in doc1:
            errs.append("§2.1 값 공간에 %s 없음" % k)
    for ak, k in kmap.items():
        if "| `%s` | `%s` |" % (ak, k) not in doc1:
            errs.append("§6.2 대응표에 %s ↔ %s 없음" % (ak, k))
    UPPER = ('"kind": "SOURCE_ASSET"', '"kind": "MEDIA_STREAM"', '"kind": "FRAME"',
             '"kind": "EXTERNAL_SOURCE"', '"kind": "INCIDENT_CLIP"', '"kind": "ANALYSIS_SOURCE"',
             '"kind": "DERIVED_ASSET"', '"kind": "REMOTE_COPY"')
    for name in ("contract-source-asset-media-stream.md", "contract-analysis-source-derived.md"):
        body = read(name)
        for u in UPPER:
            if u in body:
                errs.append("%s에 대문자 자산 kind 잔존: %s" % (name, u))
    rec("semantic", not errs, "V14 계약 본문 표기", "; ".join(errs))


# ══ V15. IncidentClip provenance · 사건 구간 canonical ref ═══════
# 규칙: contract-analysis-source-derived.md §6.2·§6.3·§6.4·§6.8·§6.9
CANONICAL_SPAN_KEYS = ("sequence", "timeline_range", "source_asset_ref", "media_stream_ref", "source_range")
FLAT_SPAN_KEYS = ("source_start_sec", "source_end_sec", "timeline_start_ms", "timeline_end_ms",
                  "start_ms", "end_ms")
INTERVAL_KINDS = ("incident_clip", "candidate_event")


def sec_interval_errs(obj, where):
    if not isinstance(obj, dict):
        return ["%s_shape" % where]
    if "start_sec" not in obj or "end_sec" not in obj:
        return ["asset_span_not_canonical: %s가 초 단위 {start_sec,end_sec}가 아님" % where]
    return []


def incident_clip_violations(clip):
    errs = []
    prov = clip.get("source_provenance") or {}
    tref = prov.get("timeline_ref")
    if not isinstance(tref, dict) or "timeline_id" not in tref:
        errs.append("provenance_timeline_ref_missing")
    elif "revision" not in tref:
        errs.append("provenance_revision_missing")
    errs += sec_interval_errs(prov.get("requested_range"), "requested_range")
    spans = prov.get("asset_spans")
    if not isinstance(spans, list) or not spans:
        errs.append("asset_spans_missing")
        return errs
    pieces = []
    for i, sp in enumerate(spans):
        for bad in FLAT_SPAN_KEYS:
            if bad in sp:
                errs.append("asset_span_not_canonical: asset_spans[%d].%s (평탄화 표기)" % (i, bad))
        if "sequence" not in sp:
            errs.append("asset_span_sequence_missing: asset_spans[%d]" % i)
        for key in CANONICAL_SPAN_KEYS:
            if key != "sequence" and key not in sp:
                errs.append("asset_span_not_canonical: asset_spans[%d].%s 없음" % (i, key))
        if "source_span_ref" in sp or "span_ref" in sp:
            errs.append("synthetic_span_ref: asset_spans[%d]" % i)
        errs += ["%s (asset_spans[%d])" % (e, i) for e in sec_interval_errs(sp.get("timeline_range"), "timeline_range")]
        errs += ["%s (asset_spans[%d])" % (e, i) for e in sec_interval_errs(sp.get("source_range"), "source_range")]
        tr = sp.get("timeline_range")
        if isinstance(tr, dict) and "start_sec" in tr and "end_sec" in tr:
            pieces.append((tr["start_sec"], tr["end_sec"]))
    # §6.3 — span 합집합이 실제 materialize된 timeline_range를 설명한다
    mat = clip.get("timeline_range")
    if isinstance(mat, dict) and ("start_ms" in mat or "end_ms" in mat):
        errs.append("asset_span_not_canonical: timeline_range가 ms 단위")
    elif pieces and isinstance(mat, dict) and "start_sec" in mat:
        lo, hi = mat["start_sec"], mat["end_sec"]
        pts = sorted(set([lo, hi] + [p for pr in pieces for p in pr]))
        for a, b in zip(pts, pts[1:]):
            if a < lo or b > hi:
                continue
            if not any(x <= a and b <= y for x, y in pieces):
                errs.append("span_coverage: [%s,%s) 미설명" % (a, b))
    return errs


def readout_input_violations(input_ref):
    errs = []
    if "span_ref" in input_ref:
        errs.append("span_ref_removed: v1.2에서 삭제된 필드가 남아 있음")
    if not input_ref.get("incident_clip_ref"):
        errs.append("incident_clip_ref_required")
    return errs


def interval_ref_violations(ref):
    if not is_ref(ref):
        return ["interval_ref_shape: %r" % ref]
    if ref["kind"] not in INTERVAL_KINDS:
        return ["interval_kind_not_allowed: %r (허용 %s)" % (ref["kind"], list(INTERVAL_KINDS))]
    return []


def check_v15():
    """CALL-18 fixture — AssetSpan identity 없음 · clip provenance · readout 입력 · evidence interval."""
    fx = load_fixture("v15-incident-clip-provenance.json", FDIR2)
    for v in fx["valid"]:
        errs = incident_clip_violations(v["incident_clip"])
        rec("semantic", not errs, "V15 %s" % v["id"], "; ".join(errs))
    for inv in fx["invalid"]:
        errs = incident_clip_violations(inv["incident_clip"])
        hit = any(inv["expect_violation"] in e for e in errs)
        rec("semantic", hit, "V15 violation detected: %s" % inv["id"],
            "" if hit else "기대 위반 %s 미검출 (%s)" % (inv["expect_violation"], errs))
    ri = fx["readout_inputs"]
    for v in ri["valid"]:
        errs = readout_input_violations(v["input_ref"])
        rec("semantic", not errs, "V15 readout input %s" % v["id"], "; ".join(errs))
    for inv in ri["invalid"]:
        errs = readout_input_violations(inv["input_ref"])
        hit = any(inv["expect_violation"] in e for e in errs)
        rec("semantic", hit, "V15 readout violation: %s" % inv["id"],
            "" if hit else "기대 위반 %s 미검출 (%s)" % (inv["expect_violation"], errs))
    ei = fx["evidence_interval_refs"]
    for v in ei["valid"]:
        errs = interval_ref_violations(v["ref"])
        rec("semantic", not errs, "V15 interval ref %s" % v["id"], "; ".join(errs))
    for inv in ei["invalid"]:
        errs = interval_ref_violations(inv["ref"])
        hit = any(inv["expect_violation"] in e for e in errs)
        rec("semantic", hit, "V15 interval violation: %s" % inv["id"],
            "" if hit else "기대 위반 %s 미검출 (%s)" % (inv["expect_violation"], errs))
    # 계약 본문: 계약 예시의 clip provenance와 readout input이 같은 규칙을 만족한다
    errs = []
    doc2 = read("contract-analysis-source-derived.md")
    n = 0
    for lang, body in FENCE.findall(doc2):
        body = body.strip()
        if '"contract": "IncidentClip"' not in body:
            continue
        try:
            n += 1
            errs += incident_clip_violations(json.loads(body))
        except json.JSONDecodeError as exc:
            errs.append("IncidentClip 예시 파싱 실패: %s" % exc)
    if n == 0:
        errs.append("§6.2에서 IncidentClip 예시를 찾지 못함")
    plate = read("contract-plate-overlay-readout.md")
    for lang, body in FENCE.findall(plate):
        body = body.strip()
        if not body.startswith("{"):
            continue
        try:
            obj = json.loads(body)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "input_ref" in obj:
            errs += readout_input_violations(obj["input_ref"])
    if "plate-readout/v1.2" not in plate or "overlay-time-readout/v1.2" not in plate:
        errs.append("plate/overlay 헤더 버전이 v1.2가 아님")
    needs = read("contract-evidence-record-needs.md")
    if '"kind":"asset_span"' in needs or '"kind": "asset_span"' in needs:
        errs.append("EvidenceNeeds 예시에 asset_span ref 잔존")
    if "candidate_event" not in needs:
        errs.append("EvidenceNeeds §8.3에 candidate_event fallback 없음")
    rec("semantic", not errs, "V15 계약 본문 대조", "; ".join(errs))



# ══ V6. 문서 — 상대 링크 · Pending 잔존 문구 · 계약-ADR 짝 ══════════
LINK = re.compile(r"`([A-Za-z0-9_./-]+\.(?:md|py))`")
ADIR = os.path.join(CDIR, "adr")
# 2026-09-08: 자산 계약 2건이 Draft로 존재한다 — 작성 대기 파일은 없다
KNOWN_PENDING_FILES = set()


MDIR = os.path.join(ROOT, "docs", "management")
PREFIXES = ("../", "./", "adr/", "docs/", "scripts/", "modules/", "contracts/", "architecture/", "management/")


def resolve_link(p, base):
    """문서 표기 관례별 해석. 명시적 경로 접두어가 있는 것과 계약/ADR/감사 파일명만 검사한다 —
    `product-spec.md`·`ownership.md`·`decisions/failure-taxonomy.md` 같은 산문 속 일반 표기는
    문서 라우터(`docs/README.md`)가 위치를 알려주는 관례라 검사 대상이 아니다."""
    if p.startswith("docs/") or p.startswith("scripts/"):
        return os.path.join(ROOT, p)
    if p.startswith("modules/") or p.startswith("architecture/") or p.startswith("management/"):
        return os.path.join(ROOT, "docs", p)
    if p.startswith("contracts/"):
        return os.path.join(CDIR, p[len("contracts/"):])
    if p.startswith("../") or p.startswith("./") or p.startswith("adr/"):
        return os.path.normpath(os.path.join(base, p))
    if "/" in p:
        return None   # 모듈 폴더 상대 표기 등 — 산문
    if p.startswith("contract-consistency-audit"):
        return os.path.join(MDIR, p)
    if p.startswith("contract-"):
        return os.path.join(CDIR, p)
    if p.startswith("adr-"):
        return os.path.join(ADIR, p)
    if p == "README.md":
        return os.path.join(base, p)
    return None


def check_v6():
    for rel in TOUCHED:
        base = os.path.dirname(os.path.join(CDIR, rel))
        missing, pending = [], []
        for m in LINK.finditer(read(rel)):
            p = m.group(1)
            if os.path.basename(p) in KNOWN_PENDING_FILES:
                pending.append(os.path.basename(p))
                continue
            cand = resolve_link(p, base)
            if cand is not None and not os.path.exists(cand):
                missing.append(p)
        rec("structure", not missing, "V6 링크 %s" % rel, ", ".join(sorted(set(missing))))
        if pending:
            rec("structure", True, "V6 NOTE %s" % rel, "작성 대기 계약 참조: %s" % ", ".join(sorted(set(pending))))
    # 종결된 항목의 옛 Pending 머리말이 계약 본문에 남아 있지 않은가
    stale_phrases = ["통합 Pending B0", "Pending B01/B02", "Pending B03/B05", "Pending B09", "Pending B08", "Pending B06~B09"]
    for name in sorted(os.listdir(CDIR)):
        if not name.startswith("contract-"):
            continue
        body = read(name)
        hits = [p for p in stale_phrases if p in body]
        rec("structure", not hits, "V6 Pending 잔존 %s" % name, ", ".join(hits))
    for fdir in (FDIR, FDIR2):
        for f in sorted(os.listdir(fdir)):
            try:
                load_fixture(f, fdir)
                rec("json", True, "V0 fixture %s/%s" % (os.path.basename(fdir), f))
            except Exception as exc:  # noqa: BLE001
                rec("json", False, "V0 fixture %s/%s" % (os.path.basename(fdir), f), str(exc))
    # 계약-ADR 짝 (contracts/README.md 규칙: contract-<slug>.md ↔ adr/adr-<slug>.md)
    adrs = set(os.listdir(ADIR))
    for name in sorted(os.listdir(CDIR)):
        if name.startswith("contract-") and name.endswith(".md"):
            slug = name[len("contract-"):-len(".md")]
            ok = "adr-%s.md" % slug in adrs
            rec("structure", ok, "V12 짝 ADR %s" % name, "" if ok else "adr/adr-%s.md 없음" % slug)
    # 자산 계약 2건의 상태 표기 — 2026-09-08 Consumer Review 종결로 Accepted 전환(ADR §4.10)
    for name in ("contract-source-asset-media-stream.md", "contract-analysis-source-derived.md"):
        head = read(name)[:2000]
        errs = []
        if "`Final — Accepted`" not in head:
            errs.append("Status가 `Final — Accepted`가 아님")
        if "**Accepted:** `2026-09-08`" not in head:
            errs.append("Accepted 날짜 표기 없음")
        if "Draft — Consumer Review 대기" in head:
            errs.append("옛 Draft Status 문구 잔존")
        rec("structure", not errs, "V12 Accepted 상태 %s" % name, "; ".join(errs))
    for name in ("adr/adr-source-asset-media-stream.md", "adr/adr-analysis-source-derived.md"):
        head = read(name)[:1200]
        errs = []
        if "Consumer Review pending" in head:
            errs.append("Status에 Consumer Review pending 잔존")
        if "**Status:** Accepted" not in head:
            errs.append("Status가 Accepted가 아님")
        rec("structure", not errs, "V12 ADR Accepted 상태 %s" % name, "; ".join(errs))


def main():
    parsed = check_v0()
    check_v1(parsed)
    check_v2()
    check_v3(parsed)
    check_v4(parsed)
    check_v5(parsed)
    check_v8()
    check_v9()
    check_v10()
    check_v11(parsed)
    check_v13()
    check_v14()
    check_v15()
    check_v6()

    total_fail = 0
    for bucket, title in (("structure", "문서 구조"), ("json", "JSON 파싱"), ("semantic", "의미 fixture")):
        rows = results[bucket]
        fails = [r for r in rows if not r[0]]
        total_fail += len(fails)
        print("== %s: %s (%d 검사, %d 실패)" % (title, "PASS" if not fails else "FAIL", len(rows), len(fails)))
        for ok, name, detail in rows:
            if not ok or " NOTE " in name:
                print("   [%s] %s — %s" % ("FAIL" if not ok else "NOTE", name, detail))
    print()
    print("이 결과는 계약 규칙 대비 fixture 정합성이다. 구현 통합 PASS·E2E PASS·Owner 수락을 뜻하지 않는다.")
    return 1 if total_fail else 0


if __name__ == "__main__":
    sys.exit(main())
