# Final Data Contract — ReadoutRun v1

**Status:** `Final — Accepted`

**Accepted:** `2026-09-06`

**수락 근거:** CALL-6 회신 — 신유민(`readout` Owner) 「(b) `AnalysisRun`처럼 `ReadoutRun`을 별도 계약으로 만드는 방향에 동의합니다. 최소 필드는 제안해 주신 구성으로 수락합니다.」 소비자 김대원(`eval`)은 2026-09-07 회차에서 run 단위 실패 집계를 확인했다(§2)

> **B03·B05 종결 (2026-09-07).** 결과 → run 연결은 결과 계약의 필수 `run_ref`(`contract-plate-overlay-readout.md` §3), 사용량 연결은 `UsageRecord.run_ref`가 authoritative(§4). 스키마는 바뀌지 않았다. 근거 `adr/adr-data-contract-call-closure-2026-09-07.md` §4.3·§4.4.

**Architecture Contract:** v4 §5-1 ⑦ · §4-모듈3 ③

**Contract:** `ReadoutRun`

**Contract Version:** `readout-run/v1`

**Related ADR:** `adr/adr-readout-run.md`

**Contract Lead / Owner:** 신유민 (`readout`)

**Runtime Producer:** `readout`

**Consumers:** `case` — 유소연 (orchestration) · `eval` — 김대원 (실패 분류 집계)

---

## 1. 계약 목적

`readout`의 **판독 실행 1회**를 기록한다. `PlateReadout`/`OverlayTimeReadout`이 「무엇을 관찰했는가」라면 `ReadoutRun`은 「그 판독 시도가 성공/부분성공/실패했는가, 어느 단계에서 실패했는가」다.

v4 §4-모듈3 ③이 반환값을 둘로 명시한다.

```
read_plate(span, target_hint?)  -> ReadoutRun, PlateReadout
read_overlay_time(span)         -> ReadoutRun, OverlayTimeReadout
```

`search`가 같은 구조를 `AnalysisRun + CandidateEvent`로 이미 풀었고, 이 계약은 그 본을 그대로 따른다.

**결과 계약 안에 실행 정보를 넣지 않는 이유** — 실행 도중 완전히 실패해 `PlateReadout`이 생성되지 않은 경우 실패 기록을 남길 곳이 없어진다(신유민, CALL-6 회신).

## 2. 책임 경계

**Producer(`readout`)가 보장하는 것**

- 판독 시도 1회당 `ReadoutRun` 1건. 결과가 생성되지 않은 실패에도 run은 남는다
- `outcome`과 실패 시 `failure.kind`/`code` 기록
- 소비한 사용량을 `usage_refs[]`로 연결

**Consumer가 기대할 수 있는 것**

- `eval` — **실패 분류는 run 단위로 집계한다**(김대원 확인, 2026-09-07). `ReadoutRun`이 `operation`을 갖고 `JobRecord`는 갖지 않으므로 번호판 판독 실패와 화면시각 판독 실패가 한 바구니에 섞이지 않는다. 비용은 execution 단위(`UsageRecord.execution_ref`)다 — 지표마다 단위가 다른 것이 정상이다. Abstention Recall·Wrong Accept Rate의 정답 라벨과 분자·분모는 `eval`이 정의했고 **계약 필드 추가는 필요 없다**(`PlateReadout.abstained`와 `observation.value`로 충분). 정답지(`READABLE`+정답 문자열 / `UNREADABLE`)는 현재 없으며 eval 소유 후속이다.
- `case` — 결과 없는 실패를 진행 상태로 표현할 수 있다. **readout 계열 Job 1 execution : `ReadoutRun` 1건**은 `case`의 orchestration 불변조건이다(`contract-job-record-case-view.md` A절 §10-5). `readout`이 보장하는 것은 「public 함수 호출 1회 = run 1건」까지다

**이 Contract가 보장하지 않는 것**

- 판독 값 자체 — `PlateReadout`/`OverlayTimeReadout` 소관
- 재시도 성공 보장. 재시도는 새 `run_id`다
- 모델·프롬프트·OCR 내부 구현 세부

## 3. 확정 Contract 스키마 (JSON)

```json
{
  "run_id": "string",
  "operation": "PLATE_READ | OVERLAY_TIME_READ",
  "outcome": "SUCCEEDED | PARTIAL | FAILED",
  "failure": { "kind": "string", "code": "string" },
  "usage_refs": "ID[]",
  "started_at": "ISO8601",
  "ended_at": "ISO8601 | null"
}
```

## 4. 필드 정의

