#!/usr/bin/env python3
"""계약 예시·fixture 의미 검사 — 2026-09-07 접합부 종결 ADR의 검증 조건 V0~V6.

규칙은 여기서 정하지 않는다. 각 검사가 옮겨 온 규칙의 원문은 함수 docstring이 가리킨다.
  - 결정 원장  → docs/architecture/contracts/adr/adr-data-contract-call-closure-2026-09-07.md §7
  - fixture    → docs/architecture/contracts/fixtures/call-closure-2026-09-07/

이 스크립트의 PASS는 「계약 규칙을 코드로 옮겼을 때 fixture가 그 규칙을 만족한다」는 뜻이다.
구현 통합·E2E·Owner 수락을 증명하지 않는다.

사용:
    python scripts/check_contract_fixtures.py
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CDIR = os.path.join(ROOT, "docs", "architecture", "contracts")
FDIR = os.path.join(CDIR, "fixtures", "call-closure-2026-09-07")

# 이번 회차에 수정한 문서. V0(JSON 파싱)·V6(링크) 대상.
TOUCHED = [
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


def load_fixture(name):
    with open(os.path.join(FDIR, name), encoding="utf-8") as fh:
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


# ══ V4. B06 — SpanResolution 완전성 ═════════════════════════════
def span_violations(sr):
    """contract-recording-timeline-asset-span.md §23 SpanResolution 1·6·7."""
    errs = []
    req = (sr["requested_range"]["start_sec"], sr["requested_range"]["end_sec"])
    pieces = [(s["timeline_range"]["start_sec"], s["timeline_range"]["end_sec"]) for s in sr["spans"]]
    pieces += [(m["timeline_range"]["start_sec"], m["timeline_range"]["end_sec"]) for m in sr["missing_ranges"]]
    for a, b in pieces:
        if a < req[0] or b > req[1]:
            errs.append("range_outside_request")
    # coverage: 합집합 == 요청 범위
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
    st = sr["status"]
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


# ══ V6. 문서 — 상대 링크 · Pending 잔존 문구 ══════════════════════
LINK = re.compile(r"`([A-Za-z0-9_./-]+\.(?:md|py))`")
ADIR = os.path.join(CDIR, "adr")
# Owner가 작성 예정이라고 명시한 계약 — 없는 것이 현재 상태다 (ADR §8.2)
KNOWN_PENDING_FILES = {"contract-source-asset-media-stream.md", "contract-analysis-source-derived.md"}


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
    for f in os.listdir(FDIR):
        try:
            load_fixture(f)
            rec("json", True, "V0 fixture %s" % f)
        except Exception as exc:  # noqa: BLE001
            rec("json", False, "V0 fixture %s" % f, str(exc))


def main():
    parsed = check_v0()
    check_v1(parsed)
    check_v2()
    check_v3(parsed)
    check_v4(parsed)
    check_v5(parsed)
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
