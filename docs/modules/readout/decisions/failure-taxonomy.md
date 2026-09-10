# readout 실패 분류 (Failure Taxonomy)

> **상태: Owner 확정.** 2026-09-04 문서 정리에서 만들었고, 미결이던 2건(①②)을 2026-09-09에 종결했다.
> 모듈 구조 설계 v3와 `modules/eval/experiment-guide.md` 템플릿에 있던 이름을 소유자 폴더로 모은 것이다. `eval`은 이 이름을 복제하지 않고 가리킨다.
> `search`의 대상 연결 실패(`TARGET_ASSOCIATION`)와 `readout`의 번호판 대상 실패(`PLATE_TARGET_ASSOCIATION`)를 **같은 통계로 뭉치지 않기 위해** 접두어를 분리한다.

> **2026-09-08 갱신.** Mock Pack PR #14 심층 검토 보고서(`docs/mock/05_mock_deep_review_report.md`) §12가 readout Owner에게 물은 2건(P0-4 · P1-12)의 답변을 등재했다. 답변 원문은 이슈 [#16 `[mock] readout 검수`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/16) 「A. 정합 검토 답변」 ①②다.
> 같은 회차에 **N02 `OVERCONFIDENT` 분리도 종결**했다(「사후 분류」 절) — 9/7 ADR §4.10이 값 정의를 이 문서에 위임한 데 따른 것이다.
> **2026-09-09 갱신.** Mock Pack v2 2차 검수(PR [#20](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/20))에서 `scenario_infra_failure_001`이 `PLATE` stage의 `INFRA` code를 쓰는 것을 확인하고, 남아 있던 **①(code 층위) · ②(`PLATE` code 등재)를 A안으로 종결**했다. code 표의 `stage` 열이 「공통」으로 바뀌었고 「Owner 확정 대기」 절은 종결 기록으로 대체됐다.
> **2026-09-10 갱신.** Mock Pack v3(PR [#29](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/29))가 이 문서의 「실패가 아닌 상태」 2행을 `CaseView.notices`로 구현한 것을 3차 검수(이슈 [#31](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/31) A-1)에서 확인하면서, `observation.reason.code` → `CaseView.notices[].code` 매핑을 같은 절에 등재했다. UNKNOWN 행의 두 `reason.code` 중 `readout.overlay.ocr_failed`쪽 notice(`readout.overlay_ocr_failed`)를 미리 등재해 재사용 사고를 막는다.
>
> **Owner 미결은 없다.** 다만 overlay 「없음」/「확인 못함」의 **판정 기준**은 실측 전 잠정이며 readout Technical Spec에서 확정한다(해당 절에 표시).

이 문서 안에서 **확정**과 **잠정**을 구분한다. 표 제목과 절 제목에 표시했다.

---

## stage

`PLATE` · `OVERLAY_TIME`

---

## kind (readout) — 런타임 확정 5종

아래 5종은 **readout이 실행 중에 스스로 감지해 `ReadoutRun`에 기록하는** 분류다. 실행 중에 판정할 수 없는 분류는 아래 「사후 분류」 절에 따로 둔다.

**값 목록은 닫지 않는다.** 신규 값은 이 문서에 등재한 뒤 사용한다. 등재되지 않은 값을 fixture·Mock·구현에서 만들어 쓰지 않는다.

| 이름 | stage | 의미 |
| --- | --- | --- |
| `PLATE_TARGET_ASSOCIATION` | `PLATE` | 사건 주체가 아닌 차량의 번호판을 읽음 |
| `PLATE_DETECTION` | `PLATE` | 번호판 영역을 찾지 못함 |
| `PLATE_RECOGNITION` | `PLATE` | 영역은 맞게 찾았지만 문자를 잘못 읽음 |
| `OVERLAY_VALIDATION` | `OVERLAY_TIME` | 화면 시각을 읽었으나 형식·단조 증가·영상 길이 정합 검증에 실패. **run 실패가 아니다 — 아래 「kind와 `outcome`은 1:1이 아니다」 참조** |
| `INFRA` | 공통 | timeout / 라이브러리 / 파이프라인 오류 |

### `OVERLAY_DETECTION`은 추가하지 않는다 (2026-09-08 확정)

Mock Pack v2가 `ReadoutRun.failure.kind = "OVERLAY_DETECTION"`(code `NO_OVERLAY_PRESENT`)을 만들어 썼으나 **이 문서에 등재된 적이 없는 값이다.** 등재 kind는 위 5종 그대로 두고 `OVERLAY_DETECTION`을 추가하지 않는다.

이유는 두 가지다.

- 그 fixture가 표현하려던 상황(「화면에 시각이 안 찍힌 영상」)은 **실패가 아니다.** 아래 「실패가 아닌 상태」 절의 매핑을 쓴다.
- overlay 계열에서 실제로 `outcome=FAILED`가 되는 것은 `INFRA`뿐이다. detection 단계를 따로 세울 대상이 없다.

같은 값이 다시 제안되지 않도록 여기에 남긴다. `NO_OVERLAY_PRESENT` code도 채택하지 않는다.

---

## code — 확정 3건 (stage 공통)

`ReadoutRun.failure.code`는 stable machine-readable failure code다(`contract-readout-run.md` §4). 실행 실패 3건을 등재한다. **code는 stage별로 나누지 않고 두 stage가 공유한다**(①, 2026-09-09 확정).

| stage | kind | code | 상황 |
| --- | --- | --- | --- |
| 공통 | `INFRA` | `READOUT_PROVIDER_TIMEOUT` | provider/모델 timeout |
| 공통 | `INFRA` | `READOUT_FRAME_ACCESS_FAILED` | 프레임/클립 접근 실패 |
| 공통 | `INFRA` | `READOUT_PIPELINE_ERROR` | 라이브러리·파이프라인 오류 |

즉 `PLATE`·`OVERLAY_TIME` 양쪽에 그대로 적용된다 — 예: `(operation=PLATE_READ, kind=INFRA, code=READOUT_PROVIDER_TIMEOUT)`.

세 경우 모두 **완전 실패이므로 결과 객체(`PlateReadout` / `OverlayTimeReadout`)를 생성하지 않는다.** 실패 사실·원인은 `ReadoutRun`만 갖는다(`contract-plate-overlay-readout.md` §4 말미 「완전 실패 예시는 없다 — 그것이 규칙이다」).

---

## kind와 `outcome`은 1:1이 아니다 — 확정 (2026-09-08)

**kind는 eval 집계용 실패 분류이고, `ReadoutRun.outcome = FAILED` 조건과 1:1로 대응하지 않는다.**

`contract-readout-run.md` §4는 `failure`를 「`outcome ∈ {PARTIAL, FAILED}`일 때 필수, `SUCCEEDED`면 null」로 규정한다. 그런데 위 kind 5종이 전부 `outcome=FAILED`를 뜻하는 것은 아니다. 이 구분이 없어서 Mock Pack이 「화면 시각 없음」을 실행 실패로 접었다(P0-4).

### `OVERLAY_VALIDATION`은 run 실패가 아니다

형식·단조 증가·영상 길이 정합 검증 실패는 **값을 읽은 뒤의 결과**다. 판독 실행 자체는 정상 종료했으므로:

```
ReadoutRun.outcome            = SUCCEEDED        (FAILED 아님)
OverlayTimeReadout.validation = *_ok = false     (계약 §7)
observation.status            = NEEDS_REVIEW | UNKNOWN
```

`contract-plate-overlay-readout.md` §10 원칙이 이미 못 박고 있다 — 「Overlay의 `NOT_PRESENT`, `OCR_FAILED`, `VALIDATION_FAILED`는 공용 `Observation.status` enum이 아니라 readout 도메인의 reason/validation 결과다.」

현재 문서가 `OVERLAY_VALIDATION`을 다른 4종과 같은 표에 실패 kind로 적어 둔 것이 혼선의 원인이었다. **값은 유지하되 층위가 다르다** — eval이 「overlay 판독이 왜 쓸 수 없었나」를 집계하는 분류이지, `ReadoutRun.failure.kind`에 실어 `outcome=FAILED`를 만드는 값이 아니다.

**overlay 계열에서 `outcome=FAILED`가 되는 것은 `INFRA`뿐이다.**

---

## 사후 분류 — 확정 1종 (N02 종결, 2026-09-08)

런타임 kind 5종과 달리 **실행 중에는 판정할 수 없고 정답지 대조로만 붙는 분류**가 하나 있다. 이름은 등재하되 층위를 분리한다.

| 이름 | 의미 | 어디에 기록하나 |
| --- | --- | --- |
| `OVERCONFIDENT` | abstain 했어야 하는데 확정값을 냄 (불확실하지만 확정값 반환) | **`ReadoutRun.failure.kind`가 아니다.** `eval`이 정답지 대조로 붙인다 |

**왜 런타임 kind가 아닌가.** readout은 실행 중에 자기가 오수용했는지 알 수 없다 — 알았다면 abstain했을 것이다. 판정에는 정답 라벨이 필요하고 정답지는 `eval` 소유다. 게다가 오수용한 실행의 `outcome`은 `SUCCEEDED`이고 `contract-readout-run.md` §4가 「`SUCCEEDED`면 `failure`는 null」로 규정하므로 **실을 자리 자체가 없다.**

**왜 그래도 등재하는가.** `Wrong Accept Rate`가 재는 것이 정확히 이것이다 — 분모는 `abstained=false`인 전체, 분자는 정답 불일치 또는 정답 `UNREADABLE`(`adr-data-contract-call-closure-2026-09-07.md` §4.10, 김대원 확정). `PLATE_RECOGNITION`에 섞으면 「잘못 읽고 불확실하다고 표시」와 「잘못 읽고 확신에 차서 확정」이 한 바구니가 된다. 제품 위험도가 다르다 — 후자는 그대로 신고서에 올라간다. `search` taxonomy도 「readout에도 같은 항목 필요」로 자리를 비워 뒀다.

**N02 종결 근거.** 9/7 회차가 「`PLATE_RECOGNITION`과 분리해 readout `failure.kind`를 6개로 닫기로 했다(김대원 동의 · Owner 신유민)」로 결정하고, 상태를 `ACCEPTED_PENDING_IMPLEMENTATION`으로, 갱신을 Owner에게, **값 정의를 이 문서에 위임했다**(같은 §4.10 — 「`modules/readout/decisions/failure-taxonomy.md`는 Owner가 갱신한다」 · 「이 문서는 값을 복제하지 않는다」). 그 위임에 따라 **이름 6개로 닫되 층위를 둘로 나눈다** — 런타임 kind 5종 + 사후 분류 1종.

> **@김대원 알림 (확인 요청이 아니라 통지).** 이 층위 분리는 `eval`의 집계 능력을 줄이지 않는다 — 오수용은 어차피 정답지 대조로만 판정되며 `ReadoutRun`에서 읽어올 수 있었던 적이 없다. 오히려 집계 코드가 `failure.kind`에서 `OVERCONFIDENT`를 찾다가 0건만 보는 사고를 막는다. 「6개로 닫는다」를 **런타임 `failure.kind` 6개**로 의도했던 것이면 알려주면 다시 연다.
>
> **측정 시점.** 정답지(plate 문자 정답)는 현재 없다 — A tier는 번호판 마스킹, B tier는 모자이크·블러라 C tier 확보 후 항목이다(같은 §4.10). 이름과 층위를 먼저 확정해 두는 것이 목적이고 실제 집계는 정답지 확보 이후다.

---

## 실패가 아닌 상태 — overlay 「없음」 / 「확인 못함」 — 확정 (2026-09-08, P0-4)

`core-user-flow.md` §5가 「**「화면에 시각이 없다」와 「확인하지 못했다」는 다른 말이다** … 둘을 하나로 합쳐 「없음」이라고 쓰지 않는다 — 없다고 하면 사용자는 화면을 다시 보지 않는다」고 못 박았다. 두 상태 모두 **판독 실행 자체는 정상 종료**이므로 실패로 표현하지 않는다.

| 상황 | `ReadoutRun.outcome` | `observation.status` | `observation.reason.code` |
| --- | --- | --- | --- |
| 화면에 시각이 안 찍힌 영상 (**사실**) | `SUCCEEDED` | `NOT_APPLICABLE` | `readout.overlay.not_present` |
| 판정 못 함 / 읽었으나 못 알아봄 (**모름**) | `SUCCEEDED` | `UNKNOWN` | `readout.overlay.presence_undetermined` · `readout.overlay.ocr_failed` |

- 두 경우 모두 `OverlayTimeReadout` 결과 객체를 **생성한다.** 실행이 정상 종료했기 때문이다.
- `NOT_APPLICABLE`·`UNKNOWN`은 둘 다 `observation.value == null`이어야 한다(`contract-observation.md` 불변조건 — 「`UNKNOWN`, `ERROR`, `NOT_APPLICABLE`이면 `value == null`이어야 한다」).
- `status` 값 공간은 공용 `Observation<T>`의 `OK / NEEDS_REVIEW / UNKNOWN / ERROR / NOT_APPLICABLE`를 그대로 쓴다. readout이 새 status를 만들지 않는다(계약 §10 원칙).
- `reason.code`는 Producer/domain이 소유하는 stable machine-readable reason이다(`contract-observation.md`). 프로그램 분기는 `status + reason.code`로 한다.

### 어느 쪽을 낼지 정하는 판정 기준 — **잠정. Technical Spec에서 확정**

**잠정 규칙 (v1):**

- 프레임 샘플링·ROI 추출이 정상 수행됐고 **샘플 전부에서 overlay가 안 보임** → `NOT_APPLICABLE`
- 프레임 접근 실패 · 유효 샘플 수 미달 · 야간/압축으로 ROI 판정 불가 → `UNKNOWN`

**이 기준은 잠정이다.** `overlay-presence-detection.md` 미결 **#3(오판율 — 있는데 없다고 / 없는데 있다고)**이 실측 전이고, 같은 문서 미결 **#4(「overlay 없음」과 「탐지 실패」를 구분하는 방법)**가 바로 이 항목이다. 두 미결 모두 「실제 블랙박스 샘플로 검증한 뒤 Owner가 Technical Spec에서 확정한다」로 되어 있다.

실측에서 false negative(있는데 없다고)가 유의미하게 나오면 **기본값을 `UNKNOWN` 쪽으로 보수적으로 옮긴다** — 「없음」이라고 하면 사용자가 화면을 다시 보지 않기 때문이다.

> 참고: 이 두 갈래를 제품이 요구하는 시점은 `core-user-flow.md` §5의 **업로드 직후 intake presence 탐지**(값 OCR 없이 유무만)인데, 그 결과를 담을 계약 필드가 아직 어디에도 없다. 계약 공백으로 이슈 #16 A①에 별도 제기했다. 이 문서는 판독 실행(`OVERLAY_TIME_READ`) 시점의 표현만 다룬다.

### `CaseView.notices[].code` 매핑 — 확정 (2026-09-10, 이슈 [#31](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/31) A-1)

두 상태는 실행 실패가 아니므로 `CaseView.progress[]`를 `FAILED`로 내리지 않고 **notice로만** 알린다. Mock Pack v3가 이 전제대로 구현돼 있음을 확인했다(`scenario_infra_failure_001` rev1·rev2의 `progress[overlay_time_read].state=DONE`).

`notices[].code`의 **표기 형식**은 `contract-job-record-case-view.md` B절 §7이 소유한다(`<producing-module>.<detail>`, dotted-lowercase). 이 문서는 그 규칙을 복제하지 않고 **readout `reason.code`와의 대응만** 정한다.

**매핑 규칙 — module 접두어는 그대로 두고 그 뒤의 점을 밑줄로 접는다. `reason.code`와 notice code는 1:1이다.**

| `observation.reason.code` | `CaseView.notices[].code` | severity | blocking | actions |
| --- | --- | --- | --- | --- |
| `readout.overlay.not_present` | `readout.overlay_not_present` | `INFO` | `false` | `[]` |
| `readout.overlay.presence_undetermined` | `readout.overlay_presence_undetermined` | `INFO` | `false` | `[]` |
| `readout.overlay.ocr_failed` | `readout.overlay_ocr_failed` | `INFO` | `false` | `[]` |

- **세 code를 하나로 합치지 않는다.** 사용자에게 요구하는 행동이 다르다 — 「없음」은 확인할 것이 없고, 「판정 못 함」은 사용자가 자기 영상에 시각이 찍히는지 봐야 하고, 「읽었으나 못 알아봄」은 사용자가 화면의 시각을 직접 입력할 수 있다. 같은 이유로 UNKNOWN 행의 두 `reason.code`에 notice 하나를 돌려쓰지 않는다.
- `readout.overlay_ocr_failed`는 **등재만 해 둔다.** 현재 pack에 이 갈래 fixture가 없다(`readout.overlay.ocr_failed` 자체가 미등장) — 생길 때 위 값을 그대로 쓰고 새로 짓지 않는다.
- **severity는 `INFO`로 고정한다.** overlay가 UNKNOWN이어서 실제로 사용자 행동이 필요해지는 지점(시각을 다른 소스로 확정해야 함)은 `event_time_display.info_state`와 `evidence.time_*` notice가 나른다. notice는 「왜」만 설명하고 「확인 필요」의 무게를 중복해서 지지 않는다.
- `actions[]`가 비는 이유는 overlay presence 판정 자체가 사용자가 손댈 수 있는 대상이 아니기 때문이다. 시각 입력·재확인 action은 위 evidence 계열 notice에 붙는다.

---

---

## `JobExecution.failure_kind` 매핑 — 확정

readout run 실패는 `JobExecution.failure_kind = "READOUT_INFRA"`로 올라간다(모듈 접두어 규칙).

`contract-job-execution.md` §6 `failure_kind`가 「모듈 접두어로 구분한다. 값 목록은 닫히지 않으며, 신규 값은 해당 모듈의 `decisions/failure-taxonomy.md`에 등재한 뒤 사용한다」로 위임했다. **`READOUT_` 접두어 값의 등재처가 이 문서다.**

| 이 문서의 `kind` | `JobExecution.failure_kind` |
| --- | --- |
| `INFRA` | `READOUT_INFRA` |

- `JobExecution` 계약의 `status` 표·전이 규칙은 여기에 복제하지 않는다. 매핑 규칙만 둔다.
- Mock Pack v2가 쓴 `READOUT_OVERLAY_DETECTION`은 **등재값이 아니다** — 위 `OVERLAY_DETECTION` 폐기와 같은 이유로 채택하지 않는다.
- `status=STALE`일 때 `failure_kind`가 null일 수 있는 것은 실행 기반 쪽 규칙이며 이 문서 소관이 아니다(`contract-job-execution.md` §6).

---

## `abstain_reason` 값 공간 — 확정 4종

`PlateReadout.abstain_reason`의 등재 목록이 지금까지 없었다(계약 예시에 `FRAME_DISAGREEMENT` 하나가 등장할 뿐이다). 아래를 등재한다. **닫힌 목록이 아니며** 신규 값은 이 문서에 등재한 뒤 쓴다.

| 값 | 의미 |
| --- | --- |
| `TARGET_AMBIGUOUS` | 대상 차량 association이 애매해 어느 차량의 번호판인지 확정할 수 없음 |
| `FRAME_DISAGREEMENT` | 프레임 간 OCR 결과가 합의되지 않음 |
| `LOW_RESOLUTION` | 번호판 영역 해상도가 문자 판독 하한에 미달 |
| `OCR_LOW_CONFIDENCE` | 인식은 됐으나 신뢰도가 확정 임계 미만 |

### 사유가 겹칠 때 우선순위 — `association > frame consensus`

`target_association.status`가 `AMBIGUOUS` 또는 `FAILED`이면 **프레임 합의 이전 단계에서 걸리므로** `TARGET_AMBIGUOUS`가 authoritative다. 이때 `FRAME_DISAGREEMENT`를 쓰지 않는다.

`abstain_reason`은 단일 값이고 evidence·web의 사용자 문구가 여기서 갈리므로 하나로 정해져야 한다.

---

## 기록 규칙

- `ReadoutRun`에 **런타임 kind**와 `failure.code`로 기록한다. **stage는 `ReadoutRun`의 필드가 아니라 `operation`(`PLATE_READ` / `OVERLAY_TIME_READ`)이 나른다** — 계약 스키마에 `stage` 필드가 없다(`contract-readout-run.md` §3). 단, **kind가 곧 `outcome=FAILED`를 뜻하지는 않는다**(위 「kind와 `outcome`은 1:1이 아니다」).
- **사후 분류(`OVERCONFIDENT`)는 `ReadoutRun`에 기록하지 않는다.** `eval`이 정답지 대조로 붙인다.
- `abstained + reason`은 **실패가 아니다.** 제대로 포기한 것은 성공으로 센다(`Abstention Recall`). abstain 결과의 `ReadoutRun.outcome`은 `SUCCEEDED`다.
- `abstain_reason`이 **authoritative**다. `observation.reason.code`는 abstain 외의 사유(`UNKNOWN`/`ERROR` 진단)에만 쓰고, `abstained=true`일 때 `reason.code`를 **중복 채우지 않는다**(`contract-plate-overlay-readout.md` §5, 2026-09-07 확정).
- abstain 표현은 `observation.status = NEEDS_REVIEW` + `abstained = true`다(계약 §11-1). 별도 `ABSTAIN` status를 신설하지 않는다.
- `eval`은 이 이름들을 복제하지 않고 이 문서를 가리킨다. 어긋나면 이 문서가 이긴다(`experiment-guide.md` §13 말미의 원본 지정 규칙).

---

## ① code 층위 — 종결 (2026-09-09, A안 채택)

`code`를 stage별로 나누지 않는다. 원인이 같은 실패는 두 stage가 **같은 code를 공유**하고, 어느 판독의 실패인지는 `ReadoutRun.operation`이 구분한다.

| 안 | 형태 | 판정 |
| --- | --- | --- |
| **A. stage로만 구분** | 같은 code를 두 stage가 공유. `(operation=PLATE_READ, INFRA, READOUT_PROVIDER_TIMEOUT)` | **채택.** code 수가 줄고 원인이 같은 실패를 같은 이름으로 집계할 수 있다 |
| B. stage별 code 분리 | `READOUT_PLATE_PROVIDER_TIMEOUT` / `READOUT_OVERLAY_PROVIDER_TIMEOUT` | 기각. code 하나만 보고 판독 종류를 알 수 있는 이점은 `operation`을 같이 읽으면 그대로 얻는다. `ReadoutRun`에 `stage` 필드가 없으므로 code에 stage를 인코딩하면 `operation`과 원천이 둘이 된다 |

**② (`PLATE` stage code 등재)는 ①에 흡수돼 함께 종결했다** — 위 「code」 절의 3건이 `PLATE`에도 그대로 적용되므로 따로 등재할 값이 없다.

`JobExecution.failure_kind`는 어느 쪽이든 `READOUT_INFRA` 하나로 접힌다.

Mock Pack v2 2차(`scenario_infra_failure_001`)가 `(PLATE_READ, INFRA, READOUT_PROVIDER_TIMEOUT)`을 이미 쓰고 있어 이 확정으로 근거가 생겼다 — fixture 수정은 필요 없다.

---

## 근거

- 이슈 [#16 `[mock] readout 검수`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/16) 「A. 정합 검토 답변」 ①(P0-4) · ②(P1-12) — 이 문서 등재 내용의 원문
- `docs/mock/05_mock_deep_review_report.md` **P0-4**(「화면 시각 없음」을 `ReadoutRun` 실패로 모델링해 제품이 요구한 상태 구분이 사라짐 + 미등록 `failure.kind`) · **P1-12**(readout / search 실행 실패 계열이 등록된 taxonomy 값으로 표현된 fixture 없음) · §12(Owner별 남은 검수 항목)
- `contract-plate-overlay-readout.md` §5(`abstain_reason` authoritative) · §7(validation 필드) · §10(실패/UNKNOWN/ABSTAIN 원칙) · §11-1(abstain 표현) · §11-4(overlay 무조건 실행 A안)
- `contract-readout-run.md` §4(`failure` 조건부 규칙 · kind는 이 문서를 따름)
- `contract-observation.md`(status 5값 · `value == null` 불변조건 · `reason.code` 소유)
- `contract-job-execution.md` §6(`failure_kind` 등재 위임)
- `overlay-presence-detection.md` 미결 #3(오판율) · #4(「없음」과 「탐지 실패」 구분)
- `product/core-user-flow.md` §5(두 문구를 합치지 않는다)
- 이슈 [#31 `[mock] readout·web 3차 검수`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/31) A-1 — notice 매핑 등재의 근거
- `contract-job-record-case-view.md` B절 §7(`notices[].code` 표기 형식 소유 · `severity`/`blocking` 의미)
- `adr-data-contract-call-closure-2026-09-07.md` §4.10(N02 — `OVERCONFIDENT` 분리 · Wrong Accept Rate 정의 · 정답지 부재)
