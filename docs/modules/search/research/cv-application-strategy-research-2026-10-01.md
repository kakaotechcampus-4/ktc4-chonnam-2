# CV 모델 적용 방향 정리 — 실측 병목 기준

작성일: 2026-10-01

상태: **Research — 구현·채택 결정 아님**

대상: `search` 모듈 Fine 입력 보강과 선택적 ADAS/CV challenger

> [YOLO 조사](./yolo-assisted-gemini-fine-research-2026-09-16.md)·[오버레이 조사](./visual-prompting-overlay-research-2026-10-01.md)·
> [적응적 샘플링 조사](./adaptive-video-sampling-research-2026-09-29.md)와 9/26~10/01 실험 결과를 합쳐
> CV를 어디에 어떤 순서로 붙일지 정리한다. `product/product-spec.md` §5의 `ADAS/CV Candidate Generator`는
> 보류 상태이고, [최종 구조 제안](../decisions/search-final-structure-2026-10-01.md) §3도 CV 후보 생성기를 넣지 않았다.
> 운영 반영은 [challenger 정책](../decisions/challenger-policy.md)을 따른다. 이 문서는 모델 채택·의존성 추가를 승인하지 않는다.

---

## 1. 한눈에 보는 결론

[crop × 힌트 실험](../experiments/gemini-fine-crop-hint-2026-10-01.md)에서 Fine은 대상 차량을 맞게 잡고
확대·느린 영상까지 받아도 `141927`을 "같은 차로 유지"로 봤다. 남은 가설은 **촬영 차량도 함께 움직여
모델이 차선 대비가 아니라 화면 대비 위치로 판단한다**는 것이다(확인 전).

CV가 줄 수 있는 것은 바로 그 빠진 신호다 — **대상 차량의 차선 대비 횡위치를 프레임마다 잰 값.**

```text
0단계  crop × 대상 힌트 → Gemini Fine                (완료: 대상 연결은 고쳐짐, 검출 0)
1단계  CV 단독 오프라인 측정: 차선 위치 + 차량 추적  (Gemini 없음. CV가 횡단을 보는지 확인)
2단계  CV 횡단 시점·key frame을 Fine에 검증 전 힌트로 (1단계 성공 시)
3단계  CV 횡단 후보 ∪ Gemini Coarse                    (가장 나중, 승인 필요)
```

선 종류(실선/점선) 판정은 Gemini에 남긴다. CV가 선 종류를 이미지에 그려 넣지 않는다.

## 2. 실측 병목

| 클립 | 사례 | 증상 | 근거 |
| --- | --- | --- | --- |
| `141927` | [오버레이 조사](./visual-prompting-overlay-research-2026-10-01.md) 사례 A (1080p, 교량, 앞 회색 SUV 실선 변경) | 힌트·crop으로 대상은 맞게 잡지만 이미지·느린 영상, 구간 4–9·4–10초 모두 "횡이동 `ABSENT`" | [crop × 힌트](../experiments/gemini-fine-crop-hint-2026-10-01.md) |
| `YT_0003` | 사례 B (640×360, 터널, 오른쪽 차로 검은색 승용차) | 대상은 맞게 잡고 원거리 횡이동을 못 봄. 원본 360p라 crop해도 새 디테일 없음 | [불확실성 규칙](../experiments/gemini-fine-window-uncertain-2026-10-01.md) |
| Coarse 누락 | — | `141927`은 Coarse가 가까운 흰색 SUV를 고르거나 후보를 내지 않음 | [handoff 트레이스](../experiments/gemini-handoff-trace-2026-09-29.md) · [최종 구조](../decisions/search-final-structure-2026-10-01.md) §4 |

정리하면:

- **fps는 병목이 아니다** ([Fine 이미지 정확도](../experiments/gemini-fine-image-accuracy-2026-09-28.md)).
- **대상 연결(`TARGET_ASSOCIATION`)은 텍스트 힌트로 이미 고쳐진다.** 운영은 사용자 `target_hint`를 넘긴다.
- **9/28에 적었던 "먼 거리 선 종류의 공간 해상도" 가설은 약해졌다.** 원본 해상도 crop으로도 판정이 같고, 모델은 선 종류가 아니라 횡이동 자체를 부정한다.
- 남은 실패는 차선 대비 위치 변화 인식이다. [최종 구조](../decisions/search-final-structure-2026-10-01.md) §4는 `PRIMITIVE_FAILURE`(가설) 후보로 적었다.

