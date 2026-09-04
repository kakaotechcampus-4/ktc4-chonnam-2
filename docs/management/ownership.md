# 대신고 — 모듈 기반 역할 배정안 v2

> **전제 문서:** `product/product-spec.md`·`product/core-user-flow.md` (제품) · `architecture/module-architecture.md` **v4** (구조) · `management/cross-cutting-decisions.md` (운영 역할)
> **이 문서가 하는 일:** 모듈 7개 + 공통 기반/운영을 6명에게 배정하고, 모듈 경계 밖 운영 역할의 담당을 정하고, 각자 **지금 단계에서 무엇을 내놓을지**까지 정한다.
> **v1 → v2에서 바뀐 것:** 절 번호를 v4로 교체 · 운영 역할 표 신설(cross-cutting 결정 11건) · 자료조사 단계 완료 표시 · 배정 근거를 사람이 아니라 **일의 특성**으로 서술 · 계약 표를 v4 §5-1에 맞춤.
> **결정 방식:** 병렬 개발 효율을 1순위로 두고, 그 안에서 PM이 사전 공유한 분배안을 최대한 따랐다. 6명 전원이 사전 분배안과 일치한다.

```text
① 담당 파트 자료조사 ✓  →  ② 모듈안 고도화 ✓ (v4)  →  ③ 데이터 계약 확정 ◀ 지금  →  ④ 목데이터 1차 통합
```

---

# 1. 배정 결과 한눈에

## 1-1. 모듈 Owner

| 이름 | 주 담당 (Owner) | 부 담당 | 초반 / 중반 / 후반 비중 |
| --- | --- | --- | --- |
| **서어진** | **`search`** 사건 탐색 | — | ●●● / ●●● / ●● |
| **김대원** | **`eval`** 성능 채점기 | `web` 영상 화면 | ●●● / ●● / ●●(FE) |
| **신유민** | **`readout`** 화면 값 판독 | **`web`** 화면 Owner | ●(web 골격) / ●●● / ●●●(web) |
| **유소연** | **`case`** 진행 관리·오케스트레이션 | E2E 통합 | ●● / ●●● / ●●● |
| **정철원** | **`recording`** 블랙박스 파일 계층 | — | ●●● / ●●● / ●● |
| **김준영** (PM) | **`evidence`** 증거 확정·신고 준비 + **공통 기반/운영** | 전반 검토·조율 | ●●● / ●● / ●● |

```text
                     ┌──────────── web ────────────┐
                     │ Owner: 신유민 (화면 상태·진행·검토) │
                     │ 영상 화면: 김대원 (후보카드·   │
                     │           타임라인·번호판확대)  │
                     └──────────────┬───────────────┘
                                    │ web은 case.get_view()만 부른다
                     ┌──────────────▼───────────────┐
                     │  case  —  유소연              │
                     │  (유일한 지휘자 · E2E가 여기서 닫힘) │
                     └──┬────────┬────────┬─────────┘
                        │        │        │
        ┌───────────────▼┐  ┌────▼─────┐  │  ┌──────────────────┐
        │ search  서어진  │  │ readout  │  └─▶│ evidence  김준영  │
        │ (최대 리스크)   │  │ 신유민    │     │ (제품 책임·규정)   │
        └───────┬────────┘  └────┬─────┘     └──────────────────┘
                │                │
        ┌───────▼────────────────▼──────────────────────────────┐
        │  recording  —  정철원   (모든 모듈의 맨 아래)           │
        └───────────────────────────────────────────────────────┘
                │                │
        ┌───────▼────────────────▼───────┐   ┌───────────────────────────┐
        │  eval  —  김대원 (단방향 채점)   │   │ 공통 기반/운영 — 김준영     │
        └────────────────────────────────┘   │ common/runtime · 비용 장부  │
                                             │ 마스킹 로거 · CI/CD·테스트   │
                                             └───────────────────────────┘
```

## 1-2. 운영 역할 (모듈 경계 밖) — `cross-cutting-decisions.md` 11건

| 역할 | Primary | Consulted / Support | 근거 |
| --- | --- | --- | --- |
| Product Spec / Must·Won't 변경 최종 승인 | 김준영 (PM) | — | B-1 |
| 발표·스토리 / 최종 Presentation · Demo 숫자 sign-off | 김준영 | 필요 시 각 Owner | B-2 |
| 문서 일관성 · `CLAUDE.md`/라우팅 표 갱신 | 김준영 | — | B-4 · A-3 |
| Product Validation (사용자 인터뷰·시제품 비교) | 김준영 (PM) | 김대원(측정·분석) · 신유민(UX 관찰) · 모집은 전원 | C-1 |
| Security / Privacy Review Coordinator | 김준영 | 각 Owner self-review | C-2 |
| **Tool Trajectory 통과 판정** | **유소연** (`case`) | 김준영(규정 해석) | C-3 |
| **학습 / 평가 데이터 재사용 정책** | **유소연** (`case`) | 정철원(보관·삭제) · 김준영(마스킹 로거·B-1) | C-4 |
| Timeout / Long-running Job Fallback | 유소연 (`case`) | 신유민 (`web`) | A-1 |
| 챌린저 개방 제안 | 서어진 (`search`) | 김대원 (`eval`) · **승인 PM** | A-2 |
| Evidence Rule / 신고요건 변경 | 김준영 (`evidence`) — 별도 서명자 없음, 변경 시 주간 회의 보고 | — | B-3 |

---

# 2. 이 배정에 쓴 규칙 6개

배정은 취향이 아니라 아래 규칙으로 나왔다. **규칙을 어기면 구조가 지켜지지 않는다.**

