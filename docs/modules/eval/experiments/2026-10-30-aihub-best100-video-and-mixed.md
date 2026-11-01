# 2026-10-30 · AI-Hub 선별 영상 유형 평가와 블박 삽입 진단

실행: `search:s3-argon-gore` 설정의 Coarse 영상 유형 평가와 별도 Coarse→Fine 합성 진단 · 모델 `gemini-4-argon` · 개발 중 반복 측정. 입력과 결과의 정본은 아래 manifest·prediction·result JSON이다. 원본 영상은 로컬에만 둔다.

## 1. 데이터와 질문

| 평가 | 입력 | 정답 | 질문 |
| --- | --- | --- | --- |
| 전체 단독 영상 | `a_aihub_best100_all` bm1 · bg1: 4종 × 100개, 원본 Training 271개 + Validation 129개, 재생 길이 합계 2733.9초 | `manifest.csv`의 4종 유형 | 선별 영상 400개 전체에서 최상위 후보의 유형이 맞는가? **Training 포함 개발 점수** |
| 단독 영상 | `a_aihub_best100_val` bm1 · bg1: 원본 Validation 129개 중 이전 A tier와 중복 12개를 뺀 117개, 재생 길이 합계 960.9초 | `manifest.csv`의 4종 유형 | 영상 전체에서 Search가 반환한 최상위 후보의 유형이 맞는가? |
| 블박 삽입 | `aihub_mixed_pilot_mp2` mp2: 검토된 C tier 2 정상 블박 8개에 위 117개 중 유형별 긴 영상 2개씩 삽입한 8개 + 같은 배경만 재인코딩한 대조 8개 | 삽입 시작·끝 20.0초~20.9–47.6초와 유형 | 상위 3개 후보가 삽입 구간 안에 있고 유형이 맞는가? 대조에서 후보는 얼마나 나오는가? |

원천 `D:/카테캠/데이터/AIHub_traffic_videos_best_100_each/manifest.csv`에는 4종별 100개씩 400개가 있다. 271개는 원본 Training이므로 **400개 전체와 Validation 중복 제거 117개를 별도로** 집계한다. 117개 표본의 유형별 크기는 신호 37 · 중앙선 36 · 실선 차로변경 35 · 안전모 미착용 9다. 모든 영상이 양성이고 위반 시점 라벨은 없다.

## 2. 실행 규칙

- 단독 영상: 제품 Search 공개 함수 `search_candidates`를 영상 전체에 적용. 점수 상위 후보의 `event_type_hint`를 `predicted`로 기록. 후보가 없거나 유형이 없으면 `NONE`. Fine 검증은 실행하지 않았다. 즉 **단독 분류기 정확도가 아니라 탐색과 유형 판정을 합친 영상 단위 적중률**이다.
- 삽입 진단: 검토된 C tier 2 정상 클립의 앞 20초와 뒤 40초 사이에 AI-Hub 영상을 넣었다. 삽입·대조 모두 H.264 CRF 26, 640×360, 10fps, 무음으로 재인코딩했다. 삽입 원본 길이는 0.9~27.6초. 상위 3개 후보의 대표 시점이 **삽입 구간 전체**에 들어오면 위치 적중, 유형도 맞으면 위치+유형 적중으로 셌다. 정밀 onset ±2초 점수가 아니다. Coarse만 실행한 run과 Coarse→Fine run은 **각각 새로 호출**했으므로 같은 후보가 이어진 한 실행으로 비교하지 않는다.
- 세 데이터셋은 S3 모델·설정(`gemini-4-argon`, Coarse 2fps)을 사용했다. 실행은 파일별 SHA-256 대조 후 시작하며, prediction은 후보 목록·실패 상태·사용량을 보존한다. 단독 영상 run은 영상당 Coarse 1회, Fine run은 영상당 Coarse 1회에 후보별 Fine 호출을 추가했다.

## 3. 결과

### 전체 선별 영상 400개 — Training 포함 개발 점수

| 유형 | 정답 / 전체 | 적중률 | 95% Wilson 구간 |
| --- | ---: | ---: | ---: |
| 신호위반 | 94 / 100 | 94% | 87.5–97.2% |
| 중앙선 침범 | 91 / 100 | 91% | 83.8–95.2% |
| 실선 차로변경 | 91 / 100 | 91% | 83.8–95.2% |
| 안전모 미착용 | 95 / 100 | 95% | 88.8–97.8% |
| **전체** | **371 / 400** | **92.8%** | **89.8–94.9%** |

