# CV_LANE_TRACK v1 차량 모델 비교 실행 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 동일 개발 영상에서 차량 detector 7종을 비교하고, 상위 2종을 같은 ByteTrack으로 재검증해 후속 교차 분석에 사용할 detector를 선정한다.

**Architecture:** 기존 AI Hub YOLOv5 adapter와 원본 프레임 캐시를 재사용한다. 새 detector도 같은 원본 좌표 Detection으로 변환하고, 저점수 예측을 저장한 뒤 calibration과 비교 채점을 분리한다. 추론·추적은 차량 정답을 받지 않으며 정답은 평가와 로컬 검수에만 사용한다.

**Tech Stack:** 기존 Python 3.10·PyTorch CUDA 환경, 별도 Python 3.12 이상 `eval-yolo` 환경, Ultralytics 8.4.133, OpenCV, NumPy, Pydantic, pytest.

**Spec:** `docs/modules/search/experiments/cv-lane-track-v1-2026-10-09.md` §2·§3·§7 및 사용자가 첨부한 같은 실험 문서. 범위는 차량 모델 비교 단계에 한정한다.

작성일: 2026-10-09. 현재 상태: **7종 추론·속도 측정 완료 / 차량 GT 미확보로 정확도 비교·선정 대기**. 계획 작성 후 사용자 실행 승인으로 별도 공개 모델 환경과 1,200프레임 패널을 준비하고 25,200행 예측을 생성했다. [실행 결과](../../modules/search/experiments/cv-vehicle-model-comparison-2026-10-09.md)에 실제 완료 범위와 제한을 기록했다.

실행 상태: Task 1은 입력 검증·패널 추출 완료, 차량 GT 작성·검수 대기다. Task 2는 adapter·추론 runner·GT gate·metric 함수와 fixture를 구현했으며 비정방형 bbox 영상 검수와 전체 채점 CLI는 미완료다. Task 3은 GT 미확보로 운영점 채점 대기, Task 4는 추론·속도 측정 완료 후 정확도 채점·상위 2종 선정 대기, Task 5는 상위 2종 미선정으로 미실행이다. Task 6은 중간 결과 문서화 완료, overlay 검수·최종 선정 보고 대기다. 아래 체크리스트는 완료한 세부 항목만 표시한다.

## 범위와 종료점

평가 순서는 **입력/환경 확인 → 차량 GT 고정 → adapter/채점 검증 → 5클립 calibration → set1 10클립 비교 → 상위 2종 ByteTrack 재검증 → 선정 보고**다. 원문 §2의 GT 선행 기준은 모델 결과 열람 전이다. GT를 입력으로 받지 않는 추론과 속도 측정은 먼저 실행할 수 있으며, 예측 bbox/overlay 열람과 채점은 검수한 GT가 고정된 뒤 진행한다.

종료 산출물은 7종 비교표, 사건별 누락표, 동일 tracker 비교표, 선정 detector·confidence와 근거다. ByteTrack은 detector 선정을 위한 공통 조건이다. ByteTrack 대 BoT-SORT 비교, 차선 모델 비교, 선 종류 라벨, 교차 규칙, C0–C5 ablation, 정상 113개 평가, Fine 연결, 제품 도입 판단은 다음 단계다.

## 현재 확인한 준비 상태

| 항목 | 확인 내용 | 실행 시 남은 작업 |
| --- | --- | --- |
| 원본 영상 | `src/daesingo/search/video/`에 15개 파일 존재 | 디코딩·크기·fps·영상 해시 확인 |
| 사건 정답 | 같은 폴더 `정답지.md` 존재 | bbox·동일 객체 ID·가시성 정답 추가 |
| 1fps 캐시 | `.omc/aihub-models/run/frames/`에 JPEG 651장 존재 | manifest 시각, 원본 크기, 프레임 해시 검증 |
| AI Hub 가중치 | Downloads의 AI모델 폴더에 차량 관련 `.pt` 3종 존재 | 로딩·클래스·가중치 해시 확인 |
| 기존 adapter | `scripts/aihub_model_video_adapters.py`의 `Detector.predict`·`Detection` 확인 | 실험용 공통 후처리와 새 모델 adapter 추가 |
| 기존 환경 | `.omc/aihub-models/venv`·YOLOv5 source 폴더 존재 | 실행 시 CUDA·FP32·패키지 버전 확인 |
| 공개 모델 환경 | `pyproject.toml`에 `eval-yolo` extra와 `ultralytics==8.4.133` 선언 | 별도 환경 준비 및 CUDA smoke 실행 |

