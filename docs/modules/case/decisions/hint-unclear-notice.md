# 설명을 잘 이해하지 못했을 때 — `search.hint_unclear` notice

> **상태: 결정 · 1단계 구현** · 결정일 2026-10-20 · 담당 유소연(`case`) · 근거 [#266](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/266)(PM (a) 방향 · web 위치 · 신호 의견, case 답변), Q3 confidence 실험(`../experiments/intent-llm-model-comparison/results/q3-confidence-experiment.md`), #259(구조화 실패는 notice 없음), #224(결과 화면에서 알린다)
> 규칙 원문은 CaseView 계약 B절 `notices[].code` 행(`docs/architecture/contracts/contract-job-record-case-view.md`)에 있다. 이 문서는 이유와 고르지 않은 안만 둔다.

## 1. 목표 · 범위

단서 구조화(`HINT_EXTRACT`)가 사용자의 설명을 잘 이해하지 못했으면, 분석은 그대로 진행하고 결과 화면에서 비차단으로 알린다(PM (a)). 사용자가 할 일은 「다시 적기」다.

**1단계(이 문서):** notice 등재 · 발동 · 저장. `actions: []`로 문구만 보인다.
**2단계:** 입력형 command 판본(case-command 계약 §2 「다음 판본」, 초안 PR #356)이 열린 뒤 `actions: [EDIT_HINT]`를 붙인다. → **2026-10-27 완료:** `EDIT_HINT{description}` command(#410, `edit-hint.md`)와 함께 `actions: [EDIT_HINT]`.

## 2. 결정

1. **대상은 `OK` + `confidence=low`와 `ABSTAINED` 둘이다.** 사용자 입장에서 「설명을 이해하지 못했다」에 가장 가까운 경우가 판단 보류(`ABSTAINED`, 단서 4개가 모두 빔)이고, low와 할 일이 같아 notice 하나로 묶는다. 그래서 이름은 `low_confidence`가 아니라 `hint_unclear`다.
2. **실행 실패(`FAILED`)는 대상이 아니다.** #259 결정 그대로다 — 호출 · 파싱 실패는 사용자가 할 일이 없고 Runtime 원장(`failure_kind`)으로 알아챈다. 빈 설명은 구조화를 건너뛰어(case-command §11) 이해할 문장이 없었으므로 대상이 아니다. `confidence`가 없는 `OK` 결과는 low로 읽지 않는다.
3. **판정은 반영 때 aggregate에 저장한다**(`CaseAggregate.hint_unclear`, state JSON). 구조화 결과 자체는 case에 남지 않아 나중에 계산할 수 없다. 다음 구조화 결과가 오면 그 결과로 바꾼다 — 다시 적어서 high가 나오면 사라진다.
4. **결과 화면(`stage`가 `INTAKE` · `SEARCHING` 뒤)에서만 붙인다.** 진행 화면은 끝까지 흐르고 결과 화면에서 알린다(#224). 문구도 과거형(「넓게 찾았어요」)이라 탐색이 끝난 뒤가 맞다.
5. **접두어는 `search`다.** 판단 근거(구조화 결과의 `confidence` · `ABSTAINED`)를 만드는 것이 search(`search/intent.py`)다(B절 「근거를 실제로 만든 모듈」 규칙). case는 읽기만 하고 search 쪽 변경은 없다.
6. **web에는 notice 유무만 내린다.** `confidence` 값 · threshold · low인지 보류인지는 내리지 않는다 — 모델 점수 해석을 web이 소유하지 않는다(PM 의견).
7. **후보 0건이면 `search.no_candidates`와 함께 붙는다.** 「왜 넓게 찾았는지」와 「결과 없음」은 뜻이 다르다.

## 3. 미결 (채우지 않는다)

- `notice.hint_unclear` 문구 — web(신유민).
- 두 notice를 화면에서 하나로 합쳐 보일지 — web 의견 대기(#266).
- `search.` 접두어 등재 — search(@kong2488-star) 이견 확인(#266).

## 4. 고르지 않은 안

| 안 | 고르지 않은 이유 |
| --- | --- |
| low일 때 탐색을 멈추고 다시 적기를 기다린다(#266 (b)) | product §6 「AI가 단서를 구조화하고 바로 분석을 시작한다」와 가장 크게 부딪힌다. 표본이 작아 hard gate로 쓰기 이르다(PM) |
| `confidence=low`만 대상 | 보류(`ABSTAINED`)가 사용자에게는 더 「이해하지 못한」 경우인데 안내가 없게 된다 |
| `FAILED`도 대상 | #259 결정과 어긋난다. 실패는 사용자 문장 탓이 아니라 「다시 적기」가 해법이 아니다 |
| 진행 화면에도 띄운다 | #224 결정(결과 화면에서 알린다)과 어긋난다 |
| `confidence`를 CaseView 필드로 내린다 | web이 모델 점수를 해석하게 된다(PM). notice 하나로 새 필드 없이 그린다(web) |
| 판정을 저장하지 않고 job 결과에서 계산 | 구조화 결과가 case에 남지 않는다. 결과 저장소(#346)가 생겨도 매 조회마다 읽을 이유가 없다 |
| `EDIT_HINT`를 지금 싣는다 | 입력형 command가 아직 없어 버튼이 늘 실패한다(B절 「실행 경로가 없는 action은 싣지 않는다」) |

## 5. 테스트

- `tests/case/test_hint_unclear_notice.py` — 모양, low · 보류 → notice, high · confidence 없음 · 실패 → 없음, 진행 화면 없음, 빈 설명 없음, `search.no_candidates`와 함께.
- `tests/case/test_case_repository_contract.py::test_hint_unclear_survives_save_and_load` — in-memory · MySQL 저장 뒤 유지.
