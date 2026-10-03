# Research Prompt 02 — API ↔ Worker Media Persistence / Upload

> **추적 정보** — 이 블록은 조사 대상이 아니다. 결과 문서에서 근거를 Decision ID에 연결하는 데만 쓴다. 아래 문서명은 조사자가 열람할 수 없고 열람할 필요도 없다.
>
> - Source: 대신고 `decision-classification.md` §6 External Research Queue
> - R1 · RD-17a · RD-17b — Compose에서 두 container의 파일 공유 · file-backed metadata 복원
> - R1 · RD-05e · RD-17a — FastAPI / Starlette 대용량 영상 upload
> - 인접(필요 시): RD-17c · RD-17d — Queue 항목은 아니며, 위 질문의 답이 직접 걸리는 범위에서만 근거를 연결한다
>
> 사용법: 이 파일 전체를 새 웹 리서치 대화에 그대로 붙여 넣는다.

---

다음 기술 조사를 수행하세요. 주제는 **Docker Compose 위의 두 container(API · Worker)가 업로드된 영상 파일과 그 등록 정보를 함께 다룰 때의 실제 동작 · failure mode, 그리고 FastAPI / Starlette가 대용량 영상 upload를 받을 때의 자원 사용 방식**입니다.

이 조사는 결정을 내리는 작업이 아닙니다. 아래 Decision의 **선택지 · 제약 · failure mode · 검증 항목을 현실화하는 근거**를 모으는 작업입니다. 최종 선택은 별도 단계에서 팀이 합니다.

## 1. 프로젝트 맥락

**대신고**는 블랙박스 영상을 받아 교통법규 위반 신고 자료 준비를 보조하는 서비스입니다. 사용자가 영상을 올리면 서버가 비동기로 영상 변환(ffmpeg), 외부 AI API 호출을 통한 후보 구간 탐색, 번호판 판독 등을 실행합니다. 6명 팀의 10주 MVP입니다.

현재 Runtime baseline(이미 정해짐):

- AWS EC2 1대 — t3.medium(2 vCPU · OS 기준 약 3.7 GiB usable RAM) · Ubuntu 24.04 · gp3 50 GiB root EBS 1개
- Docker Compose로 `api` · `worker` · `mysql` 세 service를 따로 띄운다. api와 worker는 같은 image 계열이고 command만 다르다
- FastAPI API process 1 · Worker process 1 · Worker concurrency 초기값 1
- 작업 queue는 MySQL 8.4 테이블(DB Queue)이다. MySQL은 이미 두 process가 함께 접근하는 저장소다
- 배포는 GitHub Actions OIDC → AWS role · SSM Run Command 방향으로 확정됐다

**지금 풀어야 하는 상황(사실):**

- api와 worker는 **별도 process · 별도 container**다.
- 영상 등록 상태를 관리하는 recording repository는 현재 **process 메모리(in-memory)** 에만 있다. 원본 파일의 등록 정보(SourceAsset · MediaStream), 그 파일의 local 경로(locator), timeline 등을 dict로 들고 있다.
- local 파일을 등록하면 호출마다 새 opaque ref(`sa_*` · `ms_*` 형태)를 발급하고, 그 등록을 해당 process 메모리에만 남긴다.
- 따라서 **API가 upload를 받아 등록해도 Worker는 그 등록도 파일도 볼 수 없다.** 어느 process든 restart하면 발급된 ref가 가리킬 대상이 사라진다.
- 요구: API에서 등록한 upload/source를 **Worker가 나중에 조회**할 수 있어야 하고, **restart 뒤에도 필요한 ref가 복원**될 수 있어야 한다.
- 파일 접근 방향(현재 구조 기준): 원본 파일은 API가 수신해 쓰고, Worker는 그 원본을 ffmpeg / ffprobe로 **읽기만** 한다. Worker는 변환 temp 출력과 파생 파일(분석용 영상 · 사건 clip)을 따로 만든다. 원본과 파생 파일의 저장 위치를 같게 할지 · 나눌지는 정해지지 않았다.

