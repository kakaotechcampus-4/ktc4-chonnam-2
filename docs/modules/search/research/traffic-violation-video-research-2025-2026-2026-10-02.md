# 교통위반·긴 영상 탐색 최신 연구 조사 (2025–2026)

작성일: 2026-10-02

상태: **Research — 결정 아님. 수치는 외부 조사 보고서에서 옮긴 것이며 원문 대조 전**

대상: `search` 모듈 Coarse→Fine 구조, Fine 검증 입력, 다음 실험 후보

> 2025–2026 공개 연구를 세 갈래로 나눠 정리한다. **A** 교통위반 직접 판정, **B** 교통안전 VLM·VideoQA,
> **C** 긴 영상 검색·시간 구간 grounding. "미확인"은 조사 범위 안에서 원문 값을 확정하지 못했다는 뜻이다.
> 현재 구조는 [최종 구조 제안](../decisions/search-final-structure-2026-10-01.md), CV 적용 순서는
> [CV 적용 방향](./cv-application-strategy-research-2026-10-01.md)을 따른다. 이 문서는 둘 중 어느 것도 바꾸지 않는다.

---

## 1. 한눈에 보는 결론

1. **실제 위반 판정 연구의 주류는 여전히 검출 → 추적 → 기하/규칙이다.** VLM은 저수준 측정을 대체하기보다 검색·설명·검증 쪽에 붙는다.
2. **범용 VLM은 장면 인식은 잘하지만 위반·사고 판단은 약하다** (RoadSafe365: 위반/사고 항목 다수 모델 50% 미만, 교통 데이터 튜닝 후 38→67%).
3. **긴 영상에서 실패의 대부분은 "엉뚱한 구간을 고른 것"이다** (ExtremeWhenBench: 실패의 85%가 search failure). 싼 검색 → 좁은 창에서 VLM 검증이 단일 Video-LLM보다 낫다.
4. **차선·중앙선·신호 위반은 한 장면이 아니라 상태 변화(전 → 경계 → 후)가 증거다.** 헬멧은 몇 프레임 인식 문제에 가깝다.

우리 구조(Coarse 후보 → Fine 검증)는 3번이 독립적으로 지지하는 형태다. 새로 가져올 것은 구조가 아니라 **Fine에 넣는 근거의 종류**(참고 사례, 측정값)다.

## 2. 연구 목록

### A. 교통위반 직접 판정

| 연도 | 연구 | 대상 | 카메라 | 방법 | 시간 처리 | 데이터·성능 | 코드 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026 | TrafficRAG (WACV 2026 WS) | 위반 시간 구간 grounding | 미확인 | 검증된 위반 사례 검색 → frozen Video-LLM | 시간 구간이 출력 | Direct Inference 대비 F1 개선(수치 미확인) | 미확인 |
| 2025 | DashCop (WACV 2025) | 헬멧 미착용·삼인승·번호판 | 블랙박스 1080p 25fps | YOLOv8 → 탑승자-이륜차 연결 → 추적 → 분류 → track 단위 집계 → ANPR | 같은 track 여러 프레임 투표 | RideSafe-400(400영상, 약 60만 프레임). 자동 F1 72.18, 사람 개입 F1 82.05 | 공개 |
| 2025 | UAV 교통 감시 (arXiv) | 위험 차로변경·이중주차·횡단보도 점유 | 드론 4K 수직 | 검출 → Kalman/Hungarian 추적 → homography → geofence·궤적 규칙 | 궤적 | 검출·추적 F1 90.5, MOTA 92.1 (위반 판정 F1 아님) | 미확인 |
| 2025 | Red-Light Violation Detection (ISCTIS) | 신호위반 | 교차로 고정 | 모듈형 CV | 세부 미확인 | 미확인 | 미확인 |
| 2026 | Dashcam Illegal Parking (IEEE Access) | 불법 주정차 | 블랙박스 | 2단계 pseudo-label → end-to-end | 미확인 | 미확인 | 미확인 |
| 2025/26 | Lane-Change Violations via YOLOv8 (IIH-MSP) | 차로변경 위반 | 미확인 | YOLOv8 | 미확인 | 미확인 | 미확인 |
| 2025 | Helmet violation, TAO + YOLOv8 (Frontiers AI) | 헬멧·번호판 | 도시 감시 | 탑승자 위치 → 헬멧/번호판 → OCR | 프레임 단위 | 헬멧 98.56%, 번호판 97.6% (자체 데이터) | 미확인 |
| 2025 | Triple-riding detection (Discover AI) | 삼인승 | 감시 | DetectNet_v2 + YOLOv8 → 탑승자 수 | 객체 관계 | 91.42% | 미확인 |
| 2025 | ITVDES (ICDISS) | 헬멧·차선·신호 | 감시 | CV + OCR + LLM 설명 | CV 결과 기반 | 미확인 | 미확인 |

