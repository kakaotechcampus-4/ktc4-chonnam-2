# W6 Real E2E 실행 기록 — `scenario_happy_001`

**날짜:** 2026-09-18 · **브랜치:** `feature/case-mock-real-service-adapter` · **실행자:** 유소연

**목적:** W5 Baseline + W6 Real E2E 데드라인(2026-09-22 월 20:00 회의 — "대표 실제 데이터 시나리오 1개가 전체 흐름을 실제로 통과하는지 직접 실행 확인")의 case 몫 증빙. Recording → Search → 후보 선택 → Readout → Evidence → `CaseView`가 mock JSON을 읽는 게 아니라 각 모듈의 실제 공개 함수를 호출해서 통과하는지 실행하고 기록한다.

## 재현 방법

```
# 검증(pytest) — 값이 맞는지 assert로 확인
pytest tests/case/test_real_e2e.py tests/case/test_get_view_entrypoint.py -v

# 데모(사람이 읽는 출력) — 파이프라인 1회 실행, 실제 값을 그대로 출력
PYTHONPATH=src python -m daesingo.case.demo_happy_001
```

두 명령 다 새 패키지 설치 없이 프로젝트에 이미 있는 의존성(`pydantic`/`pytest`)만으로 돈다. `PYTHONPATH=src`가 필요한 이유 — `pytest`는 `pyproject.toml`의 `pythonpath=["src"]`로 자동 처리되지만, `python -m`으로 직접 실행할 때는 그 설정이 안 먹어서 수동으로 줘야 한다.

## 무엇이 실제로 실행됐는가

| 단계 | 호출 | 실제 함수인가 |
| --- | --- | --- |
| Recording | `RecordingService.resolve_span` → `prepare_analysis_source` → `build_incident_clip` | ✅ 실제 |
| Search (후보) | `search.search_candidates(scope)` | ✅ 실제 |
| Search (Fine) | `search.verify_visual(input_ref, hint)` | ✅ 실제 |
| Readout | `readout.read_plate(request)` / `read_overlay_time(request)` | ✅ 실제 |
| Evidence | `resolve_time → assemble_evidence → calculate_evidence_needs → evaluate_requirements×2 → build_report_package` | ✅ 실제 |
| CaseView | `case.get_view(case_id, store=store)` | ✅ 실제(오늘 신설) |

"실제"의 의미는 **case가 raw mock JSON을 직접 읽지 않고 각 모듈의 공개 함수를 호출했다**는 뜻이다. search 내부의 `FixtureSearchService`, readout 내부의 `FixtureOcrProvider`는 각 모듈 자신의 stand-in(진짜 Gemini/OCR 아님)으로 여전히 남아 있다 — 이건 case가 기다리거나 손댈 대상이 아니라 search/readout Owner가 자기 W5/W6에서 따로 진행하는 부분이다(`decisions/orchestration-service-layer.md` §6·§7 참고).

## 실제 실행 결과 (2026-09-18)

```
[1/4] Recording+Search: 후보 탐색 중 (search.search_candidates 실제 호출)...
        -> 후보 발견: candidate_h001 (흰 SUV가 백색 실선을 넘어 인접 차로로 이동하는 장면)
[2/4] Readout: 번호판/화면시각 판독 중 (recording.build_incident_clip + readout.read_plate/read_overlay_time 실제 호출)...
[3/4] Evidence: 증거 조립·신고요건 판정 중 (evidence.assemble_evidence/evaluate_requirements 등 실제 호출)...
[4/4] CaseView 조립 중 (case.get_view 실제 호출)...

=== CaseView 요약 ===
  stage:        READY
  번호판:       12가3456  (info_state=INFO_SOURCE_VERIFIED)
  발생 시각:     2026-08-24T18:05:12+09:00  (info_state=INFO_SOURCE_VERIFIED)
  위반 내용:     백색 실선을 넘어 진로를 변경
  신고요건 판정: WARN
  최종 패키지:   아직 없음 — situation_response/observation_facts 미확보(알려진 단순화, real_e2e.py 참고. 실패 아님)
```

전체 `CaseView` JSON(진행 상태 8단계 전부 `DONE`, `requirements_package` 세부 판정 포함)은 데모 스크립트를 그대로 실행하면 다시 볼 수 있다 — 이 문서에는 요약만 남긴다(재실행 가능하니 통째로 박제하지 않음).

## 흥미로운 발견 — 조작 아님, 실제 판정 로직이 실행된 결과

`requirements_package`의 `package.deadline.within_policy` 체크가 `WARN`(`deadline.exceeded`)으로 나온다. `evaluated_at`을 실행 시점의 실제 현재 시각(2026-09-18)으로 넘기는데, 시나리오의 사건 발생 시각은 2026-08-24라서 신고 기한(발생 후 약 며칠)이 실제로 지나 있다 — **버그가 아니라 evidence의 기한 판정 로직이 실제 시각을 받아서 정확히 판정한 결과**다. 데모/회의에서 "왜 WARN이 뜨냐"는 질문이 나오면 이걸로 설명하면 된다.

## 알려진 단순화 (반복 — `real_e2e.py`/`decisions/orchestration-service-layer.md` §7.2가 원본)

1. `time_source_candidates` — recording이 아직 공개 함수로 노출 안 해서 raw fixture 1곳만 읽음.
2. `situation_response`/`observation_facts` — case에 만드는 로직이 없어 `None` → 그 결과 `package`가 `null`.

## W6(case 몫) 완료 증빙 3가지 — 2026-09-18 기준, 3개 중 1개만 충족

| 완료 증빙 | 상태 | 이유 |
| --- | --- | --- |
| 배포 URL 또는 배포 환경 실행 증빙 | ❌ **미충족** | 지금까지 전부 로컬 실행(pytest·`demo_happy_001.py`)뿐이고 배포된 URL/환경이 없다. 어디에 배포할지(Elice? 팀 서버?) 아직 정해지지 않았다 — 결정 필요. |
| 대표 시나리오 실행 로그/화면 | ✅ **충족** | 위 「실제 실행 결과」 절 + 회의에서 `demo_happy_001.py` 라이브 재실행 가능. |
| 최초 실제 Eval 숫자 | ❌ **미충족 — case 몫이 아님** | `eval/results`·`eval/predictions`가 현재 `demo_correct`/`demo_wrong`/`mock_*` 라벨뿐이라 eval이 아직 real 함수로 숫자를 낸 적이 없다. 이건 김대원(`eval` Owner)의 W5 항목("Eval이 실제 함수 최소 1개 호출해서 결과 생성")이고, `search`/`eval` Owner 분리 원칙(`ownership.md`) 때문에 case가 대신 채울 수 없다. |

**3가지 중 1가지만 충족한다.** 나머지 두 개는 case 혼자 못 끝내는 이유가 서로 다르다 — 배포는 인프라 결정이 필요하고, eval 숫자는 소유권이 다른 모듈 몫이다. 월요일 회의에는 이 표 그대로 "대표 시나리오 E2E는 통과, 배포·eval 실측은 각각 별도 결정/진행 필요"로 보고하면 정확하다.

## (참고) W5/W6 요청 문서 전체 기준 대비

| 요구 | 상태 |
| --- | --- |
| 대표 시나리오 1개가 전체 흐름을 실제로 통과 | ✅ (`happy_001`, `stage: READY`) |
| Mock→Real 교체 최소 1건 (PR 증빙) | ✅ `feature/case-mock-real-service-adapter` 5개 커밋 |