| # | 규칙 | 왜 | 이 배정에서 |
| --- | --- | --- | --- |
| 1 | **가장 위험한 영역의 Owner에게는 화면을 주지 않는다** | 긴 영상에서 4종 사건을 찾는 것이 제품이 지목한 「가장 위험한 한 곳」(`product-spec.md` §9) | `search` Owner는 단독. FE 없음 |
| 2 | **`search`와 `eval`을 한 사람이 소유하지 않는다** | 자기 결과를 자기가 채점하면 정답지가 편한 방향으로 흐른다 | `search` Owner ≠ `eval` Owner |
| 3 | **관찰(`search`·`readout`)과 확정(`evidence`)을 한 사람이 소유하지 않는다** | "AI가 그렇게 봤다"와 "이 값이 맞다"의 경계는 사람이 다를 때 가장 잘 지켜진다 (v4 원칙 2) | `search`·`readout` Owner ≠ `evidence` Owner |
| 4 | **모듈 하나에 Owner는 한 명.** 공동 개발은 컴포넌트 단위로만 | Owner = 최종 결정권자. 둘이면 계약이 두 벌이 된다 | `web`만 Owner 1명 + 컴포넌트 분담 |
| 5 | **초반에 서로를 기다리지 않는 사람이 최대가 되게 배치한다** | 10주에서 대기 시간이 가장 비싸다 | 초반 4명(`recording`·`search`·`eval`·`evidence`)이 완전 병렬 출발 |
| 6 | **투입이 큰 자리에 통합 부담과 초반 집중 영역을 준다** | 통합은 쪼갤 수 없고, 초반 지연은 뒤로 다 밀린다 | 투입 `상` 두 자리 → `case`(통합), `recording`(초반) |

---

# 3. 사람별 상세

각 항목은 **① 무엇을 소유하는가 → ② 이 일에 필요한 특성 → ③ 자료조사(완료) → ④ 읽어야 할 문서(v4) → ⑤ 지금 단계의 산출물 → ⑥ 누구와 붙는가 → ⑦ 절대 만지지 않는 것** 순서다. ②는 사람이 아니라 **일**을 서술한다.

---

## 서어진 — `search` (사건 탐색)

### ① 소유
긴 영상 1차 탐색(Coarse) · 후보 2차 확인(Fine / Classification) · 실행 기록 `AnalysisRun`(비용·지연·실패 분류) · 프롬프트 · 외부 AI provider 어댑터(`search/providers/` — provider API 호출은 여기서만) · **챌린저 개방 제안**(A-2)

### ② 이 일에 필요한 특성
- **10주 동안 내부가 몇 번이고 바뀔 것이 확정된 영역**이다(baseline → 실패가 증명하면 챌린저). 공식 문서를 보고 직접 구현하고 갈아끼우는 방식이 맞다.
- 성패는 **비용·지연 대비 Recall**이다. 정확도만 보는 일이 아니다.
- 이 영역의 자료조사를 수행한 사람이 그대로 Owner가 되는 것이 손실이 가장 적다.

### ③ 자료조사 — 완료
결과는 `modules/search/research/architecture-input-memo.md`. v4에 반영된 것: Files API + low-resolution·무음 profile baseline(§4-모듈2 ⑤, RT11) · Search는 span만 반환(§3-3, RT6) · `verify_visual(input_ref)`로 candidate-independent Fine(RT7). **남은 확인 항목은 v4 §11-2.**

### ④ 읽어야 할 문서
v4 §4-모듈2 · §3-3(파일 생성 안 함) · §3-5(Visual Event ≠ 신고 유형) · §5-4 `AnalysisScope` · §5-5 `CandidateEvent` · §5-6 `VisualEvidence` · §5-13 `UsageRecord` · §9(채점 구조) · §11-2 · RT6·RT7·RT11 · `modules/search/decisions/challenger-policy.md`

### ⑤ 지금 단계(③ 데이터 계약)의 산출물
- `search_candidates(scope)` / `verify_visual(input_ref, target_hint?)` 시그니처 확정
- `AnalysisRun` · `CandidateEvent` · `VisualEvidence` **계약 초안** (생산자) · `AnalysisScope`는 유소연과 공동
- `UsageRecord`에 필요한 pricing snapshot 최소 필드 제안(§11-2)
- **가짜 구현 1개** — 정답을 하드코딩해서 돌려주는 스텁. 이게 있으면 `eval`·`case` Owner가 즉시 병행 출발한다
- 실패 분류 이름 확정 — `modules/search/decisions/failure-taxonomy.md` 초안을 확정으로

### ⑥ 누구와 붙는가
- **김대원(`eval`)과 상시.** `search` Owner가 실험을 설계하고 `eval` Owner가 같은 정답지로 채점한다. **`search` Owner가 직접 점수를 매기지 않는다.**
- 정철원(`recording`) — `AnalysisSource` profile과 `RemoteCopy` 등록 규칙
- 김준영(`evidence`)과 1회 — `visual_event_type` ↔ 신고 유형 매핑표

### ⑦ 절대 만지지 않는 것
신고 요건·기한·용량 / 진행 상태 / 확정된 값 / 법적 유형 코드 / **번호판·화면시각 판독**(`readout`) / 신고용 mp4 생성 / 코드에 `if eval_mode` / **eval의 존재**

---

## 김대원 — `eval` (성능 채점기) + `web` 영상 화면

### ① 소유
정답지 · manifest 버전 · 참조자료 · locked test · 지표 계산 · 결과 파일 (`eval/` 루트 독립 패키지 — runners / scorers 분리)
**후반부터:** 후보 카드 · 타임라인 · 번호판 확대·프레임 넘기기 화면