### B. 교통안전 VLM·VideoQA

| 연도 | 연구 | 핵심 | 데이터 | 우리에게 의미 |
| --- | --- | --- | --- | --- |
| 2026 | RoadSafe365 (arXiv) | 블랙박스·감시 영상 VQA. 클립당 key frame 8장 | 36,196 클립 | 인식 항목 70–95%, 위반/사고는 다수 모델 50% 미만. Gemini 2.5 Flash 전체 74.68%. Qwen2.5-VL-7B 튜닝 후 위반/사고 38.04→67.29% |
| 2025 | InterAct-Video (arXiv) | 교차로 10초 클립 시공간 QA | 8시간, QA 2.5만+ | 10초 창 검증 = 우리 Fine 창과 비슷한 크기. 후보 찾기는 다루지 않음 |
| 2025 | MLLM 사고 분석 (Zhang et al.) | 가변 길이 영상 사고 분류·grounding, 구조화 프롬프트 | Toyota Woven | 사고·끼어들기 확장 시 참고. 수치 미확인 |

### C. 긴 영상 검색·시간 구간 grounding

| 연도 | 연구 | 핵심 | 결과 |
| --- | --- | --- | --- |
| 2025 | SALOVA (CVPR 2025) | 구간 단위 표현 → 질의 관련 구간만 Video-LMM으로 | 구간 routing으로 계산량 절감 |
| 2025 | TimeExpert (ICCV 2025) | Video-LLM + temporal expert로 시작·끝 시점 정밀화 | 수치 미확인 |
| 2026 | ExtremeWhenBench (Seo & Kim, arXiv) | 평균 75.7분·최대 9시간, 정답 구간 중앙값 9초 | 실패 85% search / 11% localization. 1fps CLIP 검색 mIoU 0.269 > 최고 open Video-LLM 0.110. 검색 → Video-LLM 하이브리드 0.354. top-K는 3 부근이 최적, 10이면 다시 하락 |

## 3. 연구에서 반복되는 위반별 증거 구조

연구들이 공통으로 하는 일은 "법규 이름을 바로 맞히기 전에 관측 가능한 요소와 시간 관계로 쪼개는 것"이다. 우리 4종에 대응하면:

| 위반 | 반드시 보여야 할 것 | 시간 증거 | 연구 근거 |
| --- | --- | --- | --- |
| 진로변경(백색 실선) | 경계선 위치, 실선/점선, 대상 차량 위치 | 같은 차량이 A쪽 → 선 위 → B쪽 | UAV 궤적·geofence |
| 중앙선 침범 | 중앙선 위치, 대상 차량 위치, 반대 차로 | 횡단 + 반대편 일정 시간 점유 + 진행 방향 | UAV 궤적 (중앙선 전용 최신 연구는 드묾) |
| 신호위반 | 해당 진행 방향 신호등 상태, 정지선, 대상 차량 | 적색 구간 안에서 정지선 통과 | ISCTIS (구현 세부 미확인) |
| 이륜차 안전모 | 이륜차-탑승자 연결, 머리 가시성, 헬멧 유무 | 여러 프레임에서 지속적인 미착용 | DashCop track 투표 |

블랙박스는 촬영 차량도 움직여서 고정 카메라 연구의 homography·정지선 좌표를 그대로 쓸 수 없다(조사자 해석). 이는 [CV 적용 방향](./cv-application-strategy-research-2026-10-01.md) §2의 "화면 대비 위치로 판단한다" 가설과 같은 문제다.

## 4. 우리 프로젝트에 쓸 수 있는 지점

### 4.1 바로 근거로 쓸 수 있는 것

| 지점 | 연구 | 현재 상태와의 관계 |
| --- | --- | --- |
| Coarse→Fine 분리 자체 | ExtremeWhenBench, SALOVA | 구조 선택의 외부 근거. 설계 설명·발표 자료에 인용 가능 |
| Coarse recall을 Fine 정확도와 따로 잰다 | ExtremeWhenBench (search/localization 실패 분리) | 이미 [Coarse recall](../experiments/gemini-coarse-recall-prompt-2026-10-01.md)·[Fine 고정 구간](../experiments/gemini-fine-window-uncertain-2026-10-01.md)으로 분리해 측정 중. 방향이 맞다는 근거 |
| 범용 VLM의 위반 판단 약점 | RoadSafe365 | `141927`·`YT_0003`의 `PRIMITIVE_FAILURE` 가설과 일치. Gemini 2.5 Flash도 같은 경향(3.8 Flash 수치는 없음) |
| 차선 대비 위치를 CV로 재는 방향 | UAV 연구, DashCop | [CV 적용 방향](./cv-application-strategy-research-2026-10-01.md) 1단계(차선 위치 + 차량 추적 오프라인 측정)의 선행 사례 |
| 위반별 증거 체크리스트 | 연구 전반 | `fine-p3-*` 사건별 지시가 이미 같은 형태(횡이동·선 종류 분리, 신호 순서·정지선, 탑승자 연결·머리 가시성). 새로 할 일 없음 |