**disk · memory 사정(사실):**

- 50 GiB 한 disk를 MySQL data · Docker image/layer · 변환 temp 출력 · 분석용 파생 영상 · 사건 clip · log · OS가 함께 쓴다. 운영 측은 Docker build cache 누적을 disk 부족의 가장 흔한 원인으로 안내한다.
- 현재 Worker는 준비된 분석용 영상 · clip bytes를 process 메모리에 들고 있어, working set이 disk보다 **Worker RSS에 먼저 쌓이는 상황**이 관찰됐다.
- 업로드 영상의 크기 · 길이 분포는 **아직 측정 전**이다. 특정 크기를 가정하지 말고, 크기가 커질수록 어느 자원이 먼저 한계에 닿는지를 구조로 설명하세요.

**이미 정해져 있어 다시 열지 않는 것:**

- Object Storage(S3 등)는 baseline 의무가 아니다. 도입하더라도 storage adapter 뒤에 둔다. 「local 재사용 성능 이득」만으로 먼저 도입하지 않는다.
- local 재사용(cache)은 durability guarantee가 아니다.
- 사용자가 올린 원본 파일을 시스템이 덮어쓰거나 지우지 않는다(시스템이 만든 관리 자산만 삭제 대상).
- 외부 공개 계약에 파일 경로(locator)를 노출하지 않는다.
- 외부 AI provider에 영상을 어떤 형태로 보낼지(원본 · 부분 · proxy · 분할)는 이 조사 범위가 아니다.
- 인증 방식은 이 조사 범위가 아니다.

**미리 정하지 않은 것:** shared volume을 쓴다고도, Object Storage를 쓴다고도 정하지 않았습니다. 후보와 trade-off만 조사하세요.

## 2. 이 조사가 근거를 제공할 Decision

| ID | 열린 질문 | 우선순위 |
| --- | --- | --- |
| RD-17a | 업로드된 원본 파일을 API와 Worker가 함께 접근하는 경로 — 어떤 파일 공유 경계(공유 파일 시스템 · storage adapter · 기타)를 두는가 | R1 |
| RD-17b | 원본 등록 metadata와 그 local locator가 process 메모리 밖에서 유지되는 위치 | R1 |
| RD-05e | upload endpoint 방식 — 요청 형식 · 크기 한도 전달 · 업로드 완료와 source 등록의 관계 | R1 |
| RD-17c (인접) | recording 상태 중 process 경계를 넘어야 하는 범위와 그 persistence 인터페이스 경계 | 필요 시 |
| RD-17d (인접) | 발급된 `sa_*` · `ms_*` ref가 restart 뒤에도 같은 자산을 가리키는지와 그 복원 방식 | 필요 시 |

RD-17c · RD-17d는 대부분 내부 설계 판단입니다. 일반 기술 패턴(예: ref와 저장 위치의 mapping을 어디에 두는가)이 Part A 답에서 자연스럽게 나올 때만 연결하세요.

## 3. 조사 질문

필요한 경우 인접 질문까지 확인하되, **위 Decision을 닫는 데 필요한 범위로 제한**하세요.

### Part A (R1 · RD-17a · RD-17b) — Compose에서 두 container가 같은 media 파일을 공유할 때

1. **bind mount vs named volume** — 현재 Docker / Docker Compose 문서 기준으로:
   - 두 방식의 동작 차이(host 경로 노출, 최초 mount 시 image 내용 복사 여부, 생성 · 삭제 시점, `docker compose down -v` 등 정리 명령의 영향)
   - backup · 운영자 접근 · host disk 사용량 관찰의 차이
   - container 재생성(`docker compose up`으로 image가 바뀔 때) · host 재부팅 뒤 데이터 유지 여부