### ② 이 일에 필요한 특성
- `eval`은 **제품 코드가 하나도 없어도 시작할 수 있는 유일한 영역**이다. 초반 병렬성이 여기서 나온다. 미리 시작해야 하는 일이다.
- 정답지 스키마와 지표 정의는 **실험을 설계해 본 감각**이 있어야 나중에 다시 만들지 않는다.
- 영상 관련 화면(후보 카드·타임라인)은 AI 결과의 구조를 이해하는 사람이 만들 때 빠르다.

### ③ 자료조사 — 완료
결과는 `modules/eval/research/architecture-input-memo.md`. v4에 반영된 것: Runner/Scorer 분리(§9-2) · A/B/C tier(§4-모듈7 ③) · 비용 분모는 일부만 수용(§4-모듈7 ⑤, RT10). **남은 확인 항목은 v4 §11-5.**

### ④ 읽어야 할 문서
v4 §4-모듈7 · §9 전체 · §2 원칙 8(제품과 Eval은 같은 public capability) · §5-4·5-5 · §11-5 · RT7·RT10 · `modules/eval/initial-evaluation-plan.md` · `modules/eval/experiment-guide.md` · (web) §4-모듈6

### ⑤ 지금 단계의 산출물
- `eval/` 골격 + `python -m eval.run --impl <이름표>` **한 줄로 도는 상태**
- 정답지 10~20건 (초기 12개 테스트 케이스를 실제 파일로)
- **가짜 구현으로 지표 검증** — 항상 정답 / 항상 오답을 넣어 계산이 맞는지 확인
- 4종별 점수를 따로 내는 결과 형식 · Classification(A tier) 지표

### ⑥ 누구와 붙는가
- **서어진(`search`)과 상시.** 단, 채점 기준은 `eval` Owner가 정한다.
- 신유민(`readout`)과 중반 — 번호판·시각 채점 진입점
- 신유민과 `web` 화면 경계 1회 합의

### ⑦ 절대 만지지 않는 것
`search`·`readout`의 **내부 코드**(프롬프트 파일·파서 import 금지) / `case`·`evidence`·`web`의 존재 / 제품 상태 / eval batch 비용을 runtime 비용과 같은 숫자로 보고

> `eval`이 구현 내부를 쓰기 시작하면 구현을 갈아탈 때 채점기도 다시 써야 한다. 그 순간 baseline과 챌린저를 같은 기준으로 비교할 수 없게 되고, 초반 투자가 전부 증발한다. **공개 함수만 부른다**가 이 역할의 제1규칙이다.

---

## 신유민 — `readout` (화면 값 판독) + `web` (화면 Owner)

### ① 소유
대상 차량 연결 · 번호판 검출 · 조각 수집 · best frame 선택 · 문자 인식 · 여러 프레임 비교 · **포기(abstain) 판단** · 화면 시각 OCR과 검증(형식·단조 증가·영상 길이 정합)
**`web`:** 화면 상태 · `CaseView` 소비 · 단계형 화면(기억 단서 입력 1곳) · 진행 표시 · 증거 검토 카드 · 실패/빈 결과 화면 · `USER_REVIEWED` 전달

### ② 이 일에 필요한 특성
- `readout`은 **새 도구를 빠르게 붙여보고 실제 샘플로 재보는 일**이다(OCR·검출기를 붙이고 실제 번호판으로 측정).
- 핵심 난제는 "틀린 값을 자신 있게 확정하지 않기"라서 **안정성 설계 감각**이 그대로 쓰인다.
- `web`은 제품 UX의 중심이라 Owner가 필요하다. `CaseView` 하나만 소비하는 구조라 프레임워크 선택지가 넓다.

### ③ 자료조사 — 완료
결과는 `modules/readout/research/architecture-input-memo.md`(readout·web 통합). v4에 반영된 것: `target_hint` optional(§3-4) · Overlay 검증 후 evidence 판정(§3-2) · `CaseView` Core Contract 승격(§5-12, RT1). **v4 §11-3 항목 전부 확인 완료.**

### ④ 읽어야 할 문서
v4 §4-모듈3 · §4-모듈6 · §3-2(Timestamp — readout은 검증까지) · §3-4(Plate Pipeline) · §5-7 · §5-12 `CaseView` · §2 원칙 7·9 · §11-3 · RT1·RT5 · `product/core-user-flow.md`(화면 흐름의 상위 문서) · `modules/readout/decisions/failure-taxonomy.md`

### ⑤ 지금 단계의 산출물
- **초반:** `CaseView` 예시 JSON으로 화면 골격 (후보 0개·low confidence·GPS 없음·Timestamp conflict·Plate abstain·partial 포함 — v4 §4-모듈5 ⑥의 7상황) → 이게 먼저 나오면 `case`·`evidence` 계약이 훨씬 빨리 확정된다
- **중반:** `read_plate` / `read_overlay_time` / `list_impls` 공개 함수 + `PlateReadout`·`OverlayTimeReadout` 계약 확정
- 번호판 조각 샘플로 측정한 baseline 숫자 1장 (정확도 / **틀리게 확정한 비율** / 제대로 포기한 비율)
- (web) 프론트 프레임워크 결정 + 프로토타입(`apps/prototype`) 확장 여부 결정

### ⑥ 누구와 붙는가
- 김대원 — `web` 화면 경계(영상 관련 화면 담당) + 번호판 채점 기준
- 유소연 — `case.get_view()` 계약. **화면은 이 함수 하나만 부른다**
- 정철원 — `read_frame` / `frame_ref` 형식

### ⑦ 절대 만지지 않는 것
어느 시각 출처를 최종으로 쓸지(**판정은 `evidence`**) / 신고 요건 계산 / 확정된 번호판 값 / 긴 영상 탐색 / Report Video에 사후 삽입된 Timestamp를 근거로 OCR
**`web`에서:** 요건·threshold·시각 우선순위를 다시 계산하는 코드. 화면이 규칙을 재계산하면 백엔드와 다른 답을 내놓는다 (v4 §4-모듈6 ③)