4종 macro recall도 **92.8%**(각 100개라 전체 적중률과 같음). 400건 모두 `SUCCEEDED`, 예측 `NONE` 5건. 원본 분할별로는 Validation **116/129(89.9%)**, Training **255/271(94.1%)**이다. 분할 간 차이를 원인이나 모델 일반화 성능으로 해석할 수 없다. 파일 선별 기준과 세부유형 분포가 다르고, 모델의 사전 학습 자료 중복 여부도 확인되지 않았다. 기록 비용은 **$2.43**, 호출 latency 중앙값 **6.4초**다.

### 중복 제거 Validation 117개 — 별도 실행

| 유형 | 정답 / 전체 | 적중률 | 95% Wilson 구간 |
| --- | ---: | ---: | ---: |
| 신호위반 | 35 / 37 | 94.6% | 82.3–98.5% |
| 중앙선 침범 | 30 / 36 | 83.3% | 68.1–92.1% |
| 실선 차로변경 | 32 / 35 | 91.4% | 77.6–97.0% |
| 안전모 미착용 | 8 / 9 | 88.9% | 56.5–98.0% |
| **전체** | **105 / 117** | **89.7%** | **82.9–94.0%** |

기존 분류 채점기의 4종 macro recall은 **89.6%**다. 117건 모두 Search 호출은 `SUCCEEDED`; 영상별 예측 중 `NONE`은 2건이었다. 대상 bbox 정답이 없어 target correctness는 `null`이다. 정상 영상이 없어 `NONE` recall·오탐률은 계산할 수 없다. 비용 기록은 **$0.75**, 호출 latency 중앙값 **6.8초**다. 400개 run 안의 같은 117개도 105개 적중했지만 **개별 예측 5개는 두 run 사이에 달랐다**. 같은 입력의 단일 실행 점수가 모델 출력을 완전히 고정하지 않는다는 뜻이다. 두 셋의 재생용 10fps 길이를 실제 촬영 시간으로 간주하지 않으므로 원본 영상 1시간당 비용 수치는 사용하지 않는다.

### 블박 삽입 8쌍 — Coarse만 실행한 run

| 지표 | 결과 |
| --- | ---: |
| 삽입 구간 안에 상위 3개 후보의 대표 시점 있음 | 8 / 8 |
| 위 조건 + 올바른 유형 | 8 / 8 |
| 정상 대조 영상에서 후보가 하나 이상 나옴 | 6 / 8 |
| 정상 대조 영상의 상위 3개 후보 합계 | 11개 |

16개 영상 모두 Search가 `SUCCEEDED`로 처리했다. 호출 사용량 합계는 **$0.39**, latency 중앙값은 **9.7초**다. 안전모 2개는 원본 길이가 0.9~1.0초로 특히 짧고, 맞힌 후보의 대표 시점도 삽입 시작 20.0초와 그 직후 20.25초다. 경계 효과를 배제할 수 없다. 대조 영상의 후보는 **Coarse 후보**이며 Fine 검증이 없어 확정 오탐 수로 부르지 않는다. 삽입 8/8은 표본이 작고 삽입 경계가 눈에 띄는 조건의 수치다.

첫 `mp1` 실행에서는 배경 영상 하나가 실제 59.7초인데 60.0초로 적혀, `injected_02`·`control_02` 모두 `MEDIA_PREPARATION_FAILED`였다. `mp2`는 렌더링된 16개 영상의 길이를 ffprobe로 측정해 고정했고 새 run ID로 전부 다시 실행했다. 첫 실행과 재시도 prediction·result는 원인 추적을 위해 보존하되 성능 표에는 사용하지 않는다.

### 블박 삽입 8쌍 — Coarse→Fine 새 실행

