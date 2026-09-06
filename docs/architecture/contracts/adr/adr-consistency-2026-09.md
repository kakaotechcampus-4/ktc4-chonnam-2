# ADR-C1: 계약 정합성 보정 — 2026-09

**Status:** Accepted
**Decider:** 김준영 (PM · 문서 일관성 소유자 — `management/cross-cutting-decisions.md` B-4)
**Date:** 2026-09-05
**Scope:** `docs/architecture/contracts/` 12건 · `docs/architecture/module-architecture.md` · `docs/management/ownership.md`

---

## 1. Context

Canonical Contract v1 확정(2026-09-05 10:00)에 앞서 Product / Architecture / Ownership / 계약 문서 사이의 **용어·규칙 충돌**을 검수했다. 검수 계획과 전체 결과표는 PM 내부 문서에 있고, 이 ADR은 **PM이 담당자 호출 없이 확정한 보정만** 기록한다.

보정 기준은 다음 셋을 전부 만족하는 경우로 한정했다.

1. 이미 수락된 ADR·계약 본문·v4 §5-1로 **정답이 유일하게 결정된다**
2. 필드 의미·enum 값 집합·모듈 경계·의존 방향을 **바꾸지 않는다**
3. 또는 PM 자신의 소유 영역이다 (문서 일관성 B-4 · `evidence` · `common/runtime`)

하나라도 걸리는 항목은 보정하지 않고 담당자 호출로 넘겼다(§4).

**수락된 생산자 ADR의 본문은 고치지 않았다.** ADR은 그 Owner의 결정 기록이므로, 보정 사실은 전부 이 문서에 모았다.

---

## 2. Decision — 보정한 것

### C1-1. 위반유형 enum을 v4 §3-5로 통일했다 — BLOCK

v4 §3-5(L407)가 baseline 4종을 고정한다.

```
SIGNAL / CENTER_LINE_CROSSING / SOLID_LINE_LANE_CHANGE / MOTORCYCLE_HELMET_NON_USE
```

3번째 값이 계약마다 갈려 있었다.

| 계약 | 값 | 판정 |
| --- | --- | --- |
| `contract-analysis-scope` (case 생산) | `SOLID_LINE_LANE_CHANGE` | v4 일치 |
| `contract-observation` 예시 | `SOLID_LINE_LANE_CHANGE` | v4 일치 |
| `contract-visual-evidence` (search 생산) | `LANE_CHANGE` | **불일치** |
| `contract-analysis-run-candidate-event` 예시 | `LANE_CHANGE` | **불일치** |

`case`가 `SOLID_LINE_LANE_CHANGE`를 보내고 `search`가 `LANE_CHANGE`를 돌려주는 구조였다. 목데이터 통합에서 `case → search → case` 왕복이 바로 깨진다.

**결정:** `contract-visual-evidence.md`(L70 예시 · L150 enum 목록)와 `contract-analysis-run-candidate-event.md`(L94 예시)의 `LANE_CHANGE`를 `SOLID_LINE_LANE_CHANGE`로 고쳤다.

**근거:** v4가 enum을 소유하고(`docs/README.md` 우선순위 2), `contract-analysis-scope`가 「v4 baseline enum으로 고정한다」고 명시했다. 의미로도 `LANE_CHANGE` 단독은 합법적 진로변경을 포함해 위반유형으로 쓸 수 없고, `product-spec.md` §6의 「진로변경(백색 실선 침범)」과도 어긋난다.

**ADR 본문까지 정리 완료 (2026-09-05, PM 지시).** 처음에는 「수락된 ADR 본문은 고치지 않는다」는 원칙 때문에 계약만 고치고 ADR은 뒀으나, 그러면 같은 값이 두 이름으로 남아 다음 사람이 어느 쪽이 맞는지 다시 판단해야 한다. PM 판단으로 ADR 본문도 맞췄다.

| ADR | 수정 |
| --- | --- |
| `adr-visual-evidence.md` | 3곳 |
| `adr-analysis-scope.md` | 1곳 — Final 계약은 `SOLID_LINE_LANE_CHANGE`인데 자기 ADR만 옛 이름이었다 |

**두 ADR 모두 `Status` 바로 아래에 수정 고지를 넣었다.** 수락된 ADR을 조용히 고치면 기록으로서의 가치가 사라진다. 고지에 「결정 내용은 바뀌지 않았고 같은 값의 표기만 v4에 맞췄다」를 명시했다 — 지원 범위 4종과 세 번째 항목이 「진로변경(백색 실선 침범)」인 것은 그대로다.

### C1-2. 계약 문서에서 ①~⑫ 번호를 제거하고 포인터로 대체했다 — WARN

계약 문서의 번호가 v4 §5-1과 한 칸씩 밀려 있었다. v4는 ④AnalysisScope ⑤AnalysisRun ⑥VisualEvidence ⑦PlateReadout ⑧TimeResolution ⑨EvidenceRecord인데, 문서는 ③AnalysisScope / "Contract 4"AnalysisRun / "Contract 5"VisualEvidence / ⑥PlateReadout / ⑦TimeResolution / ⑧EvidenceRecord였다. ①Observation과 ⑩RequirementReport만 일치했고 ⑩은 우연이다.

원인은 v4 ②·③(recording 자산 계층 8개 타입)을 1건으로 세는 옛 번호를 생산자들이 쓴 것으로 보인다.

**결정:** 계약 문서 제목·헤더에서 번호를 전부 빼고, 헤더에 포인터 한 줄만 둔다.

```
**Architecture Contract:** v4 §5-1 ⑧
```

**근거:** 번호는 v4 §5-1이 단독 소유한다. 20개 문서에 번호를 복제하면 또 밀린다(`docs/README.md` 「같은 결정을 두 곳에 두지 않는다」). 파일명에도 번호를 넣지 않았다 — 파일명이 미해결 충돌을 못박으면 안 된다.

### C1-3. `CaseView`의 「부록」 표기를 걷어냈다 — WARN

v4 §5 머리말이 「`CaseView`를 부록에서 Core Contract로 올린다」고 명시하고 ⑪로 승격했는데, 계약 문서 제목과 절 이름이 승격 전 상태(`부록 JobRecord / CaseView`, `부록-A`, `부록-B`)였다.