---

## 유소연 — `case` (진행 관리 · 유일한 지휘자)

### ① 소유
진행 상태(workflow stage) · 사용자의 사건 선택 · **모든 작업 발주 의도(`JobIntent`)** · 부분 재실행 정책 · 자연어 단서 해석(LLM 1회) · `CaseView` 조립 · `USER_REVIEWED` · 익명화 학습 로그 내보내기 · **timeout 정책**(A-1) · **Tool Trajectory 판정**(C-3) · **데이터 재사용 정책**(C-4)

### ② 이 일에 필요한 특성
- **E2E가 여기서 닫히므로 통합 부담이 가장 크고, 쪼갤 수 없다.** 투입 시간이 가장 많은 사람에게 간다.
- 지휘자는 **다섯 모듈의 계약을 동시에 읽어야** 한다. 특정 스택 숙련보다 전체를 조망하는 감각이 중요하고, 남의 계약을 읽고 붙이는 일이 절반이다.
- v4에서 실행 lifecycle이 `common/runtime`으로 빠졌으므로(원칙 6), 이 영역은 "무엇을 왜 언제"만 결정한다. Worker를 직접 만들지 않는다.

### ③ 자료조사 — 완료
결과는 `modules/case/research/architecture-input-memo.md`. v4에 반영된 것: 5-state workflow(§4-모듈5 ②) · Job Intent/Execution 분리(§4-모듈5 ④, RT8) · `CaseView` 필드 골격(§5-12). **남은 확인 항목은 v4 §11-4.**

### ④ 읽어야 할 문서
v4 §4-모듈5 · §2 원칙 6 · §3-6(신고 준비 3상태) · §5 전체(지휘자는 계약을 다 안다) · §5-12·5-13 · §6 · §7 전체(Happy Path·부분 재실행) · §8 · §11-4 · RT8·RT9 · `modules/case/decisions/` 2건 · `management/tool-trajectory-review.md`

### ⑤ 지금 단계의 산출물
- **초반:** 다른 모듈을 전부 **가짜(fake)로 바꿔** 상태 흐름이 처음부터 끝까지 도는 골격 → 5주차에 갑자기 시작하면 반드시 늦는다
- 부분 재실행 정책 표(v4 §7-4 확장) + 그 표를 그대로 검증하는 테스트
- `case` 공개 함수 시그니처 + `CaseView` 계약 초안 + `JobIntent` 계약 초안
- `AnalysisScope` 초안(서어진과) · input fingerprint / cache bypass 규칙(§11-4)
- C-4 설계 5개 초안 → PM 승인 (`modules/case/decisions/correction-log-reuse.md`)

### ⑥ 누구와 붙는가
- **신유민(`web`)과 상시** — 명령 API와 `CaseView`
- 전원과 각 1회 — 발주할 작업의 입력·출력 확정
- 김준영 — `JobRecord`·`UsageRecord`는 `common/runtime`(김준영)이고 `case`가 그 위에서 돈다

### ⑦ 절대 만지지 않는 것
프롬프트 내용 / OCR 파라미터 / 영상 코덱 / **신고 요건 계산(절대)** / **시각 출처 우선순위(절대)** / 증거 값을 복사해 들고 있기 / Worker lease·heartbeat 구현

> **매주 자기 폴더를 검색한다:** `case/`에서 `130MB`·`기한`·`프롬프트`·`VIDEO_OVERLAY`가 **0건**이어야 한다. 하나라도 나오면 규칙이 두 곳에 생긴 것이다. 이게 `case`가 God Module로 부풀지 않게 막는 유일한 장치다.

---

## 정철원 — `recording` (블랙박스 파일 계층)

### ① 소유
원본 참조(`ExternalSourceRef`, 불변) · 파일과 stream(`SourceAsset`/`MediaStream`) · 시간축과 기준점 · 파일이 주는 시각 후보들 · 파일 경계 해결(`resolve_span`) · GPS 관찰값 · 분석용 사본(`AnalysisSource`) · 외부에 올라간 사본의 참조와 만료(`RemoteCopy` registry) · Incident Clip · Report Video 등 파생 자산 · **보관기간과 일괄 삭제**

### ② 이 일에 필요한 특성
- **이 프로젝트에서 AI와 완전히 무관한 유일하게 큰 덩어리다.** 초반에 아무도 기다리지 않고 혼자 끝까지 갈 수 있다.
- 시간축 계산·파일 경계 이어붙이기·엣지 케이스가 전부다. **창의적 설계보다 빠뜨리지 않는 것**이 성패를 가른다.
- 초반에 밀어붙여야 뒤가 안 밀리므로 투입 시간이 많은 사람에게 간다.
- 외부 AI SDK가 없어 Python 단일 스택 결정에 따른 학습 곡선이 가장 완만한 영역이다.

### ③ 자료조사 — 완료
결과는 `modules/recording/research/architecture-input-memo.md`. v4에 반영된 것: AVI 한 파일에 전방·후방·audio stream 실측 → `SourceAsset`/`MediaStream` 분리(RT2) · `purge_case`가 사용자 원본을 지우지 않음(RT3) · 파일 경계·clip 생성은 recording 단독(RT6). **남은 확인 항목은 v4 §11-1.**

### ④ 읽어야 할 문서
v4 §4-모듈1 · §2 원칙 3·4(Source/Derived, 파일≠stream) · §3-3 · §5-3 · §8-4(보관·삭제) · §11-1 · RT2·RT3·RT6 · `management/pre-deploy-security-review.md` §1의 recording 행

