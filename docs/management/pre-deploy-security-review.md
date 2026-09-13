# Pre-deploy Security & Privacy Review

> Migration source: 서비스 기획안 1.3의 보안·개인정보 체크. 2026-09-04 회의 결정(`cross-cutting-decisions.md` C-2)으로 체크박스를 **담당 Owner · 확인일 · 판정** 표로 바꿨다. 초안 단계라 아직 아무 항목도 확인하지 않은 상태다.
> **Review Coordinator:** 김준영(PM/공통 기반). Coordinator가 하는 일은 **"BLOCK이 0인가" 확인 하나**다. 각 항목의 self-review와 수정은 담당 Owner의 책임이다.

## 판정 어휘

제품이 신고요건 점검에 이미 쓰는 어휘를 그대로 쓴다(`architecture/module-architecture.md` §4-모듈4 ⑤).

| 판정 | 뜻 | 배포 |
| --- | --- | --- |
| **PASS** | 확인했고 문제 없음 | 진행 |
| **WARN** | 문제가 있으나 배포를 막지 않음. 기록하고 진행 | 진행 (기록 필수) |
| **BLOCK** | 배포를 멈춘다 | **중단** |

**BLOCK이 되는 실패는 좁게 넷이다:** 키 노출 · 인증 우회 · 원본 영상 유출 · 삭제 미동작. 나머지는 WARN.

## 1. 실제 배포 전 검수표

담당 Owner는 v4의 「소유 데이터」 기준이다(`module-architecture.md` §4). 확인일과 판정은 담당 Owner가 직접 적는다. 빈 칸은 "아직 안 봤다"는 뜻이다.

| # | 항목 | 담당 Owner | BLOCK이 되는 실패 | 확인일 | 판정 |
| --- | --- | --- | --- | --- | --- |
| 1 | `.gitignore`에 `.env` (운영진 초기본 + 팀 항목) | 김준영 (공통 기반/운영) | 키 노출 | | |
| 2 | API 키가 Frontend에 없음 | 신유민 (`web`) | 키 노출 | | |
| 3 | 인증 없이 열린 API endpoint 없음 | 김준영 (공통 runtime/api) · 유소연 (`case` 명령 API) | 인증 우회 | | |
| 4 | DB / Object Storage 접근 규칙 확인 | 김준영 (공통 기반) | 원본 영상 유출 | | |
| 5 | 사용자 간 영상 IDOR 방지 | 유소연 (`case`) · 김준영 | 원본 영상 유출 | | |
| 6 | 업로드할 원본/파생영상 범위 정의 | 정철원 (`recording`) | — (WARN) | | |
| 7 | 외부 AI API에 보내는 영상 범위·provider 명시 | 서어진 (`search/providers`) | 원본 영상 유출 (범위 밖 전송) | | |
| 8 | 보관기간 / TTL / 자동삭제 실제 동작 | 정철원 (`recording`) | 삭제 미동작 | | |
| 9 | 학습·평가 데이터 재사용 정책과 고지 — **정책은 확정됨**(재사용 한다 · 평가/학습 2단계 · `modules/case/decisions/correction-log-reuse.md`). 여기서는 고지 문구·동의 저장·익명화가 구현됐는지 확인 | 유소연 (`case`) | — (WARN) | | |
| 10 | raw video 로그 미기록 | 김준영 (마스킹 로거) | — (WARN) | | |
| 11 | 차량번호·정확한 위치 로그 masking | 김준영 (마스킹 로거) | — (WARN) | | |
| 12 | FFmpeg / 파일명 입력 validation | 정철원 (`recording`) | — (WARN) | | |
| 13 | 외부 API payload 전문 · 사용자 free text 전문 · 원본 frame을 운영 로그에 남기지 않음 (`module-architecture.md` §8-5) | 김준영 (마스킹 로거) | — (WARN) | | |
| 14 | `AnalysisScope.hint.free_text`에서 개인정보를 제거한 뒤 외부 provider로 전송 (§4-모듈2 ⑦) | 유소연 (`case`) | — (WARN) | | |
| 15 | `purge_case`가 사용자 원본(`ExternalSourceRef`)을 삭제하지 않음 (§4-모듈1 ⑨) | 정철원 (`recording`) | 원본 영상 손상 = BLOCK | | |
| 16 | 외부 provider `RemoteCopy` 만료·삭제 처리 — delete API 지원 시 호출, 미지원 시 expiry까지 남는다는 사실 기록 (§8-4) | 서어진 (`search/providers`) · 정철원 (registry) | — (WARN) | | |

## 2. 얼굴 모자이크

- 안전신문고 교통위반 신고의 필수 제출 요건으로 확인되지 않았으므로 MVP Must에 포함하지 않는다.
- 블랙박스 업로드·분석은 개인영상정보 처리에 해당할 수 있으므로 privacy architecture는 MVP부터 검토한다.
- 외부 공유·데모에서 실제 영상을 사용하면 비식별 처리를 고려한다.
- 실제 신고 제출용 영상에 자동 얼굴 모자이크를 기본 적용한다고 확정하지 않는다.
- 외부공유·데모·학습데이터 구축·privacy 강화가 필요할 때 선택적 파생영상 blur를 후속 검토한다.

## 3. Source / Derived Video

- 사용자 Source video를 실수로 덮어쓰지 않는다. `recording`이 원본 무변형을 체크섬으로 검증한다.
- 신고용 Derived Evidence(Report Video)에서 압축·timestamp 삽입·블러·재인코딩 등 어떤 변환을 허용할지는 제출요건 확인 후 결정한다. 사후 timestamp 각인은 Report Video에만 허용하고 Incident Clip에는 넣지 않는다(`module-architecture.md` §3-2).

## 4. 배포 전 리뷰 질문

§1 표의 각 행을 검토할 때 보안·개인정보 관점에서 묻는 질문이다.

1. frontend secret / API key
2. 인증 없는 endpoint / IDOR
3. DB / Object Storage 접근규칙
4. source / proxy / derived video 저장 위치와 TTL
5. 외부 AI provider에 전송하는 파일 / clip 범위
6. 차량번호·GPS·주소·영상 metadata 로그
7. 학습 / 평가 데이터 재사용 동의와 비식별
8. FFmpeg / file parser 사용자 입력 validation
9. 삭제 요청 / 자동파기
10. 불필요하게 수집하는 개인정보

WARN·BLOCK 판정에는 다음 형식으로 사유를 남긴다.

```
[위험도 / 무슨 일이 일어날 수 있나 / 고치는 법]
```

확실하지 않으면 추측하지 않고 `확인 필요`로 표시한다. `확인 필요`는 PASS가 아니다.

## 5. 현재 상태

- [ ] 배포 전 전체 리뷰 수행 — §1 표의 16행 전부 확인일·판정이 채워졌는가
- [ ] **BLOCK 0건** — Coordinator(김준영) 확인
- 고친 것: `[실제 배포 전 입력]`

경로(trajectory)가 맞았는지는 이 문서가 아니라 `tool-trajectory-review.md`가 본다. 둘은 형제 문서이고 같은 판정 어휘를 쓴다.
