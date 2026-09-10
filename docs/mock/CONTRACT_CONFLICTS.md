# CONTRACT_CONFLICTS.md

이 파일은 Mock Pack 생성 지침이 요구하는 "Contract 충돌 기록 파일(CONTRACT_CONFLICTS.md 또는 동급)"이다. 전체 상세 내용과 근거는 `04_mock_validation_report.md` §3에 있고, 여기서는 그 절의 항목만 인덱스로 모았다 — 이 작업 중 발견한 어떤 설계 문제도 임의로 고치지 않았고, 전부 아래 목록 + `04_mock_validation_report.md`에만 기록했다.

## Contract 충돌 (1건, 표현력 gap — 서로 부정하는 충돌은 없음)

4. `EvidenceNeeds`(v1)가 "AI가 사건 유형 자체를 확정하지 못했다"는 상황을 표현하지 못함 — 신규(2026-09-09, 유소연) → **fixture 레벨에서 해소(2026-09-10)**, 계약 문서 정식 등재는 잔여. 이슈 #25 A절(김준영)이 `event.visual_event_type.value=null`인 `EvidenceRecord`를 제한적으로 허용하기로 답했고, `scenario_unknown_abstain_partial_001`을 이 값으로 재구성해 EVIDENCE/FINAL_PACKAGE WARN → `stage=READY` 경로까지 실제로 예시화했다(`docs/modules/case/decisions/generic-warn-package-and-situation-response.md`). 단 `contract-evidence-record-needs.md` §3 스키마 자체("event는 필수")는 아직 이 null 허용을 명문화하지 않았고, `EvidenceNeeds`에 신규 `kind`는 만들지 않기로 확정(evidence A절: "사용자 workflow action이 아니다") — 이 두 가지는 evidence 소유 계약 문서 수정 대상으로 남는다.

→ 상세: `04_mock_validation_report.md` §3.1

## 반려된 제안 (1건 — 이미 확정된 결정과 충돌)

5. 이슈 #23 B-3(서어진 제안): `AnalysisRun.input_ref.kind = ANALYSIS_SCOPE`를 소문자 `analysis_scope`로 통일하자는 제안 — **반려**. `contract-source-asset-media-stream.md` §84(항목 5)와 `adr/adr-data-contract-call-closure-2026-09-08.md` §218(항목 6)에 이미 "`ANALYSIS_SCOPE`는 자산 계층 ref가 아니며 별도 accepted 값이고, 이를 근거로 전역 대문자 규칙을 적용하지 않는다"는 명시적 결정이 있다. 제안 당시 이 선행 결정을 참조하지 못한 것으로 보임. Mock fixture(`ANALYSIS_SCOPE` 대문자 유지)는 그대로 두었고 계약 문서도 수정하지 않았다 — 수정하면 오히려 기존 ADR을 위반한다. 서어진에게 이 선행 결정을 알려 이슈 #23 B-3을 close하도록 회신 필요.

## 불명확한 Contract (8건 잔여 · 1건 종결)