### ⑤ 지금 단계의 산출물
- `resolve_span()` — 파일 경계에 걸친 구간을 이어주는 함수. **시스템 전체에서 이걸 계산하는 유일한 곳**
- `build_timeline()` + `RecordingTimeline`·`AssetSpan` 계약 (시각 후보 여러 개 + 충돌 표시 포함)
- `SourceAsset ↔ MediaStream` 스키마 · `frame_ref` 형식 · stream role 표현(§11-1)
- 샘플 폴더 하나로 도는 테스트 (시간축 정확도 / 경계 이어붙이기 / 원본 체크섬)
- 업로드·처리 전략은 **미결 유지**(v4 A6) — 계약 뒤에 숨긴다

### ⑥ 누구와 붙는가
- **김준영과 상시** — 업로드·대용량·저장·보관은 운영 이슈라 PM의 관심 영역과 겹친다
- 서어진 — `AnalysisSource` profile · `RemoteCopy` 등록(호출은 search/providers, registry는 recording)
- 신유민 — `read_frame` / `frame_ref`
- 김준영(`evidence`) — 파일이 주는 시각 후보의 형식

### ⑦ 절대 만지지 않는 것
**교통 위반이 무엇인지** — `신호위반`이라는 단어가 이 폴더에 등장하면 설계가 깨진 것이다
신고 요건 / AI 모델·프롬프트 / 진행 단계 / **어느 시각 출처가 맞는지 판정하기**(후보를 다 내놓을 뿐) / AI provider API 직접 호출(그건 `search/providers`)

> **초반에 다른 사람을 막지 않는 방법:** 완성을 기다리지 말고 **`resolve_span`과 `read_file_facts`의 목 응답을 가장 먼저** 내놓는다. 그러면 `search`·`case` Owner가 즉시 병행 출발한다.

---

## 김준영 (PM) — `evidence` (증거 확정·신고 준비) + 공통 기반/운영

### ① 소유
**`evidence`:** 확정된 값(시스템에서 유일하게 도장 찍힌 값) · **발생시각 최종 판정**(`TimeResolution`) · 부족분 요청(`EvidenceNeeds`) · 요건 검사(`RequirementReport` PASS/WARN/BLOCK) · 신고 규정 데이터 표 · 신고문 템플릿 · `ReportPackage` · handoff · `EVIDENCE_SUFFICIENT`/`PACKAGE_READY` 판정
**공통 기반(`common/runtime`):** DB Queue · Worker lifecycle(`JobRecord`) · 사용량·비용 장부(`UsageRecord`) · 마스킹 로거 · config · storage adapter
**운영:** CI/CD · 테스트·린트 · 대용량 처리 시나리오 · 전반 검토와 조율 · §1-2의 운영 역할

### ② 이 일에 필요한 특성
- PM에게 맞는 백엔드 영역은 **"전반 검토 + 운영 시나리오 + 비교적 작은 영역"**이다. `evidence`가 그 조건에 가장 정확히 맞는다 — **아무도 호출하지 않는 순수 함수 묶음**(입력 JSON → 출력 JSON)이라 PM 업무로 시간이 쪼개져도 다른 사람을 막지 않고, 소비하는 쪽은 목데이터로 먼저 개발한다.
- 동시에 **제품 책임의 절반이 여기 있다.** 신고 요건·기한·용량·유형 매핑은 기획 문서를 가장 잘 아는 사람이 소유하는 게 효율적이다.
- 공통 기반과 운영은 **모든 모듈이 그 위에서 돌지만 아무도 소유하고 싶지 않은 영역**이다. PM이 갖는 것이 가장 자연스럽다.

### ③ 자료조사 — 완료
결과는 `modules/evidence/research/architecture-input-memo.md`. v4에 반영된 것: Verified Overlay 우선 Timestamp 정책(§3-2, RT4) · Visual Event / Report Type / 표현 분리(§3-5) · 3상태 분리(§3-6, RT9) · PASS/WARN/BLOCK(§4-모듈4 ⑤) · Job Intent/Execution 분리(RT8). **v4 §11-6 항목 전부 확인 완료.**

### ④ 읽어야 할 문서
v4 §4-모듈4 · §3-2·3-5·3-6·3-7 · §5-2 `Observation` · §5-8~5-11 · §5-13 · §6-2(runtime 경계) · §8(전체) · §10 · §11-6 · RT4·RT9·RT12 · `modules/evidence/decisions/no-separate-signoff.md`

### ⑤ 지금 단계의 산출물
- `Observation` 계약 확정 — **전체에서 가장 중요한 계약.** 초반 합의 3개 중 하나
- `evidence` 공개 함수 시그니처 + **규정 데이터 표 초안**(기한·용량·필수항목·4종 유형 매핑 — 유형별 「번호판 필수인가」 포함)
- `TimeResolution`·`EvidenceRecord`·`EvidenceNeeds`·`RequirementReport`·`ReportPackage` 계약 초안
- 초기 테스트 케이스 7·9·10번을 **JSON만으로 1초에 돌리는 테스트**
- 저장소 골격 + `common/runtime` 스키마(`JobRecord`·`UsageRecord`) + 마스킹 로거 + 린트

### ⑥ 누구와 붙는가
- 정철원 — 업로드·대용량·보관, 파일이 주는 시각 후보 형식
- 서어진 — 관찰된 사건 종류 ↔ 신고 유형 매핑 · `UsageRecord`
- 유소연 — `EvidenceNeeds`를 `JobIntent`로 번역하는 규칙 · `JobRecord` row 모델(§11-4)

