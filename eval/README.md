# eval — 오프라인 평가

제품 실행과 분리된 개발용 평가 도구다. 실행 코드는 이 폴더에, 데이터셋 설명과 결과 해석은 [평가 문서](../docs/modules/eval/README.md)에 있다. 모든 점수는 보유 데이터로 반복 측정한 **개발 평가**이며, 최종 일반화 성능을 뜻하지 않는다.

## 평가 요약

블랙박스 신고 준비에 필요한 **위반 장면 탐색·위반 유형 구분·번호판 문자 인식**을 단계별로 평가한다. 같은 입력과 정답지에 설정별 예측을 대조하고, 탐색 성공률과 오탐, 번호판 정답률과 틀린 값 확정을 함께 비교한다.

아래는 **2026-11-01 보고서에 정리된 실측 결과**다. Search는 S3 설정, 번호판은 10/22 판독 규칙(O2) 기준이다.

| 평가 질문 | 데이터와 방법 | 결과 |
| --- | --- | --- |
| 위반 영상에서 유형을 맞히는가? | AI-Hub 위반 영상 400개(4종 × 100). 1순위 후보 유형과 영상 라벨 비교 | **371/400, 92.8%** 적중 |
| 실제 주행 영상에서 위반을 찾고 확인하는가? | `b_youtube_m4` 179클립, 위반 16건. 상위 3개 후보 중 시각 ±2초·유형 일치와 Fine 위반 확인 | **10/16, 62.5%** 확인(95% 구간 39–82%). 정상 클립당 최종 오탐 **0.35건** |
| 번호판 판독 규칙이 잘못된 확정을 줄이는가? | AI-Hub 번호판 crop 314장. 사전학습 그대로(O1)와 판독 규칙 적용(O2) 비교 | 틀린 값 확정 **129 → 32건**, 전체 정답률 **21.0% → 36.0%** |

유형 적중률은 위반 영상만의 결과이고, 번호판 결과는 잘라낸 이미지의 문자 인식 범위다. 실제 주행 영상의 위반 표본은 16건이며 이 중 10건은 설정 선택 실험과 겹친다. 모두 1회 실행에 기반한 개발 평가이므로, 표의 수치를 제품 전체의 일반화 성능으로 해석하지 않는다.

데이터·설정·비교표와 원본 결과 경로는 [평가 결과 보고서](../docs/modules/eval/evaluation-results-2026-11-01.md), 지표 계산 방법은 [지표 정의](../docs/modules/eval/metrics/metric-definitions.md)에서 확인할 수 있다.

## 빠른 확인

저장소 루트에서 실행한다. Python 환경을 먼저 설치해야 `eval` 모듈을 찾을 수 있다.

```bash
uv sync --extra test
uv run pytest tests/eval -q
uv run python -m eval.run --help
```

`demo_correct`의 예측과 채점 결과는 이미 커밋돼 있다. 같은 버전의 결과를 다시 저장하려고 하면 채점기가 종료 코드 3으로 덮어쓰기를 거부한다. 새 실행을 확인하려면 **새 run ID**를 사용한다.

```bash
uv run python -m eval.run --impl fake:always_correct --manifest b_youtube --stage candidate --run-id my_demo_001
uv run python -m eval.score --prediction my_demo_001
```

실행 결과는 `eval/predictions/<run_id>.json`, 채점 결과는 `eval/results/<run_id>.<gt_version>.<scorer_version>-<cost_scorer_version>.json`이다. 예: `my_demo_001.g3.s5-c3.json`처럼 버전은 실제 입력과 채점기에 따라 정해진다. 같은 run ID의 예측과 결과는 덮어쓰지 않는다.

## 입력과 재현 범위

| 경로 | 내용 |
| --- | --- |
| `manifests/` | 입력 목록과 정답지(GT) |
| `runners/` | 구현 이름표(`--impl`)와 실행기 |
| `scorers/` | 지표 계산기 |
| `predictions/`, `results/` | 커밋된 예측과 채점 JSON |
| `datasets/` | 로컬 미디어 안내. 원본 영상은 저장소에 없음 |

커밋된 예측은 원본 미디어나 유료 API 없이 **다시 채점**할 수 있다. 모델을 **다시 실행**하려면 manifest에 맞는 원본 미디어, 필요한 API 키와 실행 도구가 별도로 필요하다. 미디어가 없는 환경에서는 관련 테스트가 건너뛰어질 수 있다. 결과의 입력·코드·채점 버전은 JSON `meta`에서 확인한다. MLflow 추적은 도입하지 않았으며 결과 JSON과 Git이 기록이다.

`b_youtube`는 123개, `b_youtube_m4`는 179개 클립이다. `ctier2`, `ctier3`와 AI-Hub manifest도 있으며, 각각의 구성과 한계는 [데이터셋 문서](../docs/modules/eval/datasets/README.md)에 있다. A tier는 AI-Hub 프레임 시퀀스, B tier는 주행 영상 클립, C tier는 검토된 정상 블랙박스 클립이다.

실제 Gemini 실행에는 `uv sync --extra test --extra eval-gemini`와 루트 `.env`의 `GEMINI_API_KEY`, `DAESINGO_EVAL_DATA_ROOT`가 필요하다. 예를 들어 `--impl search:gemini-coarse-p3 --manifest b_youtube --stage candidate`를 새 run ID와 함께 실행한다. 시점별 전체 경로 비교의 등록 이름은 `search:s1-flash-1x`, `search:s2-flash-slow`, `search:s3-argon-gore`다. 실행 옵션은 `uv run python -m eval.run --help`를 본다.

CI의 [Python 테스트](../.github/workflows/python-tests.yml)는 eval 테스트를 포함한다. 로컬에서 실행한 점수의 해석과 조건은 [평가 결과](../docs/modules/eval/evaluation-results-2026-11-01.md) 및 [실험 기록](../docs/modules/eval/experiments/README.md)을 따른다.
