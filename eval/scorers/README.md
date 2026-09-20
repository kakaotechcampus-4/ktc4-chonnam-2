# eval/scorers

prediction + GT version + metric version → metrics.

지표의 계산 정의(분자·분모, 적중 판정, `null` 조건, 버전 규칙)는
`docs/modules/eval/metrics/metric-definitions.md` 가 소유한다.
지표 목록은 `docs/architecture/module-architecture.md` §9-3.

| 파일 | stage | 버전 |
| --- | --- | --- |
| `candidate.py` | Candidate | `s4` |
| `classification.py` | Classification | `cl2` |
| `plate.py` | Plate | `p2` |
| `cost.py` | Cost (stage 무관, 항상 계산) · 속도 포함 | `c2` |
