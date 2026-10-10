# CV_LANE_TRACK v1 차선 출력·속도 비교 실행 계획

작성일: 2026-10-09. 사용자 승인 범위: 차량 정량 평가를 보류하고 차선 모델 비교부터 진행한다. 이번 단계는 GT 없이 실행 가능한 출력·속도·로컬 overlay 진단이다. 정량 정확도나 최종 모델 선정은 주장하지 않는다.

## 고정 범위

- L1: 기존 AI Hub Mask R-CNN R50-FPN의 백색·황색 선 모델을 합친 기준선. 정지선/교통영역 모델은 제외한다. 두 모델 합산 처리시간을 기록한다.
- L2: 공식 CLRerNet⋆ DLA34 EMA. 공식 CUDA decoder와 전처리를 유지한다. 설치·CUDA extension 실패는 실패 행으로 보존하며 다른 모델로 대체하지 않는다.
- L3: 공식 UFLDv2 ResNet34 CULane, PyTorch CUDA FP32. 공식 전처리와 row/column anchor decoder를 원본 영상 좌표에 적용한다.
- 이전 차량 실험에서 검증한 동일 1,200프레임 manifest를 사용한다. 모든 모델은 자체 공식 입력 규격을 유지한다. source/weight/input/code/package 해시와 실제 tensor shape를 기록한다.
- 같은 GPU에서 모델을 순차 실행한다. 20회 warm-up 뒤 3회 측정한다. 전처리·추론·decoder 전체 adapter 시간과 읽기·저장 포함 wall-clock을 분리한다.
- 원본 좌표 polyline·출력 confidence·AI Hub 원시 마스크를 로컬 보존한다. geometry-only 모델의 종류·색·역할은 UNKNOWN이다. confidence 값이나 검출 선 개수로 정확도 순위를 만들지 않는다.
- 원문 §2의 모델 결과 전 GT 규정은 이번 사용자 선택으로 정량 평가를 보류한 간이 진단에 한해 변경한다. 예측을 본 뒤 만든 GT로 사전 독립 평가라고 주장하지 않는다. 기존 차량 예측은 계속 열람하지 않는다.

## 실행 단위

1. 완료(L1/L3)·차단(L2): 공식 source/weight 확인. L2는 native nvcc 부재와 실제 Docker backend 시작 오류로 환경 차단이며 실패 JSON을 보존했다.
2. 완료: lane polyline 계약·AI Hub 연결 성분별 중심선·공식 UFLDv2 decoder·runner를 구현했다. 관련 경계 테스트 6개와 compileall·error diagnostics를 통과했다.
3. 완료(L1/L3)·차단(L2): CUDA FP32 smoke 뒤 동일 1,200프레임 × 3회 × 2종(7,200행), 속도·hash·frame identity 감사 완료. L2 추론은 실행하지 않았다.
4. 완료: 사전 고정 42시점의 비교 시트 14개를 모두 직접 확인하고 `docs/modules/search/experiments/cv-lane-model-comparison-2026-10-09.md`에 기록했다. 정확도·교차 Recall·최종 선정은 이번 범위에서 제외하며 미평가다.

## GT가 없어서 제외하는 지표

GT polyline 대응률·거리·잘못된 경계 연결 정량 집계, 실선/점선·색상·중앙선 역할 정확도, 사건 차량에 대한 교차 성능은 계산하지 않는다. 후속 정량 평가에는 선 중심선·가시성·관련 경계/종류/역할의 독립 검수 GT가 필요하다.

## 산출물

로컬 `.omc/aihub-models/cv-lane-track-v1-2026-10-09/lane-comparison/`에 source/weight/provenance·예측·속도·overlay를 보존한다. Git에는 실험 코드·관련 경계 테스트·결과 요약만 추가 가능한 상태로 둔다. 기존 환경·실험 산출물·사용자의 다른 변경을 덮어쓰지 않는다. 원본 영상과 overlay는 로컬 전용이다.