2. **uid / gid · permission · ownership** — api와 worker가 non-root user로 돌 때, 두 container의 user가 다르거나 host user와 다를 때 생기는 권한 문제. bind mount와 named volume에서 ownership이 어떻게 정해지는가. umask · group 공유 패턴.
3. **atomicity · partially-written file** — 한 container가 파일을 쓰는 중에 다른 container가 그 파일을 읽을 때의 동작. 「temp 이름으로 쓴 뒤 rename」 패턴이 atomic한 조건(같은 filesystem 안이어야 하는지, mount 경계를 넘으면 어떻게 되는지). `fsync` · directory fsync가 필요한 조건.
4. **동시 접근** — 같은 파일 · 같은 directory를 두 process가 동시에 쓰거나 지울 때의 failure mode. advisory file lock(`flock` / `fcntl`)이 같은 host의 두 container 사이에서 작동하는가.
5. **cleanup** — 누가 언제 파일을 지우는가에 따른 failure mode: 읽는 중 삭제, 등록 정보는 있는데 파일이 없는 경우(stale reference), 파일은 있는데 등록 정보가 없는 경우(orphan).
6. **restart · container recreation · host restart** — 각 상황에서 파일 · 등록 정보 · 진행 중이던 쓰기가 어떻게 되는가.
7. **file-backed metadata 복원 패턴** — process 메모리에 있던 등록 정보를 process 밖에 두는 일반적인 패턴과 trade-off:
   - 이미 있는 MySQL에 등록 정보를 두고 파일은 공유 경로에 두는 방식
   - 파일 옆에 metadata 파일(sidecar)을 두는 방식
   - 공유 volume 위의 embedded DB 파일(예: SQLite)을 두 container가 함께 여는 방식 — 동시 접근 제약 포함
   - Object Storage에 파일을 두고 metadata는 DB에 두는 방식
   - 각 방식에서 「파일 쓰기」와 「metadata 기록」이 서로 다른 저장소일 때 생기는 불일치(한쪽만 성공)와 그 일반적 대응
8. **Object Storage 후보와의 비교 축** — 같은 요구(두 process 공유 · restart 뒤 복원)를 Object Storage로 풀 때 달라지는 점(local 경로가 사라짐 · Worker가 처리 전에 다시 내려받아야 함 · 비용 · 권한 · 지연). 도입을 추천하지 말고 비교 축만 정리하세요.

### Part B (R1 · RD-05e · RD-17a) — FastAPI / Starlette 대용량 영상 upload

현재 FastAPI · Starlette · python-multipart 버전 기준으로 확인하세요. 버전별로 동작이 바뀐 부분이 있으면 버전을 구분하세요.

1. **multipart 처리 경로** — `UploadFile`로 받을 때 request body가 어디에 쌓이는가. `SpooledTemporaryFile`의 memory → disk 전환 threshold와 그 값을 정하는 위치. 전환 뒤 temp 파일이 생기는 directory(container 안 `/tmp` 등)와 그 directory를 바꾸는 방법.
2. **request body buffering** — endpoint 함수가 호출되기 **전에** body 전체가 수신 · 파싱되는가. form 파싱 단계의 memory 사용.
3. **streaming 수신** — multipart를 쓰지 않고 `request.stream()` 등으로 raw body를 받아 직접 파일에 쓰는 방식의 동작 · 제약. streaming multipart parser를 직접 쓰는 방식.
4. **최대 크기 제한을 거는 위치** — 다음 각각이 크기 한도를 제공하는지, 제공하면 어떤 단위로 언제 거부하는지:
   - application(FastAPI / Starlette 설정 · multipart parser 옵션 · 직접 구현)
   - ASGI server(Uvicorn 등)
   - reverse proxy(Nginx · Caddy 등) — reverse proxy를 둘지 · 무엇을 쓸지는 이 조사 범위가 아니다. **둔다면** limit과 request buffering이 어떻게 작동하는지만 확인하세요(예: proxy가 body를 disk에 먼저 buffering하면 같은 파일이 두 번 disk에 쓰이는지)
