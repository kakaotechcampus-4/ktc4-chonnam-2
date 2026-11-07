# #583 Coarse 후보 썸네일 Runtime 연결 검증

## 기준과 판정

- 기준 HEAD: `3108418c31c67010eae8b021960df1869fa3e210`.
- 작업 브랜치: `codex/issue583-coarse-thumbnails`.
- Runtime 구현과 아래 오프라인 검증을 완료했다. 실제 MySQL·EC2·배포·브라우저 검증은 **NOT_RUN**이다.
- Case 의존성은 [#604](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/604)의 고정 HEAD `4bba4d44f1ddb658fe05fce31909da3dfed0429a`이다. 조사 당시 미병합·충돌 상태다. 해당 Case capability가 없으면 production composition은 명시적으로 실패한다. **이 Runtime 변경만 독립 배포할 수 없다.**

## 변경 동작

기존 frame 발급은 INCIDENT_CLIP_BUILD 이후에만 실행됐다. 첫 Fine 결과가 NOT_OBSERVED이거나 실패하면 clip이 발주되지 않아 다른 후보의 썸네일도 최초 생성되지 않았다.

성공 Coarse 결과 뒤, T1 produced payload를 만들기 전에 `CoarseFrameIssuer`를 호출한다. Case 공개 selector가 고른 최대 Top-3에 대해 기존 Case 위치 함수와 Recording 공개 resolve_span/resolve_frame을 사용한다. 결과는 `candidate_frame_refs`의 후보 ID → frame ref 또는 null로 전달한다. Fine·clip 결과와 독립적이며, 기존 clip frame 경로는 유지한다.

- Case ID, 선택 VIDEO의 소유권, timeline/revision, 후보 span 및 대표 시각을 검사한다. Search 계약이 허용하는 `representative_ms == end_ms`는 Case 위치 결정에 맡긴다.
- frame 발급용 context는 분석 영상을 다시 준비하지 않는다. Recording의 기존 저장·발급 경로를 사용한다. 합성 영상 검사에서는 frame 추출 중 DB transaction이 없고 context 종료 뒤 같은 Case에서 PNG를 읽을 수 있음을 확인했다.
- **resolve_frame에서만** FRAME_NOT_FOUND / STREAM_UNAVAILABLE / OUT_OF_RANGE / TEMPORARY_FAILURE를 후보별 null로 바꾼다. resolve_span·metadata·소유권·DB·취소·lease 오류는 삼키지 않는다.
- frame 후처리는 Search 오류 분류 블록 밖에 둔다. 후처리 실패 시 같은 handler 안에서 Search를 다시 호출하지 않는다. Worker의 기존 재전달·stale 회수·사용자 재시도 전체가 무과금이라는 보장은 아니다.
- T2/CaseView는 #604가 저장한 ref를 소비한다. Runtime에서 Case 상태나 후보를 직접 수정하지 않는다.
- schema, 신규 job kind, Coarse 600초, retry 정책, Search 품질·요청 cap, 배포 설정을 변경하지 않았다.

## 직접 실행한 검증

| 범위 | 결과 | 한계 |
| --- | --- | --- |
| Search handlers/composition/inputs, 기존 clip/frames, 신규 issuer, production media 8개 모듈 | **175 passed** | 오프라인·메모리 저장소 및 합성 영상. 실제 MySQL 아님 |
| 고정 #604를 합친 별도 소스 트리: 기존 Case 23개 + Runtime→Case 통합 3개 | **26 passed** | 본 작업 트리의 Case 파일은 변경하지 않음. 실제 서비스/DB 아님 |
| Runtime Ruff, Linux/Windows mypy | **PASS**, 타입 검사 각 92파일 | 정적 검사 |
| boundary / Contract fixtures / diff | **PASS** | fixture 정합성이 실제 통합·E2E 수락을 대신하지 않음 |

관련 회귀 명령:

```powershell
.venv/Scripts/python.exe -m pytest tests/worker/test_search_handlers.py tests/worker/test_search_composition.py tests/worker/test_search_inputs.py tests/worker/test_incident_frames.py tests/worker/test_incident_clip_handlers.py tests/worker/test_incident_clip_inputs.py tests/worker/test_coarse_frames.py tests/worker/test_production_media.py -q -p no:cacheprovider --basetemp=.codex-scratch/issue583-new-test-run
```

`--basetemp`는 기존 보호 디렉터리가 아닌 매 실행 새 경로를 사용한다.

통합 검사는 별도 검증 트리에 현재 Runtime 코드와 고정 #604의 preview_frame/reflection/service 변경만 합쳤다. 실제 Case selector/position과 registry payload를 Case에 반영했다. Fine NOT_OBSERVED 및 FAILED 각각에서 Top-3 refs가 유지되고 rank 4는 미발급이며 clip이 발주되지 않는 것을 확인했다. stock production composition의 실제 selector 연결도 확인했다. 해당 임시 통합 검사 파일은 제품 PR 대상이 아니므로, #604 병합 후 같은 조합의 CI 재확인이 필요하다.

## 실패·리뷰 기록

1. 구현 전 신규 13개 검사는 인자/모듈 부재로 실패했다. 구현 뒤 관련 검사가 통과했다.
2. 초기 테스트 fixture가 absolute range를 사용해 실패했다. 실제 경로의 TIMELINE_RELATIVE fixture로 교정했다.
3. production media 최초 실행은 Windows 기본 임시 경로 생성 권한 때문에 4개 setup error였다. 새 workspace basetemp로 실행해 4개가 통과했다. assertion을 완화하지 않았다.
4. 최초 mypy의 dict 타입 주석 누락 2건을 수정했다. boundary 출력의 cp949 인코딩 오류는 PYTHONIOENCODING=utf-8로 재실행했다.
5. 통합 fixture의 기존 thumbnail_ref가 rank 4 미발급 검사를 가렸다. 실제 Coarse처럼 null로 고치고 Runtime 발급 ref prefix와 발급 횟수를 확인했다. 이전 실패는 제품 결함으로 정산하지 않았다.
6. 독립 리뷰에서 정상 Search 끝점 대표 시각을 Runtime이 거부하는 P2를 발견했다. 새 endpoint 검사 RED → `<= end_ms` 수정 → GREEN을 확인했다. reviewer의 읽기 전용 재검토에서 기존 P2 해결 및 추가 P1/P2 없음으로 확인했다. reviewer는 최종 175/26개를 재실행하지 않았다.

## 남은 배포 조건

1. Case #604 충돌 해결·병합 후 통합 트리와 원격 CI를 다시 확인한다.
2. 실제 MySQL에서 새 frame refs의 T1 commit/rollback/commit-unknown 및 T2 재반영을 확인한다. 기존 generic T1 동작을 새 경로의 실측 PASS로 대신하지 않는다.
3. 새 배포 이미지에서 첫 Fine NOT_OBSERVED/실패, Top-3 카드·이미지·재선택과 clip 우선 표시를 확인한다. 신규 3프레임의 실제 시간·메모리 여유는 아직 측정하지 않았다.
4. 해당 배포본이 준비되면 #523에 연결하고 Web/Case 확인을 받는다. 현재 #583/#523 운영 검증 완료를 주장하지 않는다.

AWS·provider·Docker·운영 변경, staging·commit·push·외부 댓글은 실행하지 않았다.
