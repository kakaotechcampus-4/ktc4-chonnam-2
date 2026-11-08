# eval/scorers

prediction + GT version + metric version → metrics.

지표의 계산 정의(분자·분모, 적중 판정, `null` 조건, 버전 규칙)는
`docs/modules/eval/metrics/metric-definitions.md` 가 소유한다.
지표 목록은 `docs/architecture/module-architecture.md` §9-3.

| 파일 | stage | 버전 |
| --- | --- | --- |
| `candidate.py` | Candidate | `s5` |
| `classification.py` | Classification | `cl3` |
| `plate.py` | Plate | `p2` |
| `cost.py` | Cost (stage 무관, 항상 계산) · 속도 포함 | `c3` |
| `pipeline.py` | Coarse → Fine 전체 경로(Fine 판정 분포 · 최종 Recall). candidate stage에서 Fine 판정이 있을 때만 | `pl1` |
| `persistence.py` | Persistence(차량 검출 지속성) | `t1` |
| `interval.py` | 비율 지표의 Wilson 95% 구간 (stage 무관 · 공용) | — |
