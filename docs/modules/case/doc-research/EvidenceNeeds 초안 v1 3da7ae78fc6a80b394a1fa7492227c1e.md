# EvidenceNeeds 초안 v1

### 확정 가능한 매핑

| kind | would_fill | 매핑 대상 | 근거 | 캐시 적용 여부 |
| --- | --- | --- | --- | --- |
| OVERLAY_TIME_OCR | event_time | `readout.read_overlay_time(span)` | §7 Runtime Flow에 그림으로 명시 | 캐시 무관 |
| PLATE_REREAD | plate | `readout.read_plate(span, target_hint)` 재호출 | 부분재실행표의 "번호판 다시 읽어줘" 행(다시 도는 것: 번호판 판독만)과 이름·용도가 동일 | 캐시 우회 |
- `request_correction()`이나 `needs_map`을 통해 발주되는 **PLATE_REREAD**는 input_fingerprint 캐시 조회 자체를 건너뛰고 무조건 새로 발주한다.

### 회의

Q1(외부 정보, 김준영 필요). EvidenceNeeds.kind의 전체 목록이 이 2개가 다인지, 아니면 앞으로 늘어날 계획이 있는지 —