**결정:** 문서 제목을 `Final Data Contract — JobRecord (Job Intent) + CaseView v1`로, 절을 `A. JobRecord (Job Intent)` / `B. CaseView`로 고쳤다. 「부록-A / 부록-B」가 ADR 당시 표기이며 계약의 위상은 Core Contract임을 문서 머리에 명시했다.

**하지 않은 것:** `CaseView`의 enum(stage 5종 · progress.state 4종 · notices.severity 3종)을 v4에 복제하지 않았다. v4 §5는 의미 수준이고 「세부 필드·enum·serialization은 별도 Data Contract에서 확정한다」가 원문이다.

### C1-4. 헤더 표기를 12건에 통일했다 — WARN

`Status` / `Architecture Contract` / `Contract Version` / `Related ADR` 4개를 모든 계약에 맞췄다. 이전에는 `Status`가 `Final — Accepted`(6) / `Final`(1) / 없음(3)이었고 `Contract Version`은 `visual-evidence/v1.0` vs `observation/v1`로 갈렸으며 `Related ADR`은 4건에만 있었다. Notion export 잔재(잘린 페이지 제목이 본문 제목과 중복)도 제거했다.

**처음에는 Status 값을 바꾸지 않았다** — 수락 여부를 모르는 상태에서 `Accepted`로 올리는 것은 표기 정리가 아니라 사실 조작이기 때문이다. 이후 각 문서의 종결 증거를 확인해 3건을 채웠다(C1-13).

### C1-5. `ownership.md`의 `JobRecord` 역할 배정을 ADR에 맞췄다 — BLOCK

§3-김준영 ①에 「공통 기반: DB Queue · **Worker lifecycle(`JobRecord`)**」로 적혀 있었다. `JobRecord` ADR(부록-A §6)은 `JobRecord`=Job Intent=`case` 소유, 실행 lifecycle=`JobExecution`=`common/runtime` 소유로 재정의했으므로 **이름이 반대로 배정된 상태**였다.

**결정:** 「Job execution lifecycle(`JobExecution`)」로 고쳤다. §3-김준영 ⑤ 산출물의 `common/runtime` 스키마(`JobRecord`·`UsageRecord`)도 `JobExecution`·`UsageRecord`로 고쳤다.

### C1-6. `JobExecution` 구현 담당 배정을 `ownership.md`에 반영했다 — 회의 확정안 기록

`adr/adr-job-record-case-view.md` §4-5·§13-1이 「2026-09-04 백엔드 회의에서 `JobExecution`을 runtime/common 공통 영역으로 설계하되 주요 Owner는 김준영, **구현 담당은 정철원**으로 확정」이라고 기록했으나 `ownership.md`에는 없었다.

**결정:** 회의 확정안이므로 담당자 호출 없이 4곳에 반영했다 — §1-1 정철원 부 담당 · §3-정철원 ①⑤ · §5 부하 표 · §6 「작업 발주 vs 실행」.

**함께 넣은 것:** §3-정철원 ⑤와 §5에 「`resolve_span` 목 응답을 낸 다음」이라는 순서 조건을 명시했다. `recording`은 §5에서 초반 투입이 가장 큰 모듈이고, §3-정철원 마지막 문단이 「`resolve_span`과 `read_file_facts`의 목 응답을 가장 먼저 내놓으면 `search`·`case` Owner가 즉시 병행 출발한다」고 못박아 놨다. 순서를 적지 않으면 그 출발 조건이 밀린다. **이건 회의 확정안이 아니라 PM 판단이므로 정철원이 이견을 낼 수 있다.**

### C1-7. `VisualEvidence` 헤더의 Consumer 표기를 v4 경로로 고쳤다 — WARN

헤더가 `Consumers: 김준영(evidence), 신유민(readout)`로 `case`를 생략했다. v4 §5-1 ⑥은 Direct Consumer를 `case`로 두고 `evidence`/`readout`을 projection으로 둔다.

**표기 축약으로 판정했다.** 본문 L273-274가 「`evidence`, `case`, `readout`은 raw confidence에 임의의 정책 threshold를 만들지 않는다 / 사용자 표시가 필요하면 `case`가 `CaseView`용 상태로 projection한다」고 명시하므로 실제 의존 방향은 v4와 같다. 헤더만 정리하고 서어진 호출은 하지 않았다.

**같은 형태이지만 당시 보정하지 않은 것:** `contract-plate-overlay-readout`은 본문에 `case` 경유 서술이 없어 판정할 수 없었다 → Pass 2에서 C1-9로 닫았다.

> **기록 정정.** 이 항목을 처음 쓸 때 헤더를 고쳤다고 적었으나 실제로는 제목만 바뀌고 `Consumers:` 줄은 그대로였다. Pass 2에서 확인해 `case` — 유소연 (Direct) → `evidence`·`readout` (projection)으로 실제 반영했다.

### C1-8. 없던 계약 2건을 초안으로 작성했다 — BLOCK 해소 (PM 소유 영역)

v4 §5-1 ⑫의 `JobExecution`과 `UsageRecord`에 계약 문서가 없었다. 둘 다 `common/runtime`(김준영) 소유이므로 PM이 작성했다.

| 신규 | 근거로 삼은 것 | 새로 정한 것 |
| --- | --- | --- |
| `contract-job-execution.md` | `JobRecord` ADR 부록-A §6·§7·§13이 status 5값 · `CANCELLED` 미포함 · 캐시 semantics · 이관 필드 목록을 이미 고정 | `execution_id` 신설 · 시각 3필드 · `cost`를 금액이 아니라 `usage_refs`로 표현 (문서 §10에 3건 명시) |
| `contract-usage-record.md` | v4 §4-모듈2 ⑥(정규화 사용량 + pricing context · raw payload 분리) · §4-모듈7 ⑤(비용 분모 이중 보존) · `AnalysisRun` 계약 L36·L119·L187-194 | `execution_ref` · `case_id` 직접 보유 · `provider_label`/`operation` · `latency_ms` (문서 §9에 4건 명시) |

