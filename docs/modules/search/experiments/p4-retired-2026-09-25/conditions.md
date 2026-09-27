# p4 종료 및 실험 조건 보존

상태: 2026-09-26 사용자 결정으로 종료. p4 구현은 새 브랜치에 이식하지 않는다. p3 운영 기본값을 유지한다. 이 폴더의 원문은 과거 기록이며 현재 정책이 아니다.

## 두 회차 공통 조건

- 실행일 2026-09-25, 기존 `feature/search-gemini-p4`, 기준 커밋 `1b85147`, 미커밋 p4 구현. 두 번째 회차에는 deadline 이식 및 후보별 의미 오류 격리를 추가했다.
- 동일 로컬 7영상, 입력 SHA-256은 각 결과 JSON에 있다. 신규 YouTube 3개의 라벨은 사용자 제공이며 프레임 교차검증 전이다. `141628` 음성 라벨에도 잔여 불확실성이 있다.
- 기존 OpenAI 호환 프록시, `gemini-3.8-flash`, reasoning `low`, Coarse 1 fps/최대 360p, Fine 2 fps/최대 720p, 무음 MP4 준비, 후보 앞뒤 4초 여유, 영상별 180초 상한, 재시도 0회.
- 정답지에서 사건 유형만 선택했다. 중앙선 1영상, 실선 6영상. 정답 시각을 모델에 주지는 않았지만 유형을 미리 알고 제한한 조건이므로 일반 검색 성능으로 해석하지 않는다. 생성된 후보 전부 Fine 실행, 각 회차 단회.
- 기존 리포트의 1 ms 이상 구간 교차는 당시 탐색 점검값이다. 공식 Coarse 핵심 시각 매칭이나 정확도 지표로 사용하지 않는다. eval 합의 요청은 [#158](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/158).
- 모델 자유 서술 원응답, 영상, API 키는 기존 JSON에 저장하지 않았다. 오류 호출의 구조화 상태 보존 범위는 두 회차가 다르다. 원응답을 사후 복원하지 않는다. 단가 설정이 완비되지 않아 비용을 산출하지 않았다.
- 정확한 호출별 생성 시각, 당시 미커밋 코드 전체 fingerprint는 기존 기록에 없어 확인 불가다. 추정값을 채우지 않는다. 원 코드 복구 패치와 비추적 파일 아카이브는 Git 제외 로컬 실행 ledger에만 보관했다.

## 보존한 결과

| 회차 | 호출 | Fine | 기록 |
| --- | --- | --- | --- |
| 첫 실행 | 14 | NOT_OBSERVED 2, UNCERTAIN 1, 오류 4, OBSERVED 0 | [보고서](../gemini-p4-seven-video-probe-2026-09-25.md), [JSON](../gemini-p4-seven-video-2026-09-25-results.json) |
| deadline·예외 처리 후 | 19 | NOT_OBSERVED 4, 오류 8, OBSERVED 0 | [보고서](../gemini-p4-seven-video-deadline-exception-2026-09-25.md), [JSON](../gemini-p4-seven-video-deadline-exception-2026-09-25-results.json) |

두 보고서와 두 JSON은 원본과 byte 단위로 동일하게 복사했다. 종료한 적용 결정도 [원문 snapshot](original-challenger-decision.md)으로 보존한다.

## 당시 프롬프트 원문

아래 SHA-256은 파일 바이트 기준이다. 실행 기록의 prompt fingerprint는 조합된 템플릿 기준이므로 각 파일 해시와 구분한다.

| 원문 | SHA-256 |
| --- | --- |
| [coarse-p4.txt](prompts/coarse-p4.txt) | `f51753ef96df96fc6fff154a55def6e5464a893f037a238a4b3a9873eccbfe96` |
| [fine-p4-center-line-crossing.txt](prompts/fine-p4-center-line-crossing.txt) | `ba3f5c6c3c66e5c36ab512d94fb5ba5b86048f5e789165b7641c4e7e2acb19ac` |
| [fine-p4-motorcycle-helmet-non-use.txt](prompts/fine-p4-motorcycle-helmet-non-use.txt) | `4b85a6d7aab86a9941db17e41af167230cdab3d04238ef51daf59bf73314749a` |
| [fine-p4-signal.txt](prompts/fine-p4-signal.txt) | `13e432923f75b82e1d60a8f7ea30b6afe879c5712a6910afcd7f2fcb231811e3` |
| [fine-p4-solid-line-lane-change.txt](prompts/fine-p4-solid-line-lane-change.txt) | `033e6c55e4ff6c6c18bff2591a367d83ffee4368b34c493378eb5dc149265341` |
| [fine-p4.txt](prompts/fine-p4.txt) | `7fa46f6e205666ec0fa97dbd73df168e5eeae936cca8ae49584a35174bfc3fc9` |
