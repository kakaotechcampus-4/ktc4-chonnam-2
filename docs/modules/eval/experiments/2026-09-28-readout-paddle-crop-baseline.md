# 2026-09-28 · readout 번호판 인식 베이스라인 (AI-Hub 172 crop)

작성: 김대원 · 브랜치 `exp/eval-gemini-coarse-baseline` · 코드 `3db9b10`

readout의 공개 함수 `read_plate`와 `PaddleOcrProvider`를 AI-Hub 172 번호판 crop 500장에 처음 돌린 결과다. **이 기록에는 집계 수치만 있다.** 정답지·예측·결과 JSON에는 실제 차량번호가 들어 있어서 `DAESINGO_EVAL_PRIVATE_ROOT`(담당자 D 드라이브)에만 있다.

## 한눈에

| 지표 | 값 | 정의 |
| --- | --- | --- |
| `exact_accuracy` | **0.192** (95/496) | 보류하지 않은 판독 중 정답과 글자가 완전히 같은 비율 (scorer `p2`) |
| 공백 무시 exact | 0.331 (165/500) | 참고값. scorer 정의가 아니다 — 아래 [FAILURE] ① |
| `readable_abstention_rate` | 0.008 (4/500) | 읽을 수 있는데 보류한 비율. 사유는 전부 `LOW_RESOLUTION` |
| 값 없음 (`UNKNOWN`) | 164/500 (32.8%) | 번호판 줄을 하나도 고르지 못했다 |
| `OK`인데 틀림 | **168/332 (50.6%)** | 보류 없이 확정한 판독의 절반이 틀렸다 (공백만 다른 69건 제외) |
| CER (전체) | 0.452 | 참고값. 값이 없으면 전부 삭제로 센다 |
| `wrong_accept_rate` · `abstention_recall` | null | 정답지에 판독불가 항목이 없다 (분모 0) |
| 실패 run | 0/500 | |
| 속도 | 장당 약 0.2s (CPU, 첫 장은 모델 로딩 26s) | |

**한 줄:** 신형 1줄 번호판은 3장 중 1장 정도 읽는다. 지역명이 들어간 구형 번호판은 한 장도 못 읽는다. 가장 큰 위험은 보류율 0.8%다. 틀린 값도 거의 보류 없이 `OK`로 나온다.

## [CASE]

| 항목 | 값 |
| --- | --- |
| manifest | `private_aihub172_plate` · `m1` (비공개) |
| 정답지 | `ap1` · 500건 전부 `READABLE` — AI-Hub가 모든 crop에 `value`를 달았다 |
| 원천 | AI-Hub 172 「자동차 차종/연식/번호판 인식용 영상」 번호판OCR 구획, **Training** split |
| 표본 | seed 20260921 · 500장 · crop 중앙 266×126px (최소 106×56) — `데이터셋 생성/scripts/aihub172.py sample` |
| 분리 | readout이 PR #80에서 쓴 Validation · seed 20260915 표본과 겹치지 않는다 (도구가 그 조합을 거부한다) |
| 번호판 형태 | 신형 1줄(`12가3456`·`123가4567`) 331 · 지역명 포함 166 · 기타 3 |

**재는 것은 인식 단계뿐이다.** crop이 이미 잘려 있어 대상 차량 찾기와 번호판 위치 잡기가 빠져 있다. 고정 CCTV 원천이라 블랙박스 실도메인 절대 성능으로 읽으면 안 된다.

## [PIPELINE]

| 항목 | 값 |
| --- | --- |
| impl | `readout:paddle-crop` (`eval/runners/impls/readout_paddle.py`, v1) |
| 호출 경계 | `daesingo.readout.read_plate(request, provider=PaddleOcrProvider(CropFrameSource))` — `case/real_e2e.py`와 같은 경로 |
| provider | `paddleocr-3.7.0-ppocrv5-korean` · `PP-OCRv5_mobile_det` + `korean_PP-OCRv5_mobile_rec` · CPU |
| 입력 | crop 1장 = 프레임 1장 → consensus는 항상 `SINGLE_FRAME` |
| target_hint | 없음 → association `LOW_CONFIDENCE` / `NOT_PROVIDED` |
| 계약 | `plate-readout/v1.3` |
| 채점 | scorer `p2` · 정답지와는 `scenario_id`(표본 id)로 잇는다 |

## [RESULT]

### 판독 상태 × 정답

| status | 정답 | 공백만 다름 | 오답 | 값 없음 | 계 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `OK` | 95 | 69 | 168 | — | 332 |
| `NEEDS_REVIEW` (보류) | 1 | — | 3 | — | 4 |
| `UNKNOWN` | — | — | — | 164 | 164 |