**처음에는 둘 다 `Draft — PM 작성 · Consumer Review 대기`로 뒀다가 `Final — Accepted`로 닫았다.** 소비자 리뷰 없이 닫은 것이므로 §3에 비용으로 기록했다. 새로 정한 항목만 각 문서 §9/§10에 모아 리뷰 범위를 좁혔고, 2026-09-06 공지 시점까지 이견이 없었다. 짝 ADR은 `adr-job-execution.md` · `adr-usage-record.md`다(2026-09-06 작성 — `check_boundaries.py`의 `adr-pair` NOTE 해소).

두 문서 모두 미결을 채우지 않았다 — retry/backoff/lease/heartbeat 임계값, 통화 고정 여부, `purge_case`가 `UsageRecord`를 지우는지는 미결로 남겼다.

### C1-13. 수락 표기가 누락된 계약 3건의 헤더를 채웠다 — WARN

`Accepted` 표기가 없던 4건 중 **3건은 결정이 이미 닫혀 있고 헤더 필드만 누락된 상태**였다. 각 문서가 본문에서 스스로 종결을 선언하고 있으며, 이미 `Final — Accepted`로 표기된 6건과 같은 종류의 증거다.

| 계약 | 문서 안의 종결 증거 |
| --- | --- |
| `analysis-scope` | 머리말 「ADR-003 확정 내용을 반영한 최종 계약… 아래는 잠금(locked) 스키마」 · §5 「확정 Contract 스키마 (JSON, locked)」 · §11 Draft→Final 확정표 |
| `job-record-case-view` | §11 Consumer Review 반영 요약 — 신유민 「수정요청 → 반영 완료」 · 김대원 「승인」 · 김준영 「최종 승인」. 3인 리뷰 종료 |
| `recording-timeline-asset-span` | §25 「Pair Review 반영 최종 결정표」 · §26 「Final Contract 한 문장 정의」 |

**결정:** `Status`를 `Final — Accepted`로, `Accepted`를 **`2026-09-04`**(나머지 6건과 같은 계약 회차)로 채우고, 각 문서의 종결 증거를 `수락 근거`에 명시했다. **없던 결정을 만든 게 아니라 문서가 이미 주장하는 사실을 헤더 필드로 옮긴 것**이며, Notion export에서 잘린 제목·중복 H1을 정리한 것과 같은 성격의 보정이다.

근거를 헤더에 남겼으므로 Owner가 「이건 아직 아니다」라고 하면 그 자리에서 되돌릴 수 있다.

**채우지 않은 1건:** `plate-overlay-readout`은 본문이 `Final Contract 후보`로 **명시적 미수락**을 선언했고, 신유민이 「`frame_ref` 형식이 확정된 뒤 참조를 반영하고 `Accepted`로 전환하는 것이 맞다」고 답했다. 조건이 남아 있으므로 그대로 뒀다 — 이건 표기 누락이 아니라 실제 미결이다.

### C1-9. `PlateReadout` Consumer 표기를 `case` 경유로 고쳤다 — WARN

`contract-plate-overlay-readout` 헤더가 `Consumer: evidence(김준영), eval(김대원)`로 `case`를 생략했다. 생산자 문서에는 판정 근거가 없었지만 **소비자 쪽에 있었다.**

`contract-evidence-record-needs.md` §「책임 경계」 — 「`evidence`는 다른 모듈을 직접 호출하지 않는다. `EvidenceNeeds`를 반환하고, 실제 Job orchestration은 `case`가 소유한다.」 여기에 `ownership.md` §3-김준영 ⑦(「남에게 일을 시키지 않는다」)과 v4 §2 원칙 6(유일한 지휘자는 `case`)을 합치면 `case` 경유가 유일한 해석이다. `readout`에는 orchestration 역할이 없으므로 push 경로도 없다.

**결정:** 표기 축약으로 판정하고 헤더를 `case` — 유소연 (Direct) → `evidence` (projection) · `eval`로 고쳤다. 판정 근거를 헤더 주석으로 남겼다.

**생산자 확인 완료 (2026-09-05).** 신유민(`readout`) — 「(a)다. `readout` 결과물은 `case`가 받아서 `evidence`에 입력으로 전달한다. `Consumer: evidence`는 최종 소비자를 줄여 쓴 표기이며, `evidence`가 `readout`을 직접 호출하거나 읽는 설계가 아니다.」 소비자 쪽 근거로 내린 판정과 일치한다. **이 항목은 완전히 닫혔다.**

### C1-10. `AnalysisScope`의 `eval`을 Consumer에서 fixture Producer로 옮겼다 — WARN

헤더가 `Consumers: search · eval(fixture)`였다. v4 §5-1 ④는 **Producer / Owner를 「case / eval fixture」**로, Consumer를 `search`만으로 둔다. `ownership.md` §7-③도 「제품과 채점기가 같은 형식이어야 한다」를 이유로 `eval`을 합의 범위에 넣었다 — `eval`은 scope를 **써서 넣는** 쪽이다.

**결정:** `Producer / Owner: case · eval(fixture 생산)` / `Consumers: search`로 고쳤다. 김대원에게 통보한다 — `eval`이 `AnalysisScope`를 생산할 수 있어야 candidate-less classification fixture가 돌아간다(v4 §5-4).

### C1-11. `JobRecord`의 1차 Consumer에 `common/runtime`을 넣었다 — WARN

헤더가 `Consumer: web(신유민) — CaseView 경유 간접 소비`뿐이었다. **실행 주체가 빠졌다.** v4 §5-1 ⑫의 Direct Consumer는 `runtime / case / eval aggregation`이고, ADR 부록-A §6이 「실행 상태는 별도 `JobExecution` 레코드로 분리하며 runtime/common이 소유한다」로 확정했다. 발주 의도를 받아 실행하는 쪽이 1차 소비자다.

**결정:** `Consumer: common/runtime(실행이 이 의도를 받는다) · eval(발주/재실행 집계) · web(CaseView 경유 간접)`으로 고쳤다.

### C1-12. v4에 미등재 계약 2건을 확인 대상으로 표시했다 — NOTE

v4 §5-1 계약 목록에 없는데 다른 계약이 이미 참조하는 타입이 둘 나왔다.