존재 확인은 파일 내용의 완전성이나 GPU 실행 성공을 뜻하지 않는다. 기존 `bgr64_5fps.npy`는 LRCN용 64px 영상이므로 이번 detector/추적 입력에 쓰지 않는다. 기존 confidence 0.25 예측은 비교 참고자료이며 0.01 예측을 새로 생성해야 한다.

## Global Constraints

- RTX 3060 12GB, batch=1, CUDA FP32, 모델 하나씩 실행.
- 주 입력 640. YOLO는 비율 유지 letterbox, RT-DETR은 공식 640×640 전처리. 실제 tensor shape를 기록한다.
- crop, GT 힌트, 추론 augment, 재학습 금지.
- AP/PR 예측 confidence≥0.01, 최대 300개. NMS 모델 IoU 0.45, NMS-free 모델은 고정 버전 공식 decoder 유지.
- AI Hub car 및 COCO car/bus/truck을 VEHICLE로 합친 뒤 공통 IoU 0.7 NMS 적용.
- 기존 환경과 기존 실험 결과를 덮어쓰지 않는다. Python 3.10 환경에서 Python≥3.12 프로젝트 extra를 설치하지 않는다.
- GT/입력/가중치/source revision/설정 해시를 고정한다. 영상·프레임·가중치는 로컬에 보관한다.
- calibration·set1 모두 이미 본 개발 영상이다. held-out 또는 일반 성능 증명으로 표현하지 않는다.
- OOM·설치·CUDA 실패는 실패 행으로 남긴다. 모델·해상도·정밀도·backend를 자동 교체하지 않는다.

## 후보 모델

| ID | 모델 | 평가 클래스 |
| --- | --- | --- |
| V1 | AI Hub YOLOv5 `model_객체탐지_신호위반.pt` | car |
| V2 | AI Hub YOLOv5 `model_객체탐지_중앙선침범.pt` | car |
| V3 | AI Hub YOLOv5 `model_객체탐지_진로변경.pt` | car |
| V4 | YOLO11n `yolo11n.pt` | car/bus/truck |
| V5 | YOLO11s `yolo11s.pt` | car/bus/truck |
| V6 | YOLO26s `yolo26s.pt` | car/bus/truck |
| V7 | RT-DETR-L `rtdetr-l.pt` | car/bus/truck |

