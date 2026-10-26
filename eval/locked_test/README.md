# eval/locked_test

사전 고정 평가셋의 **목록과 개봉 기록**. 최종 제품 성능 주장은 여기 있는 셋으로만 한다(`docs/modules/eval/initial-evaluation-plan.md` §3). 개봉 횟수·승인 정책은 미결(`module-architecture.md` §10-3)이며, 아래 「개봉 규칙」은 Owner(김대원) 제안이다.

## 잠근 셋

| 영역 | manifest | 규모 | 버전 | 상태 |
| --- | --- | --- | --- | --- |
| 분류 (A tier) | `a_aihub_locked` | AI-Hub 시퀀스 120개, 유형별 30 | `lm1` / `lg1` · rule `s2` · seed 20261026 | **고정 (2026-10-26).** DEV `a_aihub` 120개를 시퀀스 단위로 빼고 뽑았다. 미개봉 |
| 후보 탐색 (C tier, 실제 장시간 영상) | — | — | — | **공백.** 팀원 원본으로 만드는 중 |
| 번호판 | — | — | — | **공백.** 미세조정 학습·m1/m2에 쓰지 않은 실제 이미지가 있는지 readout Owner에게 확인 중 |

재생성: `python -m eval.tools.sample_aihub --out a_aihub_locked --exclude-manifest a_aihub --split LOCKED --manifest-version lm1 --gt-version lg1 --per-type 30 --seed 20261026`

AI-Hub 시퀀스 번호가 이어져도 같은 주행이 아니다(연속 번호 한 쌍을 원본 프레임으로 확인 — 카메라 기종과 장소가 다르다). 그래서 시퀀스 단위 제외로 충분하다고 본다.

## DEV — 잠근 셋이 아니다

개발·모델 선택에 반복해 썼다. 여기서 나온 수치는 **DEV 결과**라고 쓰고 일반화 성능으로 부르지 않는다.

| manifest | 쓴 곳 |
| --- | --- |
| `b_youtube` (`m3` / `g3`) | 9/28 Coarse 베이스라인, #240 비교. 클립 123개 전부 `split: DEV` |
| `a_aihub` (`m1` / `g1`) | Classification 베이스라인 |
| `ab_mixed` (`am1`) | 위 둘에서 파생 |
| 번호판 m1 · m2 (비공개) | #215 미세조정 모델 선택 |
| `mock_pack` | 배관 확인용. 성능 근거가 아니다 |

## 개봉 규칙 — 제안

1. 제품 조합(모델·프롬프트·가중치·설정)과 RC SHA를 고정한 뒤에만 연다.
2. 연 뒤에는 그 결과를 보고 조합을 바꾸지 않는다. 바꿨다면 그 셋은 DEV로 내리고, 새 조합의 수치는 DEV 결과로 쓴다.
3. 열 때마다 아래 표에 한 줄을 남긴다. 같은 RC를 다시 돌린 것도 한 번으로 센다.

## 개봉 기록

| 날짜 | manifest · GT | 구현(`--impl`) | RC SHA | run_id | 실행자 | 비고 |
| --- | --- | --- | --- | --- | --- | --- |