- **`CorrectionRecord`** — v4 §4-모듈5 ⑤ 소유 데이터 표에는 `case` 소유로 있으나 §5-1 계약 목록에 없다. `contract-time-resolution`(L173·L188·L309)이 `input_ref`로 직접 참조하고 `contract-evidence-record-needs`(L499)가 provenance로 참조한다.
- **`ReadoutRun`** — v4 §4-모듈3 ③이 `read_plate`/`read_overlay_time`의 반환값으로 명시하고 `modules/readout/decisions/failure-taxonomy.md`가 기록 장소로 지정했으나 계약이 없다.

**결정:** §5-1 아래에 확인 필요 주석만 달았다. **목록에 행을 임의로 추가하지 않았다** — 계약 목록에 행을 넣는 것은 「이 계약을 만들어야 한다」는 선언이고 둘 다 Owner 소유(case / readout)다. → §4-e, §4-f

---

## 3. Consequences

**긍정:** `case → search` 위반유형 왕복이 통한다(C1-1). 계약 12건이 같은 헤더를 갖고 v4 §5-1로 역추적된다(C1-2·C1-4). 번호 드리프트가 구조적으로 재발하지 않는다. queue·비용 목 데이터를 만들 근거가 생겼다(C1-8).

**비용:** 수락된 ADR 2건의 본문을 고쳤다(C1-1). 결정이 아니라 표기만 바꿨고 수정 고지를 남겼지만, **ADR을 사후에 손대는 선례가 생긴 것은 사실이다.** 그래서 `adr/README.md`에 허용 범위를 좁혀 적었다 — 표기 보정만, 고지 필수. 신규 계약 2건(`JobExecution`·`UsageRecord`)은 소비자 리뷰 없이 Final로 닫았다(C1-8).

---

## 4. 보정하지 않은 것 — 담당자 호출로 넘김

PM이 닫지 않았다. 상세는 각 호출 카드에 있다.

> **전부 회신됐다 (2026-09-06).** 아래는 호출 당시의 기록이며, 각 항목의 처리 결과는 **§6**에 있다. 항목 서술 자체는 고치지 않는다 — 호출 시점의 판단을 남겨 두는 것이 이 절의 목적이다.
>
> | 항목 | 결과 |
> | --- | --- |
> | (a) `CaseView` 출처·정보 상태 | ✅ 종결 — §6 R-1 (유소연·신유민) |
> | (b) `PlateReadout` 소비 경로 | ✅ 종결 (2026-09-05, C1-9) |
> | (c) 수락 표기 4건 | ✅ **전부 종결** — 마지막 1건 `plate-overlay-readout`이 §6 R-5로 `Final — Accepted` 전환 |
> | (d) recording 자산 계층 | 🟡 **부분 종결** — ref 형식과 계약 분해는 확정(§6 R-5), 계약 파일 2건은 정철원 작성 대기 |
> | (e) `case` 소유 계약 미결 4건 | ✅ 종결 — §6 R-2·R-3 (유소연) |
> | (f) `ReadoutRun` 계약 없음 | ✅ 종결 — §6 R-4 (신유민) |
>
> **새로 나온 것이 하나 있었고 같은 날 닫았다** — `CaseView.requirements`가 어느 scope의 `RequirementReport`를 projection하는지 미지정. R-2의 (1)(2)를 함께 반영하면서 드러났다. **WARN으로 재판정하고 PM이 확정했다(§6 R-7).** 호출 카드는 발송하지 않았다.
>
> **결과: 정합성 검수가 연 항목 중 미해결은 0건이다.** 남은 것은 (d)의 recording 계약 2건이며, 그건 충돌이 아니라 **아직 작성되지 않은 산출물**이고 Owner가 작성을 맡았다.

**(a) `CaseView`가 출처와 정보 상태를 못 내려준다 — BLOCK.** `plate_display`/`event_time_display`/`location_display`가 `value`+`needs_review` 두 필드뿐이다. 출처 필드가 없어 `product-spec.md` §7 「출처를 표시한다」가 화면에서 깨지고, `needs_review` boolean으로는 `core-user-flow.md` §3-1의 정보 상태 5종(`AI 추정`·`출처 확인됨`·`사용자 확인됨`·`확인 필요`·`알 수 없음`)이 나오지 않는다. `user_edited`가 record 단위라 필드별 「사용자 확인됨」도 만들 수 없다. → 유소연(`CaseView` 소유) · 신유민 · 김준영

**(b) `PlateReadout`을 `evidence`가 직접 받는가 — ✅ 종결(2026-09-05).** 신유민이 `case` 경유로 확인했다. C1-9 참조. 남은 것은 `frame_ref` 확정 후 이 계약을 `Accepted`로 전환하는 것뿐이며 그건 §4-d(정철원)에 달려 있다.

**(c) 수락 표기 4건 → ✅ 3건 종결, 1건 남음.** 3건은 헤더 필드 누락이었고 C1-13으로 채웠다. 남은 것은 `plate-overlay-readout` 하나이며 `frame_ref` 확정(§4-d)에 걸려 있다. → 신유민(전환) · 정철원(`frame_ref`)

**(e) `case` 소유 계약의 미결 4건 — BLOCK.** ① `CaseView.stage=READY`가 v4 §3-6의 세 상태 중 무엇인지 미지정 — `ownership.md` §7-④가 「통합 전 `case` Owner가 확인한다(Data Contract 항목)」로 남긴 미결이 Data Contract에서도 닫히지 않았다. ② `requirements.readiness`가 `string`으로 열려 있다. ③ **`USER_REVIEWED`를 `CaseView`가 표현할 수 없다** — v4 §4-모듈5 ⑤가 `case` 소유로 배정했는데 stage 5값에도 다른 필드에도 없다. ④ `CorrectionRecord` 계약이 없다(C1-12). → 유소연 · 김준영 · 신유민

**(f) `ReadoutRun` 계약 없음 — BLOCK.** readout failure taxonomy 5개 이름(`PLATE_TARGET_ASSOCIATION`·`PLATE_DETECTION`·`PLATE_RECOGNITION`·`OVERLAY_VALIDATION`·`INFRA`)이 계약 12건 어디에도 없다. 기록할 계약이 없기 때문이다. `eval`의 실패 분류 집계와 **A-2 챌린저 개방 판정**(`challenger-policy.md`가 「실패 분류 통계가 특정 카테고리를 가리킬 때만」으로 조건을 걸었다)이 막힌다. `search`는 같은 문제를 `AnalysisRun`으로 이미 계약화했다. → 신유민 · 김대원

