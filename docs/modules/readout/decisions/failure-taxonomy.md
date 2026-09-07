# readout 실패 분류 (Failure Taxonomy)

> **상태: Owner(신유민) 확정. 2026-09-07 개정.** 최초 초안은 2026-09-04 문서 정리에서 모듈 구조 설계 v3와 `modules/eval/experiment-guide.md` 템플릿의 이름을 소유자 폴더로 모은 것이다. `eval`은 이 이름을 복제하지 않고 가리킨다.
> `search`의 대상 연결 실패(`TARGET_ASSOCIATION`)와 `readout`의 번호판 대상 실패(`PLATE_TARGET_ASSOCIATION`)를 **같은 통계로 뭉치지 않기 위해** 접두어를 분리한다.

## stage

`ReadoutRun.operation`이 담는다 — `PLATE_READ` / `OVERLAY_TIME_READ`. **별도 `stage` 필드는 두지 않는다.**

`search`는 한 `AnalysisRun` 안에 `COARSE` → `FINE` 두 단계가 들어 있어 어느 단계에서 깨졌는지 말하려면 stage 필드가 필요하다. `readout`은 그 두 단계를 애초에 두 개의 `ReadoutRun`으로 쪼갠다(`rr_h001_plate` 18:31:00–07 → `rr_h001_overlay` 18:31:08–12). 단계 구분이 run 경계에 이미 들어가 있으므로 run 안에 stage를 또 둘 이유가 없다. 초안의 `PLATE` · `OVERLAY_TIME`은 taxonomy 템플릿이 search 모양으로 쓰이면서 따라온 것이다.

## 두 축을 섞지 않는다

이 문서는 서로 다른 두 가지를 다룬다. 이름이 섞이면 eval 지표와 런타임 로그가 어긋난다.

### A. 실행 실패 — `ReadoutRun.failure.kind`

런타임에 판정 가능한 것만 들어간다. 산출물을 못 만들었거나(`FAILED`), 만든 뒤 실행이 깨진 경우(`PARTIAL`)에 기록한다(`contract-readout-run.md` §10).

| 이름 | 의미 | outcome |
| --- | --- | --- |
| `PLATE_DETECTION` | 번호판 영역을 찾지 못함 | `FAILED` |
| `OVERLAY_DETECTION` | 오버레이 영역 미검출·디코딩 불가 | `FAILED` |
| `INFRA` | timeout / 라이브러리 / 파이프라인 오류 (공통) | `FAILED`, `PARTIAL` |

### B. 평가 분류 — eval 집계용

정답 대조로만 판정된다. **`ReadoutRun`에 기록하지 않는다.** 파이프라인은 실행 중에 이 값들을 알 수 없다 — 자기가 잘못 읽었다는 것을 안다면 애초에 abstain했을 것이다.

| 이름 | 의미 |
| --- | --- |
| `PLATE_RECOGNITION` | 영역은 맞게 찾았지만 문자를 잘못 읽음 |
| `PLATE_TARGET_ASSOCIATION` | 사건 주체가 아닌 차량의 번호판을 읽음 |
| `OVERLAY_VALIDATION` | 화면 시각을 읽었으나 형식·단조 증가·영상 길이 정합 검증에 실패 |

`OVERCONFIDENT`는 별도 이름을 두지 않는다. 정의상 `PLATE_RECOGNITION` ∩ `abstained = false`이므로 별도 kind를 만들면 두 이름이 겹치는 영역이 생긴다. `abstained` 플래그로 갈라 집계하면 `Wrong Accept Rate`(틀렸는데 확정값을 냄)와 `Abstention Recall`(틀릴 상황에서 제대로 포기함)이 같은 데이터에서 나온다.

## `failure.code`

**값 공간 미확정.** 현재 등재된 값은 `NO_PLATE_REGION_FOUND`(`contract-readout-run.md` §8 예시) 하나뿐이다. `abstain_reason` 때와 같은 방식으로 kind별 code 목록을 만들어 확정한다. 확정 전까지 `scripts/validate_mock_pack.py`의 `FAILURE_CODES` 상수에 두고 미등재 값은 WARN으로 낸다.

## 기록 규칙

- 실행 실패는 `ReadoutRun.failure: {kind, code}`에 기록한다. stage는 `operation`이 담는다.
- 평가 분류는 eval 결과에 기록한다. `ReadoutRun`에 넣지 않는다.
- `abstained + reason`은 실패가 아니다. 제대로 포기한 것은 성공으로 센다(`Abstention Recall`).
- 런타임에 association 불확실을 인지해 보류한 경우는 `abstain_reason`(`TARGET_ASSOCIATION_UNCERTAIN`)이고, 사후에 다른 차량 번호판이었음이 드러난 경우가 `PLATE_TARGET_ASSOCIATION`이다. 같은 현상의 다른 축이므로 뭉치지 않는다.