AI Hub 가중치는 기존 YOLOv5 v7.0 loader로 읽는다. 최신 Ultralytics loader로 호환된다고 가정하지 않는다. YOLO26의 decoder/NMS 모드는 최신 문서 설명만으로 결정하지 않고 **실제 고정 패키지·가중치의 end2end 설정**을 확인해 기록한다. 공식 후보 자료: [YOLO11](https://docs.ultralytics.com/models/yolo11/), [YOLO26](https://docs.ultralytics.com/models/yolo26/), [RT-DETR](https://docs.ultralytics.com/models/rtdetr/).

## Review Focus

1. 원본 해상도·가로세로 비율이 달라도 bbox가 원본 좌표로 복원되는지.
2. 중복 검출·ignore 영역이 precision을 부풀리거나 FP를 잘못 지우지 않는지.
3. 사건 차량만 라벨한 5fps 프레임에서 전체 precision을 계산하지 않는지.
4. C05 두 사건, C47 경계 사건, 가림/화면 이탈/대상 미확인을 올바른 분모로 보고하는지.
5. 5fps buffer, 빈 검출 프레임, 패널 사이 시간 공백, 저점수 연결이 ID coverage를 부풀리지 않는지.

## Task 1: 입력·평가 패널·차량 GT 고정

**참조 파일:** `scripts/aihub_model_video_data.py`, `src/daesingo/search/video/정답지.md`.

**계획할 파일:** `scripts/cv_lane_track_vehicle_data.py`, `tests/search/test_cv_lane_track_vehicle_data.py`를 새로 만든다. 기존 데이터 추출기는 수정하지 않는다.

**로컬 산출물:** `.omc/aihub-models/cv-lane-track-v1-2026-10-09/vehicle-comparison/` 아래 `input_manifest.json`, `gt/vehicles_1fps.jsonl`, `gt/targets_5fps.jsonl`, `frames_5fps/`, `gt_manifest.json`.

- [x] 15영상·651캐시의 파일 대응, 원본 크기, source frame index, `time_sec=frame_index/source_fps`, SHA256을 검증한다. 실제 fps/시각 이상은 입력 실패로 분리한다.
- [ ] 15영상 공통 1fps 프레임에서 보이는 4륜 도로 차량을 전부 bbox 라벨링한다. 화면 밖 bbox 확장은 하지 않으며 이륜차·자전거·보행자는 제외한다. ignore 판독 기준을 모델 결과를 보기 전에 문서화하고 고정한다.
- [x] 차선 사건 11건의 정답 구간 전후 3초, 정상 3클립의 7–13초를 원본 해상도 5fps로 추출한다. 클립 경계 clamp·겹친 구간 병합·실제 프레임 시각을 기록한다.
- [ ] 사건 차량·혼동 가능한 이웃 차량 bbox, GT 객체 ID, 가림/가시성, 진입/이탈을 작성한다. 정상 패널의 관찰 대상도 결과 전에 고정한다. AI가 만든 초안은 사람 영상 검수 전까지 확정 GT로 사용하지 않는다.
- [ ] 사건 주체가 확인되지 않으면 `TARGET_UNRESOLVED`로 남긴다. 최종 사건 11건 목록은 유지하되 차량 지표의 평가 가능한 사건 수와 제외 건수를 함께 기록한다. unresolved가 남으면 선정은 잠정이다.
- [ ] C05의 10–12초와 20–22초를 별도 사건으로 등록한다. C47의 0.5–3초를 포함한 결과와 경계 제외 보조 결과를 준비한다. 차선·선 종류 polyline 라벨은 이 단계에서 만들지 않는다.
- [ ] 패널 경계 clamp, 구간 병합, 두 사건 ID 유지, 원본 시각 계산을 synthetic fixture로 검증한다. 영상에서 사건 차량 ID와 가시성 전환을 사람 검수한 뒤 GT 해시를 고정한다.

**통과 조건:** 1fps 완전 라벨과 5fps 부분 라벨이 명확히 구분되고, 모든 사건에 확인된 target 또는 unresolved 상태가 있다. **결과 열람·정확도 채점의 선행 조건은 차량 GT 작성·영상 검수**다. 기존 사건 시간 라벨을 bbox 정답 대신 쓰지 않는다. 독립적인 추론·속도 측정은 완료했으며 차량 GT는 미확보다.

## Task 2: 공통 adapter·저점수 캐시·평가기 검증

**참조 파일:** `scripts/aihub_model_video_adapters.py`, `scripts/aihub_hybrid_candidates.py`의 정답 없는 `ClipInput` 경계.

**계획할 파일:** `scripts/cv_lane_track_vehicle_adapters.py`, `scripts/cv_lane_track_vehicle_infer.py`, `scripts/cv_lane_track_vehicle_score.py`, `tests/search/test_cv_lane_track_vehicle_score.py`, `tests/search/test_cv_lane_track_vehicle_adapters.py`.

**인터페이스:** adapter는 기존 `Detector.predict(image) -> tuple[Detection, ...]`와 원본 좌표 `bbox_xyxy`를 사용한다. 추론 입력은 파일/프레임 ID·시각·크기·경로·모델 설정만 포함한다. 예측 JSONL은 model/panel/clip/frame ID, source frame index, 실제 시각, Detection 목록을 담는다. GT는 scorer만 읽는다.

- [ ] AI Hub와 공개 모델을 별도 프로세스·환경으로 실행한다. 기존 adapter는 감싸서 사용하고 기존 결과의 동작을 바꾸지 않는다. 환경·라이브러리·CUDA/driver·가중치·source 해시를 `environment.json`과 `models.json`에 기록한다.
- [ ] 이미지 1장으로 모델별 strict loading, CUDA FP32, 클래스 매핑, 원본 bbox 범위를 smoke 검증한다. 다운로드 경로와 해시를 고정하고 V1–V7별 성공/실패를 기록한다.
- [ ] 공통 confidence 0.01 cache와 후처리 규칙을 구현한다. 신호등 등이 최대 검출 개수를 소모하지 않도록 평가 차량 class filter와 max_det 적용 순서를 기록한다. VEHICLE 공통 NMS 전후 개수를 보관한다.
- [x] 완전 라벨 1fps에서 score 순서·IoU≥0.5·미매칭 GT 최고 IoU로 1:1 매칭한다. 동일 GT의 추가 예측은 중복 FP다. evaluable GT와 대응 가능한 예측을 먼저 처리하고 사전 ignore 영역에만 속한 예측을 제외한다. 함수·fixture 완료이며 실제 GT 채점은 미실행이다.
- [x] AP50:95는 IoU 0.50–0.95 간격 0.05, 101-point 보간으로 계산한다. 1fps 작은 차량 recall은 전체 GT와 매칭한 뒤 작은 GT slice에서 계산해 큰 차량 검출이 FP로 잘못 바뀌지 않게 한다. 함수·fixture 완료이며 실제 GT 채점은 미실행이다.
- [ ] 두 예측/한 GT → TP=1·FP=1, 완벽 예측 → AP=1, 예측 없음 → recall=0, ignore-only 예측 제외, 5fps 부분 라벨 precision 금지 fixture를 검증한다. 비정방형 프레임은 공식 좌표 복원 결과와 대조한다.

**통과 조건:** 7종의 동일 출력 계약과 평가 경계가 검증되고, 실패 모델은 식별 가능하다. 향후 CLI 옵션은 구현 후 `--help`로 확인해 실제 명령을 실행 ledger에 남긴다. 현재 없는 명령을 실행 가능하다고 제시하지 않는다.

## Task 3: Calibration 5클립에서 운영점 고정

**입력:** `141628`, `141927`, `141956`, `150504`, `youtube_clip_01`의 완전 라벨 1fps 패널. `141xxx` 파일은 `20260620_` 접두사와 `_EVT_1`을 가진다.

**산출물:** `predictions/calibration/`, `calibration.csv`, `operating_points.json`.

- [ ] 각 모델을 confidence≥0.01로 실행하고 예측을 저장한다. 후보 confidence **0.05 / 0.10 / 0.15 / 0.25 / 0.40 / 0.60**은 같은 캐시에서 채점한다.
- [ ] precision≥0.90 조건 중 recall 최대 운영점을 선택한다. 동률이면 precision, 다음 높은 confidence 순이다. precision은 완전 라벨 차량 기준으로 계산한다.
- [ ] 만족하는 confidence가 없으면 `OPERATING_POINT_FAILED`로 기록한다. 비교 수치는 진단용으로 남기되 선정 자격을 주지 않는다.
- [ ] 공통 0.25 결과도 별도 보관한다. 운영점·선정 코드·GT·예측 해시를 고정한 후 set1 채점으로 이동한다.

**통과 조건:** V1–V7 각각에 고정 운영점 또는 실패 이유가 기록된다. set1 결과로 confidence를 재조정하지 않는다.

## Task 4: Set1 10클립 차량 검출 비교와 상위 2종 선정

**입력:** 나머지 `YT_*` 10클립의 완전 라벨 1fps 및 차선 사건 9건의 5fps target 패널. 신호 2클립은 전체 차량 bbox 지표에 포함하고 차선 사건 대상 지표에서는 제외한다.

**산출물:** `detector_comparison.csv`, `event_detection.csv`, `latency.csv`, `failures.jsonl`, `top2.json`.

- [x] 고정 설정으로 모든 평가 패널을 실행한다. 합성 빈 이미지 20회 warm-up 후 같은 패널을 3회 측정했다. 검출 수치는 첫 완결 실행에서만 집계하고 반복 프레임을 새 표본으로 세지 않는다.
- [ ] CUDA synchronize를 적용해 전처리·추론·후처리·CPU 결과 변환 전체 adapter p50/p95 및 peak VRAM을 측정한다. decode/캐시 읽기/저장/로딩 포함 전체 wall-clock은 별도로 기록한다.
- [ ] 전체 precision/recall·AP50/50:95를 공통 0.25와 고정 운영점으로 나란히 보고한다. 작은 차량은 공통 640 letterbox 좌표로 환산한 **GT 높이<32px**로 정의한다.
- [ ] 5fps에서 가시 사건 target의 IoU≥0.5 검출 비율을 사건별로 계산한 뒤 사건 동일 가중 평균을 주 지표로 사용한다. 패널 전체 수치와 정답 사건 구간 수치를 구분해 남긴다.
- [ ] 사건별 최장 연속 미검출 시간, 사건 구간 검출 0건, 작은 차량/가림/야간·터널/밀집 slice와 표본 수를 보고한다. 완전 가림·이탈은 검출 실패와 분리한다.
- [ ] bbox 하단 중앙 오차/GT 폭의 중앙값·p95, 1fps 프레임당 FP·중복을 보고한다. 5fps 부분 라벨에서 전체 FP/precision을 계산하지 않는다.
- [ ] 완주·CUDA 실행·운영점 통과 모델을 **사건 target 검출률 → 작은 차량 recall → 전체 precision → adapter p95** 순으로 정렬한다. 완전 동률은 V1→V7 순이다. 상위 2종을 고정한다.
- [ ] 하나만 통과하면 해당 모델과 V1 진단을 함께 보고한다. V1도 실행 실패하면 그 이유를 남긴다. 통과 모델 0종이면 선정을 보류하고 진단 보고서로 종료한다.

**통과 조건:** 실패 모델을 포함한 7행 비교표, 사건별 수치·분모·제외 수와 순위 선정 근거가 있다. calibration 사건 2건은 set1 선정 평균에 섞지 않는다. C47 제외 보조 비교는 set1 사건 8건 기준임을 명시한다.

## Task 5: 상위 2종을 같은 ByteTrack으로 재검증

**계획할 파일:** `scripts/cv_lane_track_vehicle_track.py`, `tests/search/test_cv_lane_track_vehicle_track.py`. 검출 metric 파일에 GT coverage 계산을 추가한다.

**입력/출력:** 입력은 detector의 confidence≥0.01 예측 캐시와 정답 없는 패널 manifest다. 출력은 실제 관측과 대응하는 detection index, track ID·시각·bbox를 가진 track JSONL이다. GT target ID는 추적 입력으로 전달하지 않는다.

- [ ] 두 모델 모두 `track_high_thresh=new_track_thresh=선정 confidence`, `track_low_thresh=0.01`, `match_thresh=0.8`, `fuse_score=true`, `track_buffer=5`로 고정한다. 실제 sampling fps=5를 기록하고 `max_frames_lost==5`를 확인한다.
- [ ] 8.4.133 source의 `BYTETracker(args)`는 `max_frames_lost=args.track_buffer`를 사용한다. 다른 버전의 fps 환산이나 constructor 인자를 복사하지 않는다. [고정 버전 구현](https://github.com/ultralytics/ultralytics/blob/v8.4.133/ultralytics/trackers/byte_tracker.py).
- [ ] 각 연속 패널은 모든 5fps 프레임을 순서대로 처리한다. 검출 없는 프레임에서도 tracker를 update한다. 패널 사이 추출되지 않은 시간은 연속으로 연결하지 않으며 모델/클립/분리 패널 시작에서 상태와 ID를 reset한다. scene-cut 보정은 추가하지 않는다.
- [ ] 저점수 예측은 기존 track 연결에만 사용하고 새 track을 만들지 않는다. buffer 경계의 5·6 빈 프레임, 저점수 단독 입력, 패널 reset, 검출 없는 Kalman box의 coverage 제외를 fixture로 검증한다.
- [ ] 각 사건에서 가장 오래 유지된 단일 예측 ID가 GT 가시 프레임을 덮은 비율을 계산한다. IoU≥0.5로 대응한 **실제 검출 관측만** 인정한다. set1 확인 가능한 사건의 동일 가중 평균을 주 비교값으로 쓴다.
- [ ] track 단절, 최장 공백, 이웃 차량 ID switch, 하단 중앙 jitter, tracking wall-clock을 보고한다. calibration 사건·정상 패널은 별도 진단표로 둔다.
- [ ] coverage가 높은 detector를 선정한다. 동률이면 ID switch → 검출 주 지표 → tracking wall-clock 순이다. unresolved 또는 재검증 실패가 남으면 잠정 선정/보류를 표시한다.

**통과 조건:** detector 상위 2종 비교표와 실제 overlay가 일치한다. 단일 ID coverage는 공백을 없앤다는 뜻이 아니므로 최장 공백을 반드시 함께 해석한다.

## Task 6: 영상 검수·결과 보고 후 종료

**계획할 문서:** `docs/modules/search/experiments/cv-vehicle-model-comparison-2026-10-09.md` 결과 보고서와 해당 `experiments/README.md` 색인. 원래 전체 실험 계획을 차량 선정 결과로 대체하지 않는다.

- [ ] 실제 15영상의 평가 패널을 overlay로 검수한다. 작은 사건 차량 FN, 이웃 차량 오매칭, bbox 하단 흔들림, C05 두 사건, C47 경계, 정상 3클립을 확인한다.
- [ ] 숫자/overlay가 충돌하면 GT·좌표 복원·매칭을 확인한다. set1 성능을 높이기 위한 threshold 수정은 하지 않는다. GT 오류 수정 시 해시와 수정 이유를 남기고 관련 전 모델을 같은 GT로 다시 채점한다.
- [ ] 결과 보고서에 7모델 비교, 운영점, 상위 2종 추적 비교, 최종 선정 근거, 사건별 누락, 실행 실패, 성능·속도·분모·한계를 기록한다.
- [ ] 로컬 `selection_ledger.json`에 선정 모델·confidence·규칙·패키지·가중치/GT/input/code 해시를 연결한다. `viz/debug/`는 GT 있는 로컬 검수본, 공유가 필요할 때 `viz/reviewer/`는 GT 없이 번호판/얼굴을 비식별화한다.

**완료 정의:** 실제 검출·추적 비교 결과와 영상 검수까지 완료하면 차량 선정 단계 완료다. 이는 위반 후보 Recall·차선 교차 성능·운영 채택을 입증하지 않는다. 정상 113개 미확보와 held-out 양성 부재는 다음 단계 평가 한계로 남긴다.

## 실행 순서·시간 계획

| 순서 | 작업 단위 | 시간 계획의 기준 |
| --- | --- | --- |
| 1 | 입력 검증·실행 환경 smoke | 패키지/가중치 확보와 CUDA 확인이 끝나야 이후 일정을 산정 가능 |
| 2 | 651장 완전 bbox + 원본 5fps target 라벨 | 가장 큰 인력 작업. 20장 pilot 라벨링 시간을 측정해 잔여량을 추정하고 5fps 검수는 따로 합산 |
| 3 | adapter·scorer 구현/fixture 검증 | 환경 smoke 후 실제 인터페이스에 맞춰 진행 |
| 4 | calibration → confidence 고정 → set1 비교 | 7모델 동일 패널 3회. 한 모델 pilot에서 추론·I/O·저장 시간을 분리해 잔여 실행시간 추정 |
| 5 | 상위 2종 추적·영상 검수·보고 | 검출 캐시 재사용. 모델 재추론 없이 추적 비교 |

속도보다 **GT와 비교 조건 고정이 선행**한다. 최초 파일 확인만으로 전체 작업 시간을 확정하지 않는다. 차량 GT 담당과 검수 시간이 확보되면 1–3단계를 준비 묶음, 4–6단계를 실행/선정 묶음으로 진행한다.

## 계획 자체의 검토 기록

- 첨부 §3의 모델 7종, 공통 출력/후처리, 운영점, set1 순위, 동일 tracker 재검증을 모두 작업에 배치했다.
- §2의 차량 평가용 라벨은 포함하고 후속 차선 라벨은 범위에서 분리했다.
- 계획 작성 당시에는 실행하지 않았다. 이후 사용자 실행 승인으로 추론과 속도 측정을 완료했으며, 실제 스크립트·캐시·검증·미완료 범위는 위 실행 상태 및 결과 보고서에 기록했다. GT 양식은 확정 GT가 아니다.