**(d) recording 자산 계층 계약 공백 — BLOCK.** v4 ②의 `SourceAsset`/`MediaStream`과 ③ 전체(`AnalysisSource`/`RemoteCopy`/`IncidentClip`/`DerivedAsset`)에 스키마가 없다. `frame_ref` 형식도 없다. ~~공용 Mock Pack v1을 직접 막는다.~~ 실측 기반이고 `recording` 단독 소유이므로 PM이 쓸 수 없다. → 정철원

> **정정 (2026-09-06).** 「Mock Pack v1을 직접 막는다」는 **호출 시점에는 맞았고 지금은 아니다.** 당시엔 `frame_ref` 형식조차 없었는데 §6 R-5로 ref 형식 7종이 확정됐다. 그 뒤 실제 의존을 전수 확인한 결과:
> - 다른 계약들은 이 타입들을 **opaque `*_ref` 문자열로만 참조**한다. 필드를 dereference하는 계약이 없다(`SourceAsset`/`MediaStream`이 타입 이름으로 등장하는 것은 `contract-analysis-run-candidate-event.md`의 서술문 2줄뿐이며 스키마가 아니다).
> - 소비자가 실제로 읽는 recording 표면 — `RecordingTimeline` · `AssetSpan` · **`SpanResolution`**(`resolve_span` 응답) · `TimeSourceCandidate` — 은 `contract-recording-timeline-asset-span.md`에 **이미 Final로 있다.**
>
> 남은 공백은 각 타입의 **내부 필드**이고 그건 `recording`이 자기 안에서 쓰는 값이다. 목데이터용 ref 규약은 `architecture/mock-pack-v1-refs.md`로 분리했다 — **`contracts/` 밖에 두고, 필드를 쓰지 않고, 정철원 계약이 나오면 폐기한다.** `check_boundaries.py`의 coverage NOTE 5개는 **초록으로 만들지 않고 남겨 둔다.** 계약이 없다는 사실을 자동 점검이 계속 말해야 한다.

---

## 6. 담당자 회신 반영 — 2026-09-06

**§2의 `C1-*`과 성격이 다르므로 번호를 잇지 않는다.** `C1-*`은 「PM이 담당자 호출 **없이** 확정한 보정」이고, 아래 `R-*`는 **호출 카드에 답이 와서 그 결정을 반영한 것**이다. 결정의 주체가 PM이 아니다.

호출 카드 5장 전부 회신됐다. 각 항목의 답변자와 선택을 그대로 남긴다.

### R-1. `CaseView`에 정보 상태·출처 필드 — CALL-1 종결

**회신:** 유소연(`case`, `CaseView` 소유자) 「A안을 수용한다. `info_state` 값에 **`INFO_` 접두어를 붙인다**.」 · 신유민(`web`, 소비자) 「A안 채택. `source_label_key`는 display별로 둔다.」 · 김준영 이견 없음.

**접두어를 붙인 근거(유소연 원문 요지):** `info_state`를 `EvidenceValue`에서 파생하는 코드가 `Observation.status`와 `info_state`를 동시에 다루는 유일한 지점이고, `obs.status==NEEDS_REVIEW`를 그대로 `info_state=NEEDS_REVIEW`로 매핑하는 실수가 실제로 일어날 수 있다. 접두어 비용은 거의 없고 리뷰에서 안 잡히는 버그를 막는다. **PM이 §8 축 D의 BLOCK 기준으로 제기했지만 판단은 파생 코드를 짜는 `case`에 넘겼고, 소유자가 이렇게 닫았다.**

**반영:** `contract-job-record-case-view.md` B절 §5·§6·§7·§10 (`case-view/v1.1`).

**함께 필요했던 PM 보정 — `evidence` 쪽 작업이 없다는 카드의 전제가 틀렸다.**

CALL-1은 「`EvidenceValue.source`·`user_corrected`가 이미 있으므로 `evidence` 작업은 없다」로 보냈다. 반영 단계에서 확인하니 **그 전제가 성립하지 않았다.** `source.kind`가 열린 `namespaced string`이고 관찰/추론 분류가 어디에도 없어서, 「관찰가능 출처→`INFO_SOURCE_VERIFIED` / 추론성 출처→`INFO_AI_ESTIMATED`」를 `case`가 kind 문자열을 해석해서 판단해야 하는 상태였다. 그건 `case`가 정책 판단을 하는 것이라 v4 §3 정책 이관표와 「`case`는 authoritative 판단을 재계산하지 않는다」에 걸린다.

그래서 `EvidenceValue.source`에 **`observability`(`OBSERVED`/`INFERRED`)와 `label_key`**를 추가했다(`evidence-record/v1.1`). `evidence`는 PM 소유이므로 트랙 1이고, 필드 추가라 기존 소비를 깨지 않는다. **소비자 `case`에 통보 대상이다.** 파생 규칙 5줄은 `CaseView` B절 §7에 고정했다.

### R-2. `case` 소유 계약 미결 3건 — CALL-5 (1)(2)(3) 종결

**회신:** 유소연(`case`)

| 항목 | 답 |
| --- | --- |
| (1) `stage=READY` 정의 — BLOCK | PM 추천안 채택. **「`PACKAGE_READY` 파생 gate가 성립한 시점」** |
| (2) `requirements.readiness` 값 공간 — WARN | A안 채택. `RequirementReport.overall`의 projection이며 타입을 `PASS\|WARN\|BLOCK\|UNKNOWN`으로 좁힌다 |
| (3) `USER_REVIEWED` 통로 — BLOCK | (b) 채택. `CaseView`에 **`user_reviewed: boolean`** 추가 |

(1)은 `ownership.md` §7-④가 「통합 전 `case` Owner가 확인한다」로 넘긴 미결이 Data Contract에서도 안 닫혀 있던 것이고, 이번에 닫혔다. (3)으로 v4 §11-4의 「`USER_REVIEWED`를 case가 소유하는 것이 자연스러운가」 체크박스도 종결됐다.

