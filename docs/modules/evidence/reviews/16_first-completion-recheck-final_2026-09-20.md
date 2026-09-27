# Evidence 1차 완료 재검수 종결 — 2026-09-20

## 결론

PR #83에서 시작한 재검수는 최신 `develop` 기준으로 다시 확인했고, 오래된 브랜치를 그대로 merge하지 않고 현재 상태만 정본 문서에 반영한다.

- #97 merge: P/R 공용 evidence fixture와 `CaseView.requirements_evidence`를 active catalog에 동기화
- #114 merge: Happy real E2E에서 `case.hints.location`을 evidence까지 전달
- #115 merge: I4의 REPORT_VIDEO 관찰 Producer 경계를 실제 계약 상태에 맞게 정정
- #85/#87: P/R mismatch의 원인이 #97로 제거돼 superseded 처리
- #96: #84 변경을 최신 develop에서 분리한 #114로 대체

## RequirementReport 최종 기대값

| Scenario | EVIDENCE / FINAL_PACKAGE |
| --- | --- |
| H | `PASS / PASS` (baseline) |
| U | `WARN / WARN` (baseline) |
| P | `UNKNOWN → WARN` (EVIDENCE only) |
| R | `WARN → WARN` (EVIDENCE only) |

P/R의 `WARN`은 위치 부재를 숨기지 않는 ADR-EVIDENCE-002 §5.4의 의도된 결과이며, Web은 이 값을 blocking/UNKNOWN으로 취급하지 않는다고 #86에서 확인했다.

## 남은 후속은 별도 범위

- **#48 / I2:** 공용 H/U ReportPackage 파일을 v1.1/no-location Template 기준으로 재렌더하고 validator 보강
- **I4:** 최종 `REPORT_VIDEO`를 readout 관찰 입력으로 받을 계약/capability 확장 후 case→evidence 배선
- **D2-e:** 녹화 시작·끝 경계 처리 정책

이 셋은 evidence 1차 baseline/Contract 완료를 되돌리는 항목이 아니다. 동시에 실제 Runtime 완료로 간주해서도 안 된다.

## #83 처리

#83의 2026-09-19 재검수에서 유효했던 체크 근거는 `first-completion-checklist.md`에 반영했다. 다만 #83 브랜치는 이후 구현보다 오래돼 같은 문서 안에 “실행 코드 없음” 같은 역사적 상태가 섞여 있으므로 **unmerged superseded**로 닫는다.