### ⑦ 절대 만지지 않는 것
AI 모델·프롬프트·OCR 라이브러리 / 영상 코덱·ffmpeg / 화면 흐름 / 지금 몇 단계인지 / 외부 시스템에 직접 작업 발주
**그리고 남에게 일을 시키지 않는다** — 필요한 값이 없으면 "없음 + 이걸 구하면 채울 수 있다"를 **`EvidenceNeeds` 값으로** 말할 뿐, 다른 모듈을 호출하지 않는다

---

# 4. 모듈 → Owner 역방향 표

| 모듈 | Owner | 공동 개발 | 계약 생산자 (v4 §5-1) |
| --- | --- | --- | --- |
| `recording` | **정철원** | 김준영(업로드·대용량·보관) | `SourceAsset`·`MediaStream`·`RecordingTimeline`·`AssetSpan`·`AnalysisSource`·`RemoteCopy`·`IncidentClip`·`DerivedAsset`·시각 후보 |
| `search` | **서어진** | — | `AnalysisRun`·`CandidateEvent`·`VisualEvidence` (+ `AnalysisScope` 공동) |
| `readout` | **신유민** | — | `PlateReadout`·`OverlayTimeReadout` |
| `evidence` | **김준영** | — | `Observation`·`TimeResolution`·`EvidenceRecord`·`EvidenceNeeds`·`RequirementReport`·`ReportPackage` |
| `case` | **유소연** | — | `AnalysisScope`(공동)·`JobIntent`·`CaseView` |
| `web` | **신유민** | 김대원(후보 카드·타임라인·번호판 확대) | — (`CaseView`만 소비) |
| `eval` | **김대원** | — | 정답지·manifest·결과 형식 |
| 공통 기반/운영 (`common/runtime`) | **김준영** | — | `JobRecord`·`UsageRecord`·마스킹 로거 |

---

# 5. 시간 예산과 부하 검토

팀 전체 주당 예산 안에서 영역별 부담과 투입을 맞춰봤다.

> **투입 열은 구간 표기다** — `상`/`중`. 개인별 주당 시간은 이 문서에 적지 않는다. 이 표가 답하려는 것은 「이 영역의 부담과 붙은 투입이 맞는가」이고, 그 결론은 판정 열이다.

| 영역 | v4가 본 부담 | 배정된 투입 | 판정 |
| --- | --- | --- | --- |
| `search` | **최상** | **중** | **⚠ 부담 대비 가장 빡빡하다** → 아래 완충책 |
| `case` | 중상 (통합 부담 최대) | 상 | ○ |
| `recording` | 중상 (초반 집중) | 상 | ○ |
| `readout` | 중상 | 중 (중반 집중) | ○ — 초반엔 `web` 골격이라 시기가 갈린다 |
| `eval` | 상 (초반 집중) | 중 (초반 집중) | ○ |
| `evidence` | 중 | 중 일부 (PM 업무와 분할) | ○ — 순수 함수라 시간 대비 산출이 좋다 |
| `web` | 중상 (중후반) | 중 + 후반 합류 1명 | ○ |
| 공통 기반/운영 | 중 | 중 일부 | ○ |

## `search`에 대한 완충책 3개

가장 위험한 영역인데 배정된 투입이 그 규모를 따라가지 못한다. 이건 **의도된 배치이고, 대신 세 가지로 보완한다.**

1. **채점을 `search` Owner가 하지 않는다.** 실험 설계는 `search` Owner, **실행·집계·리포트는 `eval` Owner**가 맡는다. `search` Owner의 시간을 구현과 프롬프트 실험에만 쓴다.
2. **`search` Owner에게 화면·통합 업무를 주지 않는다.** 회의 정리, 문서화, 통합 디버깅은 다른 사람이 흡수한다.
3. **중반에 실패 분류가 특정 병목을 가리키면 인력을 붙인다.** `readout`을 일단락한 Owner가 합류 후보다 — 두 모듈이 같은 AI 영상 영역이라 맥락이 겹친다. **미리 붙이지 않는다** — 실패가 필요성을 증명할 때만(`modules/search/decisions/challenger-policy.md`).

---

# 6. 소유권 충돌 방지 — "이건 내 것이 아니다" 목록

같은 값을 두 사람이 고치기 시작하면 반드시 "어느 게 진짜냐"가 터진다. 아래 5개만 지키면 된다.

| 값 | 소유자 | 나머지 사람은 |
| --- | --- | --- |
| **번호판 문자열** | 관찰값 = 신유민(`readout`) / **확정값 = 김준영(`evidence`)** | 두 값은 **다른 값이다.** 판독 결과를 확정값으로 쓰지 않는다 |
| **사건 발생시각** | 후보 수집 = `recording`·`readout` / **최종 판정 = `evidence` Owner** | 시각 우선순위 규칙을 자기 모듈에 복제하지 않는다 |
| **사용자가 고른 사건** | **유소연(`case`)** | `evidence`는 참조만 하고 복사해 갖지 않는다. 선택이 바뀌면 증거 기록은 무효다 |
| **파일 경계 해결** | **정철원(`recording`)** | 아무도 자기 모듈에서 다시 계산하지 않는다. 특히 `web` |
| **작업 발주 vs 실행** | 발주 의도 = 유소연(`case`) / **실행 lifecycle = 김준영(`common/runtime`)** | `case`가 Worker를 만들지 않고, runtime이 "왜 필요한지" 판단하지 않는다 (v4 원칙 6) |

## 매주 확인할 것 (담당: 김준영 — B-4 문서 일관성 포함)

