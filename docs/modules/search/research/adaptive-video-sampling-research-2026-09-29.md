# 적응적 영상 샘플링·Coarse→Fine 연구 조사

작성일: 2026-09-29

상태: **Research — 구현·채택 결정 아님**

대상: `search` 모듈의 Coarse 후보 생성과 Fine 입력 전략

> 외부 조사 요약을 받아 정리했다. 수치는 조사 요약에 적힌 논문 보고치이며 **원문 대조 전**이다.
> 요약 안에서 서로 맞지 않는 수치는 §4에 모았다. 인용하기 전에 원 논문을 확인한다.

---

## 1. 한눈에 보는 결론

긴 영상을 싸게 보는 연구는 다섯 갈래로 나뉜다.

| 갈래 | 아이디어 | 대표 연구 |
| --- | --- | --- |
| 적응적 프레임 선택 | 영상마다 중요한 프레임만 골라 본다 | AdaFrame, Ada3D |
| 공간 초점 | 전체는 저해상도, 중요한 영역만 고해상도로 본다 | AdaFocus V2 |
| 조기 종료 | 판단이 확실해지면 남은 프레임을 건너뛴다 | FrameExit, AdaFocus V2+ |
| 계층·단위 처리 | 영상을 의미 단위로 나눠 단위별로 본다 | ViMo |
| 가벼운 필터 + 정밀 모델 | 싼 필터로 후보를 거르고 VLM이 재검증한다 | Cerberus |

**대신고에 바로 옮길 수 있는 것은 Cerberus 구조와 공간 초점 아이디어 두 가지다.** 나머지는 학습된
정책 네트워크(LSTM·RL 게이트)가 전제라서, 학습하지 않고 Gemini API를 호출하는 현재 구조에는
개념만 참고할 수 있다.

## 2. 연구별 요약

| 연구 | 작업 | Coarse | Fine | 보고된 효과 (미검증) | 대신고 적용 |
| --- | --- | --- | --- | --- | --- |
| AdaFrame (CVPR 2019) | 영상 분류 | LSTM 정책이 다음에 볼 프레임 선택 | 선택 프레임 CNN 특징 평균 | 25프레임 균등 대비 GFLOPs 약 59–63%↓, 정확도 유지 | 학습 필요. 짧은 차선 변경이 선택에서 빠질 위험 |
| Ada3D | 영상 분류 | 정책 헤드가 프레임 수·3D Conv 층 선택 | 선택된 연산만으로 분류 | GFLOPs 29–39%↓, mAP 약 0.7%p↓ | 학습 필요. 정적 장면 절약 개념만 참고 |
| AdaFocus V2 (CVPR 2022) | 영상 분류 | 가벼운 전역 인코더가 중요 패치 위치 예측 | 패치만 큰 백본으로 분류, V2+는 조기 종료 추가 | V2+가 GFLOPs를 절반 이하로 줄이고 mAP 약 3%p↓ | **crop 아이디어 적용 가능.** 차선·신호등처럼 작은 단서에 유리 |
| FrameExit (CVPR 2021) | 영상 분류 | 프레임마다 게이트가 종료 여부 결정 | 확신 시 결과 출력 | 10프레임 균등 대비 GFLOPs 약 37%↓, mAP 1.2%p↓ | API 호출 단위라 프레임별 게이트 없음. 적용 어려움 |
| ViMo (ACM MM 2023) | 긴 영상 분류 | 로케이터가 의미 단위 위치 탐색 | 단위 임베딩을 LSTM+Transformer로 통합 | 균등 샘플링 대비 GFLOPs 약 1/3.5, mAP 81.1→82.4% | 구간 단위 검토 개념만 참고 |
| Cerberus (arXiv 2025) | 영상 이상 검출 | 모션 마스크로 후보 빠르게 필터 | Gemini VLM이 후보만 심층 검증 | VLM 단일 파이프 대비 151.8× 빠름, 정확도 97.2%, 필터 recall 95% 이상 | **구조가 가장 비슷함.** Coarse를 CV 필터로 바꾸는 방안의 근거 |

## 3. 우리 조건에서 본 적용성

현재 제약: 팀 프록시가 영상을 **재생 1초당 1프레임·low(프레임당 66토큰)**로 다시 샘플링하고,
`fps`·`media_resolution`은 전달되지 않는다
([프록시 샘플링 실험](../experiments/gemini-proxy-video-sampling-2026-09-28.md)).