### 4.2 다음 실험 후보 (근거 있음, 측정 전)

1. **고정 참고 사례를 Fine에 넣는 A/B** — TrafficRAG.
   - `product-spec.md` §5가 TrafficRAG를 "먼저 고정 참고 사례 A/B 후 효과 확인 시 확장"으로 이미 보류 조건을 적어 두었다. 이 조사는 그 A/B를 시도할 외부 근거다.
   - 지금까지 시험한 프롬프트 변형(diagnostic·subject·multi·handoff·uncertain·crop)에는 **예시 영상/프레임을 넣은 변형이 없다.**
   - 형태 예: 실선 변경 양성 1개 + hard negative(점선 정상 변경 `141956`류, 선에 붙었다 돌아온 경우) 1–2개를 Fine 요청에 함께 보낸다. 평가 클립과 같은 영상을 참고 사례로 쓰지 않는다.
   - 비용: 참고 영상 재생 초 × 66토큰이 매 Fine 호출에 더해진다. 단, 사례가 반복 Fine에서 같으면 캐시 가능 여부를 먼저 본다.
2. **CV 측정값을 텍스트 요약으로 Fine에 전달** — UAV·DashCop·ITVDES 공통 패턴.
   - 예: `대상 차량 횡위치: 왼쪽 차로 → 4.2s 선 위 → 오른쪽 차로`. [CV 적용 방향](./cv-application-strategy-research-2026-10-01.md) 2단계와 같다. 1단계가 성공한 뒤에만 의미 있다.
3. **헬멧은 여러 프레임 집계** — DashCop.
   - 한 프레임의 "헬멧 없음"보다 같은 탑승자에서 지속적으로 안 보이는 것이 강한 증거다. 현재 프롬프트는 "머리가 가려졌다면 UNCERTAIN"까지만 있다. 헬멧 클립이 라벨 세트에 들어온 뒤 판단한다.

### 4.3 지금은 쓰지 않는 것

| 아이디어 | 이유 |
| --- | --- |
| VLM fine-tuning (RoadSafe365의 +29%p) | `product-spec.md` §5 보류. 프록시 경유 Gemini라 튜닝 경로 없음 |
| CLIP 등 임베딩 인덱스 검색 | 연구는 시간 단위 영상. 우리 입력은 최대 약 5분 클립이고 Coarse가 이미 클립 전체를 본다. 클립이 길어질 때 재검토 |
| top-K 최적값(K≈3) 그대로 적용 | 시간 단위 영상 기준 값. 5분 클립의 후보 수 기준으로 옮길 근거 없음 |
| key frame 8장 방식 | 수백 ms 경계 통과를 놓칠 수 있다. 우리는 이미 느린 영상으로 프레임 밀도를 올리는 쪽을 택함 |
| Anomaly detection으로 후보 생성 | "통계적으로 이상함" ≠ "법규 위반". 4종 고정 범위에서는 필요 없음 |
| CV 후보 생성기(Coarse 대체·합집합) | `product-spec.md` §5 보류, [challenger 정책](../decisions/challenger-policy.md) 절차 필요 |

## 5. 원문 확인이 필요한 항목

- TrafficRAG의 데이터 규모·F1 수치·코드 공개 여부. 참고 사례 A/B를 설계할 때 가장 먼저 읽을 원문이다.
- ExtremeWhenBench 수치(mIoU, 85%, 6.7배)와 top-K 실험 조건.
- RoadSafe365의 Gemini 2.5 Flash 위반/사고 항목 개별 점수(전체 74.68%만 옮김).
- Lane-Change YOLOv8·ISCTIS 신호위반 논문의 실선 구분·정지선 처리 방식(조사 범위에서 미확인).

## 미결

- 참고 사례 A/B를 할지, 언제 할지: 정하지 않음.
- 참고 사례로 쓸 클립 출처(라벨 7클립과 분리 필요): 미정.