```text
case/       에서  130MB · 기한 · 프롬프트 · VIDEO_OVERLAY   → 0건이어야 한다
recording/  에서  신호위반 · 중앙선 · 신고                   → 0건이어야 한다
search/     에서  130MB · 신고유형 · if eval_mode             → 0건이어야 한다
readout/    에서  신고유형 · 기한                            → 0건이어야 한다
evidence/   에서  ffmpeg · 프롬프트 · import search/readout  → 0건이어야 한다
eval/       에서  import case · import evidence             → 0건이어야 한다
web/        에서  threshold · 130MB · 기한                   → 0건이어야 한다

문서:  docs 안의 포인터가 실제로 존재하는가 · 같은 결정이 두 곳에서 다르게 말하는가
       CLAUDE.md · docs/README.md 라우팅 표가 현재 폴더 구조와 맞는가
```

**실행 위치는 `.github/workflows/`다.** 운영진 CODEOWNERS 개정으로 팀 자체 CI 워크플로 추가가 명시적으로 허용됐다. 운영진 소유는 `.github/` 전체가 아니라 **파일 4개**뿐이다 — `workflows/{assign-mentor,notify-discord,convention-check}.yml`과 `CODEOWNERS`. **이 4개는 수정·삭제하지 않는다**(멘토 자동 지정과 Discord 알림이 여기서 돈다). 그 밖에는 제약이 없다.

**다만 지금은 돌릴 스크립트가 없다.** `scripts/`에 README만 있고 실제 grep 스크립트가 없으므로, 순서는 **① 스크립트 작성 → ② workflow 추가**다. 그때까지는 주간 회의 전에 손으로 점검한다. 스크립트 작성은 이 절의 grep 목록이 그대로 명세다.

---

# 7. 진행 계획 — 4단계

## ① 담당 파트 자료조사 — 완료

6명 전원이 Architecture Input Memo를 냈고(`modules/<module>/research/architecture-input-memo.md`), 가장 먼저 필요했던 두 실측(블랙박스 파일 실측 · Gemini 비용·지연 실측)도 그 안에 있다.

## ② 모듈안 고도화 — 완료 (v4)

자료조사 결과로 v3를 v4로 고쳤다. 바뀐 경계는 `module-architecture.md` §12(RT1~RT12)에 기록됐다. 자료조사 전에 예상했던 「조사 결과가 이렇게 나오면 이렇게 고친다」 표 중 실제로 발동한 것:

| 예상 | 실제 |
| --- | --- |
| 로컬 처리가 유일한 현실적 선택 | 발동 안 함 — 업로드 전략은 **미결 유지**(A6). 계약 뒤에 숨겼다 |
| 파일명·메타데이터에 시각이 없는 기종이 다수 | **부분 발동** — 화면 시각 OCR이 fallback이 아니라 **Verified Overlay 우선**으로 바뀌었다(RT4). 단 사건 선택 이후에만 돈다(§7-2) |
| 번호판 검출에 외부 모델 필요 | 발동 안 함 — readout은 서버/로컬 baseline(A5) |
| 4종 중 하나가 baseline에서 안 됨 | 아직 실측 전 |

## ③ 데이터 계약 확정 — 지금

**초반에 전원이 합의할 것은 3개뿐이다.** 나머지는 생산자가 정하고 소비자가 예시 JSON으로 개발한다. 계약의 의미는 v4 §5, 필드·enum·nullable은 이 단계에서 확정한다(§13-2).

| 계약 | 초안 작성 | 합의 필요 범위 |
| --- | --- | --- |
| **`Observation`** (값 + 출처 + 상태 + 근거) | 김준영 | **전원** |
| **`AnalysisScope`** (탐색 입력, 비식별) | 유소연 + 서어진 | `search`·`case`·`eval` (**제품과 채점기가 같은 형식**이어야 한다) |
| **`AnalysisRun` + `CandidateEvent`** | 서어진 | `search`·`eval`·`case` |
| `SourceAsset`·`MediaStream`·`RecordingTimeline`·`AssetSpan` | 정철원 | `recording` → `search`·`readout`·`case` 통보 |
| `AnalysisSource`·`RemoteCopy`·`IncidentClip`·`DerivedAsset` | 정철원 (RemoteCopy 등록 규칙은 서어진과) | `recording` → `search`·`evidence` |
| `VisualEvidence` | 서어진 | `search` → `readout`(target hint)·`evidence`(유형 추천) |
| `PlateReadout`·`OverlayTimeReadout` | 신유민 | `readout` → `evidence`·`eval` |
| `TimeResolution`·`EvidenceRecord`·`EvidenceNeeds`·`RequirementReport`·`ReportPackage` | 김준영 | `evidence` → `case` |
| **`CaseView`** | 유소연 | `case` → `web` (**web의 유일한 read contract**) |
| `JobIntent` | 유소연 | `case` → `common/runtime` |
| `JobRecord`·`UsageRecord` | 김준영 (`common/runtime`) | `common/runtime` → `case`·`search`·`eval` |

> **계약 회의는 1회로 끝낸다.** 3개만 다루고, 나머지는 생산자가 문서에 적고 소비자가 이의만 제기한다. 합의된 계약은 `architecture/contracts/`로 승격한다.

## ④ 목데이터 1차 통합

**목표: 실제 AI가 하나도 없는 상태에서 처음부터 끝까지 도는 것.**

```text
[web]  목 CaseView 렌더
  ↓
[case] 상태 기계 + JobIntent 발주 (모든 모듈이 가짜)
  ↓
[recording] 목: 시간축·구간 하드코딩
[search]    목: 후보 3개 하드코딩
[readout]   목: 번호판 "12가 34?6" + 포기 상태
[evidence]  실제 코드 (순수 함수라 목이 필요 없다)
  ↓
[web]  증거 검토 카드 → 신고 꾸러미 → handoff 링크
```

**통합 담당: 유소연.** 이 시점에 확인하는 것은 기능이 아니라 **계약이 실제로 맞물리는지**다.

