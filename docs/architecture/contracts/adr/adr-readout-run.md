# ADR — `ReadoutRun` Data Contract

**Status:** Accepted
**Decider:** 신유민 (`readout` Owner)
**Date:** 2026-09-06
**Contract:** `../contract-readout-run.md`

---

## 1. Context

v4 §4-모듈3 ③이 `read_plate -> ReadoutRun, PlateReadout`으로 반환값을 둘로 명시하고, `modules/readout/decisions/failure-taxonomy.md`가 「`ReadoutRun`에 stage + kind로 기록한다」고 기록 장소까지 지정했다. **그런데 `ReadoutRun` 계약이 없었다.**

결과로 taxonomy 이름 5개(`PLATE_TARGET_ASSOCIATION` · `PLATE_DETECTION` · `PLATE_RECOGNITION` · `OVERLAY_VALIDATION` · `INFRA`)가 계약 어디에도 등장하지 않았다. 막히는 것이 셋이었다 — `eval`의 readout 실패 분류 집계, **A-2 챌린저 개방 판정**(`modules/search/decisions/challenger-policy.md`가 「실패 분류 통계가 특정 카테고리를 가리킬 때만」으로 조건을 걸었다), `Abstention Recall` 지표의 분모.

정합성 검수 Pass 3에서 F-27(BLOCK)으로 잡혔고 CALL-6으로 넘어갔다.

## 2. Decision

**(b) `AnalysisRun`처럼 별도 계약을 만든다.**

최소 필드는 PM 제안(=`AnalysisRun` §3에서 그대로 가져온 것)을 그대로 수락했다 — `run_id` · `operation` · `outcome` · `failure{kind,code}` · `usage_refs` · `started_at` · `ended_at`.

**`failure.kind`의 값 집합은 계약에 복제하지 않고** `modules/readout/decisions/failure-taxonomy.md`를 포인터로 가리킨다. `contract-analysis-run-candidate-event.md`가 Search taxonomy에 대해 이미 같은 방식이다.

**추가 요구 (신유민):** `ReadoutRun`과 그 실행이 만든 `PlateReadout`/`OverlayTimeReadout`이 **`run_id` 기준으로 연결됨을 계약에 명시**할 것 → 계약 §5로 반영했다.

## 3. 기각한 안

**(a) `PlateReadout`/`OverlayTimeReadout` 안에 run 필드를 얹는다** — 기각. **실행 도중 완전히 실패해 Readout 결과가 생성되지 않은 경우 실패 기록을 남길 곳이 없어진다**(신유민). 실패 통계를 내려는 목적 자체가 무너진다.

**(c) MVP에서는 실패 통계를 내지 않는다** — 기각. `eval`의 실패 분류 집계, A-2 챌린저 개방 판단, Abstention Recall 측정이 전부 막힌다.

## 4. 함께 확정된 것

`contract-plate-overlay-readout.md`의 기존 내용은 **Canonical Contract v1 승격에 동의**한다(신유민). 다만 readout 계약 세트는 `ReadoutRun`과 결과 연결 관계까지 들어가야 완성으로 본다.

## 5. Consumer Review

- 김대원(`eval`) — 확인 대상. `failure.kind`별 집계와 run 단위 분모가 이 계약으로 가능해진다
- 서어진(`search`) — `AnalysisRun`이 선례이며 값 공간이 분리돼 있음을 확인

## 6. 미결

`PARTIAL` 판정 기준(readout Technical Spec) · retry/timeout 정책(runtime 구현 세부). 계약 closure를 막지 않는다.
