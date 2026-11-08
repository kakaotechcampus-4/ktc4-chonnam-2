# OBSERVED 무응답 신고서 초안 및 묶음

2026-11-07 확정. [#597 B안 결정 댓글](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/597#issuecomment-6703544277).

[#171 B-2](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/171)는 신고 상황 응답 뒤에 신고문과 묶음을 만들도록 했다. #597에서는 Fine이 유형을 관찰한 경우 그 유형으로 신고서를 먼저 준비하고, 사용자가 초안에서 근거를 검토하거나 유형을 고칠 수 있도록 한다.

| Fine | 사용자 응답 | Evidence 결과 |
| --- | --- | --- |
| `OBSERVED` | `NOT_ASKED` | 관찰 출처가 있는 구체적 유형으로 특정형 렌더링. 상황 요건 `PASS` |
| `OBSERVED` | `CONFIRMED` / `CORRECTED` | 특정형 렌더링. 상황 요건 `PASS`. 정정 유형과 매핑은 기존 `SITUATION_CHANGE`로 반영 |
| `OBSERVED` | `USER_UNSURE` | 상황 요건 `WARN`, 렌더 입력 `UNKNOWN`. 초안과 묶음 생성 보류 |
| `UNCERTAIN` | `USER_UNSURE` | 일반형 렌더링. 기존 `WARN` 경로 |
| `UNCERTAIN` | `NOT_ASKED` / `CONFIRMED` / `CORRECTED` | 비조립. 기존 응답 대기 경로 |
| `NOT_OBSERVED` | 모든 경우 | 비조립 |

EvidenceRecord의 관찰 유형은 선택한 VisualEvidence를 가리키는 `search.visual_inference` 출처와 `OBSERVED` 관찰성으로 식별한다. 무응답은 `situation_response` 부재로 보존한다. 활성 요건 정책 `policy/requirement-rules-v7`은 v6을 대체하며, 위 조건을 별도 `PASS`로 두고 해소되지 않은 무응답은 `UNKNOWN`으로 유지한다. 글자 수는 선택된 template으로 실제 렌더링한 본문에서 계산한다. `safety-report-policy/v1.2`를 유지한다. 개정 대상은 렌더링 자격과 요건 판정이며 제목·본문·슬롯·template ref와 유형 매핑은 v1.2 정의를 사용한다.

## Case 호출 경계

`from daesingo.evidence import render_report_draft`

`render_report_draft(evidence_record: dict) -> dict[str, str] | None`은 조립된 EvidenceRecord를 받아 `{"title": str, "description": str}`을 반환한다. 유형과 응답 조합이 렌더링을 허용하지 않거나, 발생시각이 없거나, 번호판 값과 판독 결과가 모두 없거나, 본문이 허용 길이를 벗어나면 `None`을 반환한다. 정상 판독에서 번호를 식별하지 못한 경우에는 기존 번호판 없는 template을 사용한다. 위치가 없으면 기존 위치 없는 template을 사용한다. 계약과 내부 정책 오류는 호출자에게 전달한다.

Case는 조립된 Record가 있으면 반환값을 CaseView 최상위 `report_draft`로 옮기고, 조립 전에는 `null`을 투영한다. `package.report`는 동일한 렌더러의 제목·본문과 template ref를 포함한 최종 신고문이다. 모든 FINAL_PACKAGE 요건과 필수 자산이 준비된 경우에만 ReportPackage를 만든다. 최종 검토(`USER_REVIEWED`)는 안전신문고 이동 시 Case가 기록하는 사용자 행동이다.

## 정정과 연동

같은 후보의 유형 정정은 Record·신고문·요건·묶음 재조립으로 반영한다. 영상·번호판 이미지의 Export 입력이 같으면 기존 자산을 사용한다. 발생시각 정정으로 사후 각인 입력이 달라지면 현재 입력에 맞는 영상만 사용한다. [Case #616](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/616)과 Web을 합쳐 초안 투영, 자동 영상 발주, 최종 검토 기록을 검증한다.
