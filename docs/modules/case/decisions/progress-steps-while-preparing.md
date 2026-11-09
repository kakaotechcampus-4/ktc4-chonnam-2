# 준비 중 진행 단계 수 — 8단계를 유지하고, 끝난 실패 경로만 3단계

> **상태: 결정 · 구현** · 결정일 2026-11-09 · 담당 유소연(`case`) · 근거 #665(김준영 제보 · 신유민 이슈 작성), 계약 `contract-job-record-case-view.md` B§7 「`progress[]`의 step 집합 규칙」 1 · 4, web `selectScreen.ts` · `FlowScreen.tsx`

## 1. 문제

진행 화면의 단계 목록이 장면 찾기까지 8개 → 번호판 · 화면 시각 판독 중 5개 → 증거 정리 뒤 다시 8개로 바뀌었다. `_build_progress()`의 「`EVIDENCE_REVIEW` + evidence 없음」 일반 분기가 뒤 3단계(`evidence_assembly` · `requirement_check` · `package_assembly`)를 뺐기 때문이다. 이 분기는 mock `scenario_infra_failure_001`이 evidence를 `modules_intentionally_absent`로 선언한 것(규칙 2)에 맞춘 것이었는데, 실제 case에는 evidence가 늘 있으므로 규칙 1(package까지 이어질 수 있으면 8단계) 대상이다.

web의 진행 화면(`FlowScreen`)은 단계 수를 숫자로 보이고 단계마다 정거장을 찍어, 줄어드는 것이 그대로 보인다.

## 2. 결정

1. **준비 중(Fine · clip · 판독 진행)은 8단계다.** 판독 두 단계는 실행 상태 projection, 조립 이후 3단계는 `PENDING`.
2. **끝난 실패 경로는 3단계다** — Fine 음성 결과(`NOT_ASSEMBLED`) · Fine 실행 실패(기존) · **현재 선택 후보의 clip 준비 실패**(이번에 5 → 3). 세 경우 모두 판독~package를 시작하지 않고(규칙 3 · 4), web은 진행 화면이 아니라 `NOT_OBSERVED` · `SEARCH_FAILED` 화면을 그리며 이 두 화면은 진행 목록을 그리지 않는다. 화면 선택과 progress가 같은 CaseView에서 오므로 3단계 목록이 진행 화면에 보이는 순간이 없다. 실패 화면에 `PENDING` 단계를 남기면 「기다리면 된다」로 읽혀 넣지 않는다(계약에 「건너뜀」 상태도 없다).
3. **판정 순서는 그대로다** — 음성 · Fine 실패 → 상황 응답 대기(8단계) → clip 실패 → 일반(8단계).
4. **같은 후보로 다시 준비하면 8단계로 돌아온다** — 새 Fine · clip이 「가장 나중 실행」이 되어 실패 분기를 벗어난다(`test_reprepare_after_clip_failure_returns_to_eight_steps`).
5. **web은 바꾸지 않는다.**

## 3. 고르지 않은 것

- **clip 실패도 8단계(판독 이후 `PENDING`)** — 실패 화면에 일어나지 않을 단계를 대기로 남긴다. 같은 실패 화면으로 가는 Fine 실패와도 어긋난다.
- **clip 실패 5단계 유지** — 근거였던 「판독을 RUNNING으로 보이지 않게」는 3단계로도 지켜지고, 규칙 3 · 4와 맞지 않는다.

## 4. 함께 고친 것

- mock `scenario_infra_failure_001`: 카탈로그 manifest에서 `evidence` absent 선언을 빼고(evidence artifact가 없는 이유는 `note`로 옮김) case fixture 4개 revision의 `progress[]`를 8단계로. `validate_mock_pack.py` §8b가 그 선언으로 단계 집합을 검사하므로 둘을 같이 바꾼다.
- 계약 B§7 규칙 2 예시에서 `infra_failure_001`을 빼고, 규칙 4에 clip 실패를 더했다.

## 5. 범위 밖

- 신고요건 확인 · 신고자료 만들기가 조회 사이에 끝나 `RUNNING`으로 보이지 않는 것(#665 증상 2). 단계는 `PENDING` → `DONE`으로 순서대로 바뀌어 목록이 흔들리지 않으므로 이번에 다루지 않는다.
