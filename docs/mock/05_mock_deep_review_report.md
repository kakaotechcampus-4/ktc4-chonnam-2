# Mock Dataset Deep Review Report

> 검토일 2026-09-08 · 대상 브랜치 `mock-pack-v2` (base `origin/develop` @ `8fc0ced`)
> **검토 시점에는 어떤 Mock 파일도 수정하지 않았다.** 이 문서만 새로 추가했다.

> **수정 진행 상황 (2026-09-08, 검토 이후 1차 수정 반영).** Owner 답변이 필요 없는 항목만 먼저 처리했다.
>
> - ✅ **해소** — P0-1(사건 유형 4종 교체) · P0-2(`VisualEvidence` 필수 필드) · P1-4(off-by-one) · P1-5(overlay offset 좌표계·sample_count) · P1-8(`manifest_summary.range`) · P1-1(happy에서 purge 분리) · P2-6(정정 전 CaseView 스냅샷) · P2-5(empty 시나리오 recording fixture) · P2-7(문서 수치·스크립트 절대경로) · P2-8(opaque ref 문서화) · P2-9(`processed_duration`) · P1-9 일부(처리중·`user_reviewed=true` 스냅샷 추가) · P1-11 일부(오답 fixture의 `actual_ref` 제거) · §13-1·14(검증 규칙 대폭 강화)
> - ⏳ **Owner 답변 대기** — **P0-3**(`VISUAL_VERIFY` run) · **P0-4**(「화면 시각 없음」 모델링) · P1-2 · P1-3 · P1-6 · P1-7 · P1-10 · P1-12 · P2-2 · P2-3 · P2-4 · P3-1 · P1-9 나머지(`BLOCK`·`INFO_AI_ESTIMATED`)
> - 📌 **의도적으로 보류** — **P1-7/item 8**(`ve_u001` → `UNCERTAIN`): 실행하려다 새 문제를 발견했다. `EvidenceRecord.event.*`는 계약 스키마에서 `?` 표시가 없어 **필수**로 보이는데, `verification=UNCERTAIN`이면 `visual_event_type`을 확정할 수 없다. 「VisualEvidence가 UNCERTAIN일 때 EvidenceRecord를 아예 만들지 않는가, 아니면 event를 비운 채 만드는가」가 계약에 없다 — §12에 김준영·서어진 확인 항목으로 추가했다.
> - 갱신된 커버리지 표와 강화된 검증 항목은 `04_mock_validation_report.md`에 반영했다.

