# eval

**Owner:** 김대원

AI 단계(Search 장면 찾기 · 번호판 판독)를 정답이 있는 데이터로 채점하는 **개발용 평가** 모듈의 문서 작업공간이다. 실행 코드는 루트 [`eval/`](../../../eval/README.md)에 있다. 경계는 `docs/architecture/module-architecture.md` §4-모듈7, 역할은 `docs/management/ownership.md`를 따른다.

## 한눈에

- **무엇을 하나:** 데이터셋(manifest) + 구현 이름표(`--impl`) → runner가 prediction을 만들고 → scorer가 정답지(GT)와 대조해 지표 JSON을 낸다.
- **입력:** `eval/manifests/<이름>/`의 클립 목록·정답지, 로컬 데이터 루트의 영상(레포에 없음).
- **출력:** `eval/predictions/<run_id>.json`(바꾸지 않음), `eval/results/<run_id>.<gt>.<scorer>-<cost>.json`.
- **실행:** `python -m eval.run --impl <이름표> --manifest <manifest> --stage <stage> --run-id <id>` → `python -m eval.score --prediction <id>`. 자세한 것은 [`eval/README.md`](../../../eval/README.md).
- **테스트:** `python -m pytest tests/eval/ -q`. 미디어가 없는 clone에서도 통과한다(미디어가 필요한 테스트는 skip).
- **수치를 말하는 범위:** 잠근 평가셋은 쓰지 않기로 해서(2026-10-26) 모든 수치는 **개발 중 반복 측정**이다. 최종 일반화 성능으로 주장하지 않는다.

## 어디부터 읽나

| 알고 싶은 것 | 문서 |
| --- | --- |
| 지금까지의 결과 요약 | [`evaluation-results-2026-11-01.md`](evaluation-results-2026-11-01.md) · 발표용 [`presentation-metrics-2026-11-01.md`](presentation-metrics-2026-11-01.md) |
| 데이터셋 구성과 한계 | [`datasets/README.md`](datasets/README.md) |
| 지표 계산 정의 | [`metrics/metric-definitions.md`](metrics/metric-definitions.md) |
| 실험 기록 | [`experiments/README.md`](experiments/README.md) |
| 평가 계획 · 원칙 | [`initial-evaluation-plan.md`](initial-evaluation-plan.md) · [`experiment-guide.md`](experiment-guide.md) |
| 하네스 설계(초기 설계 기록) | [`harness-v1-design.md`](harness-v1-design.md) — 구현 전 설계라 옵션·파일명 일부는 지금 코드와 다르다. 쓰는 법은 `eval/README.md`가 기준 |

## 용어

| 용어 | 뜻 |
| --- | --- |
| A / B / C tier | 데이터 출처. A = AI-Hub 프레임 시퀀스·영상, B = 실제·YouTube 주행 영상 1분 클립, C = 팀원 블랙박스 원본. `ctier2` · `ctier3`는 C tier에서 만든 manifest다(구성은 `datasets/README.md` 표) |
| S1 · S2 · S3 | Search가 바뀐 세 시점. S1 = 9/18 Flash 1배속, S2 = 10/01 Flash 느린 영상, S3 = 10/27 argon + Fine 분기부 문장(`fine-gore-v1`). [10/28 실험 기록](experiments/2026-10-28-search-points-pipeline.md) |
| O1 · O2 · O3 · O4 | 번호판 판독이 바뀐 시점. O1 = 사전학습 그대로, O2 = 판독 규칙(공백 정리·형식 검사·2줄 반쪽 보류), O3 = 프레임 다수결(crop 한 장으로는 잴 수 없어 표에서 빠짐), O4 = 파인튜닝 인식기(제품 미반영). [10/28 OCR 기록](experiments/2026-10-28-ocr-points.md) |
| Coarse · Fine | Search의 두 단계. Coarse = 영상 전체에서 후보 구간 찾기, Fine = 후보 구간을 자세히 보고 `OBSERVED` · `UNCERTAIN` · `NOT_OBSERVED` 판정 |
| Recall@3 | 정답 사건이 상위 3개 후보 안에 시작 시각 ±2초로 들어온 비율 |
| 버전 표기 | 파일명·결과 `meta`의 짧은 버전 코드. `m` = manifest(`m4`), `g`·`bg`·`ag`·`mp` = 정답지(`g4`), `s` = candidate 채점기(`s5`), `cl` = classification(`cl3`), `p` = plate(`p2`), `c` = cost(`c3`), `pl` = pipeline(`pl1`), `t` = persistence(`t1`), `n` = normalizer(`n4`). 예: `…g4.s5-c3.json` = 정답지 g4, candidate s5, cost c3로 채점 |

## 다루는 범위

- 정답지·manifest
- AI 단계 지표 계산
- baseline/challenger 동일 기준 비교
- 실험 실행·집계·리포트

## 다루지 않는 범위

- 제품 런타임 상태 관리
- search 내부 프롬프트/파서에 결합(예외는 `eval/README.md` 「호출 규칙」)
- 사용자 인터뷰를 코드 평가와 동일시
- 자기 정답지를 구현 편의에 맞게 변경

## 문서 운영

- `research/`: 조사·비교·Spike
- `experiments/`: 실제 설정/입력/결과/learning
- `decisions/`: 조사·실험 후 확정한 module 내부 결정
- `contracts/`: 이 모듈이 생산/소비하는 계약의 초안·검토 메모. cross-module 최종 계약은 `architecture/contracts/`로 승격
- 실험 기록 템플릿은 `experiment-guide.md`의 「Experiment Note Template」 절에 있다.

빈 spec을 미리 만들지 않는다. 필요해질 때 Owner가 생성한다.