| 조사 요약의 적용안 | 우리 조건에서 | 관련 실험 |
| --- | --- | --- |
| Coarse 저fps + 후보 구간만 Fine 고fps(15–30fps), 원본 해상도 | 현재 Coarse→Fine 설계와 같다. 프록시 때문에 고fps·원본 해상도를 영상으로 보낼 수 없다. 느린 영상으로 원본 4 fps까지 올렸고 검출은 흔들림 범위 안이다 | [느린 영상](../experiments/gemini-video-slowdown-token-probe-2026-09-29.md) |
| 공간 초점: 전체 저해상도 → 차량·차선 영역 crop 고해상도 | **시험하지 않았다.** 이미지 전송은 해상도와 무관하게 프레임당 1,100토큰으로 고정되므로, crop하면 같은 비용으로 차선에 쓰이는 픽셀이 늘어날 수 있다(가설). 먼 거리 실선(`141927`) 문제와 직접 연결된다 | [이미지 전송](../experiments/gemini-image-frame-probe-2026-09-28.md) |
| 계층적 단위: 5초 단위 대표 프레임 → 필요한 단위만 전체 재평가 | `coarse-diagnostic-v1`의 구간별 검토(`window_reviews`)와 비슷하다. 이 진단 Coarse는 p3보다 후보를 덜 냈다 | [handoff 트레이스](../experiments/gemini-handoff-trace-2026-09-29.md) |
| 가벼운 필터 + VLM 재검증 (Cerberus) | Coarse를 모션·차선 검출 같은 CV로 바꾸는 방안이다. `product-spec.md` §5에서 ADAS/CV Candidate Generator는 보류 상태이고 [challenger 정책](../decisions/challenger-policy.md) 절차를 따라야 한다 | [YOLO 조사](./yolo-assisted-gemini-fine-research-2026-09-16.md) |

**비교 실험 설계에서 가져올 것**

- 지표를 **Coarse 후보 recall**, **Fine 이후 최종 precision**, **입력 토큰**, **지연 시간**으로 나눠
  보는 틀은 #158 논의와 맞는다. `141927`처럼 Coarse가 후보를 못 내면 Fine은 복구할 수 없으므로,
  Coarse recall을 따로 재야 한다.
- 조사 요약은 "균등 샘플링 baseline의 recall을 100%로 본다"고 했지만, 우리 baseline(p3 영상 1x)도
  후보를 놓치므로 이 가정은 쓰지 않는다. recall은 정답 구간 기준으로 잰다.
- 비교할 때 입력 토큰을 맞추는 통제는 유효하다. 이미지와 느린 영상 비교는 프레임 밀도는 같았지만
  토큰은 약 13–15배 달랐다.

## 4. 조사 요약의 확인 필요 사항

요약 안에서 같은 연구의 수치가 서로 다르거나, 출처가 불분명한 부분이다.

- **AdaFrame:** 비교표는 ActivityNet 정확도 "71.5%→71.5%"(동일), 본문은 "71.5→76.1% mAP 동등
  성능"이라고 적었다.
- **AdaFocus V2+:** 핵심 결론은 "84.5%→81.6% mAP, 34.1→12.0 GFLOPs", 비교표·본문은
  "78.9%→76.1%, 34.1→15.3"이다.
- **Ada3D:** FCVID와 ActivityNet의 mAP가 똑같이 "82.6%→81.9%"로 적혀 있다. 비교표는 CVPR 2023,
  참고문헌은 TPAMI'23으로 서지 정보가 다르다.
- **FrameExit:** Kinetics-Sounds 수치(33.8 GFLOPs, 76%↓)가 ViMo의 수치와 같다. 섞였을 수 있다.
- **ViMo:** 기준을 "균등 25FPS"로 적었는데, 비교 기준이 25fps인지 25프레임인지 확인이 필요하다.
- **Cerberus:** 처리 속도가 "≈0.017s/frame"과 "약 1.2ms/frame" 두 가지로 적혀 있다.
- **비용 추정:** "Gemini-1.0 기준 1k토큰당 $0.03"은 가정이며 출처가 없다. 비용은 우리 프록시
  실측 토큰으로 계산한다.

## 5. 참고문헌 (조사 요약 기재 그대로, 원문 확인 전)

- Z. Wu et al., "AdaFrame: Adaptive Frame Selection for Fast Video Recognition," CVPR 2019.
- J. Kim et al., "Ada3D: Instance-adaptive 3D CNNs for Efficient Video Recognition," TPAMI 2023.
- Y. Wang et al., "AdaFocus V2: End-to-End Training of Spatial Dynamic Networks for Video Recognition," CVPR 2022.
- A. Ghodrati et al., "FrameExit: Conditional Early Exiting for Efficient Video Recognition," CVPR 2021.
- Y. Tian et al., "View while Moving: Efficient Video Recognition in Long-untrimmed Videos," ACM MM 2023.
- Y. Zheng et al., "Cerberus: Real-Time Video Anomaly Detection via Cascaded Vision-Language Models," arXiv 2025.
