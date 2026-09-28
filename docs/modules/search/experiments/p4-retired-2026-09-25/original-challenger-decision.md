# Gemini Coarse→Fine p4 challenger 적용

작성일: 2026-09-25 · 범위: Search 내부 구현과 평가 인계

[p4 구현 계획](./gemini-coarse-fine-p4-implementation-plan-2026-09-22.md)을 현재 `develop`의 OpenAI 호환 프록시 경로에 적용한다. 기준 모델은 `gemini-3.8-flash`이며, 운영 프롬프트 기본값은 **p3**이다. `.env`에 `DAESINGO_GEMINI_PROMPT_REVISION=p4`를 명시한 실행만 challenger를 사용한다. 비교와 되돌리기는 이 값으로 수행한다. p3의 현재 Fine 리소스는 PR #136 이후 본문을 기준으로 보존한다.

## p4의 Search 내부 계약

- Coarse 응답은 사건 유형·후보 창·대상 설명·관찰·불확실성 이유·`STRONG | PLAUSIBLE | AMBIGUOUS`를 받는다. 핵심 시각이 null이면 후보 창의 중간값을 대표 시각으로 사용하고 `CRITICAL_TIMESTAMP_UNCERTAIN`을 남긴다. 같은 유형·정규화된 대상 설명·밀리초 단위 동일 span만 중복 제거한다. 강도는 `1.0 | 0.6 | 0.3`의 검색 순위로 변환되며 사건 확률은 아니다.
- Fine은 4종 사건 각각의 고정 predicate와 사건별 반증 규칙을 사용한다. `NOT_OBSERVED`는 충분한 가시성 아래의 결정적 반증과 해당 predicate 이름을 요구한다. `UNCERTAIN`은 미확정 predicate와 blocking uncertainty를 요구한다. 안전모 미착용은 `helmet_like_object=NOT_OBSERVED`가 명확한 머리 가시성과 함께 있어야 `OBSERVED`가 된다.
- Fine 응답 시각은 제공한 clip의 시작을 0으로 하는 밀리초다. context는 앞뒤 여유 구간에 있을 수 있지만 critical event는 후보 core 안이어야 한다. 원본 시각으로 내부 범위 확인을 하며 공개 `TemporalFact.at_offset_ms`의 clip 기준 의미는 바꾸지 않는다.
- 입력에 addressable frame inventory가 없으므로 모델 wire schema에 `evidence_refs`를 두지 않는다. 공개 `VisualEvidence`의 해당 필드는 빈 값이다. 실제 keyframe과 Recording 발급 `FrameRef`를 전달하는 후속 작업에서만 allowlist를 검토한다.
- p3·p4는 프롬프트와 wire parser를 각각 보유한다. 선택한 버전과 fingerprint를 사용 기록에 남기고, 공개 `CandidateEvent`·`VisualEvidence`·법적 판단 경계는 유지한다.

## Eval 담당자 인계

초기 비교 세트는 **4종 × 15개 = 60개**의 event-centered clip으로 구성한다. 유형마다 clear positive 5개, hard negative 5개, ambiguous 5개를 마련하고 대상·후보 창·핵심 시각·필수 증거 가시성·predicate별 상태를 사람 검토로 라벨링한다. 개인 영상과 원본 미디어는 저장소에 커밋하지 않는다.

동일 영상에 p3와 p4를 각각 실행한다. 모델 3.8, 프록시, FPS, 해상도, reasoning 설정을 고정하고 prompt revision만 바꾼다. 유형별 Coarse recall·시각 오차, Fine precision·false positive·unsupported evidence·UNCERTAIN 비율, token·latency·cost를 함께 보고한다. 15개/유형은 3pp 차이를 안정적으로 판별할 수 없으므로 이 세트는 초기 회귀 확인용이다. 기본값 전환은 충분한 추가 평가와 Search Owner의 별도 채택 결정 이후에만 진행한다. 채택 비교 기준은 9월 16일 개정안 §10을 따랐다(개정안은 2026-09-28 삭제, 채택 기준은 eval과 #158에서 합의 대기).