**(2)가 PM 검수가 놓친 위반을 하나 잡았다.** 기존 `CaseView` §8 예시의 `"readiness": "4/5"`는 `contract-requirement-report-package.md` §4 「`4/5`, `80% ready` 같은 단순 readiness score를 Contract에 두지 않는다」를 정면으로 위반하고 있었다. **Pass 3 축 D(동일 개념 다른 값 공간)가 잡았어야 하는 항목이며 놓쳤다.** 예시까지 대조하지 않은 것이 원인이다.

**반영:** 같은 파일 B절. 불변조건 3의 「완료 상태」도 §5.2 gate와 같은 문구인 `readiness ∈ {PASS, WARN}`으로 못박았다.

### R-3. `CorrectionRecord` 계약 신설 — CALL-5 (4) 종결

**회신:** 유소연(`case`) 「가능」 + 8필드 최소 스키마 제시.

**반영:** `../contract-correction-record.md` 신규 · `adr-correction-record.md` 신규 · v4 §5-1 **⑬** 등재.

`selection_rev`를 넣은 것이 이 스키마의 핵심이다 — `contract-time-resolution.md` §불변조건 9의 「선택 provenance에서 해당 `CorrectionRecord`까지 추적 가능」이 그 필드 없이는 성립하지 않는다.

**Status는 `Draft — Consumer Review 대기`로 뒀다.** 작성자 본인이 「정식 Consumer Review 이전 상태」라고 §11에 명시했으므로 `Final`로 올리지 않았다. 나머지 12건과 다른 유일한 계약이다.

**PM 보정 2건(표기 수준):** ① `ContractRef.kind = correction_record` 명시 — `contract-time-resolution.md` §5가 이미 그 표기를 쓰고 있어 정답이 유일했다 ② Consumer 각주에 `eval` 경로 명시 — `product-spec.md` §7이 「익명화한 뒤에만 재사용」으로 경로를 갖고 있다. `eval`을 Consumer 본문에 넣지는 않았다(직접 읽지 않고 익명화 copy를 통한다).

**미결은 채우지 않았다** — `target_field` 값 공간 · 동일 필드 다건 수정 시 현재 유효값 판정 · 실패한 수정의 레코드 생성 여부.

### R-4. `ReadoutRun` 계약 신설 — CALL-6 종결

**회신:** 신유민(`readout`) **(b) 별도 계약 채택.** 「`PlateReadout`과 `OverlayTimeReadout`은 관찰 결과를 담는 계약이고, `ReadoutRun`은 실행의 성공·일부 성공·실패와 실패 단계를 기록하는 실행 계약으로 분리하는 것이 맞다.」 최소 필드 7개는 PM 제안 그대로 수락.

**(a)를 기각한 이유(신유민 원문 요지):** 결과 계약 안에 실행 정보를 넣으면 **실행 도중 완전히 실패해 Readout 결과가 생성되지 않은 경우 실패 기록을 남길 수 없다.** (c)는 `eval` 실패 분류 집계·A-2 챌린저 개방 판단·Abstention Recall 측정을 막으므로 선택하지 않았다.

**추가 요구:** `ReadoutRun`과 결과 계약을 `run_id` 기준으로 연결하는 관계를 명시할 것 → 계약 §5와 `contract-plate-overlay-readout.md`에 양쪽 다 반영했다.

**반영:** `../contract-readout-run.md` 신규 · `adr-readout-run.md` 신규 · v4 §5-1 ⑦행에 추가 · v4 §4-모듈3 ③에 포인터.

`failure.kind` 값 집합은 계약에 복제하지 않고 `modules/readout/decisions/failure-taxonomy.md`를 가리킨다 — `contract-analysis-run-candidate-event.md`가 Search taxonomy에 쓰는 방식과 같다.

### R-5. recording 자산 계층 — CALL-4 부분 종결

**회신:** 정철원(`recording`) **(b) 최소 스키마를 recording에서 확정하여 제공한다.** 확인 결과 해당 타입들은 v4에서 소유와 책임 경계까지만 정해져 있고 Data Contract가 없는 것이 맞다.

**ref 형식 — PM 잠정안이 기각됐다.** 전부 opaque identifier로 통일한다(`sa_`/`ms_`/`fr_`/`as_`/`rc_`/`clip_`/`da_`). PM이 Mock Pack 잠정안으로 제안한 `ms_<source_asset_id>_<role>`은 **Stream identity와 role을 결합**하므로 정식 형식으로 쓰지 않고, `source_asset_ref`와 `role`을 `MediaStream`의 별도 필드로 보존한다. `frame_ref`도 `fr_<media_stream_id>@<offset_ms>`처럼 위치를 ID에 인코딩하지 않고 `media_stream_ref + source offset`을 `FrameRef` 계약 필드로 추적한다. video/audio stream 종류와 `FRONT`/`REAR`/`UNKNOWN` camera role도 분리한다.

**계약 2건으로 분해:** `contract-source-asset-media-stream.md`(`SourceAsset`·`MediaStream`·`FrameRef`) · `contract-analysis-source-derived.md`(`AnalysisSource`·`RemoteCopy`·`IncidentClip`·`DerivedAsset`). **정철원이 작성한다 — PM이 쓰지 않는다.**

**미결은 임의 확정하지 않는다** — upload 방식 · proxy profile 값 · retention 일수 · provider별 `RemoteCopy` delete 방식. ref/provenance/lifecycle 의미까지만 고정한다.

**반영:** v4 §5-3 주석 갱신. 계약 파일 2건은 정철원 작성 대기.

**함께 닫힌 것 2건**

- `contract-recording-timeline-asset-span.md` — 정철원 「Pair Review 피드백 반영이 완료되었으므로 **Accepted 전환에 동의**한다」. C1-13에서 PM이 종결 증거로 채운 헤더가 Owner 확인을 받았다.
- `contract-plate-overlay-readout.md` — **`Final — Accepted`로 전환.** 전환 조건 둘이 모두 해소됐다: `frame_ref` 형식 확정(정철원, 위) + Owner 수락(신유민 「기존 내용은 Canonical Contract v1 승격에 동의합니다」). 계약의 `frame_ref` 예시를 opaque 형식으로 고치고 형식 절을 추가했다. **§4-(c)의 마지막 1건이 닫혔고, 이로써 계약 12건이 전부 수락 표기를 갖는다.**