| 지표 | 결과 |
| --- | ---: |
| 삽입 구간 안에 상위 3개 후보의 대표 시점 있음 | 8 / 8 |
| 위 조건 + 올바른 유형 | 7 / 8 |
| 위 조건 + 올바른 유형 + Fine `OBSERVED` | **6 / 8** |
| 정상 대조 영상에서 후보가 하나 이상 나옴 | 6 / 8 |
| 정상 대조에서 `OBSERVED` 후보가 남은 영상 | **3 / 8** (후보 3개) |
| 정상 대조에서 `OBSERVED` 또는 `UNCERTAIN` 후보가 남은 영상 | 4 / 8 (후보 5개) |

16개 중 15개는 `SUCCEEDED`, `control_04`는 영상 밖 후보가 제거되어 `PARTIAL`이다. Fine 오류는 없었다. 사용량 39건(Coarse 16회와 후보별 Fine 호출), 기록 비용 합계 **$0.77**. 삽입 `injected_04`는 Coarse run에서는 안전모 유형을 상위 3개에 냈지만 이 새 실행에서는 내지 않았다. `injected_05`는 유형 후보를 냈으나 Fine이 `OBSERVED`로 확인하지 않았다. 정상 대조의 `OBSERVED` 3건은 실제 위반 정답이 없는 영상에서 남은 **최종 오탐 후보**다.

## 4. 해석과 다음 확인

이 결과는 새 영상의 유형 라벨을 활용해 현행 Search가 양성 영상을 얼마나 잘 찾아 분류하는지 보여 준다. **117개 run**에서 중앙선 오류 6건, 실선 오류 3건, 신호 오류 2건, 안전모 오류 1건이 있다. 이 run의 안전모는 9개라 구간이 넓고, 유형별 100개 전체의 점수와 구분해야 한다.

삽입 영상은 사건의 정밀 발생 시점이 알려지지 않아 삽입 구간 전체를 정답 범위로 썼다. 장면·압축·프레임 속도의 전환점이 모델에게 단서가 될 수 있고, 정상 대조 8개에서도 6개에 후보가 나왔다. **합성 개발 진단**으로만 사용한다. 원천의 선택 기준(긴 길이·가시성·밝기·선명도), 원본 Training/Validation 구분, 사전 학습 데이터와의 중복 미확인도 일반화 한계다. 최종 제품 성능은 편집하지 않은 `locked_test` 실제 장시간 블박에서 따로 측정한다.

후속 확인은 (1) 삽입 지점 앞뒤에 후보가 몰리는지 시점별 점검, (2) 아래 100쌍 확장 진단에서 정상 대조 오탐을 확인, (3) 원본 자료의 프레임별 사건 시점 라벨 확보 후 정밀 탐색 채점이다.

## 5. 재현 및 산출물

```bash
uv run python -m eval.tools.evaluate_aihub_best100 build --source D:/카테캠/데이터/AIHub_traffic_videos_best_100_each
uv run python -m eval.tools.evaluate_aihub_best100 run --run-id <새_id>
uv run python -m eval.score --prediction <새_id>
uv run python -m eval.tools.evaluate_aihub_best100 build --set all
uv run python -m eval.tools.evaluate_aihub_best100 run --set all --run-id <다른_새_id>
uv run python -m eval.score --prediction <다른_새_id>
uv run python -m eval.tools.evaluate_aihub_mixed build
uv run python -m eval.tools.evaluate_aihub_mixed run --run-id <새_id>
uv run python -m eval.tools.evaluate_aihub_mixed run --fine --run-id <다른_새_id>
```

`build`는 고정 manifest가 이미 있으면 덮어쓰지 않는다. 재생성할 때는 새 버전·경로로 만든다. 산출물은 `eval/manifests/a_aihub_best100_{all,val}/`, `eval/manifests/aihub_mixed_pilot_mp2/samples.json`, `eval/predictions/aihub_best100_{all,val}_s3_20261030.json`, `eval/results/aihub_best100_{all,val}_s3_20261030.bg1.cl3-c3.json`, `eval/predictions/aihub_mixed_pilot_mp2_s3_20261030.json`, `eval/results/aihub_mixed_pilot_mp2_s3_20261030.mp2.json`, `eval/predictions/aihub_mixed_pilot_mp2_s3_fine_20261030.json`, `eval/results/aihub_mixed_pilot_mp2_s3_fine_20261030.mp2-fine.json`이다. 혼합 MP4 16개는 `eval/datasets/aihub_mixed_pilot/`에만 있고 커밋하지 않는다.

