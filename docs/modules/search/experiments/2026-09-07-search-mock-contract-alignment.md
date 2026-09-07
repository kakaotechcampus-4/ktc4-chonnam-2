# Search Mock Contract Alignment — 2026-09-07

> **성격:** Search Mock의 계약 정합성 검수 및 수정 기록이다. 새로운 Architecture/Data Contract 결정을 확정하는 문서가 아니다.
>
> **작업 브랜치:** `fix/search-mock-contract-alignment`

## 목적

`data/mock/search/`와 연결된 case/runtime fixture를 다음 기준으로 검수하고, Seed Mock이 Consumer 개발에 더 안전하게 쓰이도록 명확한 불일치를 수정한다.

1. Final Contract 일치
2. 현실적인 값 조합
3. 실패·UNKNOWN·ABSTAIN 표현
4. Consumer 사용 가능성
5. Scenario 참조 일관성

## 검수 결과 요약

기존 fixture는 JSON 형태와 기본 ID 연결은 맞았지만 다음 의미 불일치가 있었다.

- Candidate Search와 Fine/Classification의 `VisualEvidence`가 같은 `AnalysisRun`을 사용했다.
- `VisualEvidence.temporal_facts[].at_offset_ms`가 Fine input 상대 시간이 아니라 Timeline offset처럼 기록됐다.
- `AnalysisRun.usage_summary`와 연결된 `UsageRecord`의 처리 시간·지연·통화가 일치하지 않았다.
- 차량 hint가 없는 Partial Scenario에서 `match_with_hint=false`를 사용했다.
- Candidate summary가 관찰 사실 대신 `신호 위반`이라는 법적 판단에 가까운 표현을 사용했다.
- 기존 검증 스크립트가 Candidate Search Run과 VisualEvidence Run의 동일성을 요구해 위 문제를 잡지 못했다.

## 변경 내용

### Search fixture

- 시나리오별 `VISUAL_VERIFY` AnalysisRun을 추가했다.
  - `data/mock/search/visual_verify_run.happy_001.json`
  - `data/mock/search/visual_verify_run.partial_001.json`
- `VisualEvidence.run_id`를 새 Visual Verify Run에 연결했다.
- Fine input ref에서 case 식별 표현을 제거하고 별도 opaque input ref를 사용했다.
- Fine input 시작 기준으로 `at_offset_ms`를 수정했다.
  - Happy: `8000ms`
  - Partial: `9000ms`
- 차량 hint가 없는 Partial Scenario의 `match_with_hint`를 `null`로 수정했다.
- Partial Candidate 설명을 `적색 신호 상태에서 차량이 교차로에 진입하는 장면`으로 수정했다.

### Case/runtime 연결 fixture

- 시나리오별 `VISUAL_VERIFY` JobRecord와 JobExecution을 추가했다.
- Visual Verify 호출에 대응하는 UsageRecord를 추가했다.
- Candidate Search의 `usage_summary`와 UsageRecord가 처리 시간·지연·비용에서 일치하도록 정리했다.
- `JobExecution.produced`가 Visual Verify AnalysisRun과 VisualEvidence를 참조하도록 연결했다.

### Manifest와 설명 문서

- Scenario artifact 목록과 `fixture_index.csv`에 Visual Verify Run을 추가했다.
- Mock JSON 검사 대상은 47개에서 49개가 됐다.
- `docs/mock/01~04`의 개수·흐름·예시·검증 설명을 현재 fixture에 맞게 갱신했다.
- `JobRecord.kind=VISUAL_VERIFY`는 열린 kind 확장 규칙을 따른 보수적 선택임을 `docs/mock/CONTRACT_CONFLICTS.md`에 기록했다.

## 검증 스크립트 보강

`scripts/validate_mock_pack.py`에 다음 검사를 추가했다.

- VisualEvidence가 별도 `VISUAL_VERIFY` AnalysisRun을 참조하는지
- VisualEvidence와 Visual Verify Run의 `input_ref`가 일치하는지
- `at_offset_ms`가 Mock Fine input 처리 길이 안에 있는지
- AnalysisRun과 UsageRecord의 run reference가 일치하는지
- 처리 영상 길이·token 합계·단일 호출 latency·동일 통화 비용 합계가 정합한지

## 실행 결과

2026-09-07에 다음 명령으로 확인했다.

```powershell
$env:PYTHONUTF8='1'
python scripts/validate_mock_pack.py
```

결과:

```text
검사한 JSON 파일 수: 49
오류(ERROR): 0
경고(WARN): 0
```

추가 확인:

- `validate_mock_pack.py` Python 문법 검사 통과
- `git diff --check` 통과

## 기준별 현재 상태

| 기준 | 현재 상태 | 설명 |
| --- | --- | --- |
| Contract 일치 | Seed 범위 통과 | Candidate Search와 Visual Verify 실행을 분리하고 상대 시간·usage 정합을 보강했다. |
| 현실적인 값 조합 | Seed 범위 통과 | 처리 길이·latency·비용과 hint 의미를 서로 맞췄다. |
| 실패·UNKNOWN·ABSTAIN | 대표 Partial만 통과 | Search PARTIAL/target AMBIGUOUS, GPS UNKNOWN, Plate ABSTAIN을 유지한다. |
| Consumer 사용 가능 | 제한적 사용 가능 | case/eval/readout이 ID와 핵심 출력은 읽을 수 있으나 아래 확장 Scenario는 아직 없다. |
| Scenario 참조 일관성 | 검사 통과 | scope/run/candidate/visual/job/execution/usage 참조를 검증 스크립트로 확인했다. |

## 남은 범위

다음은 이번 Seed 정합화에서 새로 확정하지 않았다.

- Candidate 0개인 정상 Search Scenario
- `AnalysisRun=FAILED`
- `VisualEvidence=NOT_OBSERVED` / `UNCERTAIN`
- Candidate Top-3와 rank/Recall@K 검증
- 복수 `target_event_types` 입력
- Candidate-independent Fine/Classification fixture
- Partial Scenario용 eval fixture
- B07 Fine input/FrameRef 실제 계약
- B08 ISO8601 AnalysisScope와 relative-only Timeline 접합
- B09 Candidate/Run의 Timeline revision 추적
- `JobRecord.kind=VISUAL_VERIFY`의 case/search Owner 확인

이 항목들은 현재 Seed Mock의 오류로 숨기지 않고 후속 Scenario/Contract 작업으로 남긴다.

## 주의

작업 시작 전부터 존재하던 미추적 파일 `docs/modules/search/first-integration-checklist.md`는 사용자 작업으로 보고 수정하지 않았다. 해당 문서에는 VisualEvidence와 Candidate Search가 같은 Run을 사용한다는 기존 설명이 남아 있으므로, 정식으로 추가하기 전 이번 기록 및 Final Contract와 다시 맞춰야 한다.