> **수정 진행 상황 (2026-09-09, case Owner 유소연 2차 검수 반영).** §12에서 유소연에게 넘겨졌던 case 담당 항목 4건을 전부 결정·반영했다.
>
> - ✅ **결정·반영** — `JobRecord.kind`에 `FINE_VERIFY`·`REPORT_VIDEO_EXPORT` 등재(+`purge_case`는 Job 밖 관리 동작으로 확정) · u001 `scope_u001`을 timeline과 일치하도록 `22:10~22:40`으로 축소(P1-8 잔여 종결) · `evidence.review_needed` OR 파생 규칙 확정 및 계약 문서 등재 · **P1-13(신규 발견·즉시 해소)**: `CaseView.requirements_*.checks[]`에 누락돼 있던 `category`·`subject_refs`·`measurement`를 대응 `evidence/*.json`에서 그대로 복사
> - ⏳ **여전히 대기** — P0-3의 나머지(서어진의 `input_ref.kind` 결정 — case의 `JobRecord.kind` 등재는 끝났지만 실제 Fine Job/AnalysisRun 추가는 이 답변 이후 한 번에 진행), P3-1(예산 통화, 유소연+김준영 공동 — 이 시점엔 아직 미결. **2026-09-09 2라운드에서 이슈 #19 답변으로 환산 규칙은 종결, 기본값·fixture 반영만 잔여**)
> - 상세 근거는 §8 P0-3·P1-8·P1-9·P1-13, §12·§13 갱신분 참고. `validate_mock_pack.py` 재실행 PASS.

> **수정 진행 상황 (2026-09-09 2라운드, 팀 리뷰 이슈 #15~#19 5건 종합 반영 — Decider 유소연).** 5명 전원이 GitHub 이슈로 남긴 §12/§13 회신을 전부 읽고(이슈는 열려있는 상태로 진행, 닫는 것은 팀원 각자 몫으로 남김) 반영했다.
>
> - ✅ **결정·반영 완료** — P0-4(신유민: overlay 「없음」 = `NOT_APPLICABLE`, 결과 객체 생성) · P1-7(서어진: `ve_u001` → `UNCERTAIN`/`visual_event_type=null`) · P2-2(김준영: `plate_visible` → `category=VEHICLE`, `AssetFacts` 보강)
> - ✅ **결정 완료 · fixture는 다음 라운드** — P0-3(서어진: `input_ref.kind=analysis_source`) · P1-12 taxonomy(신유민, `scenario_infra_failure_001` 한정)
> - 🔀 **시나리오 분리(김준영 제안, 유소연 결정)** — P1-7을 실제로 적용하니 `EvidenceRecord.event`가 필수 필드라 `EvidenceRecord` 자체를 만들 수 없었고, 이것이 같은 시나리오 안의 C·D·G·I(번호판 abstain, 사건유형 confirmed 전제)와 충돌했다. `scenario_unknown_abstain_partial_001`(E·H)과 신규 `scenario_plate_reread_001`(C·D·G·I)로 분리 — 시나리오 5개, fixture 36개.
> - 🆕 **신규 Contract Gap 발견** — `EvidenceNeeds`(v1)가 "AI가 사건 유형 자체를 확정하지 못했다"는 상황을 표현할 계약상 메커니즘이 없다. 새 계약/필드가 필요할 수 있어 case Owner 단독으로 해소하지 않고 `04_mock_validation_report.md` §3.1-4·`CONTRACT_CONFLICTS.md`에 기록했다 — evidence(김준영)/PM 확인 필요.
> - ⚠️ **이 라운드가 만든 신규 갭** — P0-4 재정의로 pack에서 유일했던 `ReadoutRun.outcome=FAILED`/`JobExecution.status=FAILED` 예시가 사라졌다(§1 Coverage 표에 기록). 완전 실패 규칙 자체는 여전히 유효하나 현재 fixture 증거가 없다 — `scenario_infra_failure_001`(§13-9)이 채워야 한다.
> - ⏳ **여전히 대기** — P1-2 실질 미해소(source.kind 5종 자체는 승인됐으나 `safety_report_type` 값 공간은 반려) · P1-6(김준영: 좌표 규칙은 결정됐으나 fixture 미구현 / 정철원: GPS 관찰 단위) · P1-10(정철원) · ~~P2-3·P2-4~~(2026-09-09 3라운드에서 해소) · P1-11/P2-9 finding 본문의 정확한 재작성(§13-19, 김대원 답변은 받았으나 텍스트 반영 전) · P3-1 기본값 결정·fixture 정규화(환산 규칙 자체는 이슈 #19로 종결) · **(신규) 김준영 §12-⑥ EvidenceNeeds 새 kind 신설 여부** — ~~P1-3~~은 이슈 #15로 완전 종결(직렬화 형식 mock 현행 유지 확인)
> - 상세 근거는 §8 P0-3·P0-4·P1-7·P1-12·P2-2, §12·§13 갱신분, `04_mock_validation_report.md` §3.1-4 참고. `validate_mock_pack.py` 재실행 PASS(36개 파일·5개 시나리오).

> **수정 진행 상황 (2026-09-09 3라운드, 이슈 #15~#19 전량 원문 재대조 — 사용자 신뢰 회복 요청에 따른 전면 재검증).** 2라운드에서 일부 답변(김준영 ①④, P3-1, P1-3)을 잘못 요약해 사용자가 정확성을 재확인 요청했다. 이에 5개 이슈 전문(코멘트 포함)을 다시 curl로 원문 그대로 가져와 대조했고, 1·2라운드가 놓쳤거나 뭉뚱그린 내용을 찾아냈다.
>
> - ✅ **fixture 반영 완료** — 신유민 B-1(`scenario_plate_reread_001` 프레임 불일치 2자리로 확장) · 신유민 taxonomy 정밀화(`readout.overlay_not_present`→`readout.overlay.not_present` 점 표기 통일, `validation.*_ok` false→null) · `scenario_correction_rerun_001`의 "Overlay NOT_RUN(배열 부재)" 설계를 정철원 확인 정책(오버레이 무조건 디스패치)과 일치시켜 "실행됨+NOT_APPLICABLE"로 재구성(u001과 동일 패턴) · `scenario_plate_reread_001`에 `evidence.plate_abstained`/`MANUAL_PLATE_INPUT` notice 추가(신유민 2차 코멘트가 지적한 0건 커버리지 해소)
> - ✅ **문서만 정밀화(fixture 변경 없음, 근거 재작성)** — P1-11(eval 채점 모델 근본원인·metric 전체 개명표·`legibility` 필드) · P2-9(비용 분모의 3단 설명) · P1-12(readout taxonomy 정확한 코드 3종·`abstain_reason` 값공간/우선순위·화면문구 매핑표) · P1-10/GPS(정철원 확정 스키마·`scenario_relative_rebase_001` 전체 메커니즘)
> - ✅ **재확인(변경 없음)** — 번호판 placeholder "34나7890"이 이미 pack 전체(readout/case/evidence/scenario 설명)에 일관 적용돼 있음을 grep으로 재확인. 신유민이 자기 모듈에서만 제안한 "광주 12가 3456"은 로컬 제안이었고 실제로 반영된 적이 없어 supersede할 것도 없었다
> - 🆕 **신규 미결 항목 등록** — 신유민 2차 코멘트(web/CaseView 소비 분석)에서 `progress[].step`(2·3단계 대응 값 없음)·`progress[].state`(부분 완료/중단 미표현) 2건을 §12 유소연 항목으로 신규 등록(⑦⑧) — 아직 결정 안 됨
> - ⏳ **여전히 대기** — P1-6/GPS·`scenario_relative_rebase_001`·`scenario_infra_failure_001`·`scenario_blocked_001`은 규칙/설계는 전부 확정됐으나 fixture 빌드아웃은 다음 라운드 · `data/mock/expected/`(eval) 실제 재작성은 김대원 소관 · §12 유소연 신규 ⑦⑧ · notices 코드 대소문자(⑤)·actions 값공간(⑥)
> - 상세 근거는 §8 P1-11·P1-12·P2-9, §12 신유민/유소연/정철원/김대원 갱신분, §13 행 19~21 참고. `validate_mock_pack.py` 재실행 PASS(36개 파일·5개 시나리오, 파일 수 변동 없음 — 이번 라운드는 기존 5개 시나리오 내부 수정만).

> **수정 진행 상황 (2026-09-09 4차 라운드, "규칙은 종결·fixture는 다음 라운드"로 남아 있던 전 항목 실제 fixture화 — Decider 유소연).** 3라운드까지 도메인 판단은 끝났지만 실행이 밀려 있던 것들을 이번 라운드에서 전부 fixture로 반영했다. 팀원이 fixture를 직접 수정 → 재추합 → 검토 → 이슈 닫기 사이클을 반복할 것을 전제로, case Owner가 진행할 수 있는 범위의 "versioned artifact" 작업도 함께 처리했다.
>
> - ✅ **fixture 반영 완료** — **P0-3**(happy·u001·plate_reread·correction_rerun 4개 시나리오에 `VISUAL_VERIFY` run 추가, `ve_*.run_id` 재연결, `as_h001_fine` 고아 해소) · **P1-10**(신규 `scenario_relative_rebase_001`, 유형 K — `USABLE_RELATIVE_ONLY`·rebase·`SpanResolution PARTIAL`+`TIMELINE_GAP` 전부 실증, case 소유 `stale_revision` 필드 신설) · **P1-12 잔여**(신규 `scenario_infra_failure_001`, 유형 J — `JobExecution STALE`→재시도→`FAILED`, `ReadoutRun.outcome=FAILED`+`INFRA` taxonomy, pack 최초 `severity=ERROR`/`blocking=true` notice) · **P3-1 기본값**(환율 placeholder 1400원/$·`budget.max_cost_krw` 300→1000·전 시나리오 `UsageRecord.cost` KRW 정규화)
> - ✅ **versioned artifact 문서화 완료(mock 권한 범위 내)** — evidence 소유 `source.kind` registry(P1-2, 승인된 5종만) · case 소유 budget KRW 정규화 규칙(P3-1) · case 소유 `stale_revision` 필드 결정(P1-10)
> - 🔶 **부분 반영 — coord까지, address는 미착수** — **P1-6/P2-1**: happy에 GPS 있음(`coord`, OBSERVED), u001에 GPS 없음(`UNKNOWN`) Observation을 recording에 추가하고 `location.coord`/`location_display.coord`까지 채웠다. 그러나 `address`는 김준영이 "versioned reverse-geocode artifact 없이 임의 생성 금지"라고 명시한 항목이라 **mock 작업 범위 밖**(실제 지오코딩 데이터가 필요) — `location_display.info_state`는 §7-(3) 규칙상 여전히 `INFO_NEEDS_REVIEW`이고, P2-1의 "happy가 완전 all-green"이라는 원래 목표는 그 artifact 없이는 달성 불가능하다.
> - ⏳ **여전히 실질적으로 열려 있음(mock이 임의로 채울 수 없음)** — `safety_report_type` 값 공간(김준영, 반려됨 — 실제 신고 규정 원본 필요) · `EvidenceNeeds` 신규 kind 신설 여부(김준영/PM 결정 대상) · `location.address`(reverse-geocode artifact 필요) · notices 코드 대소문자(⑤)·actions 값공간(⑥, 계약 자체 미확정) · `progress[].step`/`state` 어휘 확장(⑦⑧, case가 결정은 가능하나 이번 라운드 범위 밖으로 남김) · `scenario_blocked_001`(P1-9 나머지 — `BLOCK`/`INFO_AI_ESTIMATED`, 이번 라운드 범위 밖) · eval `expected/` 재작성(김대원 소관)
> - 상세 근거는 §8 P0-3·P1-6·P1-10·P2-1·P3-1 갱신분, §12·§13 갱신분 참고. `validate_mock_pack.py` 재실행 PASS(46개 파일·7개 시나리오).

> **수정 진행 상황 (2026-09-10 5차 라운드/v3, 이슈 #22·#23·#25·#26 전량 원문 재대조·반영 — Decider 유소연, mock pack v3 전체 owner).** 4차 라운드 이후 팀 5명이 올린 2차 검수 이슈(eval #22 · search #23 · evidence/common #25 · readout/web #26)를 전부 원문 그대로 가져와 대조했고, case 소유 여부와 무관하게 mock pack 전체 owner로서 fixture-actionable 항목을 전부 반영했다.
>
> - ✅ **fixture·계약 반영 완료** — `situation_confirmation`·`package.unconfirmed_fields` 신설 및 EVIDENCE/FINAL_PACKAGE WARN→`stage=READY` 경로 실증(#25) · `EvidenceNeeds.event.visual_event_type.value=null` 제한 허용으로 "사건 유형 자체 미확정" 표현(#25, §12 김준영-⑥ 종결) · `notices[].code` dotted-lowercase + `time.*` 접두어 폐기 + `actions[]` 5종 닫음(#26 A) · `REPORT_VIDEO_EXPORT_FAILED`→`notices[].code` 매핑 정정(#26) · 「1 execution : ReadoutRun 1건」 STALE 예외를 `contract-job-record-case-view.md`·`contract-job-execution.md` 양쪽에 등재(#26) · overlay `UNKNOWN` 갈래 신설(#26 B-readout-4) · `review_needed` OR 공식에 `info_state==NEEDS_REVIEW` 포함(#26 B-web-6) · 「대표 execution = attempt 최댓값」+ STALE 억제 정책(#26 B-web-7) · `candidates[].stale_revision_label_key` 신설(#26 B-web-8) · `plate_reread_001` 중복 notice 제거(#26 B-web-9) · `contract-visual-evidence.md` stale 예시 정정(#23 A) · search `usage_summary` KRW 정규화(#23 B-1) · eval 참값 라벨 2건 확정 + STALE attempt `UsageRecord` 컨벤션(#22 B-3·B-4)
> - 🚫 **반려** — `AnalysisRun.input_ref.kind=ANALYSIS_SCOPE`→`analysis_scope` 소문자 통일 제안(#23 B-3) — 이미 확정된 ADR(`adr-data-contract-call-closure-2026-09-08` §6)과 충돌해서 반려, 서어진에게 회신 필요(`CONTRACT_CONFLICTS.md`).
> - 🔶 **provisional(recording Owner 확인 대기)** — u001 `derived_assets`(report video·plate image)·`scenario_infra_failure_001`의 신규 `incident_clips` — 값은 기존 패턴에서 비례 산정, 정철원 확인 전까지 잠정.
> - ⏳ **다른 Owner 답 대기, case가 대신 결정하지 않음** — `CandidateEvent.span` 폭이 coarse 창인지 사건 구간인지(#22 B-2, 서어진) · Fine 단계 `AnalysisRun.input_ref` vs `VisualEvidence.input_ref` 자산 종류 불일치(#23 B-2, 서어진이 다음 라운드 전 결정 예정) · `contract-usage-record.md`에 STALE attempt 발행 규칙 정식 등재(#22 B-4, 김준영) · `EvidenceNeeds`/`safety_report_type` 계약 문구 정식화(evidence, 여전히 열려 있음)
> - ⏳ **여전히 열려 있음(이번 라운드도 범위 밖)** — `scenario_blocked_001` · `location.address` reverse-geocode artifact · `progress[].state="중단"`(대응 `JobExecution.status` 값 자체가 없어 김준영 확인 선행 필요, `CONTRACT_CONFLICTS.md` 항목 9)
> - ✅ **같은 날 후속 반영** — §12 유소연 ⑦(원래 갭 아니었음, `progress[]`는 AI job 전용이라 사용자 입력 단계는 대응 값이 없는 게 맞다는 근거를 계약에 명문화) · ⑧ 절반(`progress[].state=PARTIAL` 등재) · `timeline_revision`/`stale_revision`/`stale_revision_label_key`를 나머지 5개 시나리오(`empty`는 `candidates=[]`라 제외)에 backfill · **`plate_reread_001`의 "재판독 성공 후" 상태 완성**(위 줄에서는 "다음 라운드 예정"이라 적었던 항목 — 같은 날 안에 실제로 만들었다: `readout`에 성공한 재판독 `PlateReadout`/`ReadoutRun`, `common`에 `SUCCEEDED` `JobExecution`+`UsageRecord`, `evidence`에 `EvidenceRecord`(`ev_p001_v2`, `supersedes_ref` 체인)·`EvidenceNeeds`(충족)·`RequirementReport`(`UNKNOWN`→`PASS`), `case`에 `case_rev:4` `CaseView`(`EVIDENCE_SUFFICIENT=true`·`stage`는 여전히 `EVIDENCE_REVIEW`), `recording`에 재판독용 3번째 프레임(`fr_p001_plate3`). 이 커밋(mock-pack-v2-round2 브랜치, 해시 `e515f70`이 직전 5차 라운드분)의 다음 커밋으로 별도 반영했다 — 상세 `docs/mock/02_mock_scenario_catalog.md`의 `scenario_plate_reread_001` v3 노트, `docs/modules/case/decisions/eval-round2-ground-truth-and-usage.md` B-3 갱신분.
> - 상세 근거는 §12 전체 갱신분, `docs/mock/CONTRACT_CONFLICTS.md`, `docs/modules/case/decisions/generic-warn-package-and-situation-response.md`·`eval-round2-ground-truth-and-usage.md`·`candidate-stale-revision-display.md`(갱신)·`budget-krw-normalization.md`(갱신) 참고. `validate_mock_pack.py`·`check_contract_fixtures.py`·`check_boundaries.py` 재실행 전부 PASS(46개 파일·7개 시나리오, 파일 수 변동 없음 — 이번 라운드는 기존 7개 시나리오 내부 수정 + 계약/결정 문서만).

---

## 0. Executive Summary

**전체 평가: `통합 전 주요 수정 필요`**

| 등급 | 개수 |
| --- | ---: |
| P0 (Merge Blocker) | 4 |
| P1 (Merge 전 수정 권장) | 12 |
| P2 (품질 개선) | 9 |
| P3 (선택 개선) | 2 |

**가장 큰 위험 5개**

1. **제품 범위 밖 사건 유형이 3개 시나리오에 박혀 있다.** `SIGNAL_VIOLATION` · `ILLEGAL_PARKING` · `ILLEGAL_U_TURN`은 닫힌 `VisualEventType` enum(`SIGNAL` / `CENTER_LINE_CROSSING` / `SOLID_LINE_LANE_CHANGE` / `MOTORCYCLE_HELMET_NON_USE`)에도, 제품이 안내하는 지원 4종에도 없다. 이대로 통합하면 각 모듈이 지원하지 않는 사건 유형을 전제로 코드를 쓴다. (P0-1)
2. **`VisualEvidence` 3건 전부가 계약 필수 필드 2개(`uncertainties`, `legal_status`)를 빠뜨렸고**, 계약이 "Fine/Classification run이 생산한다"고 못박은 것을 `operation=CANDIDATE_SEARCH` run에 붙였다. pack 전체에 `VISUAL_VERIFY` run이 0건이라 Fine 경로가 통째로 미mock이다. (P0-2, P0-3)
3. **「화면 시각 없음」을 실행 실패로 모델링했다.** `core-user-flow.md` §5와 `readout/decisions/overlay-presence-detection.md`가 「없음(사실)」과 「확인 못함(UNKNOWN)」을 절대 합치지 말라고 명시했는데, mock은 `ReadoutRun.outcome=FAILED`로 만들어 관찰 객체 자체를 없앴다. web 문구 분기가 mock에서 재현 불가하다. (P0-4)
4. **web이 필요로 하는 상태의 큰 덩어리가 통째로 비어 있다.** `INFO_AI_ESTIMATED`(정보 상태 5종 중 1종), 처리중(`RUNNING`/`PENDING`/`INTAKE`/`SEARCHING`), `blocking=true` notice, `RequirementReport.overall=BLOCK`, `user_reviewed=true`, GPS/좌표가 있는 위치 — 어느 fixture에도 없다. (P1-9, P1-6)
5. **Eval fixture가 자기모순이고 프로젝트 metric 어휘를 쓰지 않는다.** 「의도적 오답」 fixture가 실재하는 `readout_h001_plate`를 가리키면서 그 값과 다른 `actual_value`를 적어, harness가 ref를 따라가면 오히려 정답이 나온다. metric 이름도 `Recall@K`/`Final Recall@3`/`HN-FPR`/`Abstention Recall`/`Wrong Accept Rate`가 아닌 창작 이름이다. (P1-11)

**Mock Merge 가능 여부: 현재 상태로는 불가.** P0 4건(특히 P0-1)은 잘못된 계약 해석을 그대로 각 모듈 코드에 심는다. P0 4건 + P1 중 참조/좌표계 관련 4건(P1-3, P1-4, P1-5, P1-8)만 처리하면 1차 Mock E2E 통합에 충분하다. 나머지 P1/P2는 통합과 병행 가능하다.

---

## 1. Review Scope

**읽은 것**

- Mock Pack 전체: `data/mock/` JSON 28개(모듈 fixture 21 + scenario manifest 4 + `manifest.json` + eval fixture 2), `data/mock/validate_mock_pack.py`, `scripts/build_artifact_templates_doc.py`, `docs/mock/01`~`04` + `CONTRACT_CONFLICTS.md`
- Final Data Contract: `contract-analysis-scope.md` · `contract-analysis-run-candidate-event.md` · `contract-visual-evidence.md` · `contract-plate-overlay-readout.md` · `contract-readout-run.md` · `contract-time-resolution.md` · `contract-evidence-record-needs.md` · `contract-requirement-report-package.md` · `contract-job-record-case-view.md` · `contract-job-execution.md` · `contract-usage-record.md` · `contract-source-asset-media-stream.md` · `contract-recording-timeline-asset-span.md` · `contract-analysis-source-derived.md` · `contract-observation.md`(부분) · `contract-correction-record.md`(Draft, 상태만)
- 모듈 문서: `modules/readout/decisions/failure-taxonomy.md` · `modules/readout/decisions/overlay-presence-detection.md` · `modules/eval/experiment-guide.md`(템플릿·metric 어휘) · `modules/eval/{contracts,datasets,metrics}/`(README stub 확인)
- 제품/운영: `product/core-user-flow.md` §3-1·§5·§9 · `management/ownership.md`

**충분히 읽지 못한 것 (판단 근거에서 제외했거나 "Upstream 확인 필요"로 표시)**

- `architecture/module-architecture.md` v4 전문 — 이번 검토에서는 각 계약 문서가 인용한 v4 절 번호를 통해 간접 확인만 했다. §7-1·§7-2·§7-4(Happy Path·판독 시점·후보 재선택)는 인용문 수준으로만 봤다.
- ADR 원문 전체 — 계약 문서 헤더/각주가 요약한 결정만 사용했다.
- `product/product-spec.md` 전문 — 지원 사건 4종은 `core-user-flow.md` §5의 서비스 범위 안내 문구와 `contract-analysis-scope.md` §7의 baseline enum으로 교차 확인했다.
- `modules/search/decisions/failure-taxonomy.md` — `AnalysisRun.issues[].kind` 값 검증에 필요하지만 이번 pack에 `issues`가 비어 있어 검증 대상이 없었다.

---

## 2. Mock Pack 구조 평가

**좋은 점 (유지 권장)**

- 모듈 디렉터리 × 시나리오 파일 1:1 배치는 추적이 쉽다. "이 시나리오에서 readout이 뭘 냈나"를 파일 하나로 답할 수 있다.
- `scenario_id`/`module`을 **파일 wrapper에만** 두고 계약 객체 안에는 넣지 않은 판단은 정확하다. 런타임 계약 오염이 없다.
- ID 접두어 규약(`sa_`/`fr_`/`tl_`/`candidate_`/`rr_`/`tres_`/`ev_`/`pkg_`/`exec_`/`usage_`)이 일관되고, scenario 접미(`h001`/`e001`/`u001`/`r001`)로 시나리오 소속이 즉시 보인다. 디버깅 비용이 낮다.
- `03_mock_artifact_templates.md`를 스크립트로 fixture에서 추출한 것은 문서-데이터 drift를 구조적으로 막는다. **이 패턴은 유지해야 한다.**
- 완전 정적 JSON이라 결정론적이다. 난수·현재시각·외부호출·사용자 PC 경로 의존이 fixture에는 없다.

**구조적 약점**

- `expected/`(eval)만 시나리오 트리 밖에 있고 manifest에서도 별도 취급인데, 그 안의 fixture가 `scenario_happy_001`의 런타임 ID를 직접 참조한다. 소속이 모호하다.
- `data/mock/validate_mock_pack.py`가 데이터 디렉터리 안에 있다. 데이터와 코드가 같은 트리에 섞여 있어 "fixture를 통째로 복사"하는 소비자가 코드까지 가져간다. (P3)
- `scripts/build_artifact_templates_doc.py`가 `ROOT = Path("/tmp/repo")`로 절대경로 하드코딩이라 실제 체크아웃에서 실행되지 않는다. (P2-7)
- 시나리오 manifest의 `shared_ids`가 fixture 값을 복사해 두는데 아무도 검증하지 않는다. drift 후보다. (P2-8)

---

## 3. Contract Coverage

| Contract | Normal | Empty | UNKNOWN | ABSTAIN | Partial | Failure | Coverage 평가 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `SourceAsset`/`MediaStream`/`FrameRef` | ✅ | N/A | ❌ `availability=UNKNOWN`/`UNAVAILABLE` 없음 | N/A | N/A | ❌ | 다소 부족 |
| `AssetFacts` | ✅ (2건) | N/A | ❌ | N/A | N/A | ❌ `lookup` 실패(UNKNOWN_REF/INVALID_REF_KIND) 없음 | 부족 — ASSET 판정 입력으로 쓰이는데 happy 1곳에만 있고 `plate_image`용은 없다 |
| `RecordingTimeline` | ✅ `USABLE` | N/A | ❌ | N/A | ❌ `PARTIAL`/`gaps≠[]` 없음 | ❌ `UNUSABLE` 없음 | 부족 — `USABLE_RELATIVE_ONLY`(relative-only 영상 정상 경로) 0건 |
| `TimeSourceCandidate` | ✅ | N/A | ❌ `observation_status≠OK` 없음 | N/A | N/A | N/A | 다소 부족 — 충돌 2건 케이스는 있음 |
| `SpanResolution` | ✅ `COMPLETE` | N/A | N/A | N/A | ❌ `PARTIAL`+`missing_ranges` 없음 | ❌ `FAILED`+`failure` 없음 | 부족 — 2026-09-08에 확정한 실패 직렬화가 전혀 검증 안 됨 |
| `AnalysisSource`/`RemoteCopy` | ✅ | N/A | N/A | N/A | N/A | ❌ | 다소 부족 — 게다가 어떤 run도 `as_h001_fine`를 소비하지 않는 고아 |
| `IncidentClip`/`DerivedAsset` | ✅ | N/A | N/A | N/A | N/A | ❌ export 실패(`REPORT_VIDEO_EXPORT_FAILED`) 없음 | 다소 부족 |
| `DeletionReport` | ❌ `COMPLETE` 없음 | N/A | N/A | N/A | ✅ `PARTIAL` | ❌ `FAILED`/`items[].FAILED` 없음 | 다소 부족 |
| `AnalysisScope` | ✅ `ABSOLUTE` | N/A | N/A | N/A | N/A | N/A | 다소 부족 — `TIMELINE_RELATIVE`(1.1.0 신규) 0건 |
| `AnalysisRun` | ✅ | ✅ `SUCCEEDED+candidates=[]` | N/A | N/A | ❌ `PARTIAL`+`issues[]` 없음 | ❌ `FAILED` 없음 | 다소 부족 |
| `CandidateEvent` | ✅ | ✅ | N/A | N/A | N/A | N/A | 부족 — 모든 시나리오가 후보 **1건**이라 `rank`/ordering/Recall@K를 검증할 수 없다 |
| `VisualEvidence` | ⚠️ 필수필드 누락 | N/A | ❌ `UNCERTAIN` 없음 | N/A | N/A | ❌ `NOT_OBSERVED`(hard-negative) 없음 | **부족 + 결함** — P0-2/P0-3 |
| `ReadoutRun` | ✅ | N/A | N/A | N/A | ❌ `PARTIAL` 없음 | ⚠️ `FAILED` 있으나 kind 미등록(P0-4) | 다소 부족 |
| `PlateReadout` | ✅ | N/A | ❌ `observation.status=UNKNOWN` 없음 | ✅ | N/A | N/A(완전실패면 미생성) | 충분 |
| `OverlayTimeReadout` | ✅ | N/A | ❌ | N/A | ❌ `validation.*_ok=false` 없음 | ⚠️ P0-4 | 부족 |
| `Observation<T>` (공용) | ✅ (readout 내부) | N/A | ❌ `status=UNKNOWN`+`reason.code` 없음 | N/A | N/A | ❌ `ERROR` 없음 | 부족 — **GPS Observation(`recording.gps_stream`) 0건** |
| `TimeResolution` | ✅ `OK` | N/A | ❌ `status=UNKNOWN` 없음 | N/A | ✅ `NEEDS_REVIEW`+`conflict` | N/A | 충분에 근접 |
| `EvidenceRecord` | ✅ | N/A | ✅ 필드 부재 표현 | N/A | ✅ supersede | N/A | 충분 |
| `EvidenceNeeds` | ✅ `items=[]` | ✅ | N/A | ✅ `PLATE_REREAD` | N/A | N/A | 충분 — `OVERLAY_TIME_OCR` need만 없음 |
| `RequirementReport` | ✅ `PASS` | N/A | ✅ `UNKNOWN` | N/A | ✅ `WARN` | ❌ **`BLOCK` 0건** | 다소 부족 |
| `ReportPackage` | ✅ | ✅ 미생성 | N/A | N/A | N/A | N/A | 충분 |
| `JobRecord` | ✅ | ✅ | N/A | N/A | ✅ `force_rerun` | N/A | 충분 — cache hit(동일 fingerprint 재사용) 미검증 |
| `JobExecution` | ✅ | ✅ | N/A | N/A | ✅ `QUEUED` | ✅ `FAILED` | 다소 부족 — `RUNNING`·`STALE`·`attempt≥2` 없음 |
| `UsageRecord` | ✅ | ✅ | N/A | N/A | N/A | ❌ `cost.amount=null` 없음 | 충분 |
| `CaseView` | ✅ `READY` | ✅ | ✅ | N/A | ✅ | ❌ blocking notice·`INTAKE`/`SEARCHING`·`RUNNING` 없음 | 부족 (P1-9) |
| `CorrectionRecord` (Draft) | N/A | N/A | N/A | N/A | N/A | N/A | 미생성 — Draft이므로 **정확한 판단** |

---

## 4. Scenario Coverage

| Scenario | 목적 | 품질 | 문제 | 개선 방향 |
| --- | --- | --- | --- | --- |
| `scenario_happy_001` | 전 구간 정상 관통 기준선 | 양호 | 위치가 `user_hint`뿐이라 대표 정상 경로인데 `location_display=INFO_NEEDS_REVIEW`. 삭제 리포트가 같은 스냅샷에 공존. `as_h001_fine`/`rc_h001_fine` 고아. `processed_duration_ms`가 scope와 불일치 | GPS 좌표 있는 위치로 올려 진짜 all-green 기준선으로 만들고, purge는 별도 시나리오로 분리 |
| `scenario_empty_001` | 빈 배열 ≠ 실패 | 보통 | 검증 가치는 명확하지만 recording fixture가 없어 E2E 재생 불가. `manifest_summary`가 어떤 fixture로도 뒷받침되지 않음. 사건 유형이 제품 범위 밖 | 최소 recording fixture 추가 + 유형 교체 |
| `scenario_unknown_abstain_partial_001` | 불확실성 6종 동시 | **가장 가치 높음, 그러나 결함 최다** | P0-1(유형), P0-4(overlay 실패 모델링), P1-4(off-by-one), P1-5(offset 좌표계), P1-8(manifest range). 한 시나리오에 6유형을 넣어 실패 원인 격리가 어려움 | 결함 수정 우선. 분할은 굳이 필요 없음(§9 참조) |
| `scenario_correction_rerun_001` | 사용자 정정 + supersede + NOT_RUN | 양호 | P0-1(유형), 정정 **전** CaseView 스냅샷 없음, `CorrectionRecord` opaque-only(이건 정확한 판단) | 정정 전/후 CaseView 2개로 |

**시나리오 간 차별성**: 4개 모두 서로 다른 코드 경로를 검증한다. **중복은 없다.** 오히려 부족한 쪽이다(§10).

**최소성**: `scenario_unknown_abstain_partial_001`이 6유형을 담당하는 것은 "시나리오 수를 늘리지 않는다"는 원래 지침과 맞고, 각 유형이 서로 다른 계약을 건드려 실제로 얽히지 않는다. **분할 권장하지 않는다.**

---

## 5. Cross-Artifact Consistency

### ID / Reference Graph

실제 그래프는 다음과 같이 하나로 연결된다(happy 기준). **끊긴 곳은 표시했다.**

```
case_h001
├─ job_h001_search ──▶ exec_h001_search ──▶ run_h001 (CANDIDATE_SEARCH)
│                         └─ usage_h001_coarse
│                      run_h001 ──▶ candidate_h001 ──▶ span{tl_h001 rev1, 300000–420000}
│                      run_h001 ──▶ ve_h001        ✗ 계약상 Fine(VISUAL_VERIFY) run이어야 함 (P0-3)
├─ job_h001_plate   ──▶ exec_h001_plate   ──▶ rr_h001_plate   ──▶ readout_h001_plate
├─ job_h001_overlay ──▶ exec_h001_overlay ──▶ rr_h001_overlay ──▶ readout_h001_overlay
├─ tres_h001 ◀─ readout_h001_overlay, tsc_h001_filename
├─ ev_h001 ◀─ ve_h001 + readout_h001_plate + tres_h001 + clip_h001
├─ req_h001_evidence / req_h001_final ◀─ ev_h001 (+ da_h001_report_video, da_h001_plate_image)
└─ pkg_h001 ◀─ ev_h001 + req_h001_final + da_*

고아(어떤 소비자도 참조하지 않음):
  as_h001_fine ──▶ rc_h001_fine        ← Fine run이 없어서 소비처가 없다 (P0-3와 같은 뿌리)
```

- **orphan reference: 없음** (모든 `{kind,ref}`가 같은 시나리오 안에서 해석된다 — 검증 스크립트가 확인).
- **중복 ID: 없음.** 시나리오 간 ID 충돌도 없다(접미가 다름).
- **다른 시나리오 ID 참조: `expected/eval_fixture_wrong_001.json`이 유일한 예외** — `scenario_happy_001`의 ID를 참조하면서 실재하지 않는 `candidate_h001_decoy`도 함께 쓴다 (P1-11).
- **값 복사 vs 참조**: `CaseView.package.report_fields`와 `ReportPackage.report_inputs`는 계약이 의도한 snapshot이므로 정상. `eval_fixture_correct_001`의 `actual_value` 복사는 drift 위험 (P2-6).

### 시간축

happy·u001·r001 모두 **timeline anchor + offset = 절대시각** 계산이 정확히 맞는다. 검토 중 가장 잘 만들어진 부분이다.

| 시나리오 | anchor | offset | 계산값 | fixture 값 | 판정 |
| --- | --- | --- | --- | --- | --- |
| happy | 18:00:00 | 312.48s (representative) | 18:05:12.48 | overlay 18:05:12 / occurred_at 18:05:12 | ✅ (OCR 초 단위 절삭) |
| u001 | 22:10:00 | 615.0s | 22:20:15 | `source_offset_ms=615000` → 22:20:15 | ✅ |
| r001 | 13:00:00 | 930.0s | 13:15:30 | tres v1 13:15:30 | ✅ |

**frame이 candidate 구간 안에 있는지**: 전부 통과(happy 312.48/313.1/313.6 ∈ [300,420], u001 615.0/615.8 ∈ [600,660], r001 930.0/930.6 ∈ [900,960]).

**단위 혼용 문제 2건**:
- `OverlayTimeReadout.samples[].offset_sec` — 계약 예시는 clip 기준(2.0/3.0)인데 mock은 source 기준(313.1/313.6) (P1-5).
- `CaseView.manifest_summary.range` — 계약은 "전체 구간"인데 mock은 AnalysisScope 범위를 넣었다 (P1-8).

### Provenance

- `observability`(OBSERVED/INFERRED) 구분은 잘 되어 있다: 시각 관찰=OBSERVED, 유형 매핑/문구 생성=INFERRED. **consumer가 이걸 보고 다르게 동작할 수 있다.**
- 그러나 `source.kind` 5종을 계약 등재 없이 신설했다 (P1-2).
- `TimeResolution.considered[]`가 값의 계보를 잘 남기지만, happy에서 base anchor(18:00:00)를 event-time 후보처럼 나열해 5분 차이가 나는 것처럼 보인다 (P2-4).

### Version

- 각 객체의 `contract_version`은 대체로 정확하다. 예외: `SpanResolution` — 계약 헤더 각주는 "v1 → v1.1", §8.1 스키마 예시는 `span-resolution/v1.2`. mock은 v1.2를 따랐다. **계약 문서 자체가 불일치**(Upstream 확인 필요).
- `manifest.json`에 `mock_pack_version: 1.0.0` + `source_of_truth_commit`이 있다. 좋다. scenario manifest에는 버전이 없다 (P3).

---

## 6. E2E Flow Review

### Happy Path 추적 (`scenario_happy_001`)

```
입력(2파일, 전/후방 1200s)
→ recording : sa_h001_front/rear · ms_* · tl_h001 rev1(USABLE, anchor 18:00:00 ← tsc_h001_filename)
→ case      : job_h001_search(COARSE_SEARCH, scope_h001)
→ search    : run_h001 SUCCEEDED → candidate_h001 [300s,420s] rep 312.48s
              ve_h001  ✗ 같은 run에 매달림(P0-3), uncertainties/legal_status 누락(P0-2)
→ recording : clip_h001 = tl_h001[300,420] (source_provenance 완비 ✅)
→ case      : job_h001_plate / job_h001_overlay (별도 job_id ✅ 계약 §7 준수)
→ readout   : rr_h001_plate SUCCEEDED → readout_h001_plate (12가3456, abstain 없음)
              rr_h001_overlay SUCCEEDED → readout_h001_overlay (18:05:12, validation 전부 true)
              ✗ samples[].offset_sec가 clip 기준이 아니라 source 기준(P1-5), sample_count(3)≠len(2)
→ evidence  : tres_h001 status=OK/VERIFIED (검증 overlay → §4 조건 충족 ✅)
              ev_h001 : plate·occurred_at·event 3종 confirmed, location은 user_hint만 ✗(P2-1)
              req_h001_evidence PASS → req_h001_final PASS → pkg_h001
              ✗ plate_image용 AssetFacts 없이 ASSET check를 PASS로 단정(P2-2)
→ CaseView  : stage=READY, plate/time = INFO_SOURCE_VERIFIED ✅
              ✗ location_display = INFO_NEEDS_REVIEW인데 review_needed=false(P2-1)
→ web       : 모든 표시값 존재. 단 coord=null, INFO_AI_ESTIMATED 미등장(P1-6, P1-9)
→ recording : DeletionReport(8/25) ✗ 같은 스냅샷에 AVAILABLE 자산과 DELETED 결과 공존(P1-1)
```

**연결 자체는 끊긴 곳이 없다.** ID·시간·selection 모두 같은 사건을 가리킨다. 문제는 위 6개 지점의 의미 정합이다.

### 대표 Partial Path (`scenario_unknown_abstain_partial_001`)

```
run_u001 SUCCEEDED → candidate_u001(ranking 0.61, uncertainties 1건)
ve_u001 verification=OBSERVED ✗ RED_SIGNAL primitive가 UNCERTAIN(0.47)인데 OBSERVED로 단정 → 계약 §4-1상 UNCERTAIN이어야 함(P1-7)
rr_u001_plate SUCCEEDED + abstained=true ✅ (abstain은 실패가 아니다 — 계약 §9-5 정확히 준수)
rr_u001_overlay FAILED(NO_OVERLAY_PRESENT) ✗ 「없음」을 실패로 접었다(P0-4)
ev_u001 vehicle_number 필드 부재 ✅ (null/placeholder 안 만든 것 정확)
needs_u001 PLATE_REREAD optional=false → job_u001_plate_reread(kind=PLATE_READ, force_rerun=true, 새 job_id) ✅ 계약 §7 재판독 규칙 정확 준수
req_u001_evidence overall=UNKNOWN ✅ BLOCK과 구분 정확
report_packages=[] ✅ ready-only 규칙 정확
```

**이 경로의 orchestration 부분(abstain → Needs → 자동 재발주 → QUEUED execution)은 계약을 정확히 구현했다.** 각 Owner가 다시 볼 필요가 거의 없는 수준이다.

---

## 7. Module별 검토

### recording (정철원)
계약 준수도가 가장 높다. `contract`/`contract_version` 필수 필드, `availability=AVAILABLE ⇒ byte_size non-null`, `duration/timeline_range` 쌍 규칙, `lineage` 평탄화, `PENDING_EXPIRY` 의미까지 정확하다. 남는 것: 삭제 스냅샷 공존(P1-1), `SpanResolution` 실패 직렬화·`gaps`·`USABLE_RELATIVE_ONLY`·rebase 미커버(P1-10), GPS Observation 부재(P1-6). **Owner가 볼 것은 §12의 2건뿐이다.**

### search (서어진)
`AnalysisRun`/`CandidateEvent` 직렬화는 정확하다(nested `{analysis_run, candidates}`, `timeline_revision`, `SUCCEEDED+candidates=[]`). 반면 `VisualEvidence`는 3건 모두 필수 필드 누락 + Fine run 부재 + 형식 불일치로 **이 모듈이 가장 많은 수정을 필요로 한다**(P0-2, P0-3, P1-3, P1-7). 후보가 항상 1건이라 `rank`/Recall@K 검증이 불가능한 것도 search·eval 공통 손실이다.

### readout (신유민)
`PlateReadout`의 abstain 표현(`abstained=true` + `observation.status=NEEDS_REVIEW` + `abstain_reason` authoritative, `reason.code` 미중복)은 계약 의도대로다. 문제는 overlay 「없음」 모델링(P0-4), `failure.kind` 미등록 값, `disagree_positions` off-by-one(P1-4), `samples[].offset_sec` 좌표계(P1-5), `sample_count` 불일치.

### evidence (김준영)
`EvidenceRecord`의 "확정 못한 값은 필드 부재", `EvidenceValue.needs_review`/`user_corrected` 상호배타, supersede 체인, `RequirementReport` precedence(BLOCK>UNKNOWN>WARN>PASS), ready-only `ReportPackage` — 전부 정확하다. 남는 것: 미등록 `source.kind` 신설(P1-2), ASSET 판정 입력 누락과 category 배치(P2-2), `BLOCK` 0건(P1-9), `safety_report_type` 값 공간 미확정(기존 보고서에 기재됨).

### case (유소연)
`JobRecord` append-only·별도 job_id·재판독 `force_rerun=true`·`case_rev` 증가, `CaseView`의 `info_state` 파생 규칙 적용이 계약과 정확히 일치한다. 남는 것: `manifest_summary.range` 의미 오해(P1-8), 처리중/차단 상태 미커버(P1-9), `review_needed` 파생 규칙 미확정(기존 보고서에 기재됨).

### web (신유민)
소비 관점에서 **현재 pack으로는 화면을 다 그릴 수 없다.** `INFO_AI_ESTIMATED`, 처리중, blocking notice, 좌표 표시, `user_reviewed=true` 이후 handoff 화면에 해당하는 fixture가 없다(P1-9, P1-6). 반대로 `CaseView`가 UI에서 도메인 규칙을 재계산하게 만드는 지점은 **없다** — safe projection 경계는 잘 지켜졌다.

### eval (김대원)
`expected/`를 분리하고 provisional임을 표시한 판단은 옳다. 그러나 fixture 내용이 자기모순이고(P1-11) metric 어휘가 프로젝트 문서와 다르며, hard-negative(`NOT_OBSERVED`)·후보 다건·`PARTIAL` run이 없어 `HN-FPR`·`Recall@K`·`Final Recall@3`·`FP-hour`를 검증할 입력이 없다.

---

## 8. Priority Findings

### P0

---

## `[P0-1] ✅ 해소 — 제품 지원 범위 밖 사건 유형이 3개 시나리오에 사용됨`

**관련 파일:** `data/mock/search/scenario_empty_001.json` · `search/scenario_unknown_abstain_partial_001.json` · `search/scenario_correction_rerun_001.json` · `evidence/scenario_unknown_abstain_partial_001.json` · `evidence/scenario_correction_rerun_001.json` · `case/scenario_unknown_abstain_partial_001.json` · `case/scenario_correction_rerun_001.json` · `docs/mock/02_mock_scenario_catalog.md` · `data/mock/scenarios/scenario_{empty,unknown_abstain_partial,correction_rerun}_001.json`
**Scenario:** `scenario_empty_001`, `scenario_unknown_abstain_partial_001`, `scenario_correction_rerun_001`
**관련 Contract:** `AnalysisScope`(target_event_types) · `CandidateEvent`(event_type_hint) · `VisualEvidence`(visual_event_type) · `EvidenceRecord`(event.visual_event_type)
**관련 Module:** search, evidence, case, eval

### 현재 상태
- `scenario_empty_001`: `target_event_types: ["ILLEGAL_U_TURN"]`
- `scenario_unknown_abstain_partial_001`: `["SIGNAL_VIOLATION"]`, `event_type_hint="SIGNAL_VIOLATION"`, `visual_event_type="SIGNAL_VIOLATION"`, `safety_report_type="UNSAFE_SIGNAL_VIOLATION"`
- `scenario_correction_rerun_001`: `["ILLEGAL_PARKING"]`, `visual_event_type="ILLEGAL_PARKING"`, `safety_report_type="UNSAFE_SIDEWALK_PARKING"`

### 왜 문제인가
지원 4종이 아닌 유형을 전제로 각 모듈이 분기·프롬프트·정답지·화면 라벨을 만들게 된다. `eval`은 "4종별 점수를 따로 내는 결과 형식"을 만들어야 하는데 mock의 3/4 시나리오가 4종 밖이라 그대로 쓰면 분류 버킷이 깨진다. 불법주정차·유턴은 촬영자 차량이 정지 상태를 관측해야 하는 등 파이프라인 전제도 다르다.

### 근거
- `contract-analysis-scope.md` §7: "v4 baseline enum은 `SIGNAL / CENTER_LINE_CROSSING / SOLID_LINE_LANE_CHANGE / MOTORCYCLE_HELMET_NON_USE`로 고정한다. 신규 유형 추가 시 계약 enum을 갱신한다."
- `contract-visual-evidence.md` §4-2: 같은 4종만 v1.0 지원 범위.
- `product/core-user-flow.md` §5 서비스 범위 안내: 신호위반 · 중앙선 침범 · 진로변경 · 이륜차 안전모 미착용.

### 권장 수정
등록된 4종으로 교체하되 **시나리오의 검증 의도는 유지**한다.
- `scenario_unknown_abstain_partial_001`: `SIGNAL_VIOLATION` → **`SIGNAL`** (전 파일 일괄; `safety_report_type`도 `UNSAFE_SIGNAL_VIOLATION` → 신고유형 값 공간 확정 전까지는 기존 placeholder 규칙 유지하되 코드명을 `SIGNAL` 기반으로 맞출 것). primitive `RED_SIGNAL`, temporal fact `TARGET_CROSSES_STOP_LINE`은 그대로 두면 된다.
- `scenario_empty_001`: `ILLEGAL_U_TURN` → **`CENTER_LINE_CROSSING`**, hint 문구를 "중앙선을 넘은 것 같은데 확실하지 않음" 류로 교체.
- `scenario_correction_rerun_001`: `ILLEGAL_PARKING` → **`MOTORCYCLE_HELMET_NON_USE`** 로 교체하는 것을 권장한다(4종 중 유일하게 어느 시나리오에도 없고, `temporal_facts=[]`가 정상인 object-attribute 사건이라 `VisualEvidence` §7의 "빈 배열 정상" 경로까지 동시에 커버한다). 이 경우 `ve_r001.temporal_facts=[]`, primitive는 `HELMET_ON_RIDER`/`state=ABSENT`, 차량 서술은 이륜차로, `violation_expression`도 함께 교체한다.
- `02_mock_scenario_catalog.md`와 각 scenario manifest의 서술 문구도 같이 갱신.

### 수정 범위
여러 Mock Artifact + Scenario Catalog + Manifest

### Owner 확인 필요 여부
`권장 — 수정 후 Owner sanity check` (교체 대상 값 자체는 계약이 닫아둔 목록이므로 기계적이나, `MOTORCYCLE_HELMET_NON_USE` 시나리오의 서사는 서어진·김준영이 한 번 볼 가치가 있다)

---

## `[P0-2] ✅ 해소 — VisualEvidence 3건 모두 계약 필수 필드 uncertainties·legal_status 누락`

**관련 파일:** `data/mock/search/scenario_happy_001.json` · `search/scenario_unknown_abstain_partial_001.json` · `search/scenario_correction_rerun_001.json`
**Scenario:** 전 시나리오(VisualEvidence가 있는 3개)
**관련 Contract:** `VisualEvidence` (`visual-evidence/v1.0`)
**관련 Module:** search (Producer), evidence · readout · eval (Consumer)

### 현재 상태
세 `visual_evidences[0]` 객체 모두 `schema_version` · `visual_evidence_id` · `run_id` · `input_ref` · `candidate_id` · `verification` · `visual_event_type` · `target` · `primitives` · `temporal_facts`만 있고 **`uncertainties`와 `legal_status` 키가 아예 없다.**

### 왜 문제인가
계약이 `legal_status`를 "반드시 존재하고 반드시 `null`. non-null은 Contract validation failure"로 규정한 것은, 이 필드의 **존재 자체가 「search는 법적 판정을 하지 않는다」는 경계를 코드 수준에서 강제하는 장치**이기 때문이다. 필드를 빼면 그 장치가 mock에서 사라진다. `uncertainties`도 "배열 자체는 항상 존재"이며 evidence/eval이 불확실성 진단에 쓰는 입력이다. 두 필드가 없는 fixture로 parser를 만들면 필수 키 누락을 정상으로 학습한다.

### 근거
`contract-visual-evidence.md` §3 Top-level 필드 정의: `uncertainties | Uncertainty[] | 필수 | 배열 자체는 항상 존재하며 빈 배열 가능`, `legal_status | null only | 필수 | 반드시 존재하고 반드시 null`.

### 권장 수정
세 파일의 각 VisualEvidence 객체에 다음을 추가한다.
- `"legal_status": null` (세 건 전부)
- `"uncertainties": []` — happy(`ve_h001`)와 correction(`ve_r001`)
- `ve_u001`은 빈 배열 대신 실제 불확실성을 채운다(§8 Uncertainty 구조 `{kind, detail, evidence_refs}`):
  `[{"kind":"SIGNAL_STATE_OCCLUDED","detail":"신호등이 앞 차량에 부분적으로 가려짐","evidence_refs":["fr_u001_plate1"]}]`
  — `CandidateEvent.uncertainties`(string[])와 **타입이 다르다.** 후보 쪽 `["SIGNAL_STATE_NOT_CLEARLY_VISIBLE"]`은 string[]이 맞으므로 그대로 둔다.

### 수정 범위
Fixture only

### Owner 확인 필요 여부
`불필요 — 기계적/명백한 문제` (단 `ve_u001`의 uncertainty `kind` 어휘는 search 소유라 §12에서 서어진에게 한 줄 확인)

---

## `[P0-3] ✅ 해소 — VisualEvidence가 CANDIDATE_SEARCH run에 매달려 있고, VISUAL_VERIFY run이 pack 전체에 0건`

> **2026-09-09 갱신 (팀 리뷰 이슈 #15, 서어진 답변).** 남아 있던 `input_ref.kind` 질문에 서어진이 답변해 도메인 판단이 전부 끝났다 — `analysis_source`(`as_h001_fine` 등)를 `input_ref.kind`로 사용하기로 확정, 고아 자산 문제도 함께 해소된다.
>
> **2026-09-09 4차 라운드 갱신 (fixture 반영).** happy·u001·plate_reread·correction_rerun 4개 시나리오 전부에 `operation:"VISUAL_VERIFY"` `AnalysisRun`(`run_*_fine`)을 추가하고 `VisualEvidence.run_id`를 그쪽으로 재연결했다. `input_ref={kind:"analysis_source", ref:"as_*_fine"}`이며, happy는 기존 고아 `as_h001_fine`/`rc_h001_fine`을 그대로 소비해 고아 문제도 함께 해소됐다. u001·plate_reread·correction_rerun은 동일 패턴으로 새 `AnalysisSource`/`RemoteCopy`를 recording fixture에 만들었다. `case/*.json`에 `kind:"FINE_VERIFY"` `JobRecord`, `common/*.json`에 대응 `JobExecution`+`UsageRecord`(KRW 정규화 비용, budget 여유분 안에서 산정)를 추가했다. `scenario_empty_001`은 애초에 `VisualEvidence`가 없어 대상에서 제외했다.

**관련 파일:** `data/mock/search/scenario_{happy,unknown_abstain_partial,correction_rerun}_001.json` · `data/mock/case/*` (Job 체인) · `data/mock/common/*` (execution·usage) · `data/mock/recording/scenario_happy_001.json`(고아 `as_h001_fine`/`rc_h001_fine`)
**Scenario:** 전 시나리오
**관련 Contract:** `AnalysisRun`(operation enum) · `VisualEvidence`(run_id) · `JobRecord`(kind) · `JobExecution`(produced) · `UsageRecord`(run_ref)
**관련 Module:** search, case, common/runtime, recording

### 현재 상태
- `ve_h001.run_id = "run_h001"`, `ve_u001.run_id = "run_u001"`, `ve_r001.run_id = "run_r001"` — 셋 다 `operation: "CANDIDATE_SEARCH"` 실행이다.
- pack 전체에 `operation: "VISUAL_VERIFY"`인 `AnalysisRun`이 없다.
- 그 결과 `as_h001_fine`(AnalysisSource, `profile_ref=prof_fine_v1`)와 `rc_h001_fine`(RemoteCopy)를 소비하는 실행이 없다 — 만들어졌지만 아무도 쓰지 않는 자산이다.

### 왜 문제인가
Coarse(후보 탐색)와 Fine(시각 검증)은 **비용·모델·실패 분류·재실행 단위가 전부 다른 실행**이다. 하나의 run에 두 결과를 매달면 `eval`의 `Fine Recall`·`Fine exposure`·`HN-FPR` 집계 단위가 무너지고, `case`는 "Fine만 다시 돌리기"를 mock으로 개발할 수 없다. 또한 Fine 실행이 없으면 `AnalysisSource`/`RemoteCopy` 준비→소비 흐름(recording↔search 접합부)이 mock에서 한 번도 재현되지 않는다.

### 근거
- `contract-analysis-run-candidate-event.md` §3: `operation | enum | 필수 | CANDIDATE_SEARCH | VISUAL_VERIFY`, §3-1 "`CANDIDATE_SEARCH`는 `AnalysisScope`를 참조한다. 다른 operation의 허용 input 종류는 해당 output Contract의 접합 규칙을 따른다."
- `contract-visual-evidence.md` §1·§3: "`search`의 **Fine / Classification** 분석 결과", `run_id | ref | 필수 | 결과를 생성한 **Fine / Classification** `AnalysisRun`".

### 권장 수정
각 시나리오에 `VISUAL_VERIFY` run을 하나씩 추가하고 VisualEvidence를 그쪽에 연결한다. happy 기준 구체안:
1. `search/scenario_happy_001.json`의 `analysis_run_candidate_events`에 두 번째 항목 추가:
   `analysis_run = {run_id:"run_h001_fine", operation:"VISUAL_VERIFY", input_ref:{kind:"incident_clip", ref:"clip_h001"}, implementation:{impl_id:"gemini-visual-verify@f3", model_ref:..., prompt_version:"fine-f3", config_version:"search-v2"}, outcome:"SUCCEEDED", started_at/completed_at(코스 종료 이후), issues:[], usage_refs:["usage_h001_fine"], usage_summary:{...}, contract_version:"analysis-run-candidate-event/v1.1"}`, `candidates: []`
   — **주의**: `input_ref.kind`를 무엇으로 둘지는 계약이 "해당 output Contract의 접합 규칙을 따른다"고만 하고 `VisualEvidence`도 형식을 확정하지 않았다(P1-3과 같은 뿌리). `incident_clip` 또는 `analysis_source`(`as_h001_fine`) 중 하나를 골라야 하며 **서어진·정철원 확인이 필요하다.** 확인 전까지는 `analysis_source`(`as_h001_fine`)를 쓰면 고아 자산 문제까지 함께 해소된다.
2. `ve_h001.run_id`를 `"run_h001_fine"`으로 변경.
3. `case/scenario_happy_001.json`에 Fine용 `JobRecord` 추가 — ~~단 `JobRecord.kind`에 Fine 발주용 값이 등재돼 있지 않다~~ **✅ 등재 완료(2026-09-09, 유소연): `kind="FINE_VERIFY"`, `label_key="job.fine_verify"`**(`contract-job-record-case-view.md` A절 §7·§12). case 쪽 blocker는 해소됐으나, 실제 `JobRecord`/`common` execution 추가는 아래 1의 `input_ref.kind` 답변(서어진) 이후 한 번에 진행한다 — 지금 case만 먼저 추가하면 실행 결과 없는 Job이 붕 뜬다.
4. `common/scenario_happy_001.json`에 `exec_h001_fine`(produced: `{kind:"analysis_run", ref:"run_h001_fine"}`)와 `usage_h001_fine` 추가. Job 발주 값이 미정이면 execution도 함께 보류하고 run/usage만 추가한다(`UsageRecord.execution_ref=null`은 계약상 허용).
5. u001·r001도 같은 방식으로 Fine run 추가.

### 수정 범위
여러 Mock Artifact + Upstream 확인 필요(`JobRecord.kind` 등재, `VISUAL_VERIFY.input_ref.kind`)

### Owner 확인 필요 여부
`필수 — 도메인 판단 필요` (서어진: Fine 입력 ref 종류 / ~~유소연: Fine 발주 `JobRecord.kind` 등재~~ → **종결(2026-09-09, 유소연)**, 남은 것은 서어진 답변뿐)

---

## `[P0-4] ✅ 해소 — 「화면 시각 없음」을 ReadoutRun 실패로 모델링해 제품이 요구한 상태 구분이 사라짐 (+ 미등록 failure.kind)`

> **2026-09-09 갱신 (팀 리뷰 이슈 #16, 신유민 답변 · case Owner 유소연 반영).** NOT_APPLICABLE(없음=사실) vs UNKNOWN(확인 못함) 판정 기준에 신유민이 「없음=사실」 쪽으로 답변해, 아래 "권장 수정"을 거의 그대로 반영했다. `rr_u001_overlay.outcome=SUCCEEDED`/`failure=null`, `overlay_time_readouts`에 `observation.status="NOT_APPLICABLE"` 결과 객체 추가, `JobExecution` SUCCEEDED로 정정, `CaseView.notices[]`에 `time.overlay_not_present`(INFO) 추가까지 전부 `scenario_unknown_abstain_partial_001` 재설계(§8) 과정에서 반영했다. 다만 이 재설계로 `ReadoutRun.outcome=FAILED`/`JobExecution.status=FAILED`의 fixture 실사례가 pack에서 완전히 사라졌다 — `04_mock_validation_report.md` §1에 신규 커버리지 갭으로 기록했다. 아래 "권장 수정" 6번(진짜 실행 실패 경로의 별도 시나리오)은 여전히 미착수다.
>
> **2026-09-09 3라운드 정정.** 최초 반영 시 `reason.code`를 밑줄 표기 `readout.overlay_not_present`로 잘못 썼다(아래 예시는 애초에 점 표기 `readout.overlay.not_present`였음). 신유민 이슈 #16 원문 재대조 과정에서 발견해 `scenario_unknown_abstain_partial_001`·`scenario_plate_reread_001`(해당 없음)·신규 `scenario_correction_rerun_001` overlay 결과 전부 점 표기로 통일했다. `validation.format_ok/monotonic_ok/duration_match_ok`도 신유민 지적대로 `false`(검증 시도했다가 실패)가 아니라 `null`(검증 자체를 시도 안 함)로 정정했다.

**관련 파일:** `data/mock/readout/scenario_unknown_abstain_partial_001.json` · `data/mock/common/scenario_unknown_abstain_partial_001.json` · `data/mock/evidence/scenario_unknown_abstain_partial_001.json` · `data/mock/case/scenario_unknown_abstain_partial_001.json`
**Scenario:** `scenario_unknown_abstain_partial_001`
**관련 Contract:** `ReadoutRun`(failure.kind) · `OverlayTimeReadout`(observation.status) · `Observation<T>` · `TimeResolution`(considered[]) · `CaseView`(notices)
**관련 Module:** readout, evidence, case, web

### 현재 상태
```
rr_u001_overlay : outcome=FAILED, failure={kind:"OVERLAY_DETECTION", code:"NO_OVERLAY_PRESENT"}
overlay_time_readouts: []              ← 관찰 객체가 아예 없음
JobExecution exec_u001_overlay: failure_kind="READOUT_OVERLAY_DETECTION"
TimeResolution tres_u001.considered[] : overlay 항목 없음
```

### 왜 문제인가
제품은 「화면에 시각이 없습니다」(**사실** → 파일 기록으로 계산한다고 안내)와 「확인하지 못했습니다」(**UNKNOWN** → 사용자가 직접 확인할 기회를 준다)를 다른 문구로 표시해야 한다. 지금 fixture는 둘을 "실행 실패" 하나로 접어버려서, web은 어떤 문구를 써야 하는지 mock에서 알 수 없고, evidence는 `considered[]`에 overlay를 남길 수도 없다. 게다가 `failure.kind="OVERLAY_DETECTION"`은 readout failure taxonomy에 없는 값이다(등재값: `PLATE_TARGET_ASSOCIATION` · `PLATE_DETECTION` · `PLATE_RECOGNITION` · `OVERLAY_VALIDATION` · `INFRA`). 계약이 "이 계약이 값을 추가하지 않는다"고 명시한 지점에서 mock이 값을 만들었다.

### 근거
- `product/core-user-flow.md` §5: "「화면에 시각이 없다」와 「확인하지 못했다」는 다른 말이다… **둘을 하나로 합쳐 「없음」이라고 쓰지 않는다.**"
- `modules/readout/decisions/overlay-presence-detection.md` 미결 #4: 두 상태 구분은 "readout 내부 최적화가 아니라 **화면 문구를 결정하는 항목**".
- `contract-plate-overlay-readout.md` §10: "Overlay의 `NOT_PRESENT`, `OCR_FAILED`, `VALIDATION_FAILED`는 공용 `Observation.status` enum이 아니라 readout 도메인의 reason/validation 결과다. 관찰 자체의 공용 상태는 `OK / NEEDS_REVIEW / UNKNOWN / ERROR / NOT_APPLICABLE`를 따른다." → 「없음」은 **결과 객체를 갖고** 그 안의 status/reason으로 표현되는 것이 계약의 구조다.
- `contract-readout-run.md` §6: `failure.kind` "값 집합과 확정 상태는 `modules/readout/decisions/failure-taxonomy.md`만 따른다."

### 권장 수정
`scenario_unknown_abstain_partial_001`을 **「overlay 자체가 없는 영상」**으로 바꾼다(현재 서사와 일치한다).
1. `rr_u001_overlay`: `outcome: "SUCCEEDED"`, `failure: null`로 변경. (판독 실행은 정상 수행됐고, 결과가 「없음」인 것이다.)
2. `overlay_time_readouts`에 결과 객체 1건 추가:
   ```
   readout_id: "readout_u001_overlay", run_ref:{kind:"readout_run", ref:"rr_u001_overlay"},
   case_id:"case_u001", candidate_id:"candidate_u001",
   input_ref:{incident_clip_ref:"clip_u001", source_profile:"readout-native", provenance:"SOURCE_DERIVED_INCIDENT_CLIP"},
   observation:{contract_version:"observation/v1", value:null, status:"NOT_APPLICABLE",
                source:{kind:"readout.overlay_ocr"}, support_refs:[],
                reason:{code:"readout.overlay.not_present"},
                produced_by:{module:"readout", run_ref:{kind:"readout_run", ref:"rr_u001_overlay"}}},
   validation:{format_ok:false, monotonic_ok:false, duration_match_ok:false, sample_count:0},
   samples: []
   ```
   `status`를 `NOT_APPLICABLE`(없다는 사실) 로 둘지 `UNKNOWN`(확인 못함)으로 둘지는 **두 상태를 구분하는 판정 기준이 readout Technical Spec 미결**이므로 신유민 확인이 필요하다. 위 안은 「없음=사실」쪽이다.
3. `JobExecution exec_u001_overlay`: `status: "SUCCEEDED"`, `failure_kind: null`로 변경.
4. `tres_u001.considered[]`에 overlay 항목 추가(`input_ref:{kind:"overlay_time_readout", ref:"readout_u001_overlay"}`, `value:null`, `observation_status:"NOT_APPLICABLE"`, `verification:"UNVERIFIED"`, `used:false`, `reason_code:"time.overlay_not_present"`). 이렇게 하면 「왜 파일명 시각을 썼는가」의 provenance가 완성된다.
5. `case/…`의 `progress`에서 `overlay_time_read` state를 `FAILED` → `DONE`으로, notices에 「화면 시각 없음」 안내 성격의 항목 추가 여부는 유소연 판단.
6. **별도로**, 진짜 실행 실패 경로(P1-12의 신규 시나리오 후보)에서 `failure.kind`를 taxonomy 등재값(`OVERLAY_VALIDATION` 또는 `INFRA`)으로 쓰는 fixture를 만든다.

### 수정 범위
여러 Mock Artifact + Upstream 확인 필요(NOT_APPLICABLE vs UNKNOWN 판정 기준)

### Owner 확인 필요 여부
`필수 — 도메인 판단 필요` (신유민)

---

### P1

---

## `[P1-1] 🔶 부분 해소(happy에서 분리 완료 · scenario_purge_001 신규 생성은 미완) — 같은 시나리오 스냅샷에 AVAILABLE 자산과 그 자산의 DELETED 결과가 공존`

**관련 파일:** `data/mock/recording/scenario_happy_001.json` · `data/mock/evidence/scenario_happy_001.json` · `data/mock/case/scenario_happy_001.json`
**Scenario:** `scenario_happy_001`
**관련 Contract:** `DeletionReport` · `DerivedAsset` · `AssetFacts` · `ReportPackage` · `CaseView`
**관련 Module:** recording, evidence, case

### 현재 상태
`derived_assets[da_h001_report_video].availability = "AVAILABLE"`, `asset_facts[…].availability="AVAILABLE"`(checked_at 8/24 19:10)인데 같은 파일의 `deletion_reports[0]`(8/25 09:00)은 `clip_h001`·`da_h001_report_video`를 `DELETED`로 보고한다. 동시에 `pkg_h001.assets.report_video_ref`와 `CaseView.package.artifact_ref`가 그 자산을 가리킨다.

### 왜 문제인가
소비자는 시나리오 파일을 **하나의 상태 스냅샷**으로 읽는다. 지금은 "패키지가 준비돼 있고 다운로드 가능"과 "이미 삭제됨"이 동시에 참이라, purge 이후 UI/보관 정책을 개발하는 쪽이 어느 쪽을 믿어야 할지 알 수 없다. `CaseView`에도 purge 이후 상태가 반영돼 있지 않다.

### 근거
`contract-analysis-source-derived.md` §8: `purge_case(case_id) -> DeletionReport`는 사건 종료 후 정리 동작이고, `AssetFacts.availability`는 `checked_at` 시점의 사실이다. 두 사실이 다른 시점을 가리키는데 파일에는 시점 구분 장치가 없다.

### 권장 수정
`deletion_reports`를 `scenario_happy_001`에서 **분리**해 별도 시나리오(예: `scenario_purge_001`)로 옮기고, 그 시나리오에서는 `derived_assets`/`asset_facts`의 `availability`를 `UNAVAILABLE`(+`byte_size: null` 허용 규칙 적용), `CaseView`를 purge 이후 상태로 맞춘다. happy는 "신고 준비 완료" 시점 하나만 표현하게 남긴다. 분리가 과하다고 판단되면, 최소한 happy의 `deletion_reports`를 제거하고 §10의 신규 시나리오 목록에 넣는다.

### 수정 범위
여러 Mock Artifact + Scenario Catalog + Manifest

### Owner 확인 필요 여부
`권장 — 수정 후 Owner sanity check` (정철원)

---

## `[P1-2] 🔶 부분 해소 — 계약에 등재되지 않은 source.kind 5종을 Mock이 신설하고 보고서에 기재하지 않음`

> **2026-09-09 4차 라운드 갱신 (fixture 변경 없음, 문서화).** 김준영이 승인한 5종을 `docs/modules/evidence/decisions/source-kind-registry.md`에 evidence 소유 versioned registry로 정식 등재했다(이슈 #19 "새 kind를 더 만들기 전에 evidence 소유 registry에 먼저 등재하라"는 요구 반영). fixture는 이미 이 형태로 쓰이고 있어 변경 없음. **`safety_report_type` 값 공간은 이 registry에 포함하지 않았다** — 김준영이 명시적으로 반려한 항목(placeholder일 뿐 canonical enum 아님)이라 evidence Owner의 후속 결정 없이 mock이 임의로 채울 수 없다. 그 부분만 여전히 미해소로 남긴다(registry 파일의 "아직 이 registry에 없는 것" 절에 명시).

**관련 파일:** `data/mock/evidence/scenario_happy_001.json` · `evidence/scenario_unknown_abstain_partial_001.json` · `evidence/scenario_correction_rerun_001.json`
**Scenario:** 전 evidence 시나리오
**관련 Contract:** `EvidenceRecord.EvidenceValue.source.kind` · `TimeResolution.resolved.source.kind` · `Observation.source.kind`
**관련 Module:** evidence, case, web

### 현재 상태
Mock이 사용하는 namespaced kind 중 계약 문서에 등장하는 것은 `search.visual_inference` · `readout.plate_ocr` · `readout.overlay_ocr` · `recording.filename_time` 4종이다. 나머지 5종 — `recording.file_metadata_time` · `case.user_location_hint` · `case.user_correction` · `evidence.category_mapping` · `evidence.violation_expression` — 은 어느 계약에도 없다. `case.*` 네임스페이스는 계약 전체에서 source kind로 쓰인 전례가 없다.

### 왜 문제인가
`source.kind`는 web이 `source_label_key`로 문구를 고르는 근거이자 `observability` 분류가 붙는 단위다. 계약은 "**새 `source.kind`를 추가할 때 `observability`를 함께 정한다. 분류 없는 kind는 만들지 않는다**"고 못박았다. mock이 조용히 5종을 늘리면 evidence Owner가 정하지 않은 분류가 사실상 기정사실이 되고, `04_mock_validation_report.md`가 이를 보고하지 않아 검수에서도 걸러지지 않는다.

### 근거
`contract-evidence-record-needs.md` §3 「`source.observability` · `source.label_key`」: "새 `source.kind`를 추가할 때 `observability`를 함께 정한다. 분류 없는 kind는 만들지 않는다." / "`label_key`는 … **키 네임스페이스는 `evidence`가 소유**".

### 권장 수정
값을 바꾸지 말고 **보고**한다. `docs/mock/04_mock_validation_report.md` §3.2와 `CONTRACT_CONFLICTS.md`에 "Mock이 신설한 미등재 `source.kind` 5종" 항목을 추가하고, 각 kind에 mock이 임시로 부여한 `observability`(`recording.file_metadata_time`=OBSERVED, `case.user_location_hint`=OBSERVED, `case.user_correction`=(occurred_at은 `observability` 없음), `evidence.category_mapping`=INFERRED, `evidence.violation_expression`=INFERRED)를 표로 적어 김준영이 한 번에 승인/교체할 수 있게 한다. 승인 전까지 fixture 값은 유지한다(대안 값이 없으므로).

### 수정 범위
Mock Documentation

### Owner 확인 필요 여부
`필수 — 도메인 판단 필요` (김준영 — 등재 승인 또는 교체)

---

## `[P1-3] ⏳ Owner 답변 대기 — VisualEvidence의 ref 직렬화 형식이 계약 예시와 다르고, 어느 쪽이 정답인지 미확정`

**관련 파일:** `data/mock/search/scenario_{happy,unknown_abstain_partial,correction_rerun}_001.json` · `docs/architecture/contracts/contract-visual-evidence.md`(계약, 수정 금지)
**Scenario:** 전 시나리오
**관련 Contract:** `VisualEvidence`(input_ref, evidence_refs) · `FrameRef`
**관련 Module:** search, evidence, readout

### 현재 상태
- 계약 §2 예시: `"input_ref": "analysis-input:incident-17"`, `"evidence_refs": ["frame:incident-17@6400"]` (위치를 인코딩한 문자열)
- mock: `"input_ref": {"kind":"incident_clip","ref":"clip_h001"}`, `"evidence_refs": ["fr_h001_thumb"]`

### 왜 문제인가
`04_mock_validation_report.md` §3.3-2가 "계약 예시가 stale"이라고 보고는 했지만, **`input_ref`가 ContractRef 객체인지 opaque 문자열인지**는 여전히 미정 상태로 남았다. 이건 형식 취향이 아니라 parser 시그니처다. search가 무엇을 직렬화할지, evidence/readout이 무엇을 역참조할지 정해지지 않으면 세 모듈이 서로 다른 타입으로 구현한다.

### 근거
- `contract-visual-evidence.md` §3: `input_ref | ref | 필수 | 실제 Fine 분석 입력의 opaque reference`(타입이 "ref"로만 적혀 있음).
- `contract-source-asset-media-stream.md` §5: `FrameRef`는 `fr_<opaque-id>` opaque 형식, 내부 파싱 금지(2026-09-08 종결) → `evidence_refs`는 mock 쪽이 옳다.
- `contract-observation.md` §3: 공용 `ContractRef {kind, ref}`.

### 권장 수정
fixture는 그대로 두고(현재 형식이 최신 규약에 부합한다), **계약 예시 갱신 요청**을 문서화한다. 구체적으로 `04_mock_validation_report.md` §3.3-2를 다음 두 질문으로 쪼개 기록한다.
① `evidence_refs[]`는 `fr_<opaque-id>` FrameRef로 확정하는가(mock 가정) — 서어진·정철원
② `input_ref`는 `ContractRef {kind, ref}`인가, opaque 단일 문자열인가 — 서어진(+P0-3의 `VISUAL_VERIFY.input_ref.kind`와 같은 결정)
그리고 결정이 나기 전에는 `03_mock_artifact_templates.md`에 "이 형식은 계약 예시와 다르며 확인 대기"라는 한 줄을 명시한다.

### 수정 범위
Mock Documentation + Upstream 확인 필요

### Owner 확인 필요 여부
`필수 — 도메인 판단 필요` (서어진)

---

## `[P1-4] ✅ 해소 — PlateReadout.consensus.disagree_positions off-by-one`

**관련 파일:** `data/mock/readout/scenario_unknown_abstain_partial_001.json`
**Scenario:** `scenario_unknown_abstain_partial_001`
**관련 Contract:** `PlateReadout` (`plate-readout/v1.2`)
**관련 Module:** readout(Producer), evidence·web(마스킹 표시), eval

### 현재 상태
```
observation.value = "17나28?4"     ← '?'는 index 5 (0-based)
consensus.disagree_positions = [6]
frame_results = "17나2804" / "17나2894"   ← 실제 불일치 문자는 index 5
```

### 왜 문제인가
소비자가 `disagree_positions`로 마스킹/하이라이트를 그리면 엉뚱한 자리를 가리킨다. mock이 유일한 참조 구현인 단계에서 off-by-one은 그대로 복제된다.

### 근거
`contract-plate-overlay-readout.md` §4 예시: `value="12가34?6"`, `frame_results="12가3456"`/`"12가3466"`, `disagree_positions=[5]` → **0-based**.

### 권장 수정
`disagree_positions`를 `[5]`로 수정.

### 수정 범위
Fixture only

### Owner 확인 필요 여부
`불필요 — 기계적/명백한 문제`

---

## `[P1-5] ✅ 해소 — OverlayTimeReadout.samples[].offset_sec가 clip 기준이 아니라 source 기준, sample_count와 배열 길이 불일치`

**관련 파일:** `data/mock/readout/scenario_happy_001.json`
**Scenario:** `scenario_happy_001`
**관련 Contract:** `OverlayTimeReadout` · `IncidentClip`
**관련 Module:** readout, evidence, eval

### 현재 상태
`samples = [{frame_ref:"fr_h001_plate1", offset_sec:313.1, …}, {…, offset_sec:313.6, …}]`, `validation.sample_count = 3`.
`clip_h001`은 timeline `[300,420]`이므로 clip 기준 offset은 13.1 / 13.6이다.

### 왜 문제인가
`duration_match_ok`는 "sample 간 timestamp 차이가 sample 간 `offset_sec` 차이와 허용 오차 내에서 맞는지"를 판정하는 값이다. 좌표 기준이 뒤섞이면 이 검증을 구현하는 쪽이 어떤 기준으로 빼야 하는지 알 수 없다(차이값만 쓰면 우연히 같지만, 단일 sample의 절대 위치를 clip 안에서 찾을 때 깨진다). `sample_count=3`인데 배열이 2개인 것도 `len(samples)`를 쓰는 소비자와 어긋난다.

### 근거
`contract-plate-overlay-readout.md` §6 예시: `input_ref.incident_clip_ref="clip_0001"`, samples의 `offset_sec`가 `2.0`/`3.0` — clip 기준 상대 offset.

### 권장 수정
- `offset_sec`를 `13.1` / `13.6`으로 변경(= source offset − clip 시작 300s).
- `sample_count`를 `2`로 맞추거나 sample 1건을 추가해 3건으로 만든다. **후자를 권장** — `monotonic_ok`/`duration_match_ok`를 3점으로 검증하는 편이 소비자에게 더 현실적인 입력이다(예: `fr_h001_thumb` 12.48s, raw_text "2026-08-24 18:05:12").
- 같은 규칙을 P0-4 수정에서 새로 만드는 overlay 결과에도 적용한다.

### 수정 범위
Fixture only

### Owner 확인 필요 여부
`권장 — 수정 후 Owner sanity check` (신유민)

---

## `[P1-6] 🔶 부분 해소 — GPS/위치 Observation 경로가 전면 미커버 (+ Coordinate 필드명 lat/lng vs lat/lon 상위 문서 불일치)`

> **2026-09-09 4차 라운드 갱신 (fixture 반영).** 정철원(이슈 #18)·김준영(이슈 #19) 답변대로 GPS **있음**(`scenario_happy_001`)·**없음**(`scenario_unknown_abstain_partial_001`) 경로를 각각 recording fixture에 추가했다: `recording/*.json`에 신규 배열 `gps_observations`(mock 전용 배열명 — 어떤 계약도 이 이름을 고정하지 않는다)를 만들고 `Observation<Coordinate>` 1건씩 채웠다. happy는 `status:OK`, `value:{lat:35.1522, lon:126.8515}`, `source.kind:"recording.gps_stream"`, `source.ref:{kind:"media_stream", ref:"ms_h001_front_v"}`, `support_refs:[{kind:"frame", ref:"fr_h001_thumb"}]`(정철원 답변대로 `source_asset`이 아니라 관련 `FrameRef`), `produced_by:{module:"recording", impl_ref:"gps-parser/default"}`. u001은 계약 §12 "GPS source 없음" 예시 그대로 `value:null, status:UNKNOWN, source:{kind:"recording.gps_stream"}, support_refs:[], reason.code:"recording.gps.source_absent"`. 좌표 키는 `lat`/`lon`으로 통일했다(계약 예시의 `lat/lng`는 손대지 않음 — §12 3번 그대로 "Upstream 확인 필요"로 남김). `EvidenceRecord.location.coord`(happy)도 `source.kind:"recording.gps_stream"`·`observability:OBSERVED`·`needs_review:false`로 채웠고 `CaseView.location_display.coord`도 `{lat,lon}`으로 갱신했다.
> **단, `address`/`place_name`은 채우지 않았다.** 김준영의 이슈 #19 답변 ④가 "address는 versioned reverse-geocode artifact 없이 임의 생성 금지"라고 명시적으로 못박았고, 그런 artifact(실제 좌표→주소 역지오코딩 데이터)는 mock 작업 범위에서 만들어낼 수 있는 게 아니다(가짜 주소를 지어내는 것과 다르지 않다). 그 결과 `contract-job-record-case-view.md` §7-(3)의 "대표값은 `address → place_name → user_hint` 중 존재하는 첫 값" 규칙에 따라 `location_display`의 대표 `value`/`info_state`는 여전히 `user_hint`/`INFO_NEEDS_REVIEW`다 — `coord`는 대표값 후보가 아니라 별도 채널이기 때문에(§7-(3) "coord·search_keyword는 대표값 후보가 아니며 별도 내려보낸다") 이번 fixture 추가가 `info_state`를 바꾸지는 않는다. 즉 **GPS Observation coverage 갭(P1-6의 핵심)은 닫혔지만, "happy가 완전히 all-green"이라는 P2-1의 원래 목표는 address artifact 없이는 달성할 수 없다** — 아래 P2-1 갱신 참고.

**관련 파일:** 전 시나리오(recording·evidence·case) · `docs/architecture/contracts/contract-observation.md` · `contract-evidence-record-needs.md`
**Scenario:** 전 시나리오
**관련 Contract:** `Observation<Coordinate>` · `EvidenceRecord.location` · `CaseView.location_display`
**관련 Module:** recording, evidence, case, web

### 현재 상태
- pack 전체에 `recording.gps_stream` Observation이 0건이다.
- 모든 `CaseView.location_display.coord`가 `null`이고, `EvidenceRecord.location`에 `coord`/`address`/`place_name`이 한 번도 등장하지 않는다.
- 따라서 `CaseView` §7(3)의 위치 대표값 우선순위(`address → place_name → user_hint`)가 어느 fixture로도 검증되지 않는다.

### 왜 문제인가
"GPS 없음"은 이 제품이 특별히 신경 쓰는 실패 모드다(마지막 handoff에서 처음 알게 하지 말 것). 그런데 mock에는 **GPS 있음도, GPS 없음(UNKNOWN Observation)도 없다.** web은 좌표 렌더링을 개발할 입력이 없고, evidence는 좌표 provenance 경로를 한 번도 실행하지 못한다.
추가로 상위 문서끼리 필드명이 다르다: `contract-observation.md`의 GPS 예시는 `{"lat":35.0,"lng":126.0}`, `contract-evidence-record-needs.md`의 `Coordinate`와 `CaseView.location_display.coord`는 `{lat, lon}`이다. mock이 좌표를 한 번도 쓰지 않아 이 drift가 드러나지 않았다.

### 근거
- `contract-observation.md`: GPS Observation 정상 예시(`kind:"recording.gps_stream"`, `ref:{kind:"media_stream"}`)와 부재 예시(`value:null`, `status:"UNKNOWN"`, `reason.code:"recording.gps.source_absent"`)가 모두 정의돼 있다.
- `contract-evidence-record-needs.md` §3: `Coordinate { lat: number, lon: number }`.
- `contract-job-record-case-view.md` §6: `evidence.location_display.coord | {lat, lon} | null | Y(키)`.
- `product/core-user-flow.md`: GPS 없음을 조기에 알리는 원칙.

### 권장 수정
1. `scenario_happy_001`에 GPS **있음** 경로를 넣는다: recording fixture에 `Observation<Coordinate>`(`recording.gps_stream`, `ref:{kind:"media_stream", ref:"ms_h001_front_v"}`, `support_refs:[{kind:"source_asset", ref:"sa_h001_front"}]`) 1건 추가 → `EvidenceRecord.location.coord`(+`address`)를 `observability=OBSERVED`, `needs_review=false`로 채움 → `CaseView.location_display`가 `INFO_SOURCE_VERIFIED` + `coord:{lat,lon}`이 되도록 갱신. 이렇게 하면 P2-1(happy가 완전 정상이 아님)도 함께 해소된다.
2. `scenario_unknown_abstain_partial_001`에 GPS **없음** Observation(`value:null`, `status:"UNKNOWN"`, `reason.code:"recording.gps.source_absent"`)을 추가해 「GPS 없음」 경로를 커버한다.
3. 좌표 키 이름은 **`lat`/`lon`**(evidence·CaseView 쪽)으로 통일해 fixture를 작성하고, `lat`/`lng` 불일치는 `04_mock_validation_report.md`에 **Upstream 확인 필요**로 기록한다(계약 문서는 수정하지 않는다).

### 수정 범위
여러 Mock Artifact + Mock Documentation + Upstream 확인 필요

### Owner 확인 필요 여부
`필수 — 도메인 판단 필요` (김준영: `lat/lon` 통일 및 address의 provenance / 정철원: GPS Observation을 recording이 어떤 단위로 내는지)

---

## `[P1-7] ✅ 해소 — 수정 중 새 계약 공백 발견(§12 김준영 ⑤) — ve_u001이 근거가 불충분한데 verification=OBSERVED로 단정`

> **2026-09-09 갱신 (팀 리뷰 이슈 #15, 서어진 답변 · case Owner 유소연 반영).** 아래 (A)안대로 확정 — `verification:"UNCERTAIN"`, `visual_event_type:null`로 변경했다. 다만 (A)를 실제로 적용해보니 `EvidenceRecord.event`가 계약상 필수 필드라 **`EvidenceRecord` 자체를 만들 수 없다**는 사실이 새로 드러났고(단순 필드 부재로는 해결 안 됨), 이것이 같은 시나리오에 함께 있던 C·D·G·I(번호판 abstain, 사건유형은 confirmed 전제)와 정면으로 충돌했다. 그래서 김준영 제안대로 `scenario_unknown_abstain_partial_001`(E·H, 이 항목)과 신규 `scenario_plate_reread_001`(C·D·G·I, 사건유형 confirmed)로 시나리오를 분리했다 — 상세 근거는 `04_mock_validation_report.md` §3.1-4(신규 Contract Gap: `EvidenceNeeds`가 "사건 유형 자체 미확정"을 표현 못 함).

**관련 파일:** `data/mock/search/scenario_unknown_abstain_partial_001.json` · (연쇄) `data/mock/evidence/scenario_unknown_abstain_partial_001.json`
**Scenario:** `scenario_unknown_abstain_partial_001`
**관련 Contract:** `VisualEvidence` §4-1
**관련 Module:** search, evidence, case

### 현재 상태
```
verification = "OBSERVED", visual_event_type = "SIGNAL_VIOLATION"
primitives[0] = {kind:"RED_SIGNAL", state:"UNCERTAIN", confidence:0.47}
candidate uncertainties = ["SIGNAL_STATE_NOT_CLEARLY_VISIBLE"]
```

### 왜 문제인가
신호위반의 성립 근거인 신호 상태가 `UNCERTAIN`인데 사건 관찰은 `OBSERVED`로 단정돼 있다. 계약은 "관찰 근거가 불충분하거나 모호"하면 `UNCERTAIN`이고 그때 `visual_event_type`은 **반드시 null**이라고 정했다. 지금 fixture는 evidence가 "관찰됨"으로 받아 `visual_event_type`을 confirmed value로 승격하게 만든다 — 관찰/확정 분리 원칙이 mock에서 헐거워지는 지점이다. 덤으로 `UNCERTAIN` 경로가 pack 전체에서 미커버로 남는다.

### 근거
`contract-visual-evidence.md` §4-1 표: `UNCERTAIN | Fine은 정상 실행됐으나 관찰 근거가 불충분하거나 모호함 | visual_event_type 반드시 null`.

### 권장 수정
둘 중 하나를 **명시적으로** 고른다.
- (A) 이 시나리오의 의도가 "불확실한 관찰"이라면: `verification:"UNCERTAIN"`, `visual_event_type:null`로 바꾸고, `EvidenceRecord.event.visual_event_type`은 **값을 만들지 않는다**(필드 부재 — vehicle_number와 같은 방식). `RequirementReport`의 `evidence.visual_event.present` outcome을 `WARN` → `UNKNOWN`으로 조정하고 `overall`은 그대로 `UNKNOWN`. `CaseView.case_type_display.code/label`은 `null`.
- (B) 이 시나리오를 "관찰은 됐지만 번호판만 불확실"로 유지하려면: primitive를 `state:"PRESENT"`, confidence를 0.8 이상으로 올리고 candidate `uncertainties`에서 신호 관련 항목을 뺀다.
**(A)를 권장한다** — `UNCERTAIN` 미커버가 해소되고, 시나리오 이름(`unknown_abstain_partial`)과도 맞는다.

### 수정 범위
여러 Mock Artifact

### Owner 확인 필요 여부
`권장 — 수정 후 Owner sanity check` (서어진·김준영)

---

## `[P1-8] ✅ 해소 — CaseView.manifest_summary.range가 recording 커버리지가 아니라 AnalysisScope 범위`

**관련 파일:** `data/mock/case/scenario_unknown_abstain_partial_001.json` · `data/mock/case/scenario_correction_rerun_001.json`
**Scenario:** `scenario_unknown_abstain_partial_001`, `scenario_correction_rerun_001`
**관련 Contract:** `CaseView.manifest_summary` · `RecordingTimeline`
**관련 Module:** case, web, recording

### 현재 상태
| 시나리오 | fixture의 range | timeline 실제 커버리지 |
| --- | --- | --- |
| u001 | 22:00:00 – 22:30:00 | anchor 22:10:00 + 1800s = **22:10 – 22:40** |
| r001 | 12:55:00 – 13:20:00 | anchor 13:00:00 + 1500s = **13:00 – 13:25** |
| happy | 18:00 – 18:20 | 18:00 – 18:20 ✅ |

### 왜 문제인가
`manifest_summary`는 "등록한 영상이 어느 구간을 덮는가"를 사용자에게 보여주는 값이다. 지금 값은 사용자가 요청한 검색 범위라서, web이 "영상 커버리지 밖을 검색했다"는 정상 케이스를 표현할 수 없고 recording fixture와도 어긋난다. u001은 심지어 scope(22:00~)가 timeline 시작(22:10) 이전 10분을 포함해 `SpanResolution`의 `OUT_OF_TIMELINE_RANGE` 상황을 암시하는데 그 결과가 어디에도 없다.

### 근거
`contract-job-record-case-view.md` §6: `manifest_summary.… duration_sec | 파일 등록 성공·실패 수, **전체 구간 길이**. count/duration은 항상 제공하고 정상 영상이 없으면 range=null`.

### 권장 수정
- u001: `range: ["2026-08-26T22:10:00+09:00", "2026-08-26T22:40:00+09:00"]`
- r001: `range: ["2026-08-27T13:00:00+09:00", "2026-08-27T13:25:00+09:00"]`
- 추가 권장: u001의 `scope_u001.time_ranges`가 timeline 밖 구간을 포함하는 상태를 살릴 거라면 §10의 `SpanResolution PARTIAL` fixture와 연결하고, 아니면 scope를 `22:10~22:40` 안으로 좁힌다. **둘 중 하나를 고르지 않으면 "요청 범위 일부가 영상 밖"이라는 사실이 아무 데도 표현되지 않는다.**
  **✅ 결정·적용 완료(2026-09-09, 유소연): scope를 `22:10~22:40`으로 좁혔다**(`search/scenario_unknown_abstain_partial_001.json`). `SpanResolution PARTIAL`은 §10 신규 시나리오 `scenario_relative_rebase_001`(정철원 담당)에서 별도로 커버하므로 u001에서 중복 구현하지 않는다.

### 수정 범위
Fixture only (+선택 시 Scenario 확장)

### Owner 확인 필요 여부
`불필요 — 기계적/명백한 문제` (range 값 자체는 기계적. scope 축소 여부만 유소연 판단)

---

## `[P1-9] 🔶 부분 해소(처리중·user_reviewed 스냅샷 추가 · BLOCK·INFO_AI_ESTIMATED 미해소) — web·case가 필요한 상태군이 통째로 비어 있음 (INFO_AI_ESTIMATED / 처리중 / blocking / BLOCK / user_reviewed)`

**관련 파일:** `data/mock/case/*.json`(4개) · `data/mock/evidence/*.json`
**Scenario:** 전 시나리오
**관련 Contract:** `CaseView`(info_state·stage·progress·running_jobs·notices·user_reviewed) · `RequirementReport`(overall)
**관련 Module:** case, web, evidence

### 현재 상태
| 값 | pack 내 등장 |
| --- | --- |
| `info_state = INFO_AI_ESTIMATED` | **0건** (5종 중 1종 미등장) |
| `stage = INTAKE` / `SEARCHING` | 0건 |
| `progress[].state = PENDING` / `RUNNING` | 0건 (DONE·FAILED만) |
| `running_jobs[].status = RUNNING` | 0건 (PENDING 1건만) |
| `notices[].blocking = true` | 0건 |
| `notices[].severity = ERROR` | 0건 |
| `RequirementReport.overall = BLOCK` | 0건 |
| `user_reviewed = true` | 0건 |

### 왜 문제인가
web은 이 pack만으로는 화면 절반을 못 그린다. 특히 ① 「AI 추정」 정보 상태는 제품 §3-1의 5종 중 하나이고 `observability=INFERRED` 값(예: 추론된 위치·유형)에 붙는데 어떤 `*_display`에도 없다. ② 「처리 중」 화면은 긴 검색 대기(제품의 핵심 UX)를 담당하는데 fixture가 없다. ③ `BLOCK`은 "신고 불가"라는 종착 상태인데 pack 전체에 없어서, evidence의 blocker 판정과 web의 차단 표시가 mock으로 개발되지 않는다.

### 근거
- `product/core-user-flow.md` §3-1 정보 상태 5종.
- `contract-job-record-case-view.md` §7 `info_state` 파생 규칙(5단계 중 5번 = `observability=INFERRED → INFO_AI_ESTIMATED`), `progress[].state` 4값, `notices[].blocking`, `user_reviewed`.
- `contract-requirement-report-package.md` §4.2: `BLOCK` = "판정은 성립했고 현재 정책상 진행 불가"(예: Report Video를 확인했고 번호판이 식별 불가능).

### 권장 수정
새 fixture 3건으로 대부분 해소된다(§10 참조).
1. **`scenario_happy_001`에 진행중 CaseView 스냅샷 추가** — 같은 파일 `case_views` 배열에 2번째 항목(`case_rev` 더 낮은 값, `stage:"SEARCHING"`, `progress`에 `RUNNING`/`PENDING` 혼재, `running_jobs=[{job_h001_search, status:"RUNNING"}]`, `evidence:null`, `requirements_*:null`, `package:null`). 배열이므로 파일 추가 없이 가능하고, 시간순 스냅샷 2개라는 점을 `02` 카탈로그에 명시한다.
2. **`INFO_AI_ESTIMATED`**: P1-6에서 위치를 채울 때, u001 쪽 위치를 "AI가 영상에서 추론한 주소"(`observability=INFERRED`, `needs_review=false`)로 두면 자연스럽게 등장한다.
3. **`BLOCK` + blocking notice**: §10의 신규 시나리오 `scenario_blocked_001`(번호판이 신고영상에서 식별 불가 → `category=VEHICLE`(또는 ASSET, P2-2 참조) `outcome=BLOCK` → `overall=BLOCK` → `ReportPackage` 미생성 → `CaseView.notices[].blocking=true`, `severity="ERROR"`).
4. **`user_reviewed=true`**: happy의 `case_views`에 3번째 스냅샷(사용자 최종 확인 완료, `stage=READY`, `user_reviewed=true`)을 추가하면 handoff 직전 상태가 생긴다.

### 수정 범위
여러 Mock Artifact + Scenario Catalog + Manifest

### Owner 확인 필요 여부
`권장 — 수정 후 Owner sanity check` (신유민: 화면 상태 충분성 / ~~유소연: stage·progress 조합~~ → **확인 완료(2026-09-09, 유소연)**: happy/empty/u001/r001 4개 파일의 `stage`·`progress[].state`·`running_jobs`·`case_rev` 조합을 재검토했고 모순 없음. `evidence.review_needed` OR 파생 규칙도 4개 시나리오 전부와 일치함을 확인해 B절 §7에 확정 등재)

---

## `[P1-10] ✅ 해소 — 최신 계약 변경분(TIMELINE_RELATIVE / USABLE_RELATIVE_ONLY / rebase revision / SpanResolution 실패)이 전부 미커버`

> **2026-09-09 4차 라운드 갱신 (fixture 반영).** 정철원(이슈 #18)이 확정한 메커니즘 그대로 신규 시나리오 `scenario_relative_rebase_001`(유형 K)을 만들었다 — `RecordingTimeline` revision 1(`working_anchor.status=UNKNOWN`, `timeline_status=USABLE_RELATIVE_ONLY`, `time_source_candidates=[]`) → `TIMELINE_RELATIVE` scope로 candidate 생성(`span.timeline_revision:1`) → 두 번째 소스 추가로 revision 2 rebase(600~630s 30초 공백, revision 1 보존) → `resolve_span()`(580~650s 요청)이 `status:PARTIAL`+`missing_ranges[{600~630s, TIMELINE_GAP, source_ref:null}]`. `CandidateEvent.span.timeline_revision`은 rebase 후에도 `1`로 불변, `CaseView.candidates[].stale_revision`(case 소유 신규 필드 — `docs/modules/case/decisions/candidate-stale-revision-display.md`, 계약 §13 note가 명시적으로 case Owner에게 위임한 필드명·모양 결정)이 rev1→rev2에서 `false→true`로 바뀌어 「과거 timeline revision 기준」 표시를 실증한다. `SpanResolution.FAILED`(위치를 특정할 수 없는 전체 실패)는 이 시나리오 범위 밖으로 남겼다(정철원 답변 원문 그대로 — infra 실패 시나리오 계열로 분리).

**관련 파일:** `data/mock/recording/*.json` · `data/mock/search/*.json`
**Scenario:** 전 시나리오
**관련 Contract:** `AnalysisScope` 1.1.0 · `RecordingTimeline`(timeline_status·revision) · `SpanResolution` v1.1/v1.2 · `CandidateEvent.span.timeline_revision`
**관련 Module:** recording, search, case, evidence

### 현재 상태
모든 timeline이 `revision:1` · `timeline_status:"USABLE"` · `gaps:[]`, 모든 scope가 `kind:"ABSOLUTE"`, 모든 `SpanResolution`이 `status:"COMPLETE"` · `missing_ranges:[]` · `failure:null`.

### 왜 문제인가
2026-09-07~08에 마지막으로 확정된 항목들(B06 `SpanResolution` 완전성/실패 직렬화, B08 relative-only, B09 `timeline_revision` 보존)이 **가장 최근 결정인데 검증 데이터가 0건**이다. 특히 relative-only는 "absolute anchor가 없는 블랙박스 영상"이라는 흔한 정상 입력이고, rebase(revision 2)는 `case`가 「과거 timeline revision 기준」 표시를 해야 하는 분기다. mock이 비어 있으면 이 분기들은 구현 시점에 처음 마주치게 된다.

### 근거
- `contract-analysis-scope.md` §7: "`TIMELINE_RELATIVE`는 `RecordingTimeline.timeline_status=USABLE_RELATIVE_ONLY`인 영상의 **정상 입력 경로**다."
- `contract-recording-timeline-asset-span.md` §5: rebase 시 revision 증가, "둘이 다르면 `case`가 비교해 `CaseView`에 「과거 timeline revision 기준」임을 표시".
- 같은 문서 §9·§10: `PARTIAL`+`missing_ranges`, `FAILED`+`failure` 직렬화.

### 권장 수정
§10의 신규 시나리오 `scenario_relative_rebase_001` 하나로 세 가지를 함께 커버한다.
- 시각 기준을 파싱할 수 없는 파일(파일명·metadata 모두 없음) → `working_anchor.status="UNKNOWN"`, `timeline_status="USABLE_RELATIVE_ONLY"`, `time_source_candidates=[]`
- `AnalysisScope.time_ranges = [{kind:"TIMELINE_RELATIVE", timeline_ref:{timeline_id, revision:1}, start_ms, end_ms}]`
- 두 번째 파일이 나중에 추가돼 timeline `revision:2` 생성 → 기존 candidate는 `span.timeline_revision:1` 유지 → `CaseView`가 「과거 revision 기준」 표시
- 두 파일 사이 30초 공백 → `gaps` 비어 있지 않음 → 그 구간을 요청한 `SpanResolution`이 `status:"PARTIAL"` + `missing_ranges[{reason:"..."}]`
`SpanResolution.failure`(FAILED) 케이스는 §10의 별도 항목으로 남긴다.

### 수정 범위
새 Scenario(여러 Mock Artifact) + Scenario Catalog + Manifest

### Owner 확인 필요 여부
`필수 — 도메인 판단 필요` (정철원 — gap/rebase 서사와 `missing_ranges[].reason` 값)

---

## `[P1-11] 🔶 부분 해소(오답 fixture의 actual_ref 제거) · 근본 원인 재정의(김대원 답변) — Eval fixture가 자기모순이고, 채점 모델 자체가 실제 구현과 다름`

> **2026-09-09 2라운드 갱신 (이슈 #17, 김대원 답변 · 원문 재대조로 정정).** 1라운드는 이 항목을 "metric 이름이 다르다"는 네이밍 문제로만 다뤘는데, 김대원의 답변은 **더 근본적인 문제 — 채점 모델(scoring model) 자체가 틀렸다**는 것이었다. 현재 fixture는 `candidate_id` 동일성(`actual_top_candidate_id`==`expected_top_candidate_id`)으로 채점하지만, 실제 eval 스코어러는 **구간(interval) + 위반 유형**으로 정답을 매칭한다(`event_type` 일치 AND `IoU >= 0.5`) — 실제 구현체는 자기 후보에 자기 ID를 붙이지 GT의 ID를 재현하지 않으므로, ID 매칭 방식은 "GT ID를 그대로 베낀 가짜 구현"은 통과시키고 "진짜로 정확히 탐지한 실구현"은 전부 낙제시키는 정반대 결과를 낳는다.
>
> **확정된 metric 개명(전체 표)**
>
> | 기존(mock) | 확정 명칭 | 비고 |
> | --- | --- | --- |
> | `candidate_top1_accuracy` | **`recall_at`**(K=1,3,10) | ID가 아니라 구간+유형 IoU≥0.5로 매칭 |
> | `plate_exact_match_rate` | **(이름 유지)** | 분모 = GT `legibility=READABLE`로 라벨된 판독 건수 |
> | `abstention_correctness_rate` | **폐기, 2개로 분리**: `abstention_recall` + `wrong_accept_rate` | `abstention_recall` 분모 = GT `legibility=UNREADABLE` 건수, `wrong_accept_rate` 분모 = abstain하지 않은 판독 건수 |
> | `time_within_tolerance_rate` | **`timestamp_error_sec`** | 비율이 아니라 초 단위 값 |
>
> 김대원은 05 자체의 기존 권장안(③ `plate_exact_match_rate`를 나머지 두 metric으로 교체)을 **명시적으로 반려**했다 — 세 metric의 분모가 전부 다르므로 교체하면 "정직하게 abstain했는지" 평가 능력 자체가 사라진다는 이유. 신규 필수 GT 필드: `legibility: READABLE | UNREADABLE`(현재 pack에는 `UNREADABLE` 라벨 0건이라 `abstention_recall`은 `0`이 아니라 `null`+사유로 표시해야 정확).
>
> **`data/mock/expected/` 자체의 재작성은 case Owner 소관이 아니다** — 김대원이 "확정 전에 이 이슈에 새 shape을 먼저 올리겠다"고 명시했으므로, 여기서는 근거만 정확히 반영하고 fixture 재작성은 eval Owner의 후속 PR로 남긴다.

**관련 파일:** `data/mock/expected/eval_fixture_wrong_001.json` · `data/mock/expected/eval_fixture_correct_001.json`
**Scenario:** (eval 전용)
**관련 Contract:** 없음(provisional) · 참조 대상은 `PlateReadout`·`AnalysisRun`·`TimeResolution`
**관련 Module:** eval

### 현재 상태
- `eval_fixture_wrong_001`의 각 target이 `actual_ref`로 **실재하는** `readout_h001_plate` / `run_h001` / `tres_h001`을 가리키면서, `actual_value`에는 그와 다른 값(`98다6543`, `candidate_h001_decoy`, `19:47:00`)을 적어 놨다. `candidate_h001_decoy`는 어디에도 없는 ID다.
- metric 이름이 `plate_exact_match_rate` · `candidate_top1_accuracy` · `time_within_tolerance_rate` · `abstention_correctness_rate`로, 프로젝트가 쓰는 이름(`Recall@K` · `Final Recall@3` · `Fine Recall` · `HN-FPR` · `FP-hour` · `timestamp error` · `Abstention Recall` · `Wrong Accept Rate`)과 겹치지 않는다.
- 검증 스크립트가 `expected/`를 참조 검사 대상에서 제외하고 있어 이 모순이 PASS로 통과한다.

### 왜 문제인가
"의도적 오답" fixture의 존재 이유는 metric 코드가 틀린 것을 틀렸다고 판정하는지 확인하는 것이다. 그런데 harness가 `actual_ref`를 역참조하면 **정답**이 나와 테스트가 통과해버린다 — 목적과 정반대로 동작한다. metric 이름이 다른 것도 김대원이 이 fixture를 자기 코드에 연결할 수 없게 만든다.

### 근거
- `modules/eval/experiment-guide.md` `[RESULT]`: `Recall@K / timestamp error / FP-hour / Fine Recall / HN-FPR / Precision / Final Recall@3 / latency·tokens·cost·Fine exposure`.
- `contract-readout-run.md` §2: "Abstention Recall·Wrong Accept Rate의 정답 라벨과 분자·분모는 `eval`이 정의했고 계약 필드 추가는 필요 없다."

### 권장 수정
1. `eval_fixture_wrong_001`에서 `actual_ref`를 **제거**하고 inline synthetic actual만 남긴다(참조하면 안 되는 값이므로). 또는 실제로 틀린 런타임 출력을 담은 별도 시나리오(`scenario_eval_wrong_001`)를 만들어 그것을 가리킨다. **전자를 권장**(비용 대비 효과).
2. `candidate_h001_decoy` 같은 미존재 ID는 inline actual 안에서만 쓰고, 그 사실을 파일 내 `note`에 적는다.
3. metric 이름을 프로젝트 어휘로 교체: `plate_exact_match_rate` → **`wrong_accept_rate` / `abstention_recall`** 조합, `candidate_top1_accuracy` → **`recall_at_k`(K=1) 또는 `final_recall_at_3`**, `time_within_tolerance_rate` → **`timestamp_error`**(초 단위 값 + 허용 오차). 이름 확정은 김대원 소관이므로 파일 상단 `note`에 "이름은 eval Owner 확정 대상"을 유지한다.
4. `eval_fixture_correct_001`의 `actual_value` 복사는 유지하되 "이 값은 `<파일경로>#<id>`의 사본이며 fixture 변경 시 함께 갱신"이라는 주석 필드를 추가하고, 검증 스크립트에 동기화 검사를 넣는다(§11-4).

### 수정 범위
Fixture only + Validation

### Owner 확인 필요 여부
`필수 — 도메인 판단 필요` (김대원 — metric 이름·정답 라벨)

---

## `[P1-12] 🔶 taxonomy 답변 완료(정밀화) · 신규 시나리오는 미착수 — readout / search 실행 실패 계열이 등록된 taxonomy 값으로 표현된 fixture가 없음`

> **2026-09-09 갱신 (팀 리뷰 이슈 #16, 신유민 답변).** readout failure taxonomy 쪽 답변을 받아 `scenario_infra_failure_001`을 만들 때 쓸 등록 kind가 확정됐다. 또한 아래 "현재 상태"에서 예견했던 대로, P0-4 수정으로 `rr_u001_overlay`가 성공으로 바뀌면서 **pack 전체에 `outcome=FAILED`인 fixture가 정말로 0건이 됐다**(`04_mock_validation_report.md` §1에 신규 갭으로 기록). search 쪽 `issues[]`/`outcome=PARTIAL` 값은 여전히 서어진 확인 대기. 아래 `scenario_infra_failure_001` 자체는 아직 만들지 않았다 — 다음 라운드 작업으로 남긴다.
>
> **2026-09-09 2라운드 정밀화 (이슈 #16 원문 재대조, 사용자 확인 요청으로).** 1라운드 요약이 taxonomy 세부값을 뭉뚱그렸다 — 신유민 원문을 그대로 옮긴다.
> - `OVERLAY_DETECTION` kind는 **완전히 폐기**한다(v1 정책상 오버레이 OCR은 무조건 디스패치되므로 "감지 자체를 실패"라는 개념이 없다). overlay의 진짜 실행 실패는 **`INFRA`만** 해당하며, 코드는 `READOUT_PROVIDER_TIMEOUT` / `READOUT_FRAME_ACCESS_FAILED` / `READOUT_PIPELINE_ERROR` 3종으로 한정, `JobExecution.failure_kind="READOUT_INFRA"`.
> - `OVERLAY_VALIDATION`은 **run 실패 kind가 아니다** — run은 `SUCCEEDED`인 채로 `validation.*_ok=false` + `observation.status ∈ {NEEDS_REVIEW, UNKNOWN}`로 표현되는 사후 결과다(계약 §10과 일치). `scenario_infra_failure_001`에는 쓰지 않는다.
> - `abstain_reason`은 "authoritative" — 원인이 겹칠 때도 하나만 골라야 하며, 우선순위는 **target_association 문제(예: `TARGET_AMBIGUOUS`) > frame 불일치(`FRAME_DISAGREEMENT`)**. 값 공간: `TARGET_AMBIGUOUS` / `FRAME_DISAGREEMENT` / `LOW_RESOLUTION` / `OCR_LOW_CONFIDENCE`. 신유민이 이 값 공간을 `failure-taxonomy.md`에 직접 등재하겠다고 확인했다(case Owner가 임의로 결정할 항목이 아님).
> - 화면 문구 매핑(잠정, 실측 전까지):
>
>   | 실제 상황 | outcome | observation.status | reason.code | 화면 문구 |
>   | --- | --- | --- | --- | --- |
>   | 화면에 시각이 안 찍힌 영상(사실) | SUCCEEDED | NOT_APPLICABLE | `readout.overlay.not_present` | "화면에 시각이 없습니다 → 파일 기록으로 계산했습니다" |
>   | 찍혀 있는지 판정 못함 | SUCCEEDED | UNKNOWN | `readout.overlay.presence_undetermined` / `readout.overlay.ocr_failed` | "확인하지 못했습니다 → 직접 확인해 주세요" |
>
>   신유민은 이 구분을 "잠정"이라고 못박았다 — 실사용 false-negative(오버레이가 있는데 없다고 판정) 비율이 유의미하면 `UNKNOWN` 쪽으로 기울일 계획.
> - u001의 `readout.overlay_not_present`(밑줄)는 이미 위 표의 `readout.overlay.not_present`(점 표기)로 정정 반영했다(이번 라운드, fixture 확인 완료). `correction_rerun_001`에 신규 추가한 overlay NOT_APPLICABLE 결과도 동일 코드를 썼다.

**관련 파일:** `data/mock/readout/scenario_unknown_abstain_partial_001.json` · `data/mock/common/scenario_unknown_abstain_partial_001.json` · (부재) search `AnalysisRun.issues[]`
**Scenario:** `scenario_unknown_abstain_partial_001` 및 전 시나리오
**관련 Contract:** `ReadoutRun.failure` · `JobExecution.failure_kind` · `AnalysisRun.issues[]`
**관련 Module:** readout, search, common/runtime, eval

### 현재 상태
- 유일한 실패 fixture(`rr_u001_overlay`)가 미등록 kind `OVERLAY_DETECTION`을 쓴다(P0-4에서 이 fixture 자체를 성공으로 바꾸도록 권고했으므로, 수정 후에는 **실패 fixture가 0건**이 된다).
- `AnalysisRun.issues[]`는 모든 run에서 빈 배열이며, `outcome=PARTIAL` run이 없다.
- `JobExecution`에 `STALE`·`attempt≥2`가 없다.

### 왜 문제인가
`eval`은 "실패 분류를 run 단위로 집계"해야 하고, `case`는 재시도(`STALE` → 새 `execution_id`, `attempt` 증가)를 인프라 재시도로, 재판독(새 `job_id`)과 구분해 다뤄야 한다. 두 계층 모두 mock 입력이 없다.

### 근거
- `modules/readout/decisions/failure-taxonomy.md`: 등재 kind 5종.
- `contract-readout-run.md` §2: "eval — 실패 분류는 run 단위로 집계한다."
- `contract-job-execution.md` §6·§8·§9-2: `STALE` 전이와 `attempt` 증가, 같은 `job_id`에 새 `execution_id`.

### 권장 수정
§10의 신규 시나리오 `scenario_infra_failure_001`(경량, readout+common+case만):
- `rr_*_plate`: `outcome:"FAILED"`, `failure:{kind:"INFRA", code:"READOUT_PROVIDER_TIMEOUT"}`(또는 `READOUT_FRAME_ACCESS_FAILED`/`READOUT_PIPELINE_ERROR` 중 하나 — 3종이 등록된 전부), `plate_readouts: []`(완전 실패 시 결과 미생성 규칙 재확인)
- `JobExecution` 2건: attempt 1 = `STALE`(`ended_at:null`, `failure_kind:null` — 계약 §8 예시 그대로), attempt 2 = `FAILED`(`failure_kind:"READOUT_INFRA"`)
- `CaseView`: `progress[plate_read].state="FAILED"`, `notices[]`에 재시도 안내(`blocking` 여부는 유소연 판단)
- (선택) `abstain_reason` 값 공간 4종(`TARGET_AMBIGUOUS`/`FRAME_DISAGREEMENT`/`LOW_RESOLUTION`/`OCR_LOW_CONFIDENCE`) 중 이 pack에 아직 없는 값의 fixture도 함께 검토 — 현재 `scenario_plate_reread_001`은 `FRAME_DISAGREEMENT`만 커버한다.
`AnalysisRun.outcome=PARTIAL` + `issues[]`는 search failure taxonomy를 아직 확인하지 못했으므로(§1 참조) 별도 항목으로 남기고 서어진에게 값을 받는다.

### 수정 범위
새 Scenario(여러 Mock Artifact) + Scenario Catalog + Manifest

### Owner 확인 필요 여부
`필수 — 도메인 판단 필요` (신유민: readout failure code / 서어진: search issue kind·code)

---

## `[P1-13] ✅ 해소 — CaseView.requirements_evidence/package.checks[]가 RequirementReport의 RequirementCheck 스키마를 그대로 담지 않음`

**관련 파일:** `data/mock/case/scenario_happy_001.json` · `case/scenario_unknown_abstain_partial_001.json` · `case/scenario_correction_rerun_001.json`
**Scenario:** `scenario_happy_001`, `scenario_unknown_abstain_partial_001`, `scenario_correction_rerun_001`
**관련 Contract:** `CaseView.requirements_evidence/requirements_package` · `RequirementReport.checks[]`(`RequirementCheck`)
**관련 Module:** case (Producer), evidence (RequirementCheck 스키마 소유)

### 현재 상태
`contract-job-record-case-view.md` §4 「조사에서 확인된 제약: `checks[]`는 `RequirementReport` 그대로」에도 불구하고, 4개 시나리오의 `requirements_evidence.checks[]`/`requirements_package.checks[]`가 `code`·`outcome`·`reason_code`만 담고 있었다. `contract-requirement-report-package.md` §3의 `RequirementCheck`는 `category`(필수 enum)·`subject_refs`(필수 `ContractRef[]`)·`measurement`(선택)까지 포함한다. 대응하는 `evidence/*.json`의 `requirement_reports[].checks[]`(authoritative 원본)에는 이 필드들이 이미 정확히 채워져 있었다 — case 쪽 복사본만 누락된 상태였다.

### 왜 문제인가
"그대로"라는 계약 문구를 어기고 case가 임의로 필드를 걸러낸 축소 projection이 되어 있었다. web이 `category`(체크 분류 아이콘/그룹핑)나 `subject_refs`(어떤 자산/레코드가 문제인지)를 쓰려는 소비 코드를 mock으로 검증할 수 없었고, `measurement`(예: report_video 길이 180초 제한)도 이번 mock에서 유일하게 존재하는 사례가 case 쪽에서 사라져 있었다.

### 근거
`contract-job-record-case-view.md` §4 「checks[]는 RequirementReport 그대로 | 이전 회차 확정」, `contract-requirement-report-package.md` §3 `RequirementCheck` 스키마.

### 조치
4개 파일 전부 대응하는 `evidence/*.json`의 `requirement_reports[].checks[]`에서 `category`·`subject_refs`(·해당 시 `measurement`)를 그대로 복사했다(값 변경 없음 — P2-2의 `plate_visible` category 재배치 여부는 아직 열려 있으므로 현재 `"ASSET"` 값을 그대로 옮겼다). `validate_mock_pack.py` 재실행 PASS 확인.

### 수정 범위
Fixture only

### Owner 확인 필요 여부
`불필요 — 계약 문구("그대로") 위반의 기계적 정정` (2026-09-09, 유소연 검수 중 발견·즉시 수정)

---

### P2

---

## `[P2-1] ⏳ coord까지는 반영, address artifact 없이는 종결 불가 — Happy Path가 "완전 정상"이 아니다 — 위치가 user_hint뿐이라 대표 기준선으로서 약함`

> **2026-09-09 4차 라운드 갱신.** P1-6과 함께 `location.coord`/`location_display.coord`를 채웠지만, §7-(3) 규칙상 대표값은 `address → place_name → user_hint` 중 존재하는 값만 후보이고 `coord`는 대표값 후보가 아니다. `address`는 실제 versioned reverse-geocode artifact가 있어야 채울 수 있는데(김준영, 이슈 #19 ④) 그런 artifact는 mock 작업 범위 밖이라 — **`info_state`는 여전히 `INFO_NEEDS_REVIEW`, "완전 all-green 기준선"이라는 원래 목표는 이번 라운드로 종결되지 않는다.** 아래 "현재 상태"·"권장 수정"은 이 제약을 반영해 갱신했다.

**관련 파일:** `data/mock/evidence/scenario_happy_001.json` · `data/mock/case/scenario_happy_001.json`
**Scenario:** `scenario_happy_001` | **Contract:** `EvidenceRecord.location` · `CaseView.location_display` | **Module:** evidence, case, web

### 현재 상태
`location`에 `coord`(GPS, OBSERVED)·`search_keyword`·`user_hint`가 있지만 `address`/`place_name`은 없어(§7-(3) 대표값 후보가 아님) `CaseView.location_display.info_state = INFO_NEEDS_REVIEW`가 그대로다. 같은 객체의 `review_needed`는 `false`, `RequirementReport`의 위치 check는 `PASS`.

### 왜 문제인가
"모든 것이 정상인 기준선"이어야 할 시나리오가 검토 필요 상태를 하나 포함하고, 세 신호(`info_state` / `review_needed` / requirement `PASS`)가 서로 다른 방향을 가리킨다. 신규 개발자가 정상 상태의 모양을 오해한다.

### 근거
`contract-job-record-case-view.md` §7(3): "대표값이 `user_hint`이면 `info_state = INFO_NEEDS_REVIEW`다." · 같은 절: "`coord`·`search_keyword`는 대표값 후보가 아니며 별도 내려보낸다."

### 권장 수정
`address`(versioned reverse-geocode artifact 기반, OBSERVED)가 채워지기 전까지는 규칙상 `INFO_SOURCE_VERIFIED`로 올릴 방법이 없다 — **이 항목은 case Owner가 임의로 만들 수 없는 실제 외부 데이터(지오코딩 서비스/DB)가 선행 조건**이므로 §12에 "Owner 답변/외부 artifact 필요"로 재등록한다. 그 전까지는 `info_state=INFO_NEEDS_REVIEW`가 이 시나리오의 정확한 상태이지 결함이 아니라는 점을 `04_mock_validation_report.md`에 명기하는 것으로 대신한다(`review_needed=false`/`PASS`와의 불일치는 여전히 신규 개발자에게 혼란 요소이므로 문서화만으로 완전히 닫히지는 않는다).

### 수정 범위
Fixture 일부(coord) 완료, 나머지는 외부 artifact 선행 필요 | **Owner 확인:** `필수 — reverse-geocode artifact는 mock 범위 밖`

---

## `[P2-2] ✅ 해소 — FINAL_PACKAGE의 ASSET check 입력(AssetFacts)이 없고, plate_visible의 category 배치가 §4.6과 충돌`

> **2026-09-09 갱신 (팀 리뷰 이슈 #19, 김준영 답변).** 두 항목 모두 반영했다 — `recording/scenario_happy_001.json`의 `asset_facts`에 `da_h001_plate_image`(`DERIVED_ASSET`/`PLATE_IMAGE`) 항목을 추가했고, `evidence`·`case` 양쪽의 `package.asset.plate_visible` → `package.vehicle.plate_visible_in_report_video`로 `category="VEHICLE"`·`reason_code="readout.plate_legible_in_asset"`·`subject_refs=[{readout_run: rr_h001_plate}, {derived_asset: da_h001_plate_image}]`로 변경했다(§8 P1-13 checks[] 스키마 정합 작업과 함께 반영).

**관련 파일:** `data/mock/recording/scenario_happy_001.json` · `data/mock/evidence/scenario_happy_001.json`
**Scenario:** `scenario_happy_001` | **Contract:** `RequirementReport` §4.6 · `AssetFacts` | **Module:** evidence, recording, case

### 현재 상태
`req_h001_final`이 `package.asset.report_video.exists`(measurement 포함)와 `package.asset.plate_visible`을 `category="ASSET"`으로 판정하는데, `asset_facts`에는 `clip_h001`·`da_h001_report_video` 2건만 있고 `da_h001_plate_image`용이 없다.

### 왜 문제인가
① evidence는 `recording`을 직접 호출하지 않고 `case`가 주입한 Asset Facts로만 ASSET을 판정한다. 입력 없이 결론만 있는 fixture라 evidence 구현자가 판정 재현을 못 한다. ② 계약 §4.6은 "번호판 가시성"을 Asset Facts **제외 목록**에 명시하고 "readout observation을 근거로 evidence가 판정"이라고 했다 — 즉 `plate_visible`은 ASSET이 아니라 다른 category여야 한다.

### 근거
`contract-requirement-report-package.md` §4.6(최소 자산 사실 목록과 제외 항목), §3(category enum: EVIDENCE·TIME·VEHICLE·LOCATION·ASSET·DEADLINE·REPORT_CONTENT).

### 권장 수정
- `recording/scenario_happy_001.json`의 `asset_facts`에 `da_h001_plate_image`용 1건 추가(`asset_kind:"DERIVED_ASSET"`, `derived_role:"PLATE_IMAGE"`, `duration_sec:null`, `timeline_ref:null`, `timeline_range:null`).
- `package.asset.plate_visible`의 `category`를 `"ASSET"` → **`"VEHICLE"`**로 변경하고 code도 `package.vehicle.plate_visible_in_report_video`처럼 바꾼다(최종 이름은 김준영 확인).

### 수정 범위
Fixture only | **Owner 확인:** `권장` (김준영)

---

## `[P2-3] ✅ 해소(2026-09-09 3라운드, 이슈 #19 원문 B절 재확인) — post_stamp.needed=false인데 Report Video의 transform_ref가 poststamp`

> **정정 경위.** 이 항목은 원래 김준영 이슈 #19 본문 "B. 내 모듈 fixture 검수 · Required — evidence"에 있던 구체적 fixture 결함 지적이었는데, 1·2라운드 요약이 이슈 #19의 "A. 정합 검토 답변"(도메인 결정 6건)만 §12에 반영하고 "B" 절의 8+3건 fixture 결함 지적을 놓쳤다. 사용자가 이슈 #19 B절 전문을 다시 제시해 재대조하는 과정에서 발견해 즉시 반영했다. 아래 "권장 수정"이 이미 `권장`(비-차단) 수준이라 Owner 재확인 없이 그대로 적용했다.

**관련 파일:** `data/mock/recording/scenario_happy_001.json` · `data/mock/evidence/scenario_happy_001.json`
**Scenario:** `scenario_happy_001` | **Contract:** `TimeResolution.post_stamp` · `DerivedAsset.transform_ref` §7.4 | **Module:** evidence, recording

### 현재 상태 (수정 전)
`tres_h001.post_stamp = {needed:false, reason_code:"time.verified_overlay_already_present"}` 인데 `da_h001_report_video.transform_ref = "tr_h001_poststamp_v1"`.

### 조치
`da_h001_report_video.transform_ref`를 `"tr_h001_poststamp_v1"` → `"tr_h001_trim_v1"`로 변경(opaque ref라 스키마 영향 없음). 각인이 실제로 적용되는 경로(`post_stamp.needed=true`)는 별도 시나리오로 표현할 필요가 있으면 다음 라운드 후보로 남긴다.

### 왜 문제인가
계약은 `transform_ref`가 non-null이면 "적용된 transform 종류를 machine-readable하게 조회할 수 있다"는 보장이고, evidence는 이를 근거로 "사후 각인이 실제로 적용됐다"를 확인한다. 각인이 필요 없다고 판정한 시나리오에서 각인 transform이 붙어 있으면 그 검증 로직이 모순된 입력을 받는다.

### 근거
`contract-analysis-source-derived.md` §7.4.

### 권장 수정
happy에서는 `transform_ref`를 각인이 아닌 값(예: `"tr_h001_trim_v1"`)으로 바꾸거나 `null`로 둔다. 각인 경로는 `scenario_correction_rerun_001`(post_stamp.needed=true)에서 Report Video를 생성하도록 확장해 표현한다.

### 수정 범위
Fixture only | **Owner 확인:** `권장` (정철원·김준영)

---

## `[P2-4] ✅ 해소(2026-09-09 3라운드, 이슈 #19 원문 B절 재확인) — TimeResolution.considered[]에 base anchor 값을 event-time 후보처럼 나열`

> **정정 경위.** P2-3과 같은 경위(이슈 #19 B절 재발견)로 반영. "권장 수정"의 전자안(anchor+offset 계산값으로 교체)을 그대로 적용했다.

**관련 파일:** `data/mock/evidence/scenario_happy_001.json`
**Scenario:** `scenario_happy_001` | **Contract:** `TimeResolution` §6 | **Module:** evidence, web

### 현재 상태 (수정 전)
happy의 `considered[1]`이 `{source: recording.filename_time, value: "18:00:00", used:false, reason_code:"time.superseded_by_verified_overlay"}` — 사건 시각 후보들 사이에 파일 **시작 기준시각**이 섞여 5분 차이가 나는 것처럼 보인다.

### 조치
`considered[1].value`를 `candidate_h001.representative_ms`(312480ms=312.48s) 기준 anchor+offset 계산값 `2026-08-24T18:05:12+09:00`(초 절삭)으로 교체. `considered[]`에는 `computation` 필드가 없어 "이 값이 offset 계산을 거쳤다"는 것을 별도로 표시할 수 없다는 한계는 남지만, 05 자체가 이미 이 방식을 "후보 비교 화면 개발에 유용"하다고 권장했었다.

### 왜 문제인가
`considered[]`는 "evidence가 판정에 사용한 후보 요약"이며 consumer(웹 상세, eval 진단)가 후보 간 차이를 보여줄 수 있어야 한다. 기준 anchor를 그대로 넣으면 실제로 존재하지 않는 5분 불일치를 사용자에게 보여주게 된다. (u001은 `computation.mode=BASE_PLUS_OFFSET`이 anchor임을 설명하므로 문제가 아니다.)

### 근거
`contract-time-resolution.md` §6(최소 summary snapshot), §8(BASE_PLUS_OFFSET의 base 보존은 `computation.base_input_ref`가 담당).

### 권장 수정
happy `considered[1]`의 `value`를 anchor+offset으로 계산한 비교 가능한 값(`2026-08-24T18:05:12.48+09:00` 또는 초 절삭 `18:05:12`)으로 바꾸거나, 해당 항목을 빼고 `computation`에만 남긴다. 전자를 권장(후보 비교 화면 개발에 유용).

### 수정 범위
Fixture only | **Owner 확인:** `권장` (김준영)

---

## `[P2-5] ✅ 해소 — scenario_empty_001에 recording fixture가 없어 E2E 재생 불가`

**관련 파일:** `data/mock/scenarios/scenario_empty_001.json` · `data/mock/case/scenario_empty_001.json`
**Scenario:** `scenario_empty_001` | **Contract:** `CaseView.manifest_summary` · `RecordingTimeline` | **Module:** case, recording

### 현재 상태
`modules_intentionally_absent`에 사유가 적혀 있지만, `CaseView.manifest_summary`(파일 1개, 1800초, range)가 어떤 recording fixture로도 뒷받침되지 않는다.

### 왜 문제인가
1차 통합 harness가 "시나리오 로드 → 모듈별 stub 응답"으로 돌 때 이 시나리오만 recording stub 입력이 없어 별도 예외 처리가 필요하다. 빈 결과 경로는 오히려 recording→search 접합부가 정상일 때의 대조군이라 값어치가 있다.

### 근거
`contract-job-record-case-view.md` §6 `manifest_summary`는 등록된 영상 사실의 projection이다.

### 권장 수정
`recording/scenario_empty_001.json`을 최소 구성으로 추가(SourceAsset 1 · MediaStream 1 · RecordingTimeline 1 · TimeSourceCandidate 1). frame_refs·clip은 불필요(후보가 없으므로). `manifest_summary`를 그 timeline과 일치시킨다.

### 수정 범위
Fixture only + Scenario Manifest | **Owner 확인:** `불필요`

---

## `[P2-6] ✅ 해소 — scenario_correction_rerun_001에 정정 "전" CaseView 스냅샷이 없음`

**관련 파일:** `data/mock/case/scenario_correction_rerun_001.json`
**Scenario:** `scenario_correction_rerun_001` | **Contract:** `CaseView` | **Module:** case, web

### 현재 상태
`evidence`/`time_resolutions`/`requirement_reports`는 v1·v2 두 세대가 모두 있는데 `case_views`는 정정 **후** 1건뿐이다.

### 왜 문제인가
이 시나리오의 가치는 전이(`INFO_NEEDS_REVIEW` → `INFO_USER_CONFIRMED`)인데, web은 before를 볼 수 없어 전환 렌더링을 테스트할 수 없다.

### 권장 수정
`case_views`에 `case_rev:2` 스냅샷 추가: `evidence.record_id="ev_r001_v1"`, `event_time_display={value:"2026-08-27T13:15:30+09:00", needs_review:true, info_state:"INFO_NEEDS_REVIEW", source_label_key:"time.source.filename"}`, `requirements_evidence.readiness="WARN"`, `user_edited=false`.

### 수정 범위
Fixture only | **Owner 확인:** `불필요`

---

## `[P2-7] ✅ 해소 — 문서 수치 불일치와 문서 생성 스크립트의 절대경로 하드코딩`

**관련 파일:** `docs/mock/01_mock_dataset_overview.md` · `docs/mock/04_mock_validation_report.md` · `scripts/build_artifact_templates_doc.py`

### 현재 상태
- `01` §4: "아래 **5건**" 뒤에 항목 **7개**.
- `01` §9: "실제 JSON 파일 **26개**", `04` §5: "**26개** 실제 fixture" — 실제는 JSON 28개(모듈 fixture 21 + scenario manifest 4 + manifest 1 + eval 2).
- `scripts/build_artifact_templates_doc.py`: `ROOT = Path("/tmp/repo")` 하드코딩 → 다른 체크아웃에서 실행 불가.

### 권장 수정
숫자 정정(5→7, 26→"모듈 fixture 21개 + manifest 5개 + eval 2개 = JSON 28개"), 스크립트의 ROOT를 `Path(__file__).resolve().parents[1]`로 변경.

### 수정 범위
Mock Documentation + Validation | **Owner 확인:** `불필요`

---

## `[P2-8] ✅ 해소(01 문서에 명시) — crop_ref·track_ref·shared_ids가 어디에도 정의/검증되지 않음`

**관련 파일:** `data/mock/readout/*.json` · `data/mock/scenarios/*.json`
**Contract:** `PlateReadout`(crop_ref·track_ref) | **Module:** readout, 검증

### 현재 상태
`crop_h001_001` 등 crop_ref와 `track_h001` track_ref는 계약이 허용하는 opaque 값이지만 어떤 fixture에도 정의 객체가 없고, 문자열이라 검증 스크립트도 통과시킨다. scenario manifest의 `shared_ids`도 fixture와의 일치가 검증되지 않는다.

### 권장 수정
`crop_ref`/`track_ref`는 readout 내부 opaque로 남기되 `01_mock_dataset_overview.md`에 "정의 객체가 없는 opaque ref"임을 한 줄 명시(소비자가 찾아 헤매지 않게). `shared_ids`는 §11-3의 검증 규칙으로 커버.

### 수정 범위
Mock Documentation + Validation | **Owner 확인:** `불필요`

---

## `[P2-9] ✅ 해소(수치) · 근거 정정(김대원 답변) — AnalysisRun.usage_summary.processed_duration_ms가 scope 범위와 불일치`

**관련 파일:** `data/mock/search/scenario_happy_001.json` · `data/mock/common/scenario_happy_001.json`
**Scenario:** `scenario_happy_001` | **Contract:** `AnalysisRun.usage_summary` · `UsageRecord.processed_duration_sec`

### 현재 상태
scope는 20분(1200s)인데 `processed_duration_ms: 300000`(5분), `UsageRecord.processed_duration_sec: 300.0`. (계약 §3-4 예시의 값을 그대로 옮긴 결과로 보인다.) e001·u001은 30분/30분으로 일관된다.

### 왜 문제인가
`eval`의 `cost_per_source_video_hour`·`FP-hour` 분모가 이 값이다. happy만 실제 처리 범위와 4배 어긋나면 지표 검증 fixture로 쓸 때 잘못된 분모를 학습한다.

### 조치와 근거 (2026-09-09 2라운드 정정 — 이슈 #17 원문 재대조)
수치 정정(`1200000`/`1200.0`) 자체는 맞았지만, **05 1라운드가 적은 "이유"는 틀렸다** — 김대원의 실제 답변은 3단으로 구성된다.
1. `cost_per_source_video_hour`/`FP-hour`의 분모는 **`processed_duration`이 아니라 사건 timeline의 실제 길이**(중복 제거된 원본 영상 시간)다. happy는 전/후방 2개 `source_assets`가 같은 20분 사건을 2개 각도로 찍은 것이므로, 둘의 `duration_sec`를 더하면 2400초로 이중 계상되고, `VISUAL_VERIFY` run을 추가하면 재처리할수록 비용이 더 싸 보이는 정반대 유인이 생긴다.
2. `processed_duration` 자체는 **완전히 별개의 지표** — "이 영상이 실제로 몇 번 모델에 입력됐는가"를 추적하는 재처리 배수(reprocessing multiplier)이며, 비용 분모로 쓰지 않는다.
3. 비용 집계의 권위 있는 원천은 **`UsageRecord` 원장**이다(CALL-13 결정). 불변 스냅샷인 `AnalysisRun.usage_summary`를 집계 소스로 쓰지 않는다.

김대원은 이 규칙을 `missing_ranges`가 있는 시나리오(처리 범위와 scope 길이가 정당하게 어긋나는 경우)에는 **일괄 적용하지 말라**고 명시적으로 경고했다.

### 수정 범위
Fixture only(수치는 이미 반영 완료) | **Owner 확인:** `해소` (김대원 — 분모 정의 확정)

---

### P3

---

## `[P3-1] ✅ 해소 — budget(KRW) vs cost(USD) 통화 혼용으로 예산 소진 판정을 mock으로 개발할 수 없음`

> **2026-09-09 갱신 (팀 리뷰 이슈 #19, common/runtime 답변 · 이슈 #15 search가 동일 문제 재확인).** 환산 규칙 자체는 답이 왔다 — 예산 판정의 authoritative source는 `UsageRecord`(`AnalysisRun.usage_summary`는 파생 summary), `UsageRecord.cost`는 **저장 전에 KRW로 정규화**해 `currency="KRW"`로 기록하고 환율/요율 provenance는 `pricing_id`가 가리키는 versioned pricing artifact가 보존한다. 현재 `max_cost_krw=300`과 USD 비용 조합은 이 규칙으로도 "happy로 승인 불가"라고 명시적으로 지적됐다.
>
> **2026-09-09 4차 라운드 갱신 (fixture 반영).** `docs/modules/case/decisions/budget-krw-normalization.md`에 mock 환율 placeholder(1 USD=1400 KRW, `pricing_id` 접미사 `+fx-krw-2026-09`)와 변환표를 등재하고, 5개 기존 시나리오의 `common/*.json` `SEARCH_COARSE` `UsageRecord.cost`를 전부 KRW로 정규화했다(588/546/532/462/434 KRW). `AnalysisScope.budget.max_cost_krw` 기본값을 `300`→`1000`으로 올렸다(계약 §6이 "제품 기본 숫자는 benchmark/config 관리"라고 명시해 case Owner 권한 범위 안). 이후 라운드에서 추가된 `VISUAL_VERIFY`(Fine) run 비용도 전부 이 규칙(KRW 정규화)을 따라 예산(1000 KRW) 안에 들어온다.

**관련 파일:** `data/mock/search/*.json` · `data/mock/common/*.json`
**Contract:** `AnalysisScope.budget.max_cost_krw` · `UsageRecord.cost` · `AnalysisRun.usage_summary.total_cost` | **Module:** case, eval

### 현재 상태
모든 scope가 `max_cost_krw: 300`인데 gemini 호출 비용은 `{"amount":"0.42","currency":"USD"}`(≈560원) 등으로, **네 시나리오 모두 예산을 초과한다**(0.42/0.39/0.33/0.31 USD).

### 왜 문제인가
`case`는 `UsageRecord`로 "예산 소진 판정"을 해야 하는데, 통화가 다르고 환산 규칙이 어느 계약에도 없다. 지금 fixture로 판정 로직을 짜면 전부 초과로 나온다.

### 근거
`contract-analysis-scope.md` §6(`max_cost_krw`), `contract-usage-record.md` §2(case = 예산 소진 판정), 두 계약 모두 환산 규칙을 정하지 않는다. **계약 예시 자체가 KRW·USD를 섞어 쓴다**(UsageRecord 예시는 KRW 184.20, AnalysisRun 예시는 USD 0.42) → **Upstream 확인 필요**.

### 권장 수정
fixture 값을 임의 환산하지 말고, ① `04_mock_validation_report.md`에 "예산 단위(KRW)와 비용 단위(USD)의 환산 규칙 부재 — case의 예산 판정 구현 불가" 항목을 추가하고 ② 유소연·김준영 확인 후 정해지면 그때 fixture를 맞춘다. 임시로 `budget.max_cost_krw`를 실제 비용과 모순되지 않는 값(예: 1000)으로 올리는 것도 가능하나, 이는 제품 기본값 문제라 Owner 판단이 먼저다.

### 수정 범위
Mock Documentation + Upstream 확인 필요 | **Owner 확인:** `필수` (유소연·김준영)

---

## `[P3-2] ⏳ 미착수(통합에 지장 없음) — 값의 "너무 깔끔함"과 소소한 비현실성`

**관련 파일:** 전 fixture

- 후보가 모든 시나리오에서 **1건**이라 `rank` ordering·Recall@K를 검증할 수 없다(개선 가치는 P2급이나, 해소는 §10의 다후보 fixture로).
- 검색 종료(18:21:10) 후 사용자 후보 선택까지 5초(18:21:15)로 사람의 검토 시간이 없다.
- `model_ref: "gemini-3.7-flash"`는 실재하지 않는 모델명이다(계약 예시에서 온 것이므로 그대로 두어도 무방).
- IncidentClip의 bitrate가 원본의 절반(0.29 vs 0.58 MB/s)이라 "잘라낸 클립"보다 재인코딩에 가깝다.

**권장:** 후보 다건화만 §10에서 처리하고 나머지는 그대로 두어도 통합에 지장 없다. | **Owner 확인:** `불필요`

---

## 9. 중복 / 정리 후보

**삭제·통합 후보: 거의 없다.** 이 pack의 문제는 중복이 아니라 결손이다.

| 항목 | 판단 |
| --- | --- |
| 4개 시나리오 | **모두 유지.** 서로 다른 코드 경로를 검증하며 값만 바꾼 복제가 없다 |
| `scenario_unknown_abstain_partial_001`의 6유형 동시 수용 | **분할하지 않는다.** 6유형이 서로 다른 계약을 건드려 실제로 얽히지 않고, 분할하면 시나리오 수만 늘어난다 |
| `docs/mock/CONTRACT_CONFLICTS.md` | **유지.** `04`의 인덱스 역할이 명확하고 지침이 이름으로 요구한 파일이다. 단 `04`와 내용이 이중 관리되므로 항목 추가 시 **양쪽 동시 갱신**을 §14 체크리스트에 넣는다 |
| `eval_fixture_correct_001`의 `actual_value` 복사 | 참조로 바꾸는 대신 동기화 검증 규칙 추가로 해결(§11-4) |
| `data/mock/validate_mock_pack.py` 위치 | `scripts/`로 옮기는 편이 데이터/코드 분리에 낫지만 **지금 옮길 필요는 없다**(경로 참조가 문서 여러 곳에 있다). P3 |

---

## 10. 추가하면 가치가 높은 Fixture

모두 기존 Contract/제품 문서에서 필요성이 도출되며 새 Product Requirement를 만들지 않는다.

| # | 이름(안) | 커버하는 것 | 근거 | 우선도 |
| --- | --- | --- | --- | --- |
| 1 | `scenario_blocked_001` | `RequirementReport.overall=BLOCK`(번호판 식별 불가) · `notices[].blocking=true` · `severity=ERROR` · `ReportPackage` 미생성 | `contract-requirement-report-package.md` §4.2의 BLOCK 정의 예시가 정확히 이 상황 | **높음** (P1-9) |
| 2 | `scenario_relative_rebase_001` | `timeline_status=USABLE_RELATIVE_ONLY` · `AnalysisScope.kind=TIMELINE_RELATIVE` · `revision 2` rebase · `gaps≠[]` · `SpanResolution.PARTIAL` | `contract-analysis-scope.md` §7 · `contract-recording-timeline-asset-span.md` §5·§9·§10 | **높음** (P1-10) |
| 3 | `scenario_infra_failure_001` | `ReadoutRun.FAILED(INFRA)` · `JobExecution.STALE` → `attempt 2` · 결과 미생성 | `contract-job-execution.md` §8·§9-2 · readout taxonomy `INFRA` | **높음** (P1-12) |
| 4 | `scenario_purge_001` (또는 happy에서 분리) | `DeletionReport` 후 `availability=UNAVAILABLE` 상태 · purge 이후 `CaseView` | `contract-analysis-source-derived.md` §8 | 중 (P1-1) |
| 5 | happy 내 **다후보** 확장 | `rank` 2·3, `Recall@K`·`Final Recall@3`, 사용자가 1순위가 아닌 후보를 고르는 경로 | `contract-analysis-run-candidate-event.md` §4(rank가 ordering authoritative) · `core-user-flow.md` §9(다른 후보 선택 시 재판독) | 중 |
| 6 | `MOTORCYCLE_HELMET_NON_USE` 사건 1건 | 4종 중 유일 미커버 유형 · `temporal_facts=[]` 정상 경로 · `HELMET_ON_RIDER` primitive | `contract-visual-evidence.md` §4-2·§7 | 중 (P0-1 수정 시 동시 달성 가능) |
| 7 | hard-negative `VisualEvidence` (`verification=NOT_OBSERVED`) | `HN-FPR` metric 입력 · 후보 기각 경로 | `contract-visual-evidence.md` §4-1 · `modules/eval/experiment-guide.md` `[CASE] hard-negative` | 중 |
| 8 | Report Video export 실패 | `REPORT_VIDEO_EXPORT_FAILED` → `CaseView.notices[].code` | `contract-analysis-source-derived.md` §7·§9 | 낮음 |

**권장 최소 세트**: 1·2·3 (P1 해소에 직결) + 6은 P0-1 교체 과정에서 자연히 얻는다.

---

## 11. Validation 개선 제안

현재 스크립트는 `{kind, ref}` 형태만 검사한다. **문자열 ref는 전부 사각지대**다. 아래는 지금 PASS하지만 잘못될 수 있는 것들이다.

| # | 규칙 | 지금 왜 못 잡나 | 잡아야 할 실제 오류 |
| --- | --- | --- | --- |
| 1 | **문자열 ref 해석 검사** — `thumbnail_ref` · `best_frame.frame_ref` · `frame_results[].frame_ref` · `samples[].frame_ref` · `preview_ref` · `thumb_ref` · `scope_ref` · `usage_refs[]` · `JobExecution.job_id` · `ReadoutRun.usage_refs[]` · `CaseView.evidence.record_id` · `package.package_ref` · `artifact_ref` · `time_source_candidates[]` · `media_stream_refs[]` · `source_candidate_ref` | `{kind,ref}` 형태가 아니라 walk 대상에서 빠짐 | Job↔Execution↔Usage 체인 끊김, 존재하지 않는 frame 참조 |
| 2 | **ref kind ↔ 대상 타입 대조** | ID registry가 종류 구분 없이 평면이라 `{kind:"incident_clip", ref:"sa_h001_front"}`도 통과 | 잘못된 종류의 객체 참조 |
| 3 | **manifest / scenario manifest 자체 검증** — `manifest.json`의 `manifest_ref`·`eval_fixtures` 경로 실존, `scenario_types` ↔ 카탈로그 일치, `shared_ids`가 실제 fixture에 존재 | 현재 scenario manifest의 `artifacts`만 검사 | manifest drift |
| 4 | **`expected/` fixture 검증** — `actual_ref`가 실존하는지, `actual_value`가 참조 대상의 실제 값과 **일치/불일치 중 의도한 쪽인지** | `expected/`가 scenario_docs에 안 들어가 refs를 아예 안 봄 | P1-11(자기모순 eval fixture) |
| 5 | **시간축 파생값 재계산** — `anchor + representative_ms == occurred_at`(DIRECT/BASE_PLUS_OFFSET일 때), `samples[].offset_sec`가 clip `[0, duration]` 안, `AssetSpan.source_range` 길이 == `timeline_range` 길이 | 현재는 thumbnail_ref만 검사 | P1-5(좌표계 혼용) |
| 6 | **enum 확장** — `VisualEventType`(4종) · `verification` · `association_status` · `primitives[].state` · `DeletionReport.status`/`items[].result` · `timeline_status` · `SpanResolution.status` · `RequirementCheck.category`/`outcome` · `info_state`(5종) · `progress[].state` · `notices[].severity` · `TimeSourceCandidate.source_kind` · `ReadoutRun.failure.kind`(taxonomy 파일에서 로드) | 5개 enum만 검사 | **P0-1을 즉시 잡을 수 있었다** |
| 7 | **필수 키 존재 검사(계약 단위)** — 최소한 `VisualEvidence`의 `uncertainties`·`legal_status`(그리고 `legal_status is None`), `Observation` 5키, `AnalysisRun` 10키, `SpanResolution.failure` 키 존재 | 배열 키 존재만 검사 | **P0-2를 즉시 잡을 수 있었다** |
| 8 | **조건부 불변조건** — `verification!=OBSERVED ⇒ visual_event_type is None` · `availability=AVAILABLE ⇒ byte_size!=None` · `abstained ⇒ observation.status=="NEEDS_REVIEW"` · `TimeResolution.status=="UNKNOWN" ⇒ resolved 부재` · `EvidenceValue.user_corrected & needs_review 동시 true 금지` · `value is None ⇒ needs_review False` · `duration/timeline_range 쌍` · `RequirementReport.overall == precedence(checks)` | 없음 | P1-7, 향후 회귀 |
| 9 | **consensus/마스킹 일관성** — `disagree_positions`의 각 index가 `frame_results` 간 실제 불일치 위치와 일치하고 `observation.value`의 `?` 위치와 같은지 | 없음 | **P1-4를 즉시 잡을 수 있었다** |
| 10 | **cross-scenario ID 유일성** — 같은 ID가 두 시나리오에 나타나면 경고 | 시나리오별로만 registry 구성 | 시나리오 간 오염 |
| 11 | **문서 동기화** — `03_mock_artifact_templates.md`를 재생성해 diff가 없는지 CI에서 확인 | 없음 | 문서-데이터 drift |

**구현 순서 권장:** 6 → 7 → 1 → 8 → 9 → 4 → 5 → 3 → 10 → 11. 6·7만 넣어도 이번에 발견한 P0 2건이 자동으로 걸린다.

---

## 12. Owner별 남은 검수 항목

기계적으로 판정 가능한 것은 §8에서 전부 처리했다. 아래는 **도메인 판단이 필요해 사람이 봐야 하는 것만** 남긴 목록이다.

| Owner | 반드시 직접 확인할 것 | 이유 | 관련 Fixture |
| --- | --- | --- | --- |
| **신유민** (readout) | ~~① 「화면 시각 없음」을 `observation.status`의 `NOT_APPLICABLE`로 볼지 `UNKNOWN`으로 볼지 (P0-4)~~ → **종결(2026-09-09, 이슈 #16): `NOT_APPLICABLE`(없음=사실)로 확정, fixture 반영 완료(잠정 — 실사용 false-negative 비율에 따라 `UNKNOWN` 쪽으로 조정 가능성 있음을 신유민이 명시).** ~~② overlay 실행 실패 시 쓸 taxonomy kind/code (P1-12)~~ → **종결·정밀화(2026-09-09 3라운드, 이슈 #16 원문 재대조): `OVERLAY_DETECTION` 완전 폐기, `INFRA`만 유효(코드 3종: `READOUT_PROVIDER_TIMEOUT`/`READOUT_FRAME_ACCESS_FAILED`/`READOUT_PIPELINE_ERROR`), `OVERLAY_VALIDATION`은 run 실패가 아니라 사후 결과임을 확인** — `abstain_reason` 값 공간(`TARGET_AMBIGUOUS`/`FRAME_DISAGREEMENT`/`LOW_RESOLUTION`/`OCR_LOW_CONFIDENCE`, 우선순위 association>frame-consensus)은 신유민이 `failure-taxonomy.md`에 직접 등재 예정(아직 미푸시, 이슈 #26 A절에서 재확인) — ~~`scenario_infra_failure_001` fixture 자체는 아직 미생성~~ → **종결(2026-09-10, 이슈 #16/#26 반영): `READOUT_PROVIDER_TIMEOUT` INFRA 실패로 신설, plate attempt 1(STALE)·2(FAILED) + overlay run 추가, `processed_duration_sec` null 정정·`READOUT_PLATE`/`READOUT_OVERLAY_TIME` 연산명 정정, 이 fixture가 「1 execution : ReadoutRun 1건」 불변조건의 STALE 예외(신유민·유소연 공동 제안) 최초 반례로 계약에 등재됨** ①-2(신규, 이슈 #26 B-readout-4) overlay `UNKNOWN` 갈래(`observation.status=UNKNOWN`, `reason.code=readout.overlay.presence_undetermined`) — **종결(2026-09-10): 같은 시나리오 안에 `rr_x001_overlay` 추가로 반영, 파일 추가 없음** ①-3(신규, PR #27 `failure-taxonomy.md` 리뷰 요청, 2026-09-10) 「실패가 아닌 상태」 2행이 `CaseView`에 notice로만 알려지고 `progress`를 FAILED로 내리지 않는다는 전제 확인 요청 — **전제는 이미 맞게 구현돼 있었다(`scenario_infra_failure_001` rev1부터 `progress[overlay_time_read].state=DONE`, FAILED 아님) — 다만 「없음」(`NOT_APPLICABLE`) 쪽만 notice(`readout.overlay_not_present`)가 있고 「확인 못함」(`UNKNOWN`) 쪽 notice가 빠진 비대칭을 발견해 종결: `{code:"readout.overlay_presence_undetermined", severity:"INFO", blocking:false}`를 `scenario_infra_failure_001` rev1·rev2 `notices`에 추가** | 두 상태 구분 기준·taxonomy 값 모두 답변 완료. `scenario_infra_failure_001`도 완성됐고 PR #27 리뷰 요청 2건(taxonomy 등재 확인·notice 구현)도 재확인해 후자에서 실제 누락을 찾아 고쳤다 — 남은 건 신유민 쪽 `failure-taxonomy.md` 머지뿐 | `readout/scenario_unknown_abstain_partial_001.json`(완료)·`scenario_plate_reread_001.json`(완료, B-1 프레임 불일치 폭 수정 포함)·`scenario_correction_rerun_001.json`(완료, overlay NOT_RUN→NOT_APPLICABLE 재구성)·`scenario_infra_failure_001`(완료, 2026-09-10) |
| **신유민** (web/CaseView 소비, 2차 코멘트) | ~~① `notices[].code` 대소문자 표기~~ → **종결(2026-09-10, 이슈 #26 A-⑤): dotted-lowercase `<producing-module>.<detail>` 확정, `time.*` 4종을 근거 모듈 기준으로 재정정(`evidence.*`/`readout.*`), `JobExecution.failure_kind`→`notices[].code` 매핑 규칙도 계약 A절 §7에 등재(SCREAMING_SNAKE를 그대로 복사하지 않음)** ~~② `actions[]` 값 공간~~ → **종결(2026-09-10, 이슈 #26 A-⑥): 5종(`RETRY_PLATE_READ` 포함) 확정, 값→발주 매핑표 신설, 미등록 값은 버튼 미노출(fallback)** ③ `candidates==[]`일 때 진행바 4단계 회귀 — **미해결 항목 아님**(web 스스로 파생, 확인만 남음) ④ `plate_display.needs_review=false` vs `info_state=INFO_UNKNOWN` — **미해결 항목 아님**(계약 불변조건 12로 이미 해소) — **(3차 코멘트, 이슈 #26 B-web 추가분)** ⑤ `stale_revision` 표시 label_key 부재 → **종결(2026-09-10, B-web-8): `stale_revision_label_key` 신설, 등록값 `candidate.stale_timeline_revision`** ⑥ happy_001 rev4에서 미확정 위치가 그대로 신고자료에 실림(B-web-5) → **종결: `package.unconfirmed_fields` 신설 + `CaseView.evidence.review_needed`를 true로 정정** ⑦ `review_needed` 파생 규칙이 `location_display`(needs_review=false + info_state=NEEDS_REVIEW) 케이스를 못 잡음(B-web-6) → **종결: OR 공식에 `info_state==INFO_NEEDS_REVIEW` 포함하도록 재정의** ⑧ 재시도 job의 대표 상태 규칙 없음(B-web-7) → **종결: 「대표 execution = attempt 최댓값」+ STALE 억제 정책 계약 등재** ⑨ `plate_reread_001`의 notice·`running_jobs` 중복(B-web-9) → **종결: `evidence.plate_reread_in_progress` notice 제거, `running_jobs`를 정본으로** | ①②⑤⑥⑦⑧⑨는 유소연(case)이 이슈 #26에서 전부 결정·계약 등재 완료, ③④는 신유민이 자체 확인해 닫은 항목(기록용) | `contract-job-record-case-view.md`, `docs/modules/case/decisions/candidate-stale-revision-display.md` |
| **서어진** (search) | ~~① `VISUAL_VERIFY` run의 `input_ref` 종류·직렬화 형식 (P0-3, P1-3)~~ → **종결(2026-09-09, 이슈 #15): `input_ref.kind=analysis_source`(`as_h001_fine` 등) 확정, `ContractRef {kind, ref}` 직렬화·`evidence_refs[]`의 `fr_<opaque-id>` 형식은 mock 현행 그대로가 맞다고 확인** — **fixture 반영 완료(2026-09-09 4차 라운드): happy·u001·plate_reread·correction_rerun 4개 시나리오에 `run_*_fine`(`VISUAL_VERIFY`) 추가, `ve_*.run_id` 재연결, `as_h001_fine` 고아 해소** ~~② `ve_u001`을 `UNCERTAIN`으로 내릴지 (P1-7)~~ → **종결·반영 완료(2026-09-09, 이슈 #15): `UNCERTAIN`/`visual_event_type=null`로 전환, `Uncertainty.kind`도 `SIGNAL_STATE_NOT_CLEARLY_VISIBLE`로 통일** ③ candidate 1건 고정/`rank` 항상 1 — search가 신고, 낮은 우선순위(eval 붙을 때 처리) — **(2차 검수, 이슈 #23 추가분)** ④ `contract-visual-evidence.md` 예시가 stale(§2 예시 `input_ref`가 평문 string, `evidence_refs`가 위치 인코딩) → **종결(2026-09-10, 이슈 #23 A): `input_ref`를 `{kind, ref}` 구조체로, frame ref를 `fr_<opaque-id>`로 갱신. `visual-evidence/v1.0` 유지** ⑤ search `usage_summary.total_cost`가 USD로 남아 원장(KRW)과 라벨 불일치(B-1) → **종결: 6개 시나리오 전부 KRW로 정규화(값은 원래도 정합)** ⑥ Fine 단계 `AnalysisRun.input_ref`(`analysis_source`)와 `VisualEvidence.input_ref`(`incident_clip`)가 다른 자산을 가리킴(B-2) → **종결(2026-09-10, 이슈 #35): 서어진이 RT7 재확인을 마치고 `VisualEvidence.input_ref`를 `analysis_source` 기준으로 맞추기로 확정 — search·case fixture 4개 시나리오 전부 반영 완료** ⑦ `ANALYSIS_SCOPE`→`analysis_scope` 소문자 통일 제안(B-3) — **반려**: 이미 확정된 ADR(`adr-data-contract-call-closure-2026-09-08` §6)과 충돌. 서어진에게 회신 필요 | ①②④⑤⑥은 종결, ⑦은 반려 회신 대기 | `search/*.json`(u001·plate_reread·`VISUAL_VERIFY` 4건 전부 반영 완료), `contract-visual-evidence.md`, `docs/modules/case/decisions/budget-krw-normalization.md` |
| **김준영** (evidence/PM) | ~~① Mock이 신설한 미등재 `source.kind` 5종 승인/교체 (P1-2)~~ → **종결(2026-09-09, 이슈 #19): 5종 전부 승인** — `recording.file_metadata_time`(OBSERVED, `time.source.file_metadata`) · `case.user_location_hint`(OBSERVED, `location.source.user_hint`) · `evidence.category_mapping`(INFERRED, `event.source.category_mapping`) · `evidence.violation_expression`(INFERRED, `event.source.violation_expression`) · `case.user_correction`(TimeResolution 전용, `time.source.user_correction`). fixture 재확인 결과 5개 값 전부 이미 이 형태로 쓰이고 있어 **fixture 변경 불필요** — **evidence 소유 versioned registry 문서화 완료(2026-09-09 4차 라운드): `docs/modules/evidence/decisions/source-kind-registry.md`** ② `safety_report_type` 값 공간 — ~~답변은 왔으나 미승인 상태로 확정(이슈 #19): 현 `UNSAFE_LANE_CHANGE` 등은 canonical enum이 아니라 placeholder라고 명시적으로 반려~~ → **종결(4차 통합, 2026-09-10): 김준영이 `docs/modules/evidence/decisions/safety-report-policy-v1.md`(`safety-report-policy/v1`, ACCEPTED)로 versioned registry 확보 — 내부 code 2종(`TRAFFIC_VIOLATION`/`MOTORCYCLE_VIOLATION`) + `VisualEventType`→`SafetyReportType`→기본 `violation_expression` 4종 매핑 + template 2종(`tmpl/safety-report-specific-v1`/`tmpl/safety-report-generic-v1`) + `USER_UNSURE` fallback 규칙까지 전부 확정. case가 전 evidence/case fixture(h001·r001·p001·u001)를 이 registry로 정규화 완료(`UNSAFE_*`·한국어 label 제거, `needs_review`/`unconfirmed_fields` 정합 맞춤) — Required-6 종결.** ③ ~~`plate_visible` check의 category (P2-2)~~ → **종결(2026-09-09, 이슈 #19): `category=VEHICLE`·`code=package.vehicle.plate_visible_in_report_video` 확정, `AssetFacts` 보강 완료** ④ ~~좌표 필드명 `lat/lon` 통일 및 `address` provenance (P1-6)~~ → **규칙은 종결(2026-09-09, 이슈 #19): canonical 좌표 키 `{lat, lon}`(`contract-observation.md`의 `{lat, lng}` 예시가 갱신 대상) 확정, `address`는 versioned reverse-geocode artifact 없이 임의 생성 금지** — **`coord`는 fixture 반영 완료(2026-09-09 4차 라운드): happy에 GPS 있음(OBSERVED)·u001에 GPS 없음(UNKNOWN), `location.coord`/`location_display.coord` 채움.** `address`는 여전히 versioned reverse-geocode artifact가 없어 **미착수**(mock 작업 범위 밖 — 실제 지오코딩 데이터 필요) — 그 결과 `location_display.info_state`는 규칙(§7-(3))상 여전히 `INFO_NEEDS_REVIEW` ⑤ ~~`VisualEvidence.verification=UNCERTAIN`일 때 `EvidenceRecord`를 만드는가?~~ → **종결(2026-09-09, 이슈 #19): 못 만든다(`event`가 필수 필드) — 이 결론이 `scenario_unknown_abstain_partial_001`/`scenario_plate_reread_001` 시나리오 분리로 이어졌다** ⑥ `EvidenceNeeds`(v1)에 "AI가 사건 유형 자체를 확정 못함"을 표현할 새 kind를 신설할지 — **fixture 레벨에서 해소(2026-09-10, 이슈 #25 A절, 김준영 답변): 신규 `kind` 만들지 않고 `event.visual_event_type.value=null`을 제한적으로 허용, `scenario_unknown_abstain_partial_001`을 이 값으로 재구성해 EVIDENCE/FINAL_PACKAGE WARN → `stage=READY` 경로까지 실증**(`docs/modules/case/decisions/generic-warn-package-and-situation-response.md`). `contract-evidence-record-needs.md` §3 스키마 자체("event는 필수")에 이 null 허용을 명문화하는 것은 여전히 evidence 소유 잔여 작업 | 전부 evidence가 소유한 값 공간·정책 판단이다. ①③⑤⑥은 문서화·fixture까지 완료, ④는 `coord`만 완료. **②(안 됨)·④의 `address`(reverse-geocode artifact 필요)·⑥의 계약 문구 정식 등재는 여전히 열려 있다 — mock이 임의로 채울 수 없는 항목** | `evidence/*.json`, `04_mock_validation_report.md` §3.1-4, `docs/mock/CONTRACT_CONFLICTS.md` 항목 4 |
| **유소연** (case, mock pack v3 전체 owner) | 1~2라운드 8건(① `FINE_VERIFY`/② `REPORT_VIDEO_EXPORT`·`purge_case`/③ u001 scope/④ `review_needed` OR 집계/⑤ `notices[].code` dotted-lowercase/⑥ `actions[]` 5종 닫음) — **전부 종결(§26 A-⑤⑥ 포함).** ~~⑦ `progress[].step` 2·3단계 대응 값 없음~~ → **종결(2026-09-10): 원래 갭이 아니었다 — `progress[]`는 `core-user-flow.md` §3-2가 "AI 분석 진행 전용"으로 못박은 필드이고, 2단계("사건 설명")·3단계("범위 확인")는 AI job이 아니라 사용자 입력 단계라 대응 값이 없는 게 맞다. web이 `hints`/`manifest_summary` 존재로 "완료"를 파생하는 것도 §3-2 위반 아님(정보 상태-작업 상태 혼용이 아니라 사용자 입력 여부 확인). 신규 step 추가 불필요, 계약에 이 설계 근거를 명문화했다.** ~~⑧ `progress[].state`가 "부분 완료"/"중단" 표현 못함~~ → **완전 종결(4차 통합, 2026-09-10): "부분 완료"는 `PARTIAL`(기존, `AnalysisRun.outcome=PARTIAL` 투영). "중단"은 `job-execution/v1.1`에서 `JobExecution.status`에 `CANCELLED` 신설(이슈 #33 A-2, case 통합 초안·김준영 PR 리뷰 확인 대상) 후 새 enum 값 없이 기존 `PARTIAL`로 흡수(`CANCELLED→PARTIAL` projection 등재, `case-view/v1.3`) — `CONTRACT_CONFLICTS.md` 항목 9 종결. `PARTIAL`(부분 완료/중단 둘 다)을 보여주는 demo fixture는 Should-1(비차단)로 유보돼 있었으나 **2026-09-12 11차 갱신에서 완료** — `scenario_infra_failure_001`에 `CANCELLED→PARTIAL` 경로(`job_x001_plate_reread`/`exec_x001_plate_reread`, `CaseView rev3`) 데모를 추가해 종결했다(`04` §1·§12 row 9 갱신 참고).** **(신규, 2026-09-10 v3 라운드, 이슈 #22/#23/#25/#26 종합) 이번 라운드에 새로 결정·등재한 것**: `situation_confirmation`·`package.unconfirmed_fields` 신설(#25) · `candidates[].stale_revision_label_key` 신설(#26) · `review_needed` OR 공식에 `info_state==NEEDS_REVIEW` 포함(#26) · 「대표 execution = attempt 최댓값」+ STALE 억제 정책(#26) · `REPORT_VIDEO_EXPORT_FAILED`→`notices[].code` 매핑 정정(#26) · `contract-job-execution.md`/`contract-job-record-case-view.md`의 STALE 예외 조항(공동, 신유민과) · eval 참값 라벨 2건 확정 + STALE attempt `UsageRecord` 컨벤션 확정(#22, `contract-usage-record.md` 정식 등재는 김준영 잔여) · `contract-visual-evidence.md` stale 예시 정정(#23 A, 서어진 소유지만 계약 문구 자체를 이번에 같이 갱신) · search `usage_summary` KRW 정규화(#23 B-1) · `progress[].step` 범위 확정(⑦) · `progress[].state=PARTIAL` 등재(⑧ 부분) | ⑦은 완전 종결, ⑧은 "중단"만 김준영 확인 대기로 남았다. 나머지는 이번 라운드에 전부 계약·fixture·결정 문서에 반영했다 | `case/*.json` 전체, `contract-job-record-case-view.md`, `contract-job-execution.md`, `contract-visual-evidence.md`, `docs/modules/case/decisions/*.md`, `docs/mock/CONTRACT_CONFLICTS.md` |
| **정철원** (recording) | ~~① GPS Observation을 recording이 어떤 단위·주기로 내는지 (P1-6)~~ → **종결(2026-09-09, 이슈 #18): 원시 고정주기 로그가 아니라 요청된 사건 시각마다 `Observation<Coordinate>` 1개, `{lat,lon}` 십진도, `source.kind="recording.gps_stream"`, `support_refs`에 관련 `FrameRef`, `produced_by.module="recording"`. 부재/무효 시 `value:null, status:"UNKNOWN", reason.code:"recording.gps.source_absent"`. 샘플링 주기는 기기/포맷 의존 구현 세부사항이라 의도적으로 고정하지 않음. happy에는 정상 GPS Observation, u001에는 부재/UNKNOWN 배치 예정** ~~② `scenario_relative_rebase_001`의 gap/rebase 서사와 `missing_ranges[].reason` 값 (P1-10)~~ → **종결(2026-09-09, 이슈 #18): 전체 메커니즘 확정** — 절대시각 파싱 불가한 파일로 revision 1(`working_anchor.status=UNKNOWN`, `timeline_status=USABLE_RELATIVE_ONLY`, `time_source_candidates=[]`) 생성 → Search가 revision 1 기준 Candidate 생성(이후 revision에도 불변) → 두 번째 SourceAsset 추가로 revision 2 생성, 두 소스의 usable 구간 사이에 의도적으로 30초 공백 유지(revision 1 보존, 덮어쓰지 않음) → 그 공백을 가로지르는 `resolve_span()`은 `status:PARTIAL`, `failure:null`, 해석 가능한 edge는 `spans[]`, 내부 30초 공백은 `missing_ranges[]` 1건(`{timeline_range:{start_sec:600.0,end_sec:630.0}, reason:"TIMELINE_GAP", source_ref:null}`) — `TIMELINE_GAP`(내부 공백) vs `OUT_OF_TIMELINE_RANGE`(요청이 바깥 경계 초과)의 구분이 이걸로 확정됨. `SpanResolution.FAILED`·recording 실패 taxonomy는 이 시나리오 범위 밖(별도 infra 시나리오용으로 남김) — **양쪽 모두 fixture 반영 완료(2026-09-09 4차 라운드): GPS는 happy/u001 recording에 `gps_observations` 추가, rebase/gap은 신규 `scenario_relative_rebase_001`(유형 K) 전체 빌드** GPS 스키마·gap/rebase 서사 모두 recording 소유 판단이었고 fixture까지 전부 반영됐다. **(신규, 2026-09-10 v3 라운드) 정철원 확인 대기 — provisional로 표시만 해둠**: ③ `scenario_unknown_abstain_partial_001`에 u001의 `REPORT_VIDEO_EXPORT` job 신설에 맞춰 `derived_assets`(`da_u001_report_video`·`da_u001_plate_image`)·`asset_facts`를 `da_h001_*` 패턴 그대로 확장해 채워 넣음 — 실제 값(길이 비례 산정 등)은 recording Owner 확인 전까지 provisional ④ `scenario_infra_failure_001`에 그동안 없던 `incident_clips`(`clip_x001`, 30.0s) 신설 — overlay UNKNOWN readout이 참조할 대상이 fixture에 아예 없어서 validator가 `DANGLING_STRING_REF`로 잡았던 것을 고치며 추가, duration 값은 정철원 확인 전까지 provisional | GPS·gap/rebase는 완료, ③④는 case가 recording 패턴을 그대로 따라 채웠지만 recording Owner 확정 필요 | `scenario_relative_rebase_001`(신규 6개 파일), `recording/scenario_happy_001.json`+`scenario_unknown_abstain_partial_001.json`(GPS Observation), `recording/scenario_unknown_abstain_partial_001.json`+`scenario_infra_failure_001.json`(신규 provisional) |
| **김대원** (eval) | ~~① metric 이름·정답 라벨 확정과 `expected/` 재작성 (P1-11)~~ → **근본원인·개명 확정(2026-09-09 3라운드, 이슈 #17): 채점 모델을 구간+유형 IoU 매칭으로 교체, `recall_at`/`plate_exact_match_rate`(유지)/`abstention_recall`+`wrong_accept_rate`(분리)/`timestamp_error_sec`로 개명, GT에 `legibility:READABLE|UNREADABLE` 신규 필수.** `data/mock/expected/` 실제 재작성은 김대원이 별도 PR로 진행("확정 전에 이 이슈에 먼저 올리겠다") — **case Owner가 손댈 fixture 아님** ~~② `processed_duration` 분모 정의 (P2-9)~~ → **종결(2026-09-09 3라운드, 이슈 #17)** cp949 인코딩 버그 제보는 `validate_mock_pack.py`에 반영 완료(별건, 신유민도 동일 이슈 독립 제보) **(신규, 2026-09-10 v3 라운드, 이슈 #22) B-1~B-4**: ③ `expected/` 스키마를 `readout_ref`/`resolution_ref`/`timeline_ref` 참조 방식(`eval-expected/v2`)으로 재작성 — **김대원 자기 소유 작업, case는 `data/mock/expected/` 미터치로 동의만 함** ④ `CandidateEvent.span`이 coarse 후보 창인지 사건 구간인지(B-2) — **case가 결정할 사안 아니라 서어진(search) 답 대기, `CONTRACT_CONFLICTS.md` 신규 등재, fixture 미변경** ⑤ 참값 라벨 2건(B-3) → **종결: `plate_reread_001` 실제 번호판 `17나2867`(두 프레임 추정 모두와 다르게 골라 abstain이 옳았음을 재확인) 확정, `unknown_abstain_partial_001`은 참값 없음(`scoring:EXCLUDED`, 시나리오 자체가 "AI가 사건 유형을 확정 못함"을 표현하려고 설계된 것이라 정답 부여 시 설계와 모순) — 둘 다 fixture 변경 불필요, `eval-round2-ground-truth-and-usage.md`에 근거.** `plate_reread_001` 재판독 완료 후 상태 신설 계획도 확인 요청 → **답변 당시엔 "다음 라운드"였으나 같은 날 후속으로 완결: `case_rev:4`에 재판독 성공 `CaseView`(`requirements_evidence.readiness=PASS`) 추가, `04` §1 커버리지 갭에서 제거** ⑥ STALE/FAILED attempt의 `UsageRecord` 발행 여부(B-4) → ~~mock 컨벤션으로 "발행한다" 확정, `infra_failure_001`에 이미 반영. `contract-usage-record.md`(김준영 소유) 정식 등재는 잔여~~ → **종결(4차 통합, 2026-09-10, 이슈 #33 Required-5): `usage-record/v1.2`(§9-6)에 조건을 정식 등재하되 "attempt마다 무조건"에서 "실제 capability/provider invocation이 시작됐을 때(결과 무관)"로 좁혔다 — case 통합 초안, 김준영 PR 리뷰 확인 대상.** | eval Ground Truth 스키마 자체가 아직 없고 metric 정의는 eval 소유다. ①②는 종결, ③은 eval 자기 작업, ④는 search 답 대기, ⑤⑥은 이번 라운드에 case가 직접 답하고 등재까지 마쳤다 | `expected/*.json` 2개(eval Owner 후속 PR 대상), `docs/modules/case/decisions/eval-round2-ground-truth-and-usage.md`, `docs/mock/CONTRACT_CONFLICTS.md`, `04_mock_validation_report.md` §1 |
| **유소연 + 김준영** | ~~예산 단위(KRW) vs 비용 단위(USD) 환산 규칙 (P3-1)~~ → **규칙은 종결(2026-09-09, 이슈 #19 common/runtime 답변): 예산 판정의 authoritative source는 `UsageRecord`(`AnalysisRun.usage_summary`는 파생 summary일 뿐), `UsageRecord.cost`는 저장 전 KRW로 정규화해 `currency="KRW"`로 기록, 환율/요율 provenance는 `pricing_id`가 가리키는 versioned pricing artifact가 보존.** 현재 `max_cost_krw=300`과 `$0.42` 등 USD 조합은 비교 불가능해 이슈 #15(search)도 "happy로 승인 불가"로 지적함 — **기본값 결정 + fixture 정규화 전부 완료(2026-09-09 4차 라운드): `budget.max_cost_krw` 300→1000, 환율 placeholder(1400원/$, `docs/modules/case/decisions/budget-krw-normalization.md`), 전 시나리오 `UsageRecord.cost` KRW 정규화**. eval이 이슈 #22에서 이 원장 기준 9건(VISUAL_VERIFY 포함) 전부 예산 안임을 재확인(✅, 액션 없음). **(신규, 2026-09-10) 서어진이 이슈 #23 B-1에서 원장과 별개로 search 자체 `usage_summary.total_cost` snapshot이 USD로 남아 있던 gap을 지적 → 종결: 6개 시나리오 전부 KRW로 정규화(금액은 원래도 원장과 정합, 라벨만 교정)** | 규칙·기본값·fixture 정규화 모두 완료(원장 + search snapshot 둘 다) | 전 `search/*` · `common/*` |

**Owner에게 넘기지 않은 것**: enum 값 교체, 필수 필드 추가, off-by-one, 좌표계 환산, manifest range, 문서 수치, 검증 규칙 — 전부 §8·§11에 기계적 수정 지시로 확정해 두었다.

---

## 13. 다음 수정 Agent용 작업 목록

| 순서 | 상태 | Priority | 작업 | 대상 파일 | 완료 조건 | Owner 확인 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | ✅ 완료 | P0 | 검증 스크립트에 enum 검사 확대(§11-6)와 필수 키 검사(§11-7) 추가 후 **먼저 실행**해 실패 목록 확보 | `data/mock/validate_mock_pack.py` | 스크립트가 P0-1·P0-2를 자동 검출 | 불필요 |
| 2 | ✅ 완료 | P0 | 사건 유형을 등록된 4종으로 교체 (P0-1) | search 3 · evidence 2 · case 2 · scenarios 3 · `02` 카탈로그 | 모든 `target_event_types`/`event_type_hint`/`visual_event_type`이 4종 안에 들고 스크립트 통과 | 권장(서어진·김준영) |
| 3 | ✅ 완료 | P0 | `VisualEvidence`에 `uncertainties`·`legal_status:null` 추가 (P0-2) | search 3 | 3건 모두 §3 필수 필드 완비 | 불필요 |
| 4 | ✅ 완료(2026-09-09, 신유민 답변 반영) | P0 | overlay 「없음」을 결과 객체로 재모델링 (P0-4) | readout 1 · common 1 · case 1 | `rr_u001_overlay` SUCCEEDED + `OverlayTimeReadout` 1건(`NOT_APPLICABLE`) — 반영 완료. `considered[]`에 overlay 항목 추가는 아직 안 함(잔여, evidence 1) | 불필요(반영 완료) |
| 5 | ✅ 완료(2026-09-09 4차 라운드) | P0 | `VISUAL_VERIFY` run 추가 및 `ve_*.run_id` 재연결 (P0-3) | search 4 · common 4 · case 4 · recording 3 | 모든 VisualEvidence가 `operation=VISUAL_VERIFY` run을 가리키고 `as_h001_fine` 고아 해소 | 불필요 — 서어진(`input_ref.kind=analysis_source`)·유소연(`JobRecord.kind=FINE_VERIFY`) 둘 다 2026-09-09 결정, fixture 반영까지 완료 |
| 6 | ✅ 완료 | P1 | 참조·좌표계 기계 수정: `disagree_positions`(P1-4), `samples[].offset_sec`+`sample_count`(P1-5), `manifest_summary.range`(P1-8), `processed_duration`(P2-9) | readout 1 · case 2 · search 1 · common 1 | 값이 §8 지시대로 정정되고 스크립트(§11-5·§11-9 규칙 포함) 통과 | 불필요 |
| 7 | 🔶 부분(2026-09-09 4차 라운드 — coord 완료, address는 mock 범위 밖) | P1 | GPS/위치 경로 추가 + happy 위치 승격 (P1-6, P2-1) | recording 2 · evidence 1 · case 1 | `coord` non-null(happy)·GPS 부재 Observation(u001) 완료. `location_display.info_state`는 `address` artifact 없이는 `INFO_SOURCE_VERIFIED`로 못 올림 — §7-(3) 규칙상 정확한 상태 | **완료(김준영·정철원 규칙대로 실행) — `address`만 외부 artifact 선행 필요, 추가 Owner 판단 불필요** |
| 8 | ✅ 완료(2026-09-09, 서어진 답변 반영 — `EvidenceRecord` 완전 미생성으로 귀결, 시나리오 분리) | P1 | `ve_u001` → `UNCERTAIN` 전환과 연쇄 반영 (P1-7) | search 1 · evidence 1(비움) · case 1 · 신규 `scenario_plate_reread_001` 전 모듈 | `verification=UNCERTAIN`, `visual_event_type=null` 반영. `EvidenceRecord`는 필드 부재가 아니라 **완전 미생성**(`evidence_records=[]`)으로 처리 — 단순 필드 부재로 안 되는 것이 확인돼 C·D·G·I 서사는 `scenario_plate_reread_001`로 분리 | 불필요(반영 완료) |
| 9 | 🔶 부분(2026-09-09 4차 라운드 — 3건 중 2건 완료) | P1 | 신규 시나리오 3건 추가 (P1-9·P1-10·P1-12 / §10의 1·2·3) | `scenario_blocked_001`(미착수) · `scenario_relative_rebase_001`(✅) · `scenario_infra_failure_001`(✅) 전 모듈 + manifest + `02` | `USABLE_RELATIVE_ONLY`·`STALE`은 pack에 등장 완료(`validate_mock_pack.py` PASS, 46개 파일·7개 시나리오). `scenario_blocked_001`의 `BLOCK`/`INFO_AI_ESTIMATED`는 아직 없음(P1-9 나머지) | `scenario_blocked_001`만 잔여 — **필수(정철원·신유민·유소연)** |
| 10 | ✅ 완료 | P1 | happy `case_views`에 진행중·최종확인 스냅샷 추가, correction에 정정 전 스냅샷 추가 (P1-9, P2-6) | case 2 | `SEARCHING`/`RUNNING`/`user_reviewed=true`/정정 전 `INFO_NEEDS_REVIEW`가 등장 | 권장(신유민) |
| 11 | 🔶 부분(actual_ref 제거 ✅ / metric 이름 대기) | P1 | eval fixture 재작성 (P1-11) | `expected/` 2 | `actual_ref` 제거 또는 실재 오답 fixture 연결, metric 이름 교체, §11-4 검증 통과 | **필수(김대원)** |
| 12 | 🔶 부분(happy 분리 ✅ / purge 시나리오 미생성) | P1 | purge를 happy에서 분리 (P1-1) | recording 1 (+신규 `scenario_purge_001`) | happy 스냅샷에 AVAILABLE/DELETED 공존 없음 | 권장(정철원) |
| 13 | ✅ 완료(2026-09-09 3라운드, P2-3·4 이슈 #19 B절 재발견으로 해소) | P2 | 나머지 P2 정리: AssetFacts 보강·category(P2-2), transform_ref(P2-3), considered[](P2-4), empty 시나리오 recording(P2-5), crop/track 문서화(P2-8) | 다수 | 각 항목 완료 조건은 §8 참조 | 권장 |
| 14 | ✅ 완료 | P2 | 검증 스크립트 나머지 규칙(§11-1·2·3·4·8·10) 구현 | `validate_mock_pack.py` | 새 규칙 추가 후에도 pack 전체 PASS | 불필요 |
| 15 | 🔶 부분(수치·ROOT·03·04 ✅ / 신규 Upstream 항목 반영 잔여) | P2 | 문서 동기화: 수치 정정, 스크립트 ROOT, `03` 재생성, `04`/`CONTRACT_CONFLICTS`에 신규 발견 항목(§8의 Upstream 항목들) 반영 | `docs/mock/*` · `scripts/*` | `03` 재생성 시 diff 없음, `04`와 `CONTRACT_CONFLICTS` 항목 수 일치 | 불필요 |
| 16 | ✅ 완료 | P1 | `CaseView.requirements_*.checks[]`에 `category`·`subject_refs`(·`measurement`) 보강 (P1-13, 유소연 2차 검수 중 발견) | case 4 | `checks[]`가 대응 `evidence/*.json`의 `requirement_reports[].checks[]`와 필드 단위로 일치 | 불필요 |
| 17 | ✅ 완료(2026-09-09, 유소연) | P0/P1 | case 담당 §12 항목 4건 결정·반영: `JobRecord.kind`에 `FINE_VERIFY`·`REPORT_VIDEO_EXPORT` 등재(+`purge_case` Job 밖 확정), u001 `scope_u001` 범위 축소(P1-8 잔여), `evidence.review_needed` OR 파생 규칙 확정 | `contract-job-record-case-view.md`, `search/scenario_unknown_abstain_partial_001.json` | 계약 문서에 등재·확정 기록, `validate_mock_pack.py` PASS | 불필요(case Owner 본인 결정) |
| 18 | ✅ 완료(2026-09-09, 팀 리뷰 이슈 #15~#19 5건 종합 반영) | P0/P1 | 팀원 5명 GitHub 이슈 회신 전부 읽고 반영: P0-3(서어진, 결정만) · P0-4(신유민, 반영 완료) · P1-7(서어진, 반영 완료) · P1-12 taxonomy(신유민, 결정만) · P2-2(김준영, 반영 완료) · **`scenario_unknown_abstain_partial_001` → `scenario_unknown_abstain_partial_001`(E·H) + 신규 `scenario_plate_reread_001`(C·D·G·I) 분리**(김준영 제안) | search/readout/evidence/case/common/scenarios 각 2개(u001+p001 신규) · `recording/scenario_happy_001.json`(AssetFacts) · `manifest.json` · `02_mock_scenario_catalog.md` · `04_mock_validation_report.md` · `CONTRACT_CONFLICTS.md` | `validate_mock_pack.py` PASS(36개 파일·5개 시나리오), `03` 재생성 diff 없음 | 불필요(전부 팀원 답변 반영) |
| 19 | ✅ 완료(2026-09-09 3라운드) | P1 | P1-11/P2-9 finding 본문을 김대원 이슈 #17 답변 그대로 재작성 | `05_mock_deep_review_report.md` §8 | P1-11에 채점 모델 근본원인·metric 개명 전체표·`legibility` 필드 요건 반영, P2-9에 3단 설명(timeline 길이 분모·`processed_duration`은 별개 지표·`UsageRecord` 원장) 반영 | 불필요 |
| 20 | ✅ 완료(2026-09-09 3라운드, 이슈 #15~#19 원문 재대조 — 사용자 신뢰 회복 요청에 따른 전량 재검증) | P1 | ① `scenario_plate_reread_001` 프레임 불일치 2자리로 확장(신유민 B-1: `disagree_positions [5]→[5,6]`, 마스킹 `17나28?4→17나28??`) ② `scenario_correction_rerun_001`의 "Overlay NOT_RUN(배열 부재)" 설계를 폐기하고 u001과 동일한 "실행됨+NOT_APPLICABLE"로 재구성(정철원 이슈 #18: 오버레이 OCR 무조건 디스패치 정책과 모순이었음) ③ `scenario_plate_reread_001` case에 `evidence.plate_abstained`/`MANUAL_PLATE_INPUT` notice 추가(신유민 2차 코멘트: 계약 §9 예시에는 있었으나 fixture 0건) | readout 1(plate_reread) · readout/case/common 각 1(correction_rerun, overlay 신규 3파일 변경) · case 1(plate_reread notice) | `validate_mock_pack.py` PASS(36개 파일·5개 시나리오 그대로) | 불필요(전부 팀원 답변의 정확한 재구현) |
| 22 | ✅ 완료(2026-09-09 3라운드, 사용자가 이슈 #19 원문 B절 전체를 재제시해 발견) | P2 | 이슈 #19 본문 "B. 내 모듈 fixture 검수"(김준영의 evidence/common fixture 결함 지적 11건)가 1·2라운드에서 "A. 정합 검토 답변"(도메인 결정 6건)만 반영되고 누락됐던 것을 발견 — 11건을 현재 fixture와 대조한 결과: P2-3·P2-4(post_stamp/transform_ref 모순, considered[] anchor)는 이번에 해소, `ve_u001` 연쇄·overlay JobExecution 건은 이미 다른 라운드에서 해소, 번호판 형식 불일치는 "34나7890" 통일로 이미 해소(값은 다르지만 문제는 해소), 나머지(정책/신고문 template 실물 부재, coverage 갭 8종, common의 USD/KRW 혼용, RUNNING/STALE/attempt2/Report Video export 부재)는 전부 §12(김준영·P3-1)·§13(row 7·9)·04의 기존 gap 목록에 이미 정확히 대응되는 항목임을 확인 — **신규로 놓친 항목은 없었고, P2-3·P2-4 2건만 실제로 미반영 상태였다** | `05_mock_deep_review_report.md` §8 P2-3·P2-4, `recording/scenario_happy_001.json`, `evidence/scenario_happy_001.json` | 이슈 #19 B절 11건 전부 현재 fixture/문서 상태와 대조 완료, PASS | 불필요(전량 재확인 완료) |
| 21 | ⏳ 대기(유소연) | P2 | 신유민 이슈 #16 2차 코멘트(web/CaseView 소비 관점)에서 나온 신규 미해결 2건을 §12에 등재만 하고 아직 결정하지 않음: (a) `progress[].step` 8종이 제품 확정 7단계 사용자 플로우의 2·3단계("사건 설명"·"범위 확인")를 표현할 방법이 없음 (b) `progress[].state` 4종이 제품 정의 6개 작업상태 중 "부분 완료"·"중단"을 표현 못함(기존에 알려진 SKIPPED 문제와 별개) | (결정 시) `contract-job-record-case-view.md`, `case/*.json` | 유소연이 §12에서 결정 후 처리 | **필수(유소연 — 아직 미결)** |
| 23 | ✅ 완료(2026-09-09 4차 라운드) | P0/P1 | "규칙은 종결·fixture는 다음 라운드"로 남아 있던 전 항목 실행: `VISUAL_VERIFY` run 4개 시나리오 추가(row 5) · `scenario_relative_rebase_001`(K)·`scenario_infra_failure_001`(J) 신규 시나리오 2건(row 9 중 2/3) · budget KRW 정규화 기본값·fixture(P3-1) · GPS `coord` happy/u001(P1-6 부분, row 7) · `CaseView.candidates[].stale_revision` 신규 필드(계약 §13 note가 case Owner에게 위임한 결정) | recording 3(GPS 2·rebase 신규) · search 4(fine run) · case 6(fine·rebase·infra) · common 6(fine·rebase·infra) · readout 1(infra) · scenarios 2(신규) · manifest.json · `02` 카탈로그 · `docs/modules/{case,evidence}/decisions/*` 신규 3건 | `validate_mock_pack.py` PASS(46개 파일·7개 시나리오) | 불필요 — 전부 이미 결정된 규칙의 실행. `address`(reverse-geocode artifact)·`scenario_blocked_001`·`safety_report_type`·`EvidenceNeeds` 신규 kind만 여전히 외부 판단/artifact 대기 |
| 24 | ✅ 완료(2026-09-10, 4차 통합 — 이슈 #31/#33/#34/#35 + PR #32 반영, case 통합 주도) | P0/P1 | mock-pack-v3가 merge된 뒤(PR #29, `develop=e056d64`) 3차 검수 라운드의 7개 Required 항목 + evidence PR #32(김준영, doc-only)를 전부 반영. **계약 문서**: `contract-evidence-record-needs.md`→`evidence-record/v1.3`(`situation_response` 신설, Required-4) · `contract-usage-record.md`→`usage-record/v1.2`(`run_ref_reason`·row 생성 규칙 좁힘, Required-5/7) · `contract-job-execution.md`→`job-execution/v1.1`(`CANCELLED` 신설, 이슈 #33 A-2) · `contract-job-record-case-view.md`→`case-view/v1.3`(`situation_confirmation` 값공간 정정·`report_type_display.info_state`·`package.report_field_states`·`CANCELLED→PARTIAL`, Required-3/6) · `contract-analysis-run-candidate-event.md` Consumer 문구 정정(`case_id`/`run_ref` 집계 키 분리, Required-7) · `contract-correction-record.md`→`correction-record/v1.1`(Draft→Final, evidence Consumer Review 6건 반영). **Fixture**: `happy_001` Report Video export 순서 역전 수정(Required-1, `job_h001_report_video.case_rev` 4→2 + fingerprint에서 미래 `pkg_h001` 참조 제거) · `u001` post-stamp Job chain 신설(`job/exec/usage_u001_report_video`)+`transform_ref` 개정+FINAL_PACKAGE post-stamp 검사+notice(Required-2) · `situation_confirmation` 12개 candidate 전량 백필(`NOT_ASKED`/`USER_UNSURE`, Required-3) · `ev_u001.situation_response` 신설(Required-4) · `SafetyReportType` 전 fixture 정규화(`UNSAFE_*`/한국어 label 제거, Required-6) · `run_ref_reason` 전 `UsageRecord` fixture 백필(Required-5/7) · 이월 수정 2건: `plate_reread_001`의 `ev_p001_v2.selection_rev` 1로 원복(이슈 #33 A-5, 후보 재선택 없었음) + reread 프레임의 재사용 `crop_ref`(`crop_p001_001/002`, `source_profile` 변경됨)를 신규 id(`crop_p001_004/005`)로 분리(이슈 #31 A-3) · `CorrectionRecord` 계약이 Final이 되며 처음으로 실제 fixture 객체 생성(`cr_r001_time`, `correction_records[]`) — `data/mock/validate_mock_pack.py`의 `EXEMPT_KINDS`에서 `correction_record` 제거 | 계약 6건, case/common/evidence/readout/recording fixture 다수(§ 상세는 `CONTRACT_CONFLICTS.md`·`04_mock_validation_report.md` 갱신분 참고) | `validate_mock_pack.py` PASS(계속 46개 파일·7개 시나리오+`correction_records[]` 1건) · `check_contract_fixtures.py` PASS(60/26/104) · `check_boundaries.py` PASS | 신유민·김준영 PR 리뷰 확인 대상(case가 초안 작성, 원 Owner는 review-only) — Should-1(`progress[].state=PARTIAL`/`CANCELLED` demo fixture)은 비차단으로 유보됐다가 2026-09-12 11차 갱신에서 종결(`scenario_infra_failure_001` 확장) |

**상태는 2026-09-09 2차 수정(유소연 case 파트 정합 검토 + 팀 리뷰 이슈 5건 종합 반영) 기준이다.** 1차 수정(2026-09-08)에서 답변이 필요 없는 1·2·3·6·10·14를 완료했고 11·12·13·15는 답변 불필요 부분만 처리했다. 2차(2026-09-09) 1라운드에서 유소연이 case 담당 §12 항목 4건(①~④)을 전부 결정·반영했고(17), 그 과정에서 새로 발견한 `checks[]` 필드 누락도 수정했다(16). 2라운드(18)에서 팀원 5명의 이슈 회신을 전부 반영해 4·8이 완료로 바뀌었고, 5는 도메인 판단이 끝나 fixture 반영만 남았다. 남은 것은 5 fixture 반영(서어진 결정 반영)·7(김준영 P1-2-②·P1-6 구현·정철원)·9(정철원·신유민·유소연 — 신규 시나리오 3건, taxonomy는 이미 답변받음)·13 잔여(P2-3·4)·19(김대원 답변의 정확한 재작성)와, P3-1(환산 규칙은 이슈 #19로 종결, budget 기본값은 유소연이 다시 정하고 그 값대로 `common/*`을 KRW로 정규화하는 fixture 작업만 남음)이다. 이번 라운드에서 **`EvidenceNeeds`가 "사건 유형 자체 미확정"을 표현 못 한다는 새 Contract Gap**을 발견해 `04_mock_validation_report.md` §3.1-4에 기록했다 — case Owner 단독 해소 범위 밖이라 evidence(김준영)/PM 확인이 필요하다.

> **정정 (같은 날, 사용자 확인 요청으로 재검증).** 위 §12/§13 갱신 직후 이슈 #19·#15 원문을 다시 대조해보니 부정확한 부분이 있었다 — 김준영 §12 ①(source.kind 5종)은 "미해소"가 아니라 **승인 완료**(fixture도 이미 5종 전부 승인된 형태로 일치, 변경 불필요)였고, ④(lat/lon)도 규칙 자체는 **결정 완료**(구현만 잔여)였다. P3-1도 "미해소"가 아니라 **환산 규칙은 결정 완료**(budget 기본값·fixture 정규화만 잔여)였다. P1-3(ref 직렬화 형식)은 이슈 #15로 **완전 종결**(mock 현행 유지 확인)이라 더 이상 열린 항목이 아니다. 위 표·문단은 이 정정을 반영해 다시 썼다.

---

## 14. 수정 후 재검증 체크리스트

- [ ] P0 4건 모두 해소 (사건 유형 4종화 / VisualEvidence 필수 필드 / VISUAL_VERIFY run / overlay 「없음」 모델링)
- [ ] P1 12건 모두 해소 또는 `04_mock_validation_report.md`에 **명시적 보류 사유와 함께** 기록
- [ ] `python3 data/mock/validate_mock_pack.py` PASS — **§11의 규칙 6·7·1·8·9가 추가된 상태에서**
- [ ] ID/reference graph: 문자열 ref 포함 전량 해석되고 orphan 0건, `as_*_fine` 고아 해소
- [ ] Happy Path가 recording→search(Coarse+Fine)→readout→evidence→case→web으로 끊김 없이 연결
- [ ] 대표 Partial Path(`unknown_abstain_partial`)에서 abstain·overlay 없음·시각 충돌·자동 재판독이 모두 관찰 객체를 가진 상태로 연결
- [ ] Runtime Output과 Ground Truth 분리 유지 — `expected/`의 어떤 fixture도 런타임 fixture를 정답으로 사용하지 않음
- [ ] pack 전체에 다음이 최소 1건씩 존재: `RequirementReport.overall=BLOCK` · `info_state=INFO_AI_ESTIMATED` · `progress[].state=RUNNING` · `notices[].blocking=true` · `user_reviewed=true` · `timeline_status=USABLE_RELATIVE_ONLY` · `SpanResolution.status=PARTIAL` · `JobExecution.status=STALE` · `verification=UNCERTAIN` · GPS Observation(있음/없음)
- [ ] `manifest.json` · scenario manifest · 실제 파일 3자 일치(`shared_ids` 포함)
- [ ] `03_mock_artifact_templates.md` 재생성 diff 0
- [ ] `04_mock_validation_report.md`와 `CONTRACT_CONFLICTS.md`의 항목이 서로 일치하고, 이번 검토에서 새로 발견한 Upstream 항목(SpanResolution 버전 표기 불일치 · `lat`/`lng` drift · 예산 통화 · VisualEvidence ref 형식 · Fine 발주 kind)이 모두 등재
- [ ] §12 표에 남은 항목만 Owner에게 전달되고, 기계적 항목은 하나도 남지 않음