## 6. 확장 혼합 세트: 100쌍

8쌍 파일럿을 확장해 `aihub_mixed_100_v1`을 만들었다. 서로 다른 검토된 `ctier2` 정상 블랙박스 100개를 배경으로 쓰고, AI-Hub 원본 100개를 유형별 25개씩 삽입했다. 같은 배경만 재인코딩한 정상 대조 영상 100개를 함께 만들었으므로 총 200개다. 파일럿의 배경 8개는 제외했다. 원본은 기존 A tier와 시퀀스 중복을 제거한 Validation 84개를 우선 사용했고, 안전모 표본 부족분 Training 16개를 사용했다. `samples.json`에 영상별 배경 ID, 삽입 원본 ID·분할, 유형, 삽입 구간, 인코딩 후 길이, SHA-256을 기록했다.

삽입 시작은 순서대로 10·20·30초를 반복한다. 블랙박스 앞부분과 뒷부분을 이어 붙이고, 원본·대조 모두 640×360, 10fps, H.264 CRF26, 무음으로 인코딩했다. 원본 프레임의 10fps는 실제 촬영 시각이 아닌 재생용이므로, 이 결과에서 시간당 오탐률을 제품 수치로 해석하지 않는다. 삽입 경계와 화면 출처 차이가 단서로 작용할 수 있다.

재현 명령:

```bash
uv run python -m eval.tools.build_aihub_mixed_100 --workers 4
uv run python -m eval.tools.evaluate_aihub_mixed run --dataset aihub_mixed_100_v1 --fine --workers 4 --run-id aihub_mixed_100_v1_s3_fine_20261030
```

영상은 `eval/datasets/aihub_mixed_100_v1/`에 로컬 보관하고 manifest는 `eval/manifests/aihub_mixed_100_v1/samples.json`이다.

### 확장 세트 평가 결과: Coarse + Fine

동일한 Search S3 설정으로 200개를 각각 호출했다. 상위 3개 후보의 대표 시점이 삽입 영상 전체 구간 안에 들어오면 위치 일치, 유형까지 맞으면 유형 일치, Fine이 `OBSERVED`까지 반환하면 검증 일치로 집계한다. 위반 onset의 ±2초 정답은 원본에 없어 이 지표를 사건 탐지 recall로 부르지 않는다.

| 구분 | 삽입 구간 위치 일치 | 위치 + 유형 일치 | 위치 + 유형 + Fine `OBSERVED` |
| --- | ---: | ---: | ---: |
| 중앙선 침범 (25개) | 24 | 21 | 19 |
| 안전모 미착용 (25개) | 24 | 21 | 21 |
| 신호 위반 (25개) | 24 | 22 | 20 |
| 실선 차로 변경 (25개) | 25 | 25 | 18 |
| **전체 삽입 100개** | **97 (97%)** | **89 (89%)** | **78 (78%)** |

| 정상 대조 100개 | 결과 |
| --- | ---: |
| 상위 3개 후보가 하나라도 나온 영상 | 72개 |
| 상위 3개에서 `OBSERVED`가 하나라도 나온 영상 | **29개 (29%)** |
| `OBSERVED` 후보 수 | 40개 |

전체 200개 중 191개는 `SUCCEEDED`, 9개는 `COARSE_SPAN_OUT_OF_SOURCE`가 포함된 `PARTIAL`이었다. 후보별 Fine `ProviderPayloadError`도 2건 있었고 해당 후보는 검증 일치에 넣지 않았다. 이 오류와 부분 처리 사례를 제외하지 않은 전체 100쌍 기준 수치다. 총 모델 호출 기록 491건, 기록 비용 **$9.03**이다. 원본 Training 16개가 포함되어 있고 영상 자체도 장면을 통째로 끼워 넣은 합성이므로, 이 수치는 실제 위반 탐지 성능이나 실시간 오탐률이 아니다. 특히 정상 배경 29개에서 검증된 후보가 나와 배포 전 실제 영상의 오탐 확인이 필요하다.

원본 결과는 `eval/predictions/aihub_mixed_100_v1_s3_fine_20261030.json`과 `eval/results/aihub_mixed_100_v1_s3_fine_20261030.mixed-fine.json`에 있다.
