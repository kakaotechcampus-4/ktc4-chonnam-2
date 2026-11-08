# INCIDENT_CLIP_BUILD 구현 계획

> superpowers:executing-plans로 직접 실행하고, 구현 후 새 읽기 전용 검토자가 리뷰한다. staging·커밋·푸시·PR 작업은 하지 않는다.

**목표:** Case가 발주한 clip Job을 Recording 공개 capability와 기존 T1/T2로 실행한다.

**구조:** 호출자의 짧은 트랜잭션에서 분리된 입력과 실행별 Recording context를 사용한다. 연결 반환 후 미디어를 처리한다. Fine의 produced 결과가 AnalysisSource를 식별하고 Recording 공개 메타데이터가 명시적인 VIDEO stream을 제공한다. 현재 선택값으로 대체하지 않는다.

**기술 구성:** Python, SQLAlchemy Core, MySQL 8.4, ffmpeg, pytest.

**명세:** `docs/modules/case/decisions/incident-clip-observation-input.md`, `docs/runtime/runtime-tech-spec.md`, #297 댓글 6464169000과 사용자 구현 요청.

## 제약과 검토 중점

- IN_PROGRESS · 관련 이슈 #297(RT-10(b)). Readout/export handler와 Case/Web 표시는 제외한다.
- 고정된 후보/세대/span/Fine/scope가 일치해야 한다. 최신 Fine이 실패했으면 이전 성공을 재사용하지 않는다.
- INCIDENT_CLIP_BUILD_FAILED만 RECORDING_INCIDENT_CLIP_BUILD_FAILED로 매핑한다. 알 수 없는 코드는 전파한다.
- 입력 트랜잭션이 열린 상태에서 미디어를 처리하지 않는다. 공개 호출 사이에 checkpoint를 두고 취소·오류 시 닫는다.
- 진입한 실행마다 build 호출은 정확히 한 번이다. T1 재실행·T2 재전달에서 다시 호출하지 않는다.
- 명시적 clip 인코딩이 필요하며 capability가 없으면 kind를 미등록으로 남긴다.

## 작업

- [x] `tests/worker/test_incident_clip_handlers.py`와 `test_incident_clip_inputs.py`에 실패 시험을 추가하고, Git 제외 scratch에 실패 증거를 보존한다.
- [x] `IncidentClipInput`, `IncidentClipInputs`, `incident_clip_registry`를 구현한다. 고정 결속·정확한 payload·알려진/알 수 없는 오류·Runtime 예외·취소·연결 반환을 시험한다.
- [x] 명시적 Recording clip 인코딩 설정과 운영 실행별 factory를 추가하고 Worker main의 통합 registry에 배선한다. 설정 누락 동작을 보존한다. 운영 조립 시험은 구현 전에 작성한다.
- [x] 실제 MySQL 영속 복원·rollback/commit 응답 소실/재시도·취소·실제 AVI 생성 시험을 추가하고 실패→통과를 확인한다.
- [x] 별도 API/Worker 프로세스로 Fine 성공·clip 성공·동일 ref의 readout 발주까지 인수 시험한다(handler는 미등록 유지). 실패→통과를 확인한다.
- [x] 집중·관련 회귀, 필수 MySQL 부분집합, 경계·계약 fixture 검사를 실행한다. 전체 pytest와 필수 MySQL은 정책 변경 없이 원격 regression/mysql/test CI에 맡긴다.
- [x] 확인된 오류 분류와 별도 구현 기록을 문서화하고 구현 로그에 추가한다. 새 독립 읽기 전용 리뷰를 수행하고 실제 결함은 TDD로 수정·재검증한다. 모든 경로와 남은 한계를 보고한다.
