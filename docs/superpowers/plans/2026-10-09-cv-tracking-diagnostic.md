# CV_LANE_TRACK v1 — 전체 영상 추적 진단 실행 계획

사용자 요청: 차선 출력·속도 비교 이후 다음 작업 진행. 이번 단위는 **전체 15영상 5fps의 임시 V1＋L3 perception과 ByteTrack/BoT-SORT 추적 진단**이다. 기존 원문의 GT 기반 detector 상위 2종/최종 선정은 미평가 상태를 유지한다. V1은 기존 차량 기준선, L3는 앞선 실행 가능한 geometry 후보로 임시 사용하며 정확도 순위에 따른 선정이 아니다.

## 고정 실행 범위

- 기존 15영상 전 구간을 원본 해상도 5fps로 캐시한다. 사건 구간만 추론하지 않는다. 새 추론 inventory에는 파일·source timing·hash만 넣고 사건 GT·차량/차선 정답을 전달하지 않는다.
- V1 기존 원본 YOLOv5 adapter confidence 0.01 출력과 L3 공식 CUDA FP32 geometry를 각각 한 번 실행한다. 모델별 별도 프로세스, 기존 inference 환경 유지. 이 단계의 캐시는 반복 속도 비교용이 아니라 다음 추적·교차 단계의 전체 입력이다.
- 고정 Ultralytics 8.4.133 ByteTrack과 BoT-SORT(ReID off, sparseOptFlow)를 **같은 V1 출력**으로 비교한다. high/new 0.25는 GT로 선정한 운영점이 아니라 임시 공통 threshold다. low 0.01, match 0.8, fuse_score=true, track_buffer=5. 실제 max_frames_lost=5를 확인한다. 원문 추적기 진단 단계대로 scene-cut reset은 적용하지 않는다. 클립 경계에서 새 tracker를 만든다.
- tracker가 제공한 원본 detection index를 저장하고 실제 검출 bbox와 Kalman 수정 bbox를 구분한다. 검출 관측만 추적 출력에 인정하고 lost/prediction-only box를 출력하지 않는다.
- 전체 추적 JSONL, 시간·raw track 수/공백 등 출력 진단, L3 함께 표시한 로컬 비교 영상을 보존한다. 전 15클립의 고정 짧은 연속 시점을 직접 확인한다. ID switch/사건 coverage/정량 정확도를 GT 없이 계산하지 않는다.
- 이번 단위는 추적 진단까지다. 차선 ID 시간 연결·교차 state machine·의미 종류 판정·C0–C5·Fine·운영 변경·외부 게시·최종 조합 선정은 후속 단위다. 앞선 영상/예측을 검수한 뒤 만든 라벨을 사전 독립 GT로 주장하지 않는다.

## 실행 단위

1. 완료: GT 없는 source inventory에서 15영상 전 구간 3,233프레임을 원본 해상도 5fps로 캐시하고 공식 tracker 계약·독립 tracking runtime을 확보했다.
2. 완료: 전체 perception 캐시·추적 runner·관측 시각화 구현. 원본 index/저점수/버퍼 상태/clip reset/덮어쓰기 테스트 7개와 compileall 통과.
3. 완료: V1/L3와 ByteTrack/BoT-SORT 각각 전체 3,233프레임 완료. 12,932행의 스키마·프레임·원본 detection index·코드 해시 감사와 전체 30개 MP4 디코딩 검증 통과.
4. 진행: 전 15클립 연속 6프레임과 14개 전후 비교 시트, 총 29시트·128개 시점을 직접 검수 완료. 결과 보고서·index·ledger 저장과 최종 검증을 마무리한다.

산출물은 `.omc/aihub-models/cv-lane-track-v1-2026-10-09/tracking-diagnostic/`에 새로 보존한다. 이전 evidence 디렉터리에 다시 실행하지 않는다. 원본·시각화는 로컬 전용이며 다른 사용자의 변경은 보존한다.
