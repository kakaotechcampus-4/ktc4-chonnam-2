# YOLO 추적 근거를 Gemini Fine에 전달하는 방식 조사

작성일: 2026-09-16

상태: **Research / Spike 제안 — 구현·채택 결정 아님**

대상: `search` 모듈의 Fine visual verification과 선택적 ADAS/CV challenger

> 이 문서는 YOLO 계열 모델로 후보 영상의 객체를 검출·추적하고, 그 결과를 원본 영상과 함께
> Gemini Fine에 전달하는 방식을 조사한다. `product/product-spec.md` §5에서
> `ADAS/CV Candidate Generator`는 보류 상태이고,
> `modules/search/decisions/challenger-policy.md`의 개방 절차도 아직 충족됐다고 가정하지 않는다.
> 따라서 이 문서는 기본 파이프라인 변경, 특정 모델 채택, 의존성 추가를 승인하지 않는다.

---

## 1. 한눈에 보는 결론

기술적으로 가능하며, 대신고에서는 다음 역할 분리가 가장 적합하다.

```text
YOLO 계열 detector/tracker
  = 객체 위치·종류·track ID·대표 프레임 후보 생성

Gemini Fine
  = 원본 픽셀에서 대상·시각 primitive·시간 순서 검증

Application gate
  = 필수 근거 완전성·UNKNOWN/UNCERTAIN 차단·정책 적용

사용자
  = 사건과 최종 신고자료 확인
```

Gemini에는 **YOLO 오버레이 영상만** 보내지 않는다. 권장 입력 bundle은 다음과 같다.

1. 오버레이가 없는 원본 후보 클립
2. 대상 track을 표시한 주석 key frame 3~7장
3. timestamp·정규화 bbox·track ID·confidence·가림 경고를 담은 구조화 metadata

전체 오버레이 영상은 개발자 디버깅 또는 사용자 근거 화면용 파생 자산으로는 유용하지만,
Gemini 입력으로는 원본 영상과 key frame 조합을 우선 비교한다.

---

## 2. 조사 대상과 출처 성격

### 2.1 Ultralytics 교통 관리 글