5. **interrupted upload** — client가 upload 중간에 끊으면 어떤 예외 · 상태가 생기는가. 이미 생성된 temp 파일은 누가 언제 지우는가. process가 upload 처리 중 죽으면 temp 파일이 남는가.
6. **temp file cleanup** — `UploadFile` close 시점, request 종료 시 자동 정리 범위, 비정상 종료 뒤 잔여 파일.
7. **단일 EC2 · 제한된 RAM · disk에서의 자원 위험** — 위 동작을 1절의 환경(약 3.7 GiB usable RAM · 50 GiB 공유 disk · Worker RSS 선행 적재)에 적용했을 때:
   - 업로드 1건이 RAM · temp disk · 최종 저장 위치에 각각 몇 번 쓰이는가(복사 횟수 구조)
   - 동시 upload 수가 늘 때 먼저 한계에 닿는 자원
   - Worker가 같은 파일을 처리하는 중에 새 upload가 들어올 때의 경쟁
   - 수치를 만들지 말고 **구조와 관찰해야 할 지표**로 설명하세요
8. **업로드 완료와 source 등록의 관계 — 일반 패턴** — 수신 완료 뒤 검증 · 등록을 한 번에 하는 방식, upload session 생성 → 업로드 → finalize의 2단계 방식, checksum 검증, resumable / chunked upload protocol(예: tus), Object Storage presigned URL 직접 업로드. 각 패턴이 Part A의 공유 경계 선택과 어떻게 맞물리는지만 정리하고 추천하지 마세요.

## 4. 범위 밖

다음은 조사하지 마세요.

- 외부 AI provider로 영상을 보내는 전략(원본 · 부분 · proxy · 분할)
- 공개 endpoint · domain · TLS 구성
- 인증 · 권한 설계
- 개인정보 보관 기간 · 파기 법령
- Worker 수를 늘리는 scaling 판단
- Kubernetes · ECS · EFS 등 새 topology 추천

## 5. 조사 방법

자료 우선순위:

1. 기술 자체의 최신 공식 문서 (Docker · Docker Compose · FastAPI · Starlette · python-multipart · Uvicorn · Linux man page)
2. 공식 AWS 문서 (Object Storage 비교 축에 한함)
3. 신뢰할 수 있는 engineering / architecture 자료
4. 해당 OSS의 공식 GitHub issue · discussion · source (Starlette · python-multipart의 실제 buffering 동작은 source 확인을 권장)
5. 커뮤니티 글은 보조 근거로만

- 현재 시점 기준 최신 정보를 확인하세요.
- **버전을 반드시 구분하세요.** Starlette · FastAPI · python-multipart는 upload 처리 동작이 버전마다 바뀌어 왔습니다. 확인한 버전과 확인일을 적고, 구버전 동작을 현재 동작처럼 쓰지 마세요.
- 공식 문서가 명시하지 않은 동작은 「문서에 명시 없음」으로 표시하고, source로 확인했다면 그 commit · 파일을 적으세요.

## 6. 출력 원칙

**사실 · 해석 · 적용을 섞지 마세요.** 각 주장에 다음 중 하나를 표시하세요.

- **Verified fact** — 공식 문서 · source가 직접 말하는 사실. 출처 필수
- **Interpretation** — 여러 근거를 종합한 해석. 근거 목록 필수
- **Daesingo implication** — 위 대신고 구조에 적용했을 때의 의미

**최종 선택을 하지 마세요.** 「따라서 named volume이 최선이다」 「따라서 S3를 도입해야 한다」 「따라서 upload는 streaming으로 받아야 한다」 같은 결론을 쓰지 않습니다. 선택지와 trade-off까지만 정리합니다.