1. `TimeResolution.resolved.verification`과 `computation.mode=USER_OVERRIDE`의 대응 관계 미명시
2. 순수 사용자 입력 값의 `EvidenceValue.source.observability`/`user_corrected` 판정 기준 미명시
3. ~~`CaseView.evidence.review_needed`의 파생 규칙 미명시~~ → **종결(2026-09-09, 유소연)**: 여섯 `*_display.needs_review`의 OR 집계로 확정, `contract-job-record-case-view.md` B절 §6·§7 등재
4. `EvidenceRecord.event.safety_report_type`의 실제 값 공간(등록된 enum) 부재 — 김준영이 이슈 #19에서 **명시적으로 반려**(placeholder일 뿐 canonical enum 아님). evidence 소유 versioned artifact 필요, mock이 임의로 채울 수 없음. 같은 이유로 `CaseView.evidence.report_type_display`에는 `info_state`/`source_label_key`를 아직 추가하지 않았다(2026-09-10, u001 WARN 재구성 중 보류) — registry가 나오면 `case_type_display`/`violation_display`와 같은 파생 규칙으로 채운다.
5. 신규(2026-09-10, 유소연) — `CaseView.candidates[].situation_confirmation`·`CaseView.package.unconfirmed_fields`는 이슈 #25 요구를 fixture로 구현했지만 `contract-job-record-case-view.md` 본문에는 아직 미등재. `docs/modules/case/decisions/generic-warn-package-and-situation-response.md` 참고.
6. 신규(2026-09-10, 서어진, 이슈 #23 B-2) — Fine 단계에서 `AnalysisRun.input_ref`(`{analysis_source, as_*_fine}`)와 그 결과 `VisualEvidence.input_ref`(`{incident_clip, clip_*}`)가 서로 다른 자산 종류를 가리킴. VISUAL_VERIFY가 추가된 4개 시나리오(`happy`·`plate_reread`·`correction_rerun`·`unknown_abstain_partial`) 전부 동일 패턴. 두 후보안: (a) 의도된 층위 차이로 인정하고 계약에 "run.input_ref ≠ ve.input_ref 가능"을 명시 vs (b) `verify_visual`이 실제로 보는 자산이 incident clip이므로 run.input_ref도 `incident_clip`으로 맞춤(fixture 수정). **서어진이 RT7(`verify_visual(input_ref)`) 재확인 후 다음 라운드 전 결정하기로 명시적으로 보류** — 이번 라운드에서 fixture는 손대지 않았다.
7. 신규(2026-09-10, 김대원, 이슈 #22 B-2) — `CandidateEvent.span`이 (a) coarse 후보 창인지 (b) 사건 구간(계약 §4-1 예시가 보여주는 18초 폭)인지 계약 문구가 명확히 답하지 않음. 현재 fixture는 60~120초 폭이라 eval의 IoU>=0.5 매칭이 구조적으로 불가능(대표 사례: `happy_001` 120초 폭, `representative_ms` 오차는 0인데 IoU 최대 0.15). `relative_rebase_001`은 span이 요청 scope와 완전히 동일해 오차가 정의상 0이 되는 부가 문제도 있음. **`AnalysisRun`/`CandidateEvent` 계약 소유자 서어진(search)의 답이 필요** — case/mock owner가 대신 결정하지 않았다. 답에 따라 (a) eval의 매칭 규칙을 `representative_ms`+onset 오차 기준으로 바꾸거나 (b) fixture의 span을 사건 길이로 좁혀야 한다.
8. 신규(2026-09-10, 김대원, 이슈 #22 B-4) — 실패/STALE attempt도 `UsageRecord`를 발행해야 하는지 `contract-usage-record.md`(Producer/Owner: 김준영, common/runtime)가 명문화하지 않음. **mock pack v3는 "발행한다"로 fixture 컨벤션을 확정**했고(`scenario_infra_failure_001`의 `exec_x001_plate_a1` STALE attempt에 0 KRW `usage_x001_plate_a1` 추가) `docs/modules/case/decisions/eval-round2-ground-truth-and-usage.md`에 근거를 남겼다. 계약 본문 정식 등재는 common/runtime 소유라 case가 대신 쓰지 않았다.
9. 신규(2026-09-10, 유소연, `05` §12 유소연-⑧) — `CaseView.progress[].state`가 제품 정의 6개 작업상태(`core-user-flow.md` §3-2) 중 "중단"(사용자가 분석을 중단한 경우, §4)을 표현하지 못함. "부분 완료"는 기존 `AnalysisRun.outcome=PARTIAL`을 그대로 투영하면 돼서 이번에 `PARTIAL`로 등재했지만, "중단"은 대응할 `JobExecution.status`(닫힌 5값: `QUEUED/RUNNING/SUCCEEDED/FAILED/STALE`, Producer/Owner 김준영 common/runtime)에 CANCELLED류 값 자체가 없다. `CaseView.progress[].state`만 case가 임의로 늘려도 그 상태를 가리킬 실제 `JobExecution` 데이터가 없어 fixture화가 불가능하다 — **김준영의 `JobExecution.status` enum 확장 결정이 선행돼야 한다.**

→ 상세: `04_mock_validation_report.md` §3.2

## Architecture 확인 필요 (0건 잔여 · 2건 종결)

1. ~~`JobRecord.kind`에 Report Video export / `purge_case()` 발주용 값 미등재~~ → **종결(2026-09-09, 유소연)**: `FINE_VERIFY`·`REPORT_VIDEO_EXPORT` 등재, `purge_case()`는 Job 밖 관리 동작으로 확정. `contract-job-record-case-view.md` A절 §7·§12·§13
2. ~~`contract-visual-evidence.md` 예시의 stale non-opaque frame ref 형식~~ → **종결(2026-09-10, 서어진)**: 이슈 #23 A절에서 계약 소유자(서어진)가 직접 답함 — `input_ref`는 `AnalysisRun.input_ref`와 같은 `{kind, ref}` 구조체, frame ref는 `fr_<opaque-id>`(위치 인코딩 폐기). 예시·문구 정정이라 `visual-evidence/v1.0` 유지, `contract-visual-evidence.md` §2·§3·§5·§6·§7·§8 갱신.

→ 상세: `04_mock_validation_report.md` §3.3

## Fixture 생성 불가 (1건)

1. `contract-correction-record.md`가 아직 Draft라서 `CorrectionRecord` 자체 필드 fixture를 생성하지 않음(opaque ref만 사용)

→ 상세: `04_mock_validation_report.md` §3.4