### R-6. `Final Data Contract v1.1` 문서는 반영하지 않았다

CALL-1·CALL-5 회신과 함께 `Final Data Contract v1.1 — 부록-A JobRecord + 부록-B CaseView` 문서가 별도로 왔다. **위 R-1·R-2의 결정만 반영하고 그 문서 자체는 병합하지 않았다.**

그 문서는 **closure 이전 판본**을 베이스로 작성됐다. 현재 계약(`contract-job-record-case-view.md`)은 그 위에 9/4~9/5의 closure와 PM 보정이 얹힌 상태다. 그대로 병합하면 **이미 Accepted된 결정 12개가 되돌아간다.** 문서의 「v1.1 변경 이력」은 추가 7건만 적고 있어 **회귀는 이력에 나타나지 않는다** — 의도한 삭제가 아니라 베이스 차이가 따라온 것이다(경위는 §7).

되돌아가는 것 중 BLOCK 4건만 적는다.

| 되돌아가는 것 | 레포 현재 (Accepted) | 왜 BLOCK |
| --- | --- | --- |
| `force_rerun` 캐시 semantics | `SUCCEEDED` 결과만 재사용, `FAILED`/`STALE`은 재실행 | `contract-job-execution.md` §10 불변조건 6과 충돌. v4 §12 RT8 종결 근거가 사라진다 |
| `JobRecord` Consumer | `common/runtime` · `eval` · `web`(간접) | C1-11을 되돌린다. v4 §5-1 ⑫와 불일치 |
| `CaseView.evidence`의 `case_type_display`·`report_type_display`·`violation_display`·`preview_ref` | 4필드 존재 | 위반유형·신고유형 표시가 화면에서 사라진다 |
| `running_jobs`의 `label_key`·`status` | `label_key` 필수 + fallback, `status: PENDING\|RUNNING` | `contract-job-execution.md` §7 매핑표가 이미 확정한 것을 `[작성 필요]`로 되돌린다 |

이 밖에 WARN 8건이 「확정 → [작성 필요]/제안」 방향으로 후퇴한다 — `progress[].state` · `notices[].severity` · `package.*` 타입 · `manifest_summary.range` nullable · `requested_at` · §11의 김준영 최종 승인 표기 · A절 §12의 `JobExecution` 구현 담당 기록 · 헤더 4종과 「부록」 표기(C1-2·C1-3·C1-4).

**판정:** 회귀는 작성자의 의견이 아니라 **베이스 착오**다. 답변자 의견 우선 원칙은 **회신 내용**에 적용하고, 회신이 건드리지 않은 v1 closure는 전부 유지한다. `case-view/v1.1`은 이 기준으로 PM이 병합했다.

**`case_type_display`·`report_type_display`·`violation_display`·`preview_ref`는 유지로 PM이 임의 확정했다.** 이 넷은 상태 후퇴가 아니라 **필드 삭제**라 위 회귀들과 성격이 다르고, 의도 여부를 따로 묻지 않았다.

**왜 묻지 않고 닫았나.** 정합성 검수가 열려 있으면 Mock Pack v1과 목데이터 통합이 통째로 대기한다. 확인을 한 번 더 돌리는 비용이 유지의 위험보다 크다. 유지 쪽 근거도 명확하다 — `product-spec.md` §7이 4종 유형 표시를 불변 경계로 두고, `core-user-flow.md` §12~§14가 그 값들을 화면에서 쓴다. **삭제가 의도였다면 그건 제품 경계를 바꾸는 결정이므로 어차피 별도 호출 대상이다.**

되돌리는 비용도 낮다 — 필드 4개를 빼는 것뿐이고 다른 계약이 참조하지 않는다. 유소연이 삭제 의도였다고 하면 그때 뺀다.

### R-7. `CaseView.requirements`의 scope — PM 확정 (호출하지 않음)

R-2의 (1)(2)를 함께 반영하면서 드러난 항목이다. **회신 내용이 아니라 회신을 반영해서 생긴 후속 항목**이므로 R-1~R-6과 성격이 다르다.

**문제.** `contract-requirement-report-package.md` §5는 케이스 하나에 `RequirementReport`를 **둘** 둔다(`scope=EVIDENCE` · `scope=FINAL_PACKAGE`). `CaseView.requirements`는 scope 없는 단일 객체다. `readiness`가 free string이던 동안엔 모호함이 숨어 있었는데, `overall`의 projection으로 타입을 좁히고 `stage=READY`를 `PACKAGE_READY` gate로 정의하자 「어느 report인가」를 답해야 했다.

**등급을 BLOCK에서 WARN으로 내렸다.** 처음 BLOCK으로 적었으나 §3의 기준(「④ 목데이터 통합에서 두 모듈이 다르게 구현하면 깨진다」)에 맞지 않는다.

- `case`가 생산하고 `web`은 **표시만** 한다. web은 scope로 판단하지 않으므로 **handshake가 깨지지 않는다**
- 목데이터도 `readiness` 한 줄이면 돌아간다
- 증상이 나오는 시점은 두 report가 동시에 존재하는 **신고 꾸러미 단계** 하나다 — 값이 잘못 보이는 문제이지 통합이 멈추는 문제가 아니다

**결정: `requirements.scope: EVIDENCE | FINAL_PACKAGE` 추가. PM이 확정했고 호출 카드를 보내지 않았다.**

`CaseView`는 유소연 소유라 원칙적으로 트랙 2지만, 아래 셋을 근거로 C1-13과 같은 방식(**근거를 문서에 남기고 「이견 시 되돌린다」**)으로 닫았다.

1. **정답 후보가 셋뿐이고 우열이 명확하다** — 필드 추가(a) / 객체 분리(b) / 규칙 고정(c). (a)가 `contract-requirement-report-package.md` §5의 gate 정의와 1:1이고 필드 하나로 끝난다. (b)는 대부분의 stage에서 한쪽이 null이라 web 분기만 늘고, (c)는 `stage`와 `readiness`가 서로를 참조하게 된다
2. **기존 소비를 깨지 않는다.** 필드 추가이며 `scope`를 무시하는 코드도 그대로 동작한다
3. **되돌리는 비용이 한 줄이다.** 다른 계약이 이 필드를 참조하지 않는다