**외부 숫자를 대신고 baseline으로 쓰지 마세요.** 다른 서비스가 「upload limit 1GB」 「spool threshold N MB」를 쓴다면, 그 숫자는 **그 환경의 숫자이며 대신고에 직접 적용할 수 없다**고 구분해서 적으세요. library 기본값은 Verified fact로 적되 「기본값」임을 표시하세요.

**작성 언어와 기준일.** 결과는 한국어로 쓰고, 기술 용어 · 설정 이름 · 원문 인용은 영어 그대로 둡니다. 결과 맨 위에 조사 기준일을 적으세요.

**제출 전 자기 점검.** 결과를 내기 전에 「~해야 한다」 「~가 최선이다」 「권장한다」처럼 선택을 확정하는 문장이 남아 있는지 확인하고, 있으면 조건과 trade-off를 설명하는 문장으로 바꾸세요. 출처가 없는 Verified fact가 있으면 Interpretation으로 내리거나 9절(Unresolved)로 옮기세요.

## 7. 결과 형식

다음 구조로 작성하세요.

```markdown
# Research Result — API ↔ Worker Media Persistence / Upload

## 1. Executive Summary
- 조사 결과의 핵심 사실만
- 최종 Decision 추천은 하지 않음

## 2. Questions Investigated
- Part A · Part B 질문별 실제 조사 범위

## 3. Verified Technical Facts
| Fact | Version / Condition | Evidence |

## 4. Options / Patterns
- 파일 공유 경계 후보 · metadata 위치 후보 · upload 수신 방식 · 완료-등록 관계 패턴
- 각 항목에 trade-off

## 5. Failure Modes / Operational Risks
| Failure mode | 발생 조건 | 영향 | 완화 가능성 |

## 6. Daesingo-specific Implications
- 현재 대신고 구조에 직접 적용되는 제약
- 어떤 RD / sub-decision(RD-17a · 17b · 05e, 필요 시 17c · 17d)에 영향을 주는지

## 7. What External Research Cannot Decide
- 대신고 내부 합의가 필요한 것
- 실험이 필요한 것
- External Input이 필요한 것

## 8. Suggested Pre-implementation Checks
- 필요 시 작은 spike / integration test (예: api · worker 두 process에서 같은 source를 등록 · 조회하는 최소 경로)
- 실제 production baseline 숫자를 만들지는 않음

## 9. Unresolved / Unverified
- 확인하지 못한 사실
- 문서 간 불일치
- 추가 확인 필요사항

## 10. Sources
- URL
- 문서명
- 버전 / 게시일 또는 확인일
```

## 8. Research Completion Criteria

이 조사는 다음에 답할 수 있을 때 완료입니다.

- Compose에서 두 container가 같은 파일을 bind mount · named volume으로 공유할 때의 실제 semantics(권한 · atomicity · 정리 · restart · 재생성)를 설명할 수 있는가?
- process 메모리 밖에 등록 metadata를 두는 패턴별 trade-off와, 파일 · metadata가 서로 다른 저장소일 때의 불일치 failure mode를 설명할 수 있는가?
- 현재 FastAPI / Starlette가 대용량 upload body를 어디에 · 언제 쌓는지, 크기 한도를 어느 층에서 걸 수 있는지 버전과 함께 설명할 수 있는가?
- 끊긴 upload · 비정상 종료 뒤 temp 파일이 어떻게 되는지 설명할 수 있는가?
- 단일 EC2의 RAM · disk 제약에서 upload가 만드는 위험을 구조로 설명하고, 관찰해야 할 지표를 구분했는가?
- 대신고에서 spike로 확인해야 할 조건을 구분했는가?
- 외부 조사만으로 결정할 수 없는 부분을 식별했는가?
- 각 결과가 RD-17a · RD-17b · RD-05e(필요 시 RD-17c · RD-17d) 중 어디에 영향을 주는지 연결했는가?
- 핵심 주장에 출처가 붙어 있는가?
