# Mock Pack v1 — `case` (2026-09-06 18:00 공유분)

**Owner:** 유소연 (`case`)
**범위:** 정합 검사(BLOCK 접합부) 완결을 기다리지 않고, 현재 확정된 값 공간과 참조 모양만으로 만든 **고정 Happy Path 1개 + 대표 Partial/UNKNOWN 1개**.

## 무엇을 옮겼나

`CaseView`·`JobRecord`(Job Intent) 각각의 §8 정상 예시와 §9 실패/부분성공/UNKNOWN 예시를 그대로 fixture 파일로 분리했다. 원문: `../../../architecture/contracts/contract-job-record-case-view.md` A절(§8·§9)·B절(§8·§9).

| 파일 | 원문 | 비고 |
| --- | --- | --- |
| `case-view.happy-path.json` | B§8 | `thumb_ref`만 아래 사유로 수정 |
| `case-view.partial-unknown.json` | B§9 | 원문 그대로 (candidate 없음 · PLATE_ABSTAINED notice) |
| `job-record.happy-path.json` | A§8 | 원문 그대로 |
| `job-record.force-rerun.json` | A§9 | 원문 그대로. Job Intent 자체는 성공/실패 상태가 없어 이 파일이 "실패" 대신 강제 재실행 케이스를 대표한다 |

**`thumb_ref` 수정 사유:** 계약 원문 예시는 `"frame:a09@178.6"`이지만 2026-09-06 `recording`이 "ref에 위치를 인코딩하지 않는다"로 확정했다(`adr-consistency-2026-09.md` §6 R-5, `module-architecture.md` §5-3). 계약 §13도 recording 계약 2건이 나오기 전까지는 목데이터에 `mock-pack-v1-refs.md`를 쓰라고 명시한다. 그래서 `thumb_ref`를 그 문서의 opaque 샘플 `fr_a1b2c3`로 바꿨다. 그 외 필드는 손대지 않았다.

## 이 Pack이 보증하지 않는 것

- **B01/B02 미해결**: `evidence.*_display`의 파생 규칙(needs_review 생산, occurred_at 변환, 위치 대표값, source_label_key 전달)과 `requirements.scope`/`readiness` 선택 근거는 Pending이다. 두 fixture의 해당 필드는 계약 §8/§9가 이미 예시로 든 값을 그대로 옮긴 것이지, 이 Pack이 새로 판정한 값이 아니다.
- **recording 자산 계약 2건 미작성 (B06~B09)**: `thumb_ref`는 opaque id 형태만 맞췄을 뿐 실제 자산 lookup이 되지 않는다. `candidates[].thumb_ref`가 가리키는 자산 종류(`fr_`/`da_`)는 recording 계약이 나온 뒤 확정한다.
- `ownership.md` §7-④의 전체 E2E 6기준 통과를 의미하지 않는다. 이 Pack은 **개별 fixture 단위 비교용**이며, 고정 입력에 대한 화면 렌더 확인 이상의 통합 보증이 아니다.

근거 전문: `../../../architecture/contracts/adr/adr-consistency-followup-2026-09-06.md` §3·§5, `../../../architecture/mock-pack-v1-refs.md`.