| 필드 | 타입 | 필수 | 규칙 |
| --- | --- | --- | --- |
| `run_id` | string | Y | 고유 식별자. 재사용 없음 |
| `operation` | enum(2) | Y | 어떤 public capability의 실행인가 |
| `outcome` | enum(3) | Y | `SUCCEEDED` / `PARTIAL` / `FAILED` |
| `failure` | object \| null | 조건부 | `outcome ∈ {PARTIAL, FAILED}`일 때 필수, `SUCCEEDED`면 null |
| `failure.kind` | string | Y(있을 때) | readout failure taxonomy의 상위 종류. **값 집합은 `modules/readout/decisions/failure-taxonomy.md`를 따른다** |
| `failure.code` | string | Y(있을 때) | stable machine-readable failure code |
| `usage_refs` | ID[] | Y(빈 배열 허용) | 이 실행이 소비한 `UsageRecord` 참조. **조회 편의용 파생값이며 authoritative가 아니다** — 어느 run에 속한 사용량인지의 기준은 `UsageRecord.run_ref`이고 두 값이 어긋나면 `UsageRecord.run_ref`가 기준이다(B05, 2026-09-07 · `contract-usage-record.md` §8-11). 양방향 정합을 이 계약의 불변조건으로 강제하지 않는다 |
| `started_at` | ISO8601 | Y | 실행 시작 |
| `ended_at` | ISO8601 \| null | Y(키) | 종료. 관측하지 못했으면 null |

## 5. 결과 계약과의 연결

> **B03 종결 (2026-09-07 · Decider 신유민 · 확인 유소연·김대원).** 연결 필드는 결과 계약이 소유한다 — `contract-plate-overlay-readout.md` §3 「`ReadoutRun`과의 연결 — `run_ref`」. 이 절은 run 쪽에서 보이는 의미만 적는다.

`PlateReadout` / `OverlayTimeReadout`은 최상위 필수 `run_ref: {kind:"readout_run", ref:<run_id>}`로 **자신을 생성한 실행을 보존한다.**

- `ReadoutRun` 1건 : 결과 0~1건. `outcome=FAILED`이면 결과가 없다(§8의 `rr_882`)
- **결과가 존재하면 `run_ref`가 존재·유효하다** — `outcome` 값과 무관
- 결과에서 run으로 역추적할 수 있어야 하고, 그 반대는 보장하지 않는다. **`result_refs[]`는 두지 않는다**
- 재시도는 새 `run_id`와 새 `readout_id`다(§9-1). 결과 간 supersede는 `readout` 소유가 아니다
- `Observation<T>`의 `produced_by.run_ref`는 readout 산출 Observation일 때 `{kind:"readout_run", ref:<run_id>}`로 이 run을 참조한다(`contract-observation.md` §6 등재). 결과 최상위 `run_ref`와 같은 실행이다
- `ReadoutRun`에는 `execution_ref`가 없다. `ReadoutRun → JobExecution` 역추적은 `JobExecution.produced`의 `{kind:"readout_run", ref}`가 담당한다(`contract-job-execution.md` §5)

## 6. Enum

**`operation`** — `PLATE_READ` · `OVERLAY_TIME_READ`. v4 §4-모듈3 ③의 public capability와 1:1이다. **`PLATE_REREAD`를 추가하지 않는다** — 재판독은 readout에게 `read_plate` 호출 1회이고 `PLATE_REREAD`는 `EvidenceNeeds.kind`의 값 공간이다. `JobRecord.kind`와는 같은 이름의 값끼리 대응한다(`contract-job-record-case-view.md` A절 §7).

**`outcome`** — `SUCCEEDED` · `PARTIAL` · `FAILED`. `AnalysisRun`과 같은 값 공간이다.

**`failure.kind`** — 값 집합과 확정 상태는 `../../modules/readout/decisions/failure-taxonomy.md`만 따른다. taxonomy는 현재 Owner 확정 전 초안이며 eval 확인도 대기다.

## 7. 정상 예시

```json
{
  "run_id": "rr_881",
  "operation": "PLATE_READ",
  "outcome": "SUCCEEDED",
  "failure": null,
  "usage_refs": ["usage_5521"],
  "started_at": "2026-09-05T09:12:00+09:00",
  "ended_at": "2026-09-05T09:12:07+09:00"
}
```

## 8. 실패 / 부분성공 예시

결과가 생성되지 않은 실패:

```json
{
  "run_id": "rr_882",
  "operation": "PLATE_READ",
  "outcome": "FAILED",
  "failure": { "kind": "PLATE_DETECTION", "code": "NO_PLATE_REGION_FOUND" },
  "usage_refs": ["usage_5522"],
  "started_at": "2026-09-05T09:13:00+09:00",
  "ended_at": "2026-09-05T09:13:04+09:00"
}
```

## 9. 불변조건

1. 동일 `run_id`는 재사용되지 않는다. 재시도는 새 run이다
2. `outcome=SUCCEEDED`이면 `failure`는 null이다
3. `outcome ∈ {PARTIAL, FAILED}`이면 `failure.kind`와 `failure.code`가 존재한다
4. `failure.kind`는 readout failure taxonomy의 값이며 이 계약이 값을 추가하지 않는다
5. **`abstained + reason`은 실패가 아니다.** 제대로 포기한 판독은 `outcome=SUCCEEDED`로 세고 포기 사실은 `PlateReadout.abstained`가 갖는다 (`modules/readout/decisions/failure-taxonomy.md`)
6. `ended_at`이 null인 채로 남을 수 있다. 종료 시각을 관측하지 못했다는 뜻이며 값을 만들어내지 않는다 (`product-spec.md` §7)

## 10. 미해결 항목

- `PARTIAL`의 정확한 판정 기준 — `readout` Technical Spec 소관
- retry/timeout 정책 — `common/runtime` 구현 세부이며 본 계약의 closure를 막지 않는다
