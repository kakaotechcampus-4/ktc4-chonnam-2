# Final writer C 구현·검증 계획

기준: 사용자가 준비한 `codex/issue452-final-writer`, clean HEAD/B `ce0750d5a3317ad1c810783d67f8a05ba88bce08`. 이 브랜치에서 작업하며 checkout·commit·push·게시를 하지 않는다. #583 썸네일·Case·Worker 기능과 운영 설정은 변경하지 않는다.

목표: C 기본 신규 쓰기를 chunk/envelope로 복귀한다. B의 dual reader·exact 비교·기존 표현 보존·SAVEPOINT·RR 보완은 유지한다. 실제 O/B 고정 source와 현재 C를 구분하며 B→C→B 읽기·metadata-only·재전달을 확인할 검사를 준비한다. C 이후 O rollback은 승인하지 않는다.

## 1. 기본값과 revision 역할의 RED

- `tests/recording/test_compatible_release.py`: 옵션 없는 실제 repository의 envelope 기본값, 명시 legacy 정책과 잘못된 정책 거부를 구분한다.
- `tests/recording/test_compatible_revision_sources.py`: O/B 고정 SHA, 현재 C root, Git archive의 실제 B source를 DB 없이 검사한다.
- 현재 구현에서 위 검사의 실패를 먼저 기록한 뒤 기본값과 fixture를 변경한다.

## 2. 최소 제품 변경과 historical 검사 정리

- `src/daesingo/recording/mysql_repository.py`: release 기본값과 설명만 변경한다. 메서드 구현은 B와 byte 단위로 유지한다.
- 기존 legacy 정책 검사는 현재 C의 명시 legacy guard 검사로 이름/정책을 구분한다. 실제 B라고 보고하지 않는다.
- 한도 검사는 C의 실제 default path와 명시 legacy를 구분하며 기존 transaction·packet·정밀도 assertion을 유지한다.

## 3. 고정 B와 현재 C의 전이·production default 검사

- `test_compatible_revisions_mysql.py`: O=`e50b2976ef4edc3a030cfc5b03a5206340dd917b`, B=`ce0750d5a3317ad1c810783d67f8a05ba88bce08`, C=현재 source. 각 revision을 독립 subprocess로 import한다. B legacy 신규 쓰기·C 재전달의 raw 불변성·C metadata-only/envelope/chunk·B 읽기/재전달과 O 거부를 검사한다.
- `test_final_writer_mysql.py`: 실제 API command·Worker analysis/incident factory가 생성한 repository를 통해 합성 media를 쓰고 raw SQL로 envelope/chunk를 확인한다. repository/쓰기 옵션은 대체하지 않는다. Case/provider/encoding 경계는 시험용으로 중단하므로 전체 HTTP/handler E2E와 구분한다.
- 신규 필수 identity는 `recording_acceptance.py`와 독립 checker에 함께 추가한다. 기존 strict gate·timeout·skip은 완화하지 않는다.
- MySQL과 actual-source offline 검사를 실행하는 regression CI의 pinned commit/tree 사전검사를 O/B 고정 SHA와 일치시킨다. C는 실제 checkout이며 과거 `ceb6f5fa`를 최종 C로 사용하지 않는다.

## 4. 실행 범위와 완료 기록

현재 C: free7589703680bytes, Windows available memory6703976448bytes, Ubuntu/Docker Desktop Stopped, 시험 DB URL 없음. 이전 native venv/report root 미발견 이력도 있으므로 Ubuntu/Docker 기동·image 복제·로컬 DB 재구축은 하지 않는다. 실제 MySQL·production default DB 쓰기·canonical/strict/실제 변조는 로컬 NOT_RUN이며 기존 원격 CI에서 실행할 수 있게 준비한다.

- 실행: 관련 offline 검사, 실제 Git source archive/identity, collection/mandatory inventory, lint/type·경계/계약 중 변경에 필요한 검사, YAML·Bash 사전검사, diff 검사.
- 독립 리뷰: 변경 범위와 검증 한계를 reviewer에게 전달하고 확정 지적을 처리한다.
- `docs/runtime/final-writer-c.md`: 결과·미실행·Draft 본문·배포 전 조건을 기록한다. 고정 source와 운영 SHA/image/승인을 혼동하지 않는다.
- Coarse600초와 종료 후 새 reader를 유지한150초 복귀/기존600초 scope 정산을 유지한다. AWS·운영 DB·publish·배포·원본 E2E·backup/restore는 NOT_RUN이다.

## 실행 결과

기본값/revision 역할의 실제 RED→GREEN, 관련 offline·source identity·codec, 새 필수 identity checker, collection audit, Ruff·경계/계약·제품 AST·YAML/Bash 검사를 실행했다. 독립 리뷰의 regression shallow history P1을 처리하고 재확인했다. 실제 DB·수정 후 원격 CI는 NOT_RUN이며 최종 수치·근거·한계는 `docs/runtime/final-writer-c.md`를 따른다. 체크 여부나 source 검사로 DB gate·배포 승인을 대신하지 않는다.