### 번호판 형태별

| 형태 | n | exact | 값 없음 |
| --- | ---: | ---: | ---: |
| 신형 1줄 | 331 | 96 (29.0%) | 129 |
| 지역명 포함 | 166 | **0** | 33 |
| 기타 | 3 | 0 | 2 |

지역명 번호판 166장 중 96장은 지역명 뒤쪽(`12가3456` 부분)만 읽었다.

### 오답 유형 (값을 냈는데 틀린 171건 + 공백 69건)

| 유형 | 건수 |
| --- | ---: |
| 길이 다름 (대부분 지역명 누락) | 158 |
| 공백만 다름 | 69 |
| 같은 길이에서 글자 오인식 | 13 — 틀린 자리 20곳이 **전부 한글**이다 |

## [FAILURE]

분류 이름은 `docs/modules/readout/decisions/failure-taxonomy.md`를 따른다.

| stage | kind | 건수 | 관찰 |
| --- | --- | ---: | --- |
| PLATE | `PLATE_RECOGNITION` — 지역명 | 166 | 지역명 번호판을 한 장도 못 읽는다. `PLATE_PATTERN`(`\d{2,3}[가-힣]\d{4}`)이 지역명을 모르고, 2줄 배치에서 윗줄을 버린다 |
| PLATE | `PLATE_RECOGNITION` — 무검출 | 164 | 번호판 줄 후보가 필터를 하나도 통과하지 못해 `UNKNOWN`이 됐다. 신형 1줄에서도 129건 나왔다 |
| PLATE | `PLATE_RECOGNITION` — 한글 | 13 | 숫자는 맞고 한글 한 글자가 틀렸다 |
| — | 채점 정의 | 69 | ① 값에 공백이 들어 있다(`12가 3456` 모양). scorer는 문자열 완전일치라 오답으로 센다. 공백을 제품이 정규화할지, 채점기가 무시할지는 **readout Owner와 정할 일**이다. 여기서는 scorer를 바꾸지 않았다 |

**보류가 거의 작동하지 않는다.** 확정(`OK`) 332건 중 168건이 공백 차이가 아닌 진짜 오답이다. 보류 사유는 4건 모두 `LOW_RESOLUTION`이었다. 표본 전체가 `READABLE`이라 scorer의 `wrong_accept_rate`는 null이다. 그래도 제품 위험으로 보면 「읽을 수 있는 번호판을 확신에 차서 틀리게 읽는」 경우가 가장 크다.

## readout 기준선과의 관계

readout PR #80은 Validation 500장에서 Exact 5.6% · CER 55.3%를 냈다(`docs/modules/readout/experiments/ocr-baseline-2026-09-15/`). 이번 수치(exact 0.192 · CER 0.452)와 **직접 비교하지 않는다.** split이 다르고(Validation ↔ Training), 그때는 팀 레포 밖 스크립트로 돌렸고, 지금은 제품의 `read_plate` 판정과 `pick_plate` 필터를 거친다. 지표 분모도 다르다.

## 재현

```bash
uv sync --extra test --extra readout-paddle
# .env: DAESINGO_EVAL_PRIVATE_ROOT=D:/카테캠/데이터/_derived/eval_private
uv run python -m eval.tools.build_private_aihub172 --source D:/카테캠/데이터/_derived/aihub172/track2_recognition
uv run python -m eval.run --impl readout:paddle-crop --manifest private_aihub172_plate --stage plate --run-id readout_paddle_crop_baseline_20260928
uv run python -m eval.score --prediction readout_paddle_crop_baseline_20260928
```

결과 파일: `<PRIVATE_ROOT>/results/readout_paddle_crop_baseline_20260928.ap1.p2-c3.json`

## [LEARNING]

- **다음에 바꿀 한 가지:** 공백 정규화를 readout과 합의한다. 이것만으로 exact가 0.19에서 0.33이 되고, 코드 한 줄짜리 결정이다.
- 지역명 번호판(166/500)을 계속 셋에 둘지 정해야 한다. 블랙박스 실도메인에서 구형 지역명 번호판이 얼마나 되는지 모르면, 이 33%가 성능을 얼마나 깎아야 맞는지도 모른다. 형태별 수치를 따로 보고하는 편이 낫다.
- 보류 판정에 **형식 검사**를 넣을 여지가 있다. 오답 대부분이 길이가 맞지 않는 값이다.
- 판독불가 라벨이 있는 셋(C tier)이 생기기 전까지 `wrong_accept_rate`는 잴 수 없다. 이 셋의 「OK인데 틀림」 비율은 그 대용으로만 본다.
