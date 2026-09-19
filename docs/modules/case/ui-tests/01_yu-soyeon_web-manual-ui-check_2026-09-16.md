# case 주관 UI 수동 테스트 보고서 — 1회차

> **작성일 2026-09-16 · 작성 담당 유소연(`case`) · 문서 성격: `apps/web` 수동 UI 점검 결과 기록(비정기, 필요 시 회차 누적).**
> 이 문서는 1차 Mock Merge 통합(`develop`, PR #62) 반영 직후 `apps/web`을 로컬에서 직접 띄워 시나리오별 화면 전환·표시값을 눈으로 확인한 결과를 기록한다. `pytest`/`vitest`/`tsc` 등 자동화 검증(→ `docs/mock/04_mock_validation_report.md`)과는 별도 축이며, "코드가 안 깨진다"가 아니라 "화면이 의도대로 보인다"를 확인하는 것이 목적이다.
> 근거: `apps/web/src/state/selectScreen.ts`(stage→화면 매핑 로직) · `apps/web/src/contracts/fixtures.ts`(스냅샷 로더/파싱 검증) · `docs/product/core-user-flow.md` §4 · `docs/architecture/contracts/adr/adr-location-absent-package.md`(ADR-EVIDENCE-003) · `docs/modules/case/checklists/phase1-completion-checklist.md`.

---

## 1. 테스트 방법

- 실행: 리포 루트에서 `npm install` → `npm run dev:web` (Vite dev server), 브라우저로 로컬 주소 접속.
- 데이터: 별도 mock 서버 없음 — `apps/web/src/contracts/fixtures.ts`가 `data/mock/case/*.json`을 `import.meta.glob`으로 직접 로드. 화면 상단 버튼 1개 = 시나리오 파일의 `case_views[]` 스냅샷 1개.
- 기준 브랜치: `develop` (1차 Mock Merge 통합 PR #62 반영 이후).
- 점검 포인트: 아래 6개 항목을 시나리오별로 순서대로 확인.
  1. meta bar의 "스냅샷 N건 파싱 OK" 여부(0건 이상이면 즉시 문제)
  2. 시나리오 버튼 전환 시 case_id/rev 갱신 여부
  3. `stage` → 화면 종류 매핑이 `selectScreen.ts` 로직과 일치하는지
  4. `unknown_abstain_partial` 등 WARN/ABSTAIN이 있어도 화면이 죽지 않는지
  5. `correction_rerun` 전후로 correction 대상 필드만 바뀌고 나머지는 유지되는지
  6. 액션 버튼 클릭 시 "발주 경로 미연결" 안내가 계약대로 설명되는지 / `infra_failure` 재시도 흐름에서 job 목록이 중복 없이 대표 1건만 남는지

## 2. 결과 요약

| 항목 | 결과 |
| --- | --- |
| meta bar 파싱 | 스냅샷 16건 파싱 OK, 문제 0건 |
| stage → 화면 매핑 | 확인한 모든 스냅샷에서 `selectScreen.ts` 로직과 일치 |
| 발견된 버그 | 없음 |
| 워딩 관찰 1건 | `infra_failure` "부분 완료" 상태의 notice 문구가 INFO 심각도인데 "~가 중단됐습니다"로 다소 실패처럼 읽힘(§4 참고) |

## 3. 시나리오별 상세

### 3-1. `correction_rerun`

- `EVIDENCE_REVIEW`(evidence 있음) 스냅샷 #1→#2 전환 시, WARN "사건 시각을 확인해 주세요"(시각 직접입력) → 정정 후 INFO "촬영 후 찍힌 시각이라 확인이 필요합니다"(신고용 영상 만들기)로 갱신. **확인한 내용 중 발생 시각만 바뀌고 나머지 필드는 유지** — correction 반영 범위가 대상 필드로 한정된다는 설계와 일치.
- `CANDIDATE_REVIEW`(후보 0건) → NO_RESULT 화면. 액션 버튼 2종 구분 확인:
  - "설명 고치기"(`EDIT_HINT`) — "발주 없음 — 검색 단서 입력, 다음 재검색의 입력이 된다"
  - "다시 찾기"(`RETRY_SEARCH`) — "JobRecord 발주 — kind=COARSE_SEARCH · force_rerun=false"
  - 힌트 수정 자체는 job을 발주하지 않고, 재검색만 실제 발주로 이어진다는 구분이 화면에 그대로 드러남 — 정상.
- `SEARCHING` → PROGRESS 화면 정상.
- `READY`(package 있음) → HANDOFF 화면 정상.

### 3-2. `infra_failure` (4회 재시도)

- `EVIDENCE_REVIEW`(evidence 조립 전) + 번호판 판독 "진행 중": 진행 상태 목록과 진행 중인 작업(`job_x001_plate`) 항목이 서로 일치해 "결과 아직 없음 · 진행 중"임이 명확함.
- `EVIDENCE_REVIEW`(evidence 조립 전) + 번호판 판독 "실패": ERROR "번호판 판독에 실패했습니다" + "번호판 다시 읽기"(`RETRY_PLATE_READ`, "새 job_id로 번호판 재판독 발주"). notice severity(ERROR)와 progress 상태(실패)가 일치.
- `EVIDENCE_REVIEW`(evidence 조립 전) + 번호판 판독 "부분 완료" (2개 스냅샷): notice severity가 INFO("번호판 판독이 중단됐습니다")로, ERROR/WARN이 아님 — 코드 동작 자체는 상태값과 일치하지만, **문구가 "중단됐습니다"라 실패로 오인될 여지 있음(워딩 검토 후보, §4).**
- 이후 `EVIDENCE_REVIEW`(evidence 있음) 2개 스냅샷에서 번호판이 "알 수 없음" → "17나2867"로 실제 해소되는 회복 과정 확인. WARN(번호판 미확정) → INFO(신고용 영상 미생성)로 notice가 단계에 맞게 전환됨.
- `CANDIDATE_REVIEW`(후보 1건) → CANDIDATES 화면 정상.
- **결론: 4회 재시도 전 구간에서 화면 크래시·job 중복 표시 없음.**

### 3-3. `unknown_abstain_partial`

- `EVIDENCE_REVIEW`(evidence 있음): WARN 2건(시각 단서 상이, 상황 미확인) + INFO 2건(화면 시각 없음, 촬영 후 시각) 동시 표시. 차량번호/발생시각은 확인됨, 발생장소/사건분류는 "알 수 없음"·"확인 필요"로 정직하게 표시 — 화면이 값을 임의로 채우지 않음.
- `READY`(package 있음)까지 진행해도 동일한 WARN/INFO 4건이 유지되고, "확인 필요 4건" · 신고요건=확인 필요 · 자료완성=확인 필요 · 사용자확인=미완료가 함께 표시됨. **이는 버그가 아니라 의도된 동작:**
  - `stage=READY`는 "package 조립 완료"를 뜻할 뿐 "사람 검토 불필요"를 뜻하지 않음 — HandoffScreen 자체가 제출 전 최종 확인을 위한 화면.
  - 완료기준 §17 "UNKNOWN/ABSTAIN/부분실패가 Case 전체를 깨지 않는다"를 실제로 만족시키는 장면.
  - 발생장소가 READY까지 "알 수 없음"으로 유지되는 것도 `ADR-EVIDENCE-003`(위치 없는 사건의 ReportPackage 발행 허용)과 일치.

## 4. 관찰 사항 (버그 아님, 검토 후보)

1. `infra_failure`의 "부분 완료" progress 상태에 연결된 notice 문구가 "~가 중단됐습니다"로, severity=INFO와 달리 사용자에게 실패처럼 읽힐 수 있음. web 담당(신유민)과 문구 조정 검토 필요.
2. (별건) `apps/web/README.md`가 아직 "코드도 package.json도 없다"는 병합 이전 문구를 유지하고 있음 — web merge(Step 6) 반영 후 갱신 필요.

## 5. 다음 회차 예정

- 본 문서는 case 주관 반복 점검용으로, 이후 회차는 같은 폴더(`docs/modules/case/ui-tests/`)에 `NN_yu-soyeon_<주제>_<날짜>.md` 형식으로 누적한다.
- 다음 회차 후보: Mock→Real 전환(W5) 1차 모듈 교체 직후 회귀 확인.