2024-11-29 게시된 [「Ultralytics YOLO11을 통한 교통 관리 최적화」](https://www.ultralytics.com/ko/blog/optimizingtraffic-management-with-ultralytics-yolo11)는
차량 검출·추적, 속도 추정, 주차, 번호판 인식 등 활용 사례를 설명하는 제품 기술 블로그다.

이 글은 다음을 제공하지 않는다.

- 교통위반 데이터셋 구성과 정답지
- 학습·검증·테스트 분리
- 교통위반 유형별 precision/recall
- 추적 ID switch와 대상 association 정확도
- 속도 추정 오차와 카메라 보정 절차
- 신호·차선·차량 사이의 관계 추론 성능

따라서 이 글은 제품 성능 근거가 아니라 **구현 가능한 CV primitive와 도구 후보를 찾는 자료**로
사용한다.

### 2.2 확인한 공식 기능

- [YOLO11 공식 문서](https://docs.ultralytics.com/models/yolo11/): detect, segment,
  classify, pose, OBB 작업과 모델별 COCO benchmark를 제공한다. COCO 수치는 대신고 4종 사건
  성능이 아니다.
- [Ultralytics tracking 문서](https://docs.ultralytics.com/modes/track/): 프레임 사이에 객체
  ID를 유지하는 tracker와 이동 카메라용 camera-motion compensation 선택지를 설명한다.
- [Ultralytics object counting 문서](https://docs.ultralytics.com/guides/object-counting/):
  추적 객체가 선 또는 영역을 통과할 때 IN/OUT을 집계한다.
- [Ultralytics speed estimation 문서](https://docs.ultralytics.com/guides/speed-estimation/):
  FPS와 `meter_per_pixel`을 사용하며 결과는 카메라 조건에 의존하는 추정치라고 명시한다.
- [Gemini video understanding 문서](https://ai.google.dev/gemini-api/docs/video-understanding):
  한 요청에서 여러 영상과 텍스트를 조합할 수 있고 static 처리의 FPS를 지정할 수 있다.
  기본 static 처리는 1 FPS이므로 빠른 사건은 별도 key frame 또는 높은 FPS가 필요하다.
- [Ultralytics 라이선스 안내](https://www.ultralytics.com/ko/license): 전체 프로젝트의
  AGPL-3.0 준수 또는 Enterprise license가 필요한 사용 조건을 안내한다. 현재 저장소는 MIT이므로
  실제 의존성·가중치 도입 전 별도 라이선스 검토가 필요하다.

공식 문서는 현재 YOLO11 이후 모델도 함께 안내한다. 따라서 Spike가 열리더라도 제품 계약과
문서 이름에 `YOLO11`을 고정하지 않고 `implementation.model_ref`로 실제 모델·가중치 버전을
기록한다.

---

## 3. 풀려는 문제

현재 Gemini Fine은 짧은 후보 구간을 보고 사건 primitive와 시간 관계를 구조화한다. 다음 실패가
반복되면 detector/tracker 근거가 도움이 될 수 있다.

- 여러 차량 중 사용자 기억 단서와 일치하는 대상을 잘못 연결함 (`TARGET_ASSOCIATION`)
- 가림 전후의 동일 차량을 다른 차량으로 해석함
- 번호판 OCR에 다른 차량의 crop을 전달함
- 이륜차와 탑승자 또는 탑승자와 머리 영역을 연결하지 못함
- 빠른 선 통과 순간을 Gemini 영상 sampling 사이에서 놓침
- 작은 객체가 포함된 중요한 프레임을 선택하지 못함

YOLO 출력은 위 실패를 줄일 수 있는 **attention hint**이지 사건의 정답이나 법적 판정이 아니다.

---

## 4. 제안 파이프라인

```text
Recording Timeline의 후보 span
        ↓
앞뒤 padding을 포함한 원본 후보 클립
        ↓
┌────────────────────────────────────┐
│ 선택적 CV perception              │
│ - vehicle/motorcycle/person detect │
│ - multi-object tracking            │
│ - target 후보 ranking              │
│ - key frame selection              │
└────────────────────────────────────┘
        ↓
Fine input bundle
  ├─ original candidate clip
  ├─ annotated key frames
  └─ track metadata JSON
        ↓
Gemini Fine visual verification
        ↓
VisualEvidence
  - target.track_ref
  - primitives
  - temporal_facts
  - uncertainties
```

### 4.1 적용 위치

첫 Spike에서는 YOLO를 장시간 영상의 필수 Coarse 앞단으로 두지 않는다.

YOLO가 놓친 객체나 사건은 downstream에서 복구할 수 없기 때문이다. 기존 Coarse recall을 유지하기
위해 **Coarse가 만든 짧은 후보에만 실행하는 Fine 보조 경로**를 우선 비교한다.

장시간 영상 Candidate Generator로의 확장은 다음 조건에서만 별도 검토한다.

- `SEARCH_FAILURE` 또는 비용 문제에 대해 동일 정답지 실험에서 개선 근거가 있음
- 사건 유형별 recall 감소가 허용 범위 안임
- Product Spec과 challenger 개방 절차를 통과함

### 4.2 권장 Fine input bundle

#### A. 원본 후보 클립

오버레이가 없는 원본 또는 원본에서 무손실 의미를 유지한 파생 clip이다. Gemini는 이 입력에서
신호색, 차선 종류, 번호판, 안전모, 차량과 선의 접촉 관계를 직접 확인한다.

#### B. 주석 key frame 3~7장

사건 전후의 다음 시점을 우선한다.

- 사건 전 안정 상태
- primitive가 처음 보이는 시점
- 접촉·통과 직전
- critical timestamp
- 통과 직후 또는 다른 차로에서 안정화된 시점

박스는 대상 객체의 픽셀을 최소한으로 가리도록 얇게 그리고, 라벨은 객체 밖에 배치한다.

#### C. 구조화 track metadata

```json
{
  "schema_version": "cv-track-hints/v0",
  "clip_ref": "derived_clip_001",
  "time_basis": "CLIP_RELATIVE_MS",
  "target_track": "yolo:T17",
  "tracks": [
    {
      "track_ref": "yolo:T17",
      "class_label": "car",
      "first_seen_ms": 1200,
      "last_seen_ms": 6800,
      "best_frame_ref": "fr_4300",
      "observations": [
        {
          "at_ms": 3200,
          "bbox_norm_xyxy": [0.42, 0.51, 0.58, 0.78],
          "confidence": 0.93,
          "frame_ref": "fr_3200"
        },
        {
          "at_ms": 4300,
          "bbox_norm_xyxy": [0.39, 0.49, 0.57, 0.76],
          "confidence": 0.91,
          "frame_ref": "fr_4300"
        }
      ],
      "warnings": ["PARTIAL_OCCLUSION"]
    }
  ]
}
```

이 JSON은 Spike용 내부 형식 예시이며 Final Data Contract가 아니다. 계약으로 승격하려면
`architecture/contracts/` 절차를 따른다.

---

## 5. Gemini 지시 원칙

YOLO의 annotation error가 Gemini 판단을 고정시키는 automation bias를 막아야 한다.

프롬프트에는 다음 의미를 명시한다.

```text
The boxes and track IDs are machine-generated attention hints,
not verified facts.

Verify them against the original video. If an annotation conflicts
with the original pixels, the original video is authoritative.

Do not infer a traffic violation solely from a bounding box,
class label, tracking ID, or detector confidence.
```

추가 규칙은 다음과 같다.

1. `confidence`를 사건 판정 threshold로 사용하지 않는다.
2. track이 가림 뒤 같은 객체인지 불명확하면 `target.association_status=AMBIGUOUS` 또는
   `UNCERTAIN` 근거를 남긴다.
3. 원본에서 확인되지 않는 annotation은 근거로 채택하지 않는다.
4. YOLO label은 `car`, `motorcycle`, `person` 같은 중립적 관찰어만 사용한다.
5. `violator`, `illegal`, `red-light offender`처럼 결론을 선행하는 label을 만들지 않는다.

---

## 6. 오버레이 렌더링 규칙

### 6.1 원본 보존

- Source video를 덮어쓰지 않는다.
- overlay는 별도 derived asset이다.
- 원본 FPS·프레임 순서·timeline mapping을 보존한다.
- clip-relative `t=4.300s`와 canonical Timeline 위치를 혼동하지 않는다.
- 원래 블랙박스 timestamp/metadata overlay를 가리지 않는다.

### 6.2 시각 표현

- 신호 상태와 혼동될 수 있으므로 대상 bbox에 빨강·초록을 사용하지 않는다.
- 대상 track은 청록, 비교 track은 자홍 등 신호색과 무관한 색을 쓴다.
- `T17 car`처럼 짧은 ID만 표시한다.
- confidence와 긴 설명은 영상 위에 겹치지 않고 JSON으로 전달한다.
- 번호판·신호등·차선·운전자 머리 영역을 라벨 배경으로 가리지 않는다.
- 추정 궤적은 실제 관찰점과 보간 구간을 시각적으로 구분한다.

### 6.3 identity

동일한 ID가 세 입력에서 일치해야 한다.

```text
overlay label                T17
internal track metadata      yolo:T17
VisualEvidence.track_ref     yolo:T17
```

`yolo:`는 예시 namespace다. 특정 모델명보다 해당 run에서의 identity임을 나타내도록 실제 naming
규칙은 구현 Spike에서 결정한다.

---

## 7. 사건 유형별 적용성

| 사건 | detector/tracker가 제공할 수 있는 것 | 별도로 필요한 것 | 초기 우선순위 |
| --- | --- | --- | --- |
| `SIGNAL` | 대상 차량 track, 신호등 후보, key frame | 적용 신호 association, 신호 상태, 정지선, crossing 순서 | 중간 |
| `CENTER_LINE_CROSSING` | 대상 차량 궤적과 footprint 후보 | 중앙선 identity·geometry, ego-motion 보정, crossing extent | 낮음/조건부 |
| `SOLID_LINE_LANE_CHANGE` | 차량의 횡방향 이동과 track | origin/target lane, 실선·점선 분류, 실제 crossing zone | 중간/조건부 |
| `MOTORCYCLE_HELMET_NON_USE` | 이륜차·사람 후보와 track | rider association, head crop, helmet 전용 분류, 가림 처리 | 높음 |

### 7.1 신호 사건

필요한 관계는 다음과 같다.

```text
subject track
  → travel direction
  → applicable signal
  → signal state
  → stop line/intersection boundary
  → crossing timestamp
```

일반 객체 검출만으로 `applicable signal`과 `stop line`은 확정되지 않는다. YOLO bbox는 대상 차량
association과 key frame 선택에만 먼저 사용한다.

### 7.2 중앙선·실선 사건

차량 bbox 중심점만으로 선 통과를 판정하지 않는다. 이동 블랙박스에서는 camera motion과 원근이
크므로 차량 footprint, local road geometry, 연속 프레임의 선 연결이 필요하다. 별도 lane/marking
segmentation은 `PRIMITIVE_FAILURE`가 실측된 뒤 연다.

### 7.3 안전모 사건

첫 Spike에서 가장 적합한 유형이다.

```text
motorcycle detect
  → person/rider association
  → head-region crop
  → helmet attribute verification
  → multi-frame agreement
```

한 프레임에서 머리가 작거나 가려졌으면 `NOT_OBSERVED`가 아니라 `UNCERTAIN`으로 처리한다.

### 7.4 번호판 best frame 보조

번호판 OCR 확정은 `readout` 경계다. Search/CV는 다음 hint까지만 제공할 수 있다.

- 대상 차량 track
- 프레임별 차량 bbox
- 크기·선명도·정면성·가림 정도에 따른 best-frame 후보
- 대상 association 불확실성

최종 crop identity와 OCR은 기존 `readout` 계약을 따른다.

---

## 8. 이동 블랙박스에서의 특별한 위험

Ultralytics 교통 예시는 대부분 고정 카메라 사용을 전제로 한다. 대신고 영상은 camera ego-motion이
있어 다음 위험이 추가된다.

- 배경·차선·신호등도 매 프레임 이동함
- 상대속도와 실제 차량 속도가 다름
- 진동·급회전·rolling shutter로 bbox와 궤적이 흔들림
- 가림 뒤 ID switch가 발생함
- 유사한 차량 사이에서 ReID가 잘못 연결될 수 있음
- 영상 파일 경계에서 tracker state가 끊김

Spike에서는 단순하고 빠른 tracker와 camera-motion compensation을 제공하는 tracker를 같은
영상으로 비교한다. 특정 tracker를 이 문서에서 기본값으로 확정하지 않는다.

속도 추정은 초기 범위에서 제외한다. 이동 카메라에서는 카메라 보정, ego-motion 제거, 도로 평면,
실거리 기준이 추가로 필요하고 초기 4종 사건의 필수 Evidence도 아니다.

---

## 9. 기존 계약과의 연결

현재 `src/daesingo/search/visual.py`의 공개 구조로 다음 값을 표현할 수 있다.

| CV 결과 | 기존 공개 구조 |
| --- | --- |
| 대상 track identity | `Target.track_ref` |
| association 성공/애매함/실패 | `Target.association_status` |
| 대표·근거 프레임 | `Target.evidence_refs`, 각 primitive의 `evidence_refs` |
| 차량·이륜차·사람 등 관찰 | `Primitive` |
| 가림·ID switch·작은 객체 | `Uncertainty` |
| 중요한 상태 변화 시각 | `TemporalFact.at_offset_ms` |

따라서 최초 Spike는 공개 `VisualEvidence` 계약을 변경하지 않고 search 내부 adapter로 수행할 수
있다. 다만 CV metadata 전체를 장기 저장하거나 다른 모듈이 직접 소비해야 한다면 별도 계약 검토가
필요하다.

`AnalysisRun.implementation`에는 최소한 다음을 기록한다.

- model/weight reference
- detector config version
- tracker 종류와 config version
- inference image size와 sampling FPS
- overlay/key-frame renderer version
- target selection strategy version

---

## 10. Gemini 영상 sampling과 key frame

Gemini 공식 문서상 기본 static video processing은 1 FPS다. 빠른 신호 전환이나 선 통과는 sampling
사이에서 사라질 수 있다. YOLO가 원본 프레임 속도로 추적했어도 Gemini가 같은 프레임을 보지
않는다면 시간 근거가 전달되지 않는다.

Fine 비교안은 다음을 포함한다.

1. 원본 후보 클립을 현재 Fine 설정으로 처리
2. critical timestamp 전후의 주석 key frame을 별도 이미지로 전달
3. 필요 시 Fine video FPS를 올리되 비용·지연을 함께 기록

Gemini에 전체 원본 clip과 전체 overlay clip을 동시에 넣는 방식은 입력량이 커지므로 독립 variant로
측정하고 기본안으로 가정하지 않는다.

---

## 11. 실험 설계

### 11.1 개방 전제

아래 실험은 다음 절차를 통과한 뒤 수행한다.

1. `eval`이 동일 정답지로 baseline failure를 집계한다.
2. `PRIMITIVE_FAILURE` 또는 `TARGET_ASSOCIATION`이 CV challenger 필요성을 지목한다.
3. Search Owner가 근거·예상 비용과 함께 주간 회의 안건으로 올린다.
4. PM 승인 뒤 Spike 실행과 결과를 `experiments/`에 기록한다.

### 11.2 비교 variant

| Variant | Gemini Fine 입력 | 목적 |
| --- | --- | --- |
| A | 원본 후보 클립 | 현재 baseline |
| B | YOLO overlay 후보 클립만 | annotation-only 위험 측정 |
| C | 원본 후보 클립 + annotated key frame + track JSON | 권장 hybrid 가설 |
| D | 원본 후보 클립 + 전체 overlay clip + track JSON | 비용 대비 추가 효과 측정 |

동일 candidate와 동일 Fine prompt/schema를 사용하고 입력 bundle만 변경한다. 모델·prompt·FPS·tracker를
한 번에 바꾸지 않는다.

### 11.3 정답 주석

최소한 다음 ground truth가 필요하다.

- 대상 차량 identity와 등장 구간
- 가림 전후 동일 객체 여부
- critical timestamp
- 번호판 best-frame 사용 가능 여부
- 사건 유형별 필수 primitive visibility
- YOLO annotation이 잘못된 hard-negative 사례

### 11.4 지표

#### CV/association

- target association accuracy
- ID switch count / track
- track fragmentation rate
- target not-found/ambiguous rate
- best-frame usable rate

#### Fine/E2E

- 유형별 precision, recall, F1
- Final Top-3 recall
- crossing/critical timestamp MAE
- `UNCERTAIN` rate
- Unsupported Evidence Rate
- 잘못된 YOLO annotation을 Gemini가 그대로 수용한 비율

#### 운영

- 영상 1분당 CPU/GPU 처리시간
- p50/p95 latency
- peak memory/VRAM
- derived asset 크기
- Gemini input/output/thought token과 총 비용

### 11.5 채택 게이트 제안

최종 게이트는 실험 전에 `eval`과 합의해야 한다. 시작점으로 기존 Fine 비교 계획을 따른다.

- E2E recall 저하 3 percentage points 이내
- precision 5pp 이상 증가 또는 false positive 25% 이상 감소
- target association accuracy의 의미 있는 개선
- Unsupported Evidence Rate 악화 없음
- 비용·지연 예산 준수

YOLO 자체의 COCO mAP 개선은 채택 근거가 아니다.

---

## 12. 구현 시 예상 구조 — 미승인 제안

챌린저가 개방될 경우 다음과 같이 search 내부 선택 경로로 격리하는 안을 검토한다.

```text
src/daesingo/search/
  perception/
    detector.py          # local model adapter
    tracker.py           # track identity와 camera motion 설정
    target_selection.py  # 사용자 hint/후보와 track association
    keyframes.py         # critical/best-frame 선택
    overlay.py           # derived annotation asset 생성
    models.py            # 내부 CV hint models
```

이 경로는 공개 entrypoint를 추가하자는 확정안이 아니다. `search_candidates()`와
`verify_visual()`의 공개 시그니처를 유지하고, 선택된 implementation 내부에서만 호출하는 것을
우선한다.

현재 `pyproject.toml`에는 CV runtime이 없다. 실제 Spike에서는 core install에 바로 넣지 말고
별도 optional dependency 또는 격리된 worker/runtime을 검토한다.

---

## 13. 개인정보·파생 자산·라이선스

### 13.1 개인정보와 보존

- 가능하면 detector/tracker는 로컬 또는 관리되는 worker에서 실행해 원본 외부 전송을 늘리지 않는다.
- overlay와 key frame도 차량번호·얼굴을 포함할 수 있는 개인정보 자산으로 취급한다.
- 원본, Fine clip, overlay, key frame의 lineage와 삭제 정책을 유지한다.
- Gemini에 보내지 않아도 되는 주변 차량 crop은 최소화한다.

### 13.2 라이선스

저장소는 MIT지만 Ultralytics 공식 안내는 AGPL-3.0 공개 의무 또는 Enterprise license 조건을
제시한다. 다음을 확인하기 전에는 `ultralytics` package나 해당 가중치를 제품 dependency로
추가하지 않는다.

- 프로젝트 전체 공개·배포 방식
- SaaS/비공개 서비스 여부
- 학습 코드와 커스텀 weight의 취급
- 모델 서버를 분리했을 때의 의무
- Enterprise license 필요 여부와 비용

이는 법률 자문을 대신하지 않는다. 채택 전 프로젝트 책임자의 라이선스 검토가 필요하다.

---

## 14. 하지 않는 것

- YOLO confidence만으로 교통위반을 확정하지 않는다.
- 오버레이 영상만을 canonical evidence로 사용하지 않는다.
- Source video를 annotation 영상으로 덮어쓰지 않는다.
- `violator` 같은 법적·규범적 label을 detector 출력에 넣지 않는다.
- 고정 카메라용 `meter_per_pixel` 속도 계산을 이동 블랙박스에 그대로 적용하지 않는다.
- baseline failure와 승인 없이 ADAS/CV Candidate Generator를 기본 경로로 승격하지 않는다.
- 번호판 OCR 확정을 search가 가져오지 않는다.

---

## 15. 미결 질문

1. 실제 baseline에서 `TARGET_ASSOCIATION`과 `PRIMITIVE_FAILURE`는 얼마나 발생하는가?
2. 원본 clip + key frame 조합이 전체 overlay clip보다 품질/비용 면에서 우월한가?
3. 이동 블랙박스에서 ID switch를 감당할 수 있는 tracker와 설정은 무엇인가?
4. target track 선택에 사용자 차량 hint를 어느 정도 사용할 것인가?
5. 4종 중 안전모와 번호판 best-frame만 먼저 여는 것이 타당한가?
6. CV hint JSON을 실행 중 임시 데이터로 둘 것인가, 재현을 위해 저장할 것인가?
7. MIT 저장소와 향후 배포 계획에서 사용 가능한 detector/runtime의 라이선스 선택은 무엇인가?
8. 파생 overlay/key-frame 자산의 보존 기간과 삭제 책임은 어느 모듈이 소유하는가?

이 질문은 이 문서에서 임의로 종결하지 않는다. 실험 결과와 기존 승인 절차에 따라 결정 문서로
승격한다.
