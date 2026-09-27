# input_fingerprint의 implementation label 포함 여부 — 지금은 보류

> 결정일 2026-09-20 · 담당 유소연(`case`) · 근거 이슈 #77 · 현재 코드 확인(`src/daesingo/case/jobs.py`, search/readout `list_impls()` 미구현)

## 결정된 것

- 지금 `case`가 `input_fingerprint`에 `AnalysisScope + active implementation label`을 자동으로 조합해 넣는 로직은 **만들지 않는다.** `jobs.py`는 계속 호출자가 전달한 문자열을 그대로 `JobRecord`에 저장한다.
- 요구사항 자체("prompt/model이 바뀌면 이전 `SUCCEEDED` 결과를 재사용하면 안 된다")는 **여전히 유효**하다고 본다 — 폐기가 아니라 **구현 시점을 미룬다.**

## 왜 지금은 필요 없는가

- `case`에는 `input_fingerprint`로 기존 `JobRecord`를 조회해 "같으면 재사용, 다르면 새로 실행"을 판단하는 캐시/dedup 로직이 **아직 어디에도 없다.** `issue_job()`은 항상 새 `JobRecord`를 만들 뿐이다 — 참고할 캐시 자체가 없으니 fingerprint가 무엇을 구분하는지가 지금은 관찰 가능한 차이를 만들지 않는다.
- research/ADR이 전제한 `list_impls()`(search/readout가 "지금 활성 구현 이름표"를 내놓는 함수)가 실제로 구현된 적이 없다(`readout/README.md`에 이름만 있음). `case`가 지금 이 값을 조합하려 해도 받아올 producer가 없다.
- 즉 지금 만들면 "무엇으로부터 라벨을 받을지"·"캐시가 그 값을 어떻게 쓸지" 둘 다 추측으로 채워야 한다 — `orchestration-service-layer.md` D2가 이미 짚은 것과 같은 이유("추측으로 만든 코드는 실제 계약이 나오면 다시 갈아엎어야 한다")로 지금 만들지 않는다.

## 이미 다른 문서가 정한 것 (여기서 다시 정하지 않는다)

- fingerprint 조합 공식(`hash(정규화된 AnalysisScope + list_impls() 활성 구현 이름표)`) 자체는 `architecture-input-memo.md`/`adr-job-record-case-view.md`가 이미 적어뒀다 — 이 결정은 그 공식을 바꾸지 않는다. 실제로 캐시 로직을 만들 때 그대로 가져다 쓴다.
- `PLATE_REREAD`가 이 fingerprint 캐시 조회를 예외적으로 건너뛴다는 규칙(`부분 재실행 정책 표`)도 그대로 유효하다 — 캐시가 생기면 그 예외도 같이 구현해야 한다.

## 재검토 트리거

아래 중 하나라도 실제로 생기면 다시 조사한다.

- [ ] search 또는 readout가 `list_impls()`(또는 동등한 "활성 구현 이름표" 조회 수단)를 실제로 구현한다
- [ ] `case`가 `input_fingerprint` 기준으로 기존 `JobRecord`를 조회해 재사용 여부를 판단하는 캐시 로직을 실제로 붙인다

(둘 중 하나만 먼저 생겨도 트리거된다 — 나머지 하나가 그 시점에 같이 확정돼야 한다.)

## 남은 것

| 항목 | 상태 | 무엇으로 정하는가 |
| --- | --- | --- |
| fingerprint 생성 책임(`case` vs producer vs common) | 보류 | 캐시 로직을 실제로 붙이는 시점에 재검토 트리거와 함께 확정 |
| implementation label 변경 판단 기준(prompt/model/threshold/refactor 중 어디까지 포함할지) | 보류 | 같은 시점, search/readout Owner와 합의 |
| canonicalization/hash 공통 함수 필요 여부 | 보류 | 같은 시점 |
