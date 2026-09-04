# readout 실패 분류 (Failure Taxonomy) — 초안

> **상태: 초안. Owner(신유민) 확정 전.** 2026-09-04 문서 정리에서 만들었다.
> 모듈 구조 설계 v3와 `modules/eval/experiment-guide.md` 템플릿에 있던 이름을 소유자 폴더로 모은 것이다. `eval`은 이 이름을 복제하지 않고 가리킨다.
> `search`의 대상 연결 실패(`TARGET_ASSOCIATION`)와 `readout`의 번호판 대상 실패(`PLATE_TARGET_ASSOCIATION`)를 **같은 통계로 뭉치지 않기 위해** 접두어를 분리한다.

## stage

`PLATE` · `OVERLAY_TIME`

## kind (readout)

| 이름 | 의미 |
| --- | --- |
| `PLATE_TARGET_ASSOCIATION` | 사건 주체가 아닌 차량의 번호판을 읽음 |
| `PLATE_DETECTION` | 번호판 영역을 찾지 못함 |
| `PLATE_RECOGNITION` | 영역은 맞게 찾았지만 문자를 잘못 읽음 |
| `OVERLAY_VALIDATION` | 화면 시각을 읽었으나 형식·단조 증가·영상 길이 정합 검증에 실패 |
| `INFRA` | timeout / 라이브러리 / 파이프라인 오류 (공통) |

## Owner가 확정할 때 함께 볼 후보 이름

`experiment-guide.md` §13의 `OVERCONFIDENT`(불확실하지만 확정값 반환)는 readout의 핵심 실패다 — 1.3의 `Wrong Accept Rate`가 재는 것이 이것이다. **abstain해야 했는데 값을 낸 경우**를 `PLATE_RECOGNITION`과 구분할지 확정한다.

## 기록 규칙

- `ReadoutRun`에 stage + kind로 기록한다.
- `abstained + reason`은 실패가 아니다. 제대로 포기한 것은 성공으로 센다(`Abstention Recall`).
