# 2026-09-28 · readout 트랙① 차량 검출 지속성 (AI-Hub 172 CCTV)

작성: 김대원 · 브랜치 `exp/eval-gemini-coarse-baseline` · 코드 `cc08e16`

readout 대상 차량 실험(`docs/modules/readout/experiments/track1-vehicle-2026-09-19/`)의 검출기 설정을 AI-Hub 172 CCTV 프레임에 다시 돌렸다. 지속성 정의도 그 실험과 같다.

> **제품 코드 평가가 아니다.** readout에는 아직 차량 검출 공개 함수가 없다. 이 기록이 재는 것은 「readout이 실험에서 고른 검출기(YOLO11n)가 이 데이터에서 라벨 차량을 얼마나 잡는가」다. 제품에 검출이 들어오면 그 공개 함수로 다시 잰다.

## 한눈에

| 지표 | 값 | readout 71555 (참고) |
| --- | --- | --- |
| 프레임 검출률 (라벨 차량을 IoU≥0.5로 잡은 프레임) | **95.7%** (976/1,020) | — |
| 영상별 검출 비율 | 중앙 1.00 · p10 0.83 · p90 1.00 | 중앙 1.00 · p10 0.38 |
| 한 번도 안 끊긴 영상 | **60%** (12/20) | 80.9% |
| 1~2회 끊김 · 3회 이상 | 10% · **30%** | 14.6% · 4.5% |
| 최장 연속 검출 | 중앙 36.5 · p10 14 · p90 89 프레임 | 중앙 7 |
| 2·3·5프레임 이상 검출 (`MULTI_FRAME` 가능) | 100% · 100% · 100% | 92.1% · 85.4% · 71.9% |
| 속도 | 1,020프레임 약 90s (CPU, 모델 로딩 포함) | 0.152s/프레임 |

**한 줄:** 라벨된 차량은 프레임의 96%에서 잡힌다. 그런데 영상 20편 중 6편은 3번 이상 끊긴다. 이 끊김은 같은 차량을 놓친 것이라고 단정할 수 없다(아래 「해석 주의」).

**71555와 나란히 둔 숫자는 비교용이 아니다.** 데이터(블랙박스 위반 클립 ↔ 고정 CCTV), 대상(위반 차량 ↔ 라벨 차량), 프레임 간격이 모두 다르다.

## 해석 주의 — 이 숫자가 뜻하지 않는 것

1. **같은 차량의 추적이 아니다.** 라벨이 프레임당 1대(1,016/1,020)다. 연속된 라벨 박스끼리 IoU 중앙값이 **0.02**이고, 62%는 0.1 미만이다. 라벨 간격 사이에 차량이 크게 움직였거나 다른 차량이 라벨됐다. 그래서 「끊김」은 대상을 놓친 것일 수도 있고, 새로 라벨된 차를 못 잡은 것일 수도 있다.
2. **연속 프레임이 아니다.** 라벨 frameNo 간격은 중앙 30 · 최소 5 · 최대 2,378이다. `gaps`는 라벨 프레임 순서 기준이다 (scorer coverage `SPARSE_FRAMES`).
3. **오검출은 세지 않는다.** 라벨이 전수가 아니어서 라벨 없는 차량의 검출이 전부 FP가 된다 (`NO_FP`).
4. **쉬운 도메인이다.** 고정 CCTV이고 차량 박스 높이가 중앙 260px(최소 55px)이다. 블랙박스 실도메인 절대 성능으로 읽으면 안 된다.

## [CASE]

| 항목 | 값 |
| --- | --- |
| manifest | `private_aihub172_track1` · `m1` (비공개 — AI-Hub 재배포 금지) |
| 정답지 | `at1` · 차량 박스(`car.bbox`)만. 번호판 박스는 회색 마스킹이라 쓰지 않는다 |
| 원천 | AI-Hub 172 원본이미지(merged) 라벨 |
| 표본 | 라벨 30프레임 이상 영상 5,639편 중 seed 20260921로 20편 · 1,020프레임 — `데이터셋 생성/scripts/aihub172.py frames` |
| 위치 | 부천 일대 고정 CCTV |

## [PIPELINE]

| 항목 | 값 |
| --- | --- |
| impl | `readout-exp:yolo11n` (`eval/runners/impls/yolo_persistence.py`, v1) |
| 검출기 | Ultralytics `yolo11n.pt` (COCO 사전학습) · ultralytics 8.4.133 · CPU |
| 설정 | conf 0.25 · imgsz 640 · COCO `car`·`motorcycle`·`bus`·`truck` — readout `ENVIRONMENT.md`와 같다 |
| 매칭 | conf 내림차순 greedy · IoU ≥ 0.5 (scorer `persistence` `t1`) |
| 지속성 | `runs()` — 첫 검출과 마지막 검출 사이의 미검출 구간 수. 앞뒤는 세지 않는다 (`scripts/aihub71555_clips.py`와 같다) |

## [RESULT] — 영상별

| 끊김 | 영상 수 | 영상 (검출/보임 · 최장 연속 · 끊김) |
| --- | ---: | --- |
| 0 | 12 | 전부 검출률 1.00 |
| 1 | 2 | 46/47 · 26 · 1 — 67/68 · 50 · 1 |
| 3~5 | 6 | 32/43 · 11 · 5 — 27/33 · 14 · 5 — 55/64 · 26 · 5 — 30/35 · 15 · 4 — 32/36 · 11 · 4 — 33/40 · 23 · 3 |

끊김이 많은 6편은 CCTV 두 곳(`14_1`·`116_2`)과 교차로 두 곳(`44_2`·`154_2`), 지하차도 한 곳에 몰려 있다. 같은 카메라의 다른 날짜 영상은 끊김이 0인 경우도 있다(`116_2` 3편 중 2편).

## 재현

```bash
uv sync --extra test --extra eval-yolo
# .env: DAESINGO_EVAL_PRIVATE_ROOT=D:/카테캠/데이터/_derived/eval_private
uv run python -m eval.tools.build_private_aihub172 --track 1 --source D:/카테캠/데이터/_derived/aihub172/track1_association
uv run python -m eval.run --impl readout-exp:yolo11n --manifest private_aihub172_track1 --stage persistence --run-id readout_yolo11n_track1_baseline_20260928
uv run python -m eval.score --prediction readout_yolo11n_track1_baseline_20260928
```

결과 파일: `<PRIVATE_ROOT>/results/readout_yolo11n_track1_baseline_20260928.at1.t1-c3.json` · 가중치 `<PRIVATE_ROOT>/models/yolo11n.pt`

## [LEARNING]

- **다음에 바꿀 한 가지:** 같은 차량인지 알 수 있는 데이터로 다시 잰다. 차량 id가 있는 라벨이나 연속 프레임이 필요하다. 지금 셋으로는 「tracker가 필요한가」에 답할 수 없다.
- 프레임 단위 검출은 이 도메인에서 문제가 아니다(96%). readout 쪽 병목은 검출이 아니라 **어느 차를 고르느냐**(71555 association 57.7%)와 **번호판 인식**(트랙② exact 0.19)에 있다.
- 끊김이 특정 카메라에 몰린다. 조건별로 나눠 보려면 카메라와 시간대를 층으로 삼아 표본을 늘린다. 라벨 30프레임 이상 영상이 5,639편이라 여유가 있다.