통과 기준 (v4 어휘):
- [ ] 사용자 수정 → 필요한 `JobIntent`만 재발주되는가 (v4 §7-4 부분 재실행 표대로)
- [ ] 번호판을 목에서 **abstain**으로 만들었을 때, 선택한 사건과 나머지 값이 살아 있는가
- [ ] 시각 출처를 충돌로 만들었을 때, `TimeResolution`이 CONFLICT를 보존하고 non-blocking warning이 `CaseView.notices`로 나가는가 · `EvidenceNeeds`가 나오면 `case`가 그것을 `JobIntent`로 바꾸는가
- [ ] `EVIDENCE_SUFFICIENT` → `PACKAGE_READY` → `USER_REVIEWED` 세 상태가 `CaseView`에 구분되어 표시되는가 (`4/5` 같은 실패 표시 없이 — `core-user-flow.md` §19)
- [ ] `eval`이 가짜 `search` 구현을 채점해서 결과 파일을 내놓는가
- [ ] **Tool Trajectory Review 1회차** 실시 (`management/tool-trajectory-review.md`)

> `case` workflow stage의 `READY`(v4 §4-모듈5 ②)는 §3-6의 세 상태와 어떻게 대응하는지 v4가 명시하지 않았다. 통합 전 `case` Owner가 확인한다(Data Contract 항목).

---

# 8. 리스크와 대응

| # | 리스크 | 왜 위험한가 | 대응 |
| --- | --- | --- | --- |
| 1 | **`search`에 배정된 투입이 이 영역의 규모를 따라가지 못한다** | v4가 부담을 「최상」으로 본 영역이다 | §5 완충책 3개. 채점·문서·통합을 `search` Owner에게서 떼어낸다 |
| 2 | **PM이 구현(`evidence`)을 겸한다** | PM 업무가 늘면 구현이 밀린다 | `evidence`는 **아무도 호출하지 않는 순수 모듈**이라 밀려도 다른 사람을 막지 않는다. 소비자는 목데이터로 진행 |
| 3 | **Python 단일 스택 결정에 따른 초반 적응 비용** | 초반 속도 저하 | `recording`은 외부 AI SDK가 없어 학습 곡선이 가장 완만하다. 초반 2주는 산출물보다 **`resolve_span` 하나를 정확히** 만드는 데 쓴다 |
| 4 | **`readout`과 `web`이 한 사람에게 있다** | 동시에 하면 둘 다 늦는다 | **시기를 분리한다.** 초반 = `web` 골격(목데이터) / 중반 = `readout` / 후반 = `web` 완성 |
| 5 | **`eval` Owner가 후반에 FE로 전환한다** | 전환 후 채점이 방치될 수 있다 | 전환 전에 **`eval`을 자동 회귀**로 만든다(실행 위치는 §6이 말한다). 사람이 매번 돌리지 않게 |
| 6 | **`case`에 모든 통합 부담이 몰린다** | 여기가 늦으면 데모가 안 된다 | 초반부터 **가짜 모듈로 골격**을 세운다. 후반에 시작하지 않는다 |
| 7 | **업로드 전략 결정이 늦어진다** | `recording`·`search` 둘 다 대기 | 결정 전에도 **샘플 클립 몇 개로 양쪽이 진행 가능**하다. 전략은 계약 뒤에 숨어 있다(v4 A6) |
| 8 | **4종 중 일부가 baseline에서 안 된다** | 스코프 위기 | `modules/search/decisions/challenger-policy.md`대로. **안 되는 유형을 "지원 범위 밖"으로 표시하는 경로를 먼저 만든다** |
| 9 | **PM 1인에 운영 역할이 모인다** (§1-2의 10개 중 7개) | 병목 | C-3·C-4를 `case`로 옮겨 이미 줄였다. 각 역할의 실제 일은 「BLOCK 0 확인」「안건 승인」처럼 짧게 설계됐다. 더 몰리면 §1-2 표에서 다시 나눈다 |

---

# 9. 조정 가능한 지점과 바꾸면 안 되는 것

## 조정 가능한 지점 2개

배정에서 유일하게 취향이 갈릴 수 있는 부분이다. **팀에서 바꾸고 싶으면 바꿔도 구조는 깨지지 않는다.**

1. **`web` Owner를 김대원으로 옮기기.** 다만 **초반에는 김대원이 `eval`에 집중해야 해서 Owner십을 들 수 없다.** 그래서 초반 Owner를 신유민으로 두고, **후반에 김대원으로 넘기는 것도 가능하다**(조건: `eval` 자동 회귀가 돈 뒤).
2. **`recording`의 미디어·운영 절반을 김준영이 가져가기.** 파일 사실 계층(시간축·파일명·GPS)은 `recording` Owner, 사본·업로드·보관·삭제는 공통 기반/운영 Owner로 나누는 방식. **단 모듈 Owner는 여전히 한 명(`recording` Owner)이어야 한다** — 최종 결정권이 갈리면 계약이 두 벌이 된다.

## 바꾸면 안 되는 것 4개

| | 왜 |
| --- | --- |
| `search` Owner는 화면·채점을 갖지 않는다 | 제품 최대 리스크 영역에 Owner의 시간을 지킨다 |
| `eval` Owner는 `search` Owner와 다른 사람이다 | 자기 결과를 자기가 채점하면 정답지가 편한 방향으로 흐른다 |
| `evidence`를 관찰 담당(`search`·`readout`)이 소유하지 않는다 | "AI가 그렇게 봤다"와 "이 값이 맞다"의 경계가 무너진다 |
| 작업을 발주하는 사람은 `case` Owner 한 명이다 | 지휘자가 둘이면 같은 작업이 두 번 돌고, 늦게 온 결과가 새 결과를 덮는다 |
