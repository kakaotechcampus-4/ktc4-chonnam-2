# 기존 EC2 — 원본 15개 전체 Coarse 준비 완료 실측

**Status: Result · 운영자 제공 EC2 증거 · 준비/송신 직전 guard/자동 복구 PASS. 실제 provider·제품 배포·Case/Web E2E·Package READY·다운로드는 NOT_RUN.**

기록일은 운영자 증거의2026-11-05(KST)다. #452의 준비시간 측정 요청에 따라 #580 병합 실행물로 수행한 격리 실험을 기록한다. 이 문서는 결과 근거이며 운영 Search/Case 정책이나 실제 E2E 예산의 결정이 아니다.

## 근거와 확인 주체

| 구분 | 근거·확인 범위 |
| --- | --- |
| 운영자가 실행·제공한 결과 | 로컬 보호 증거 `operator-final-result.private.json`과 [#452 최신 공유6641419996](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452#issuecomment-6641419996). 아래 EC2 측정·정리·복귀 상태는 이 두 근거의 보고값이다 |
| 이번 문서화에서 직접 확인 | 보호 JSON의 수치/상태, 공유 댓글과의 일치, [#580](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/580)의 merged 상태/병합SHA, 로컬 고정 package manifest의 revision/hash·실험config, 문서 링크·비노출·diff |
| 이번 직접 실행하지 않은 것 | AWS/EC2 조회, 영상 변환·DB/복구 재실험, 실제 SDK/HTTP/provider, 제품 배포·Case/Web E2E. 운영 결과를 에이전트의 직접 서버 검증으로 표기하지 않는다 |

원본명/목록·media payload·개인정보·운영자 owner·서버/사용자 경로·계정/endpoint·bucket·credential 값은 공개 문서에 옮기지 않는다. 보호 JSON과 기존 실패 원본은 유지한다.

## 실행 환경·고정 조건

| 항목 | 운영자 보고 / 실행물 결속값 |
| --- | --- |
| 환경 | 기존 EC2의 격리 실험. 신규 제품 revision의 운영 배포와 구분 |
| 고정 revision | `8b32924ee69e19cd177eababa4887909bf288db0` — #580 병합SHA |
| package manifest SHA-256 | `501749ab1bc57782021dda2f6b04bf5c60de4d76d4f070b97846f514d003df05`. 운영자 JSON과 로컬 manifest 대조 일치. 로컬 구조는270파일이며 이 대조가 서버 실행의 독립 재검증을 뜻하지는 않음 |
| 입력 | 동일 원본15개 전체·logical 길이 **1584.173332초**. 운영자 공유의 hash/size/mtime 대조 PASS.20분 절단 성공으로 대체하지 않음 |
| 선행 검증 | 새 실행물의 무미디어 acceptance·10초 smoke·120초 대표 구간 PASS(운영자 공유) |
| 실험 모드 | `probe_profile=full15-512m`, `full_probe_mode=coarse_270p_stop_before_send` |
| Coarse | **270p·CRF28**, 기존 배속 변환 유지. 디코더 최적화 미적용. 품질 동등성이나 일반 운영 채택을 이 결과로 재판정하지 않음 |
| 준비 상한 | `full_search_prepare_budget_ms=900000` — 격리 준비 단계의 유한900초. 일반 운영 Search150초·Case 정책·기존 cap 변경 없음 |
| CPU 결속값 | runner quota2,DB quota0.5,cpus0·1. 로컬 package config에서 확인한 실험값이며 운영 호스트 전체 자원 보장값이 아님 |

실행/계측/guard의 경계는 [고정 revision의 준비 runbook](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/8b32924ee69e19cd177eababa4887909bf288db0/docs/runtime/experiments/2026-11-05-coarse-preparation-measurement-runbook.md)을 참조한다. 준비 문서와 과거 NOT_RUN 기록은 당시의 상태로 보존하고, 이번 실측을 소급 삽입하지 않는다.

## 측정 결과

| 항목 | 운영자 제공 관측 |
| --- | --- |
| 전체 scope | `PASS_ALL_FIFTEEN_EXACT_ENDPOINT` |
| Recording 결과 | **425,679,447B** |
| 새 연결 DB 재조회 | **PASS_HASH_LENGTH_DETACHED** |
| Coarse 준비 완료 | `search_prepare_completed=true`, **173.771196208초** |
| 최종 Search media | **34,016,924B**, 기존40MiB(41,943,040B) 이내 |
| 출력 duration | **3168.0초** |
| request guard | **PASS_STOP_BEFORE_SEND** |
| SDK 진입 sentinel | **1회** — 송신 직전 차단 지점 진입이며 실제 SDK body 호출수가 아님 |
| 실제 provider | **0회**. SDK body·provider HTTP 송신 미실행 |
| 준비 중 cgroup 표본 최대 | **1,241,538,560B** |
| runner cgroup peak | **1,912,156,160B** |

준비 시간은 원문 `173.7711962079993`초를 소수9자리로 반올림했다. Recording 재생성·DB 조회를 포함한 전체 준비/제품 완료시간이나 실제 전송/provider 응답시간이 아니다. 측정 경계는 하네스의 MediaPreparer 완료 지점이며, request guard는 별도 확인이다.

**출력3168초와 입력1584.173332초는 다른 값이다.** 전자는 기존 Coarse 배속 변환으로 만들어진 재생용 media의 duration, 후자는 원본 전체 logical 길이다. 출력 duration을 원본 길이로 바꾸어 적거나20분/26분 지원 범위로 재해석하지 않는다.

메모리1,241,538,560B는 준비 단계의 **표본 최대**이므로 표본 사이의 연속 peak를 보장하지 않는다.1,912,156,160B는 **runner cgroup peak**이며 Search 준비 단계만의 peak나 호스트 전체 메모리가 아니다. 두 수치의 범위/측정 방식을 구분하고 작은 단회 관측을 다른 입력의 메모리 상한으로 외삽하지 않는다.

## 자동 복구·정리·운영 복귀

아래는 운영자가 실행 후 제공한 상태다. 이번 문서화에서 서버에 재접속하거나 서비스를 재시작하지 않았다.

| 항목 | 보고값 |
| --- | --- |
| session | `status=PASS`, `host_passed=true`, `original_recovered=true` |
| full | `status=PASS`, `cleanup=true` |
| 정리 세부 | cleanup 오류0·잔존 자식0 |
| 서비스 복귀 receipt | **PASS** |
| 서비스 | Docker·Caddy·mount 모두active,API/MySQL healthy·Worker 실행 중(운영자 공유) |
| readiness | API READY **200**, Worker status **OK** |
| 배포 dirty 상태 / 운영 잠금 | **ABSENT / ABSENT** |

운영자는 콘솔 재로그인 후에도 별도 재시작 없이 종료 결과를 확인했다고 공유했다. 이는 이번 고정 실행물의 자동 복구 성공 관측이며 이전 자동 복구 실패의 원인을 확정하는 근거는 아니다.

## 이전 실패와의 관계

[기존 준비 runbook](./2026-11-05-coarse-preparation-measurement-runbook.md)의 이전150초 deadline 실패와 자동복구 미완료·별도 수동복구 기록은 보존한다. 당시 source copy 약1.617초·재인코딩 약148.383초 후 중단된 **29,622,320B는 미완성 출력**이며, 이번 완성 media34,016,924B와 구분한다.

이번 자동 복구 PASS로 이전 실패를 성공으로 덮거나, broken output 등 특정 가설을 실제 원인으로 확정하지 않는다. **이전 자동 복구 실패 원인은 UNKNOWN 유지**다.

## 해석·남은 결정·NOT_RUN

- 이번 단회에서는 전체 입력의 Coarse 준비와 최종 media/request guard까지 통과했다. **준비만173.771초로150초를 초과**하므로 현재150초 Search 상한으로 이 동일 경로의 전체 Search 완료를 보장할 수 없다.
- **900초는 이번 격리 준비 실험의 상한**이다.173.771초나900초를 실제 E2E 실행 예산·일반 운영값·장시간 지원 보장으로 자동 채택하지 않는다.
- Search는 실제 전송/provider 응답·기존 재시도·수용 여부/비용을 포함한 유한 E2E 예산 후보와 적용 범위를 검토하고,Case는 `max_latency_sec` 적용 시 #564의 대기 공식·60분 상한·late 반영을 대조한다. 최종 숫자는 PM과 관련 Owner가 별도로 결정한다. Runtime은 실행/재시도·배포/복귀 호환성을 대조한다.
- **실제 provider·제품 배포·Case/Web E2E·Package READY·신고영상 다운로드는 NOT_RUN**이다. 실제 provider 수용성·응답시간·비용도 미측정이며 이번 준비 PASS를 제품 전체 완주로 확대하지 않는다. #452는 **IN_PROGRESS**로 유지한다.

이번 변경은 별도 결과 문서와 실험 인덱스 연결뿐이다. 직접 로컬 확인은 자료/수치/링크/비노출/diff 대조이며,코드·운영 설정 변경·재실험·AWS·배포·commit/push·외부 게시는 하지 않는다.
