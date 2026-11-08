# 준비 미디어 메타데이터 정밀도 보존 구현 계획

> **실행 에이전트 지침:** 사용자의 현재 승인 범위에서 직접 실행한다. 완료 전 새 읽기 전용 리뷰가 필요하다. 커밋·staging·푸시·배포는 하지 않는다.

**목표:** 불변 ref의 충돌 거부를 유지하면서 MySQL JSON 저장 전후에 준비 미디어 메타데이터를 정확히 보존한다.

**구조:** analysis_source/incident_clip 행만 원래 모델 JSON을 문자열로 담은 엄격한 버전 envelope로 인코딩한다. 목록을 포함한 저장소 읽기 경계에서 디코딩한다. MySQL은 내부 숫자 리터럴을 다시 해석하지 않는다. 기존 dict는 계속 읽을 수 있으며 재작성하지 않는다. 공개 모델·stable_media fingerprint·정확한 동등 비교·미디어 검증기는 유지한다.

**명세:** 사용자 요청, `docs/architecture/contracts/contract-analysis-source-derived.md` §4/§6, `docs/modules/recording/chunked-prepared-media.md`, 이전 실영상 실험과 보존된 실패 증거.

## 제약

- 현재 브랜치/HEAD를 유지하고 기존 미커밋 변경·증거를 보존한다.
- epsilon·반올림·동등 비교 제거·PTS/duration/provenance 완화·상한 변경은 하지 않는다.
- 스키마 migration이나 native JSON이 이미 바꾼 기존 값의 자동 복구는 하지 않는다.
- 손상된/알 수 없는 envelope와 JSON 외 숫자를 거부하고, 기존 형식의 정확한 불일치 거부를 유지한다.
- 원본은 읽기 전용으로 다루고 소유 자원만 사용한다. provider/HTTP·AWS·운영 작업은 하지 않는다.

## 작업과 검증

- [x] 제품 변경 전 actual100 비교를 수집한다. end_sec의 float hex가 1ULP 다름을 확인하고 원래 실패를 별도로 보존한다.
- [x] 실패 확인: 실제 MySQL AnalysisSource/IncidentClip의 숫자 정밀도 보존 발행이 불변 비교에서 실패한다.
- [x] `src/daesingo/recording/prepared_metadata.py`에 집중 codec을 추가하고 두 prepared kind의 `_row`, `_get`, `_models`에만 연결한다.
- [x] 통과 확인: codec 경계(비정규화 최솟값 영역/최대 float/음의 0/Unicode/비유한 값/손상), 실제 MySQL 정확한 읽기/재전달/충돌/메타데이터 전용 연결/기존 형식 호환성.
- [x] 새 시험 식별자를 독립 MySQL 목록에 보존한다.
- [x] 기존 청크/불변성 집중 회귀, Runtime 품질·경계·계약·공백 검사를 수행한다.
- [x] 단계별 예산을 다시 확인한다. actual10 이후 동일한 actual100으로 commit/새 물리 연결 읽기/분리된 Search/전송 차단 상태의 엄격한 디코딩을 확인한다. 선행 gate 통과 뒤에만 조건부 240을 진행한다.
- [x] 새 읽기 전용 검토자가 구현·증거·결론을 확인하고 지적을 수정·재확인한다.
- [x] 원본·보호 자원을 검증하고 작업 소유 자원만 정리한다. 최초 실패를 보존한 채 최종 결과를 기록한다.

## 검토 중점

- nextafter 수준의 정확한 차이도 충돌로 유지하고 행/청크/Case 연결은 변경하지 않는다.
- 중첩 IncidentClip provenance와 목록/읽기/메타데이터 전용 경로가 같은 디코딩 경계를 사용한다.
- 인식된 형식의 손상된 envelope는 외부 구조 변조·알 수 없는 버전을 포함해 기존 형식으로 대체 해석하지 않는다.
- 기존 형식의 동일 재전달은 이전 payload를 다시 쓰지 않는다. 원래 증거 없이 옛 값을 복구하지 않는다.
- 새 저장 표현은 구 코드로 읽을 수 없다. DDL 변경이 없어도 rollback 호환성을 문서화한다.