모두 7클립 소수 반복 관찰이며 eval 채점 통계는 아직 없다(#158 답변 대기).

## 3. 단계별 적용안

### 0단계 — crop × 대상 힌트 (완료, 2026-10-01)

[crop × 힌트 실험](../experiments/gemini-fine-crop-hint-2026-10-01.md) 결과:

- 대상 연결은 crop이나 힌트 어느 하나로 고쳐졌다.
- 검출은 모든 조건에서 0이었다. 점선 음성 `141956` 오탐은 0이었다.
- 한계: crop 영역은 가운데 1/2 한 가지만 시험했다.

이 결과로 "Gemini에 픽셀을 더 몰아 주면 된다"는 방향은 `141927`에서 지지되지 않는다.
대상 단일 표시 오버레이(SoM 계열)도 우선순위가 내려간다. 해당 문제(대상 연결)는 텍스트 힌트로 이미 풀린다.

### 1단계 — CV 단독 오프라인 측정 (다음 후보)

Gemini 없이 CV만 돌려, **CV가 `141927` 4–10초에서 대상의 차선 횡단을 보는가**를 확인한다.

- 차선 위치 모델(§6.1) + 차량 검출·추적(§5)을 프레임마다 돌린다.
- 대상 차량 접지점과 인접 차선의 부호 있는 횡거리(lane-relative signed lateral position)를 시간축으로 그린다([YOLO 조사](./yolo-assisted-gemini-fine-research-2026-09-16.md) §18.1).
- 사람 육안 판독(약 7–8초 선 위, 약 10초 오른쪽 차로 진입, [crop × 힌트](../experiments/gemini-fine-crop-hint-2026-10-01.md))과 시점이 맞는지 본다. **라벨링 없이 판단할 수 있다.**
- 같은 측정을 `141956`(점선 변경, 음성)에도 돌린다. CV는 여기서도 횡단을 잡아야 정상이다. 실선과 점선을 가리는 일은 2단계에서 Gemini가 맡는다.
- `YT_0003`(360p 터널 원거리)은 차선 모델도 약할 가능성이 높아 대조로만 둔다.

CV도 횡단을 못 보면 이 클립에서는 CV 경로를 접는다.

### 2단계 — CV 횡단 정보를 Fine 힌트로 (1단계 성공 시)

- 원본 클립에 다음을 함께 넘긴다: CV가 고른 횡단 전·중·후 key frame과 시각 정보(JSON).
- CV 정보는 "검증되지 않은 기계 측정"이고 원본 영상이 우선한다는 지시를 붙인다([YOLO 조사](./yolo-assisted-gemini-fine-research-2026-09-16.md) §5).
- 비교 기준은 0단계 조건이다. 음성(`141956` 점선 변경)이 `OBSERVED`로 끌려가는지 따로 센다. CV는 이 클립에서도 횡단을 보고하기 때문이다.
- 운영 반영: `PRIMITIVE_FAILURE`로 challenger 개방 절차. Fine 입력이 바뀌므로 **eval에 먼저 통보**(원칙 8).

### 3단계 — CV 후보 생성기 (Coarse 누락 대응, 가장 나중)

- 추적기 횡이동 + 차선 기하로 "선 횡단 시점"만 후보로 내고 Gemini Coarse 후보와 합친다([YOLO 조사](./yolo-assisted-gemini-fine-research-2026-09-16.md) §21 P3).
- 선 종류 판정은 Gemini에 남긴다.
- 차선 모델 도입·라이선스 검토·PM 승인 필요.

## 4. 오버레이 조사의 실험안에서 바꿀 것

[오버레이 조사](./visual-prompting-overlay-research-2026-10-01.md) 사례 A·B 실험안 기준.

- **CV가 그린 "노란 실선 강조"는 넣지 않는다.** Gemini가 확인할 primitive를 답으로 그려 주는 셈이다. 같은 조사가 잘못된 오버레이의 환각 유발을 지적한다.
- **붉은 박스를 쓰지 않는다.** 신호색과 혼동된다.
- **대상 모델을 GPT-4V에서 Gemini로 바꾼다.** 프록시 경유 조건이다.
- **대상 박스+ID 오버레이는 후순위.** 사례 A(`141927`)에서 대상 연결은 텍스트 힌트로 이미 고쳐졌고 검출은 바뀌지 않았다.
- **사례 B(`YT_0003`)는 후순위.** 원본 픽셀이 적어 crop·오버레이로 늘어날 정보가 없다.

## 5. Ultralytics 제공 범위

공식 문서(docs.ultralytics.com) 기준, 2026-10-01 확인.

| 제공 | 내용 |
| --- | --- |
| 작업 | detect · segment · classify · pose · OBB |
| 모델 | YOLOv3~YOLO26, YOLO11·v8·v10, RT-DETR, YOLO-World, SAM/SAM2/MobileSAM/FastSAM |
| 모드 | train · val · predict · track · export · benchmark |
| 추적기 | BoT-SORT(기본, GMC: ORB·SIFT·ECC·sparse optical flow, ReID 옵션), ByteTrack |
| Solutions | 선·영역 카운팅, 속도 추정(`meter_per_pixel`), 거리, 히트맵, 주차·대기열 등 |
| export | ONNX · TensorRT · OpenVINO · CoreML · TFLite/LiteRT · NCNN 등 20여 종 |
| 기본 가중치 | COCO 80종(car·truck·bus·motorcycle·bicycle·person·traffic light·stop sign 등) |

제공하지 않는 것:

- 차선 검출, 실선/점선, 중앙선 의미, 정지선
- 신호등 색 상태와 적용 신호 연결
- 안전모 클래스
- 번호판 OCR(패키지 기능 아님, 어차피 `readout` 경계)
- 이동 블랙박스용 속도·거리(Solutions는 고정 카메라 전제)
- 위반 판정 로직

라이선스는 **AGPL-3.0 또는 Enterprise**다. 저장소는 MIT이므로 제품 의존성 전 검토가 필요하다([YOLO 조사](./yolo-assisted-gemini-fine-research-2026-09-16.md) §13.2).
1단계의 차량 검출·추적은 Ultralytics 범위다. 차량 검출과 차선 분할을 한 번에 주는 YOLOPv2(MIT)로 대신할 수도 있다.

## 6. 차선 모델

1단계에 필요한 것은 **차선 위치**다. 선 종류 분류는 필수가 아니다.

### 6.1 위치만 찾는 모델 — 흔함

| 모델 | 출력 | 라이선스 | 비고 |
| --- | --- | --- | --- |
| UFLDv2 | 차선 곡선 좌표 | MIT | ONNX·TensorRT, 고속 |
| CLRNet | 차선 곡선 좌표 | Apache-2.0 | 구형 환경, 별도 컨테이너 필요 |
| LaneATT | 차선 곡선 좌표 | 확인 필요 | |
| YOLOPv2 | 차량 검출 + 주행영역 + 차선 픽셀 분할 | MIT | 차선 종류 구분 없음 |

TuSimple·CULane 학습 모델은 데이터에 차선 종류 라벨이 없어서 선 위치까지만 준다.

### 6.2 실선/점선 구분 — 드묾

- LVLane (arXiv 2023): 검출 + 실선/점선 분류 연구. 가중치 공개 여부·한국 도로 적용성 미확인.
- CondLaneNet: [오버레이 조사](./visual-prompting-overlay-research-2026-10-01.md)는 "실선/점선 분리 분류 기능 있음"이라 적었으나 위치 검출 모델로 알려져 있다. 원문 확인 필요.
- 차선 모델 + 픽셀 후처리: 검출 곡선을 따라 색과 끊김 패턴을 본다([YOLO 조사](./yolo-assisted-gemini-fine-research-2026-09-16.md) §18.3). 학습은 필요 없지만 먼 거리에서 약하다.

### 6.3 AI Hub 차선/횡단보도 인지 영상 — 학습된 모델 있음

[수도권](https://aihub.or.kr/aidata/27675) · [수도권 외](https://www.aihub.or.kr/aihubdata/data/view.do?currMenu=115&topMenu=100&dataSetSn=196) 데이터셋 페이지 기준.

| 항목 | 내용 |
| --- | --- |
| 데이터 | 차량 카메라 영상 추출 이미지, 수도권 845,571장 · 수도권 외 850,407장 |
| 라벨 | 차선·정지선 polyline, 횡단보도 polygon. 속성 `type`(dotted/solid), `color`(white/yellow/blue) |
| 모델 | **FCN ResNet50**. 페이지 표기는 Object Detection이지만 구조상 분할 모델 |
| 학습 과제 | 차선 색(백·황·청) + 실선/점선, 정지선, 횡단보도 |
| 성능 | F1 0.8972 (기준값 0.6). 자체 테스트셋, F1 산출 방식은 페이지에 없음 |
| 구축 | 2020년 (2021-11 갱신) |
| 다운로드 | "AI 모델 다운로드" 링크. 데이터셋 신청 승인 후, **내국인만** 신청 가능 |

[AI Hub 이용정책](https://aihub.or.kr/intrcn/guid/usagepolicy.do):

- 영리·비영리 연구·개발 목적 활용 가능. 데이터셋 판매 등은 별도 협의.
- 한국지능정보사회진흥원 사업 결과임을 표시해야 하고, 2차 저작물에도 동일하게 표시해야 한다.
- 국외 주체 이용·국외 반출은 별도 합의 필요.

받아 봐야 알 수 있는 것:

1. 다운로드 구성 — 가중치·코드 포함 여부(페이지 표기는 "상세 설명서")
2. 실행 환경 — 2020년 모델, 구형 PyTorch 가능성
3. 우리 영상 성능 — 블랙박스 화질, 먼 거리 선(`141927`), 640×360 영상에서 미지수
4. 모델 파일에 별도 라이선스가 붙어 있는지

한국 도로 학습 + 위치와 선 종류를 함께 주는 유일한 기성 후보다. 1단계 차선 위치 모델 후보로 6.1 모델과 함께 비교한다.

## 7. 학습과 라벨링

- **AI Hub 데이터로 학습하면 라벨링은 거의 필요 없다.** 라벨이 이미 있고 형식 변환만 하면 된다.
- **1단계는 라벨링 없이 가능하다.** 정답지 시각과 육안 판독으로 횡단 시점만 맞춰 본다.
- **기성 모델을 여러 클립에 정량 평가하려면 평가용 라벨이 필요하다.** `video/정답지.md`는 사건 단위라 프레임별 차선 라벨이 아니다.
  - 정답지 7클립 위반 전후 프레임, 클립당 10~20장, 합계 100~150장(가늠치)
  - 차선별 polyline + 색·실선/점선, AI Hub와 같은 형식
  - 도구: CVAT 또는 Label Studio polyline
  - 사람도 판단하기 어려운 먼 거리 선은 "판단 불가"로 따로 표시한다
- **추가 학습(fine-tuning)용 라벨은 평가에서 크게 떨어질 때만** 수백 장 규모로 만든다.

권장 순서:

```text
1단계 CV 단독 측정 — 141927·141956 (라벨링 없음)
  → (성공 시) 2단계 Fine 힌트 비교
  → (여러 클립 정량화 필요 시) 평가용 100~150장 라벨링
  → (기성 모델 부족 시) AI Hub 데이터로 학습 — 주간 회의 안건
```

## 8. 문서 간 충돌

| 항목 | [오버레이 조사](./visual-prompting-overlay-research-2026-10-01.md) | [YOLO 조사](./yolo-assisted-gemini-fine-research-2026-09-16.md) / 공식 |
| --- | --- | --- |
| YOLOv7/v8 라이선스 | "오픈" | Ultralytics AGPL-3.0 또는 Enterprise |
| UFLD 라이선스 | GPL | UFLDv2 MIT |
| CondLaneNet 학회 | ICCV'19 | 확인 필요 |

의존성 판단 전에는 YOLO 조사 쪽과 공식 저장소를 기준으로 다시 확인한다.

## 9. 승인·통보

| 작업 | 혼자 해도 되나 | 필요한 것 |
| --- | --- | --- |
| AI Hub 데이터셋·모델 신청 | 예 | Owner 본인 신청(내국인) |
| 1단계 CV 단독 오프라인 측정 | **판단 필요** | [YOLO 조사](./yolo-assisted-gemini-fine-research-2026-09-16.md) §11.1은 CV 실험을 challenger 개방 후로 둔다. [최종 구조](../decisions/search-final-structure-2026-10-01.md) §5-4는 두 미해결 클립을 eval 실패 통계에 넣어 개방 근거로 쓰겠다고 한다. 주간 회의 안건으로 올리는 것이 안전하다 |
| 2단계 Fine 힌트 운영 반영 | 아니오 | challenger 개방(`PRIMITIVE_FAILURE`), eval 사전 통보(원칙 8), 라이선스 검토 |
| 3단계 CV 후보 생성기 | 아니오 | challenger 개방, PM 승인, 차선 모델 라이선스 |
| AI Hub 데이터로 학습 | 아니오 | 주간 회의 안건(PM 승인), GPU·일정 |

## 10. 미결

- `141927` 실패 원인이 화면 대비 위치 판단(ego-motion)인지: 확인 전.
- CV 차선 모델이 `141927` 교량 원거리에서 차선을 안정적으로 잡는지: 미측정.
- crop·key frame 파생 자산의 저장 여부와 보존 기간: 미정([YOLO 조사](./yolo-assisted-gemini-fine-research-2026-09-16.md) §15-8).
- eval 반복 횟수와 공식 매칭 기준: #158 답변 대기.
- AI Hub 모델 다운로드 구성과 우리 영상 성능: 미확인.
- CondLaneNet·LVLane의 실선/점선 분류 기능과 가중치 공개 여부: 미확인.