**projection 규칙은 `RequirementReport` 쪽(PM 소유)에 뒀다** — `contract-requirement-report-package.md` §5.2-1. `FINAL_PACKAGE` scope report가 존재하면 그것을, 없으면 `EVIDENCE` scope를, 둘 다 없으면 `requirements=null`. `CaseView`에는 값 공간과 불변조건만 두고 규칙을 복제하지 않았다.

**반영:** `contract-job-record-case-view.md` B절 §5·§6·§7·§10-3·§10-9·§12 · `contract-requirement-report-package.md` §5.2-1. 작성해 둔 `secret/calls/CALL-7`은 **발송하지 않고 결정 기록으로 남긴다.**

유소연에게는 호출이 아니라 **통보**로 나간다. 이견이 있으면 그 자리에서 되돌린다.

---

## 7. 이번 회차에서 드러난 프로세스 결함

**R-6의 원인은 문서 접근이 아니다.** 확인된 것과 PM 추측을 나눠 적는다.

**확인된 사실**

- **closure가 반영된 Final은 노션 팀 공간에 올라가 있었다.** 「담당자가 최신본을 볼 수 없었다」는 사실이 아니다.
- 돌아온 v1.1 문서의 「변경 이력」은 **추가 7건만** 적고 있다. **되돌아간 12건은 이력에 없다.** 문서만 봐서는 회귀가 보이지 않는다.

**PM 추측 — 작성자 확인 전이다**

- 작성자가 **개인적으로 보관하던 이전 사본**을 베이스로 작업했고, PM이 닫아 둔 미결이 그 사본에는 열린 채로 남아 있었을 것이다.
- 되돌린 것이 의도가 아니라 **베이스 차이가 자동으로 따라온 것**일 것이다. 변경 이력에 회귀가 한 줄도 없다는 점이 근거다.

> **2026-09-06 확인 요청을 보냈고 회신 전이다.** 「의도적으로 다시 오픈한 것인지, 과거 문서를 베이스로 작업하면서 발생한 것인지」를 물었다. **회신이 오면 이 절을 갱신한다.** 그 전까지 위 두 줄은 추측이며, 아래 재발 방지 항목은 추측이 틀려도 유효한 것만 적었다.

**어느 한쪽의 과실로 보기 어렵고, 그렇게 기록하지 않는다.** 결과적으로 손실도 없다 — 검토 단계에서 잡혔고, 검토 단계는 그러라고 있다. 다만 재발 방지를 위해 **양쪽에서 각각 한 가지씩** 짚는다.

| 어디 | 무엇 | 왜 그게 결정적인가 |
| --- | --- | --- |
| 작성자 쪽 | **문서 전체를 교체하는 형태로 돌려줬고, 어느 판본을 베이스로 삼았는지 적지 않았다** | 델타로 왔으면 회귀가 애초에 생기지 않는다. 전체 교체는 「적지 않은 것까지 함께 바뀐다」 |
| PM 쪽 | **미결을 닫은 사실을 공지하지 않았다** | 9/5 전체 공지는 번호 제거·문서 위치·`Accepted` 표기만 알렸다. `progress.state`·`notices.severity`·`running_jobs.label_key`·`package.*` 타입이 닫혔다는 것은 어디에도 고지되지 않았다. 소유자가 자기 계약의 미결이 닫힌 줄 모르는 상태를 만든 것은 PM이다 |

**「개인 사본으로 작업한 것」 자체는 심각한 문제가 아니다.** 심각해지는 조건은 하나뿐이다 — **베이스를 밝히지 않은 채 전체를 교체하는 것.** 개인 사본을 쓰더라도 「무엇을 무엇에서 바꿨다」가 적혀 있으면 이번 회귀는 나오지 않았다.

**규칙으로 고정한다.**

1. **호출 카드는 결정만 받는다. 레포 파일 수정은 PM이 한다.** 카드 §「정해지면 반영되는 곳」에 담당자 이름을 적지 않는다 — 반영 주체는 항상 PM이고, 그 절은 「PM이 어디를 고칠 것인가」의 목록이다. `calls/CALL-1` §5가 「B절 §5 스키마·§6 필드 정의 — 유소연」으로 배정하고 「v1.1」이라는 이름까지 준 것이 전체 교체를 유도했다.
2. **계약 문서를 통째로 돌려주지 않는다.** 답은 「어느 절의 무엇을 무엇으로」 형태의 델타로 받는다. 부득이하게 전체를 주고받으면 **베이스 판본(`Contract Version`)을 문서 머리에 밝힌다.**
3. **PM이 미결을 닫으면 그 사실을 해당 계약 소유자에게 알린다.** 「닫았다」는 「고쳤다」와 같은 무게의 변경이다. 계약 문서에 `Contract Version`과 변경 고지를 붙이는 이유가 이것이며, 이번 회차부터 `case-view/v1.1` · `evidence-record/v1.1`처럼 붙였다.
4. 계약 문서의 **canonical 위치는 레포**다. 노션은 회의 기록이며 계약의 현재 규칙을 갖지 않는다(`contracts/README.md`). 노션에 올려 둔 것과 레포가 같은지는 **PM이 확인할 일**이다.

**PM 검수 자체의 누락도 하나 기록한다.** R-2에 적은 `"readiness": "4/5"`는 Pass 3 축 D가 잡았어야 했다. **예시 JSON을 대조 대상에서 빼놓은 것**이 원인이며, `scripts/check_boundaries.py`의 다음 확장 후보다.

---

## 8. Change rules

- 이 ADR은 보정 기록이다. 계약의 현재 규칙은 항상 `contracts/contract-<slug>.md`가 소유한다.
- §4의 항목이 담당자 답변으로 닫히면 이 문서를 고치지 않고 해당 계약의 새 ADR을 쓴다.
- 계약 번호는 v4 §5-1이 소유한다. 계약 문서에 번호를 다시 넣지 않는다.
