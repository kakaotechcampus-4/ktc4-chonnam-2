# Cross-cutting Open Items — 회의용 결정안

> **[아카이브] 상태: 결정 완료 (2026-09-04).** 11건의 결정은 `docs/management/cross-cutting-decisions.md`에 있다. 이 파일은 「왜 이 항목들이 안건이 됐는가」를 보존하기 위한 snapshot이며 더 이상 갱신하지 않는다.
> 본문의 `§11-1-1`·`§9-4`·`§5-④` 등은 모듈 구조 설계 **v3** 절 번호다. A-1의 「현재 Candidate + `[직접 타임라인]`」 인용은 1.2 이전 판본의 잔재로, 확정 시 `core-user-flow.md` §7·§22를 따르는 것으로 정리했다.

> 목적: 서비스 기획안 1.3에는 있었지만 현재 Module Architecture / R&R의 명시적 소유권으로 완전히 닫히지 않았거나, 구현 모듈 밖의 운영 책임이라 팀 합의가 필요한 항목을 결정한다.
>
> **이 문서는 Source of Truth가 아니다.** 회의 후 결정된 내용은 `ownership.md`, `module-architecture.md`, 각 module spec, product 문서 등 알맞은 위치에 다시 반영하고 이 안건은 `결정 완료`로 닫는다.

## ⚠ 읽는 방법 — 팀 전원이 함께 보는 문서다

**이 문서는 각자 자기 항목만 확인하고 넘어가는 문서가 아니다. 회의에서 팀 6명이 같은 화면을 보며 함께 결정한다.**

- 여기 적힌 **「추천」은 결정이 아니라 회의의 시작점**이다. 추천 담당자로 지목된 사람이 혼자 읽고 수락하는 방식으로 닫으면 안 된다.
- 모든 항목이 **두 개 이상의 모듈 경계나 운영 책임에 걸쳐 있다.** 그래서 module 문서가 아니라 여기에 있는 것이다. 한 사람의 판단으로 확정하면 나중에 소유권이 갈라진다.
- `담당 추천 명확`으로 분류된 항목도 **회의에서 소리 내어 확인하고 넘어간다.** 이의가 없다는 것을 전원이 들은 상태여야 확정이다.
- 결정하지 못한 항목은 **미결로 남긴다.** 회의를 끝내기 위해 임의로 확정하지 않는다.

> 안건 출처: 1.3 → Living Docs 분할 정합성 감사(`doc/대신고 docs 1.3 Migration 정합성 감사 보고서.md`)에서 "현재 Module Architecture / R&R로 닫히지 않는다"고 판정된 항목들이다.

## 회의에서 사용할 상태

- `담당 추천 명확`: 현재 경계상 Primary 추천이 명확. 회의에서는 확인 후 배포.
- `추천 + 팀 확인`: 추천은 가능하지만 governance/운영 책임이므로 팀 선언이 필요.
- `회의 필수`: 복수 모듈·제품 운영이 얽혀 단독 추천으로 확정하면 안 됨.

---

## A. 담당 추천이 비교적 명확한 항목

### A-1. Timeout / Long-running Job Fallback

**1.3에서 남은 내용**

- 일정 시간 초과 시 현재 Candidate + `[직접 타임라인]` 제공
- 실제 timeout 값은 baseline 실측 후 결정

**현재 확인 상태**

- 반복/비용 상한, 부분 재실행, 실패 UX는 현재 구조에서 다뤄질 수 있으나 **명시적인 timeout policy의 Owner와 결정 시점은 별도 항목으로 남아 있다.**

**추천**

- Primary: **유소연 (`case`)**
- Consulted: **신유민 (`web`)**

**추천 이유**

- timeout 발생 여부와 작업 중단/계속 정책은 작업 lifecycle·orchestration 문제라 `case`에 가깝다.
- timeout 시 현재 후보와 직접 타임라인을 어떻게 보여줄지는 `web` 표현 문제다.

**회의에서 결정할 것**

- [ ] Primary/Consulted 배정 확인
- [ ] timeout 수치 자체는 baseline 실측 후 정한다는 원칙 확인

> **이미 정해진 것과 헷갈리지 말 것:** timeout이 걸렸을 때 *무엇을 보여줄지*는 1.3에서 정해졌다 — 현재까지의 Candidate + `[직접 타임라인]`(`product/core-user-flow.md` §7). 이 안건에서 정하는 것은 **값과 담당**뿐이다.

**결정 후 반영 위치**

- `modules/case/spec.md` 또는 해당 decisions 문서
- `modules/web/ux/`의 timeout UI

---

### A-2. 챌린저를 "연다"고 선언하는 주체

**1.3에서 남은 내용**

- `Failure decides the challenger` — SEARCH / TEMPORAL_ORDER / PRIMITIVE / TARGET_ASSOCIATION / FINE_FN / COST 각각에 대응하는 챌린저 매핑
- 서명자 지정 초안: `Candidate/Fine 평가 기준 변경 = 평가·QA + AI 담당 Pair`

**현재 확인 상태**

- 매핑 6행 자체는 **복원 완료**다 → `architecture/module-architecture.md` §11-1-1이 소유한다.
- 남은 것은 **"실패 분류가 필요성을 증명했다"고 판단하고 챌린저를 여는 결정을 누가 선언하는가**이다. 실험 설계는 `search`, 채점은 `eval`로 나뉘어 있어 한쪽이 단독으로 선언하면 "자기 결과를 자기가 채점하지 않는다"는 배정 규칙의 취지가 흐려진다.

**추천**

- Primary: **서어진 (`search`)** — 챌린저를 실제로 구현·교체하는 쪽
- Consulted: **김대원 (`eval`)** — 실패 분류가 실제로 그 카테고리를 가리키는지 판정하는 쪽

**추천 이유**

- 챌린저 교체는 `search/coarse/` 내부 사정이고, 모듈 경계상 다른 사람이 소유할 수 없다.
- 다만 "열 근거가 충분한가"는 채점 결과에 대한 판단이므로 `eval`의 동의가 필요하다.

**회의에서 결정할 것**

- [ ] Primary/Consulted 배정 확인
- [ ] 챌린저 개방을 **2인 합의**로 할지, PM 승인까지 필요로 할지
- [ ] 개방 결정을 어디에 기록할지 (`modules/search/decisions/` 권장)

**결정 후 반영 위치**

- `management/ownership.md`
- `modules/search/decisions/`

---

### A-3. `CLAUDE.md` — 제품 불변 규칙 파일의 작성·소유

**1.3에서 남은 내용**

- 3-4에 CLAUDE.md 초안(제품 불변 규칙 약 20개)이 있고, `[ ] 실제 프로젝트 저장소 반영 전`으로 미완료 표시되어 있었다.
- 5-2 첫 커밋 항목도 `CLAUDE.md · docs/product-spec.md · eval/`이었다.

**현재 문제**

- 규칙의 **내용**은 `architecture/module-architecture.md` §3-6이 "무엇이 이걸 구조로 강제하나"로 흡수했고, 제품 수준 6개는 `product/product-spec.md` §7에 있다.
- 그러나 §3-6의 전제는 **"약속만으로는 6주쯤에 반드시 깨진다 → 구조 + 규칙 이중 방어"**다. 구조 절반은 소유자가 있는데 **규칙 파일 절반은 작성 주체가 없다.**
- `ownership.md` 김준영 첫 산출물은 `저장소 골격 + CI + 린트 + 작업 큐 표 + 마스킹 로거`로 CLAUDE.md를 명시하지 않는다.

**추천**

- Primary: **김준영 (공통 기반/운영)** — CI·린트와 같은 성격의 저장소 골격 산출물
- 내용 검토: **전원 1회**

**추천 이유**

- 새로 쓰는 문서가 아니다. `architecture` §4 「알면 안 되는 것」과 §3-6, `product-spec.md` §7에서 **파생시키는** 작업이다.
- AI 보조 개발 비중이 높은 팀이므로 이 파일이 없으면 규칙이 리뷰어의 성실함에만 걸린다.

**회의에서 결정할 것**

- [ ] 작성 주체
- [ ] 저장소 내 위치와 이 docs와의 관계 (규칙 원문의 canonical은 어디인가)
- [ ] 갱신 트리거 — product-spec/architecture가 바뀔 때 누가 반영하는가

**결정 후 반영 위치**

- `management/ownership.md` (김준영 첫 산출물)

---

## B. 추천은 가능하지만 팀 확인이 필요한 항목

### B-1. Product Spec / Must-Won't 변경 권한

**1.3에서 남은 내용**

- 과거 역할표에서는 PM이 Product Spec·Must/Won't·수렴 최종 결정을 소유했다.

**현재 문제**

- 현재 모듈 R&R은 구현 소유권 중심이라, living `product/product-spec.md`의 최종 변경 authority가 명시적으로 보이지 않는다.

**추천**

- Primary: **김준영(PM)**

**추천 이유**

- 기존 1.3의 PM 책임과 일관되고, 구현 세부와 분리된 제품 Scope governance가 필요하다.

**회의에서 결정할 것**

- [ ] Product Spec 최종 승인자를 1명 둘 것인가
- [ ] module Owner가 Product Scope 변경을 제안할 때 어떤 회의/승인 절차를 거칠 것인가

**결정 후 반영 위치**

- `management/ownership.md`
- 필요하면 `product/README.md`의 governance 한 줄

### B-2. 발표·스토리 / 최종 Presentation Owner

**1.3에서 남은 내용**

- 과거 역할표에서는 발표·스토리를 김준영이 담당했다.

**현재 문제**

- 현재 R&R은 module 개발 책임 중심이라 발표·스토리 같은 프로젝트 운영 역할은 명시적이지 않다.

**추천**

- Primary: **김준영**
- Support: 필요 시 각 module Owner

**회의에서 결정할 것**

- [ ] 기존 담당을 유지할지
- [ ] 최종 Demo/PPT 숫자의 sign-off를 누가 할지

**결정 후 반영 위치**

- `management/ownership.md`의 운영 역할

### B-3. Evidence Rule / 신고요건 변경의 서명자

**1.3에서 남은 내용**

- 「서명자 지정 — 우리 제품의 출력에 대해 책임지는 사람(영역별 1명)」에서 `Evidence Rule / 신고요건 변경 = 평가·QA 담당자`였다.
- 즉 1.3은 이 sign-off를 **의도적으로 PM이 아닌 사람**에게 뒀다.

**현재 문제**

- 현재 R&R에서 `evidence` 모듈 Owner는 김준영(PM)이다. 구현 소유권으로만 보면 자연스럽다.
- 그러나 **소유권(구현)과 서명(출력 책임)은 1.3에서 다른 개념이었다.** `architecture/module-architecture.md` §9-5도 "이해 상충이 있다 … 1.3의 `서명자 지정`이 이 문제를 이미 지적하고 있다"며 이 개념을 **유효한 것으로 인용**한다.
- 즉 architecture는 서명자 개념을 살아 있는 것으로 다루는데, 이 문서는 한때 §D에서 "소유권으로 대체됨"으로 닫아 두었다. **두 문서의 태도가 달랐으므로 안건으로 되돌린다.**

**추천**

- 없음. **회의에서 정한다.**

**왜 팀 확인이 필요한가**

- 1.3의 취지대로 별도 서명자를 둘 것인지, 모듈 소유권으로 갈음할 것인지는 팀 운영 방식의 문제다.
- 별도로 둔다면 `evidence` Owner가 아닌 사람이어야 의미가 있다.
- 갈음한다면 그 결정을 명시적으로 기록해야 한다. 조용히 사라지면 안 된다.

**회의에서 결정할 것**

- [ ] Evidence Rule / 신고요건 변경에 별도 서명자를 둘 것인가
- [ ] 둔다면 누구인가 (`evidence` Owner와 다른 사람이어야 하는가)
- [ ] 두지 않는다면, 그 판단 근거를 어디에 기록할 것인가

**결정 후 반영 위치**

- `management/ownership.md` §6 소유권 충돌 방지 표

### B-4. 문서 일관성(docs consistency) 소유자

**1.3에서 남은 내용**

- 5-2 역할표에서 `발표·스토리` 담당(김준영)이 소유하는 것 중 하나가 **「문서 일관성」**이었다.

**현재 문제**

- 현재 `ownership.md`에 이 항목이 없다. B-2도 발표·스토리만 다룬다.
- 이번 감사에서 발견된 문제 중 상당수가 이 공백의 결과였다 — 이미 들어온 파일을 "나중에 넣을 것"이라고 쓴 README 4건, `eval`과 `architecture`의 failure taxonomy 분기, 존재하지 않는 소유권을 가리키던 포인터 1건.

**추천**

- Primary: **김준영** — `ownership.md` §6의 매주 grep 점검을 이미 담당하므로 같은 리듬에 붙일 수 있다.

**회의에서 결정할 것**

- [ ] Primary 배정
- [ ] 점검 리듬 (주간 grep과 함께 / 격주 Won't 검토와 함께 / 별도)
- [ ] 점검 범위 — 문서 간 포인터가 실제로 존재하는가, 같은 결정이 두 곳에서 다르게 말하는가

**결정 후 반영 위치**

- `management/ownership.md`의 운영 역할과 §6

---

## C. 회의에서 반드시 정해야 하는 항목

### C-1. Product Validation Owner

**1.3에서 남은 내용**

- 실제 신고 경험자 행동 인터뷰
- 기존 방식 vs Prototype의 직접 작업시간·검토후보수·수정횟수·준비완료·handoff/실제 제출 행동 비교
- 사건 재탐색이 최우선 pain인지 검증

**현재 문제**

- `eval`은 AI/시스템 평가 역할이고, Product metric은 사용자 테스트로 별도 확인해야 한다.
- 현재 module R&R만으로는 사용자 인터뷰와 Product Validation의 명시적 Owner가 자연스럽게 하나로 정해지지 않는다.

**추천안**

- Product Validation Primary: **김준영(PM) 추천**
- 측정/분석 지원: **김대원(`eval`)**
- UX 관찰 지원: **신유민(`web`)**

**왜 회의가 필요한가**

- PM 업무로 둘지, 평가 업무 일부로 둘지, UX 리서치로 둘지 팀 운영 방식에 따라 달라질 수 있다.
- Product metric을 eval 코드 책임과 섞지 않는 경계는 유지해야 한다.

**회의에서 결정할 것**

- [ ] Primary Owner
- [ ] 인터뷰 모집/진행/분석 역할 분담
- [ ] 제품 지표 최종 기록 위치

**결정 후 반영 위치**

- `management/ownership.md`
- `product/user-validation-plan.md`
- 필요 시 해당 담당자의 working docs

### C-2. Security / Privacy 최종 Review Coordinator

**1.3에서 남은 내용**

- secret/API key, auth/IDOR, storage, 외부 AI 전송, TTL/삭제, 민감 로그, 학습 재사용, FFmpeg 입력검증 등 배포 전 전체 review

**현재 문제**

- 실제 책임은 여러 모듈에 흩어진다.
  - 파일·보관·삭제: recording
  - 외부 AI 전송: search
  - 인증/진행: case/공통 기반
  - 확정 Evidence·신고정보: evidence
  - frontend secret: web
- 각자 자기 경계를 검토하더라도 **전체 checklist가 닫혔는지 확인하는 coordinator**는 별도 운영 책임이다.

**추천안**

- Review Coordinator: **김준영(PM/공통 기반) 추천**
- 각 module Owner: 자기 영역 self-review 및 수정 책임

**왜 회의가 필요한가**

- coordinator는 보안 구현 전체를 직접 소유한다는 뜻이 아니며, sign-off 방식과 각 Owner 책임을 팀이 합의해야 한다.

**회의에서 결정할 것**

- [ ] 전체 review coordinator
- [ ] module별 보안 check sign-off 방식
- [ ] 배포 차단 기준

**결정 후 반영 위치**

- `management/ownership.md`
- `management/pre-deploy-security-review.md`
- 필요한 module spec/decisions

### C-3. Tool Trajectory 통과 판정 — 누가, 언제, 어디에

**1.3에서 남은 내용**

- 「네 가지」 #4: **통과 판정 = 결과 eval + Tool Trajectory + 사용자 검토부담·E2E 행동**, 3축이다.
- 3-2에 `거쳐온 경로가 맞나` 체크리스트가 있다.
  - Main Agent가 수정 요청에 필요한 단계만 재실행했는가
  - Fine을 건너뛰고 법적 유형을 확정하지 않았는가
  - Plate 결과에 target vehicle·detection·best/multi-frame 근거가 연결됐고 불확실하면 abstain했는가
  - GPS 없을 때 주소를 생성하지 않았는가
  - Timestamp Resolver가 source+offset/provenance를 보존하고 사후각인 표시가 있었는가
  - Evidence Rule을 실제 통과했는가
  - Source video를 덮어쓰지 않았는가

**현재 문제**

- 3축 중 **trajectory 축만 소유자가 없다.** 결과 지표는 `eval`, 제품 지표는 C-1이 정할 예정인데 경로 판정은 어디에도 없다.
- **`eval`에 자동 배정할 수 없다.** `architecture/module-architecture.md` §9는 `eval`이 `case`·`evidence`를 몰라야 한다고 못 박았다. "필요한 단계만 재실행했는가"는 `case`를 알아야 판정할 수 있다.
- 개별 규칙은 §3-6이 구조로 강제하고 `ownership.md` §7-④(목데이터 통합 통과 기준)가 일부를 검사하지만, **경로가 맞았는지를 판정하고 기록하는 절차는 없다.**

**왜 회의가 필요한가**

- 구조적으로 `eval`에 넣을 수 없으므로 단독 추천이 불가능하다.
- `case`(JobRecord 보유)에 둘지, 운영/통합 책임으로 둘지, 목데이터 통합 통과 기준을 확장할지가 팀 운영 방식에 달렸다.
- 이 축이 비어 있으면 **결과 지표만 좋고 경로가 틀린 상태**를 데모 직전까지 아무도 잡지 못한다. 1.3 지뢰 ⑤(데모만 되고 실제로 안 됨)와 직결된다.

**회의에서 결정할 것**

- [ ] Primary Owner
- [ ] 언제 확인하는가 (목데이터 통합 시 / 주간 / 데모 전)
- [ ] 어디에 기록하는가
- [ ] `ownership.md` §7-④ 통과 기준을 확장하는 것으로 갈음할 것인가

**결정 후 반영 위치**

- `management/ownership.md`
- 필요 시 `modules/case/` 또는 `modules/eval/`

### C-4. 학습 / 평가 데이터 재사용 default 정책

**1.3에서 남은 내용**

- 보안 체크리스트: `학습 데이터 재사용 default 정책 명시`
- 배포 전 리뷰 질문 7번: `학습/평가 데이터 재사용 동의와 비식별`
- 4-1: AI-Hub와 별개로, 사용자 correction 데이터를 `Future Training source`로 본다는 기록

**현재 문제**

- `architecture/module-architecture.md` §9-4는 `case.export_learning_log()`로 **익명화 로그를 내보내는 경로**를 설계했다. 즉 기술적 준비는 되어 있다.
- 그러나 **"사용자 동의 없이 기본 재사용할 것인가"는 코드가 아니라 정책**이고, 어느 모듈도 소유하지 않는다. §11-1 열린 결정 13행에도 없다.
- 현재는 `pre-deploy-security-review.md`의 체크박스 한 줄로만 존재해서, 배포 직전에야 발견될 위치에 있다.

**왜 회의가 필요한가**

- 제품 약속(개인정보 처리 범위)과 데이터 자산 전략(`10주 뒤 남을 것` 2순위)이 정면으로 맞물린다.
- opt-in / opt-out / 재사용 안 함 중 무엇을 기본으로 두느냐가 사용자에게 보여줄 문구와 `case`의 export 동작을 동시에 바꾼다.
- C-2(보안 coordinator) 안건에 흡수해도 되지만, **체크리스트 항목이 아니라 결정이라는 점**은 별도로 확인해야 한다.

**회의에서 결정할 것**

- [ ] default 정책 (재사용 안 함 / opt-in / opt-out)
- [ ] 결정 Owner — 제품 약속이므로 Product Spec 권한(B-1)과 묶을 것인가
- [ ] 익명화 수준이 §9-4(번호판 문자열 제거·정확한 좌표 제거)로 충분한가
- [ ] C-2에 흡수할 것인가 별도로 둘 것인가

**결정 후 반영 위치**

- `product/product-spec.md` §7 (사용자 약속이 되는 경우)
- `management/pre-deploy-security-review.md`
- `modules/case/decisions/` (export 동작)

---

## D. 회의 안건에서 제외 — 최신 문서로 이미 대체/해소된 것

다음은 1.3에 있었지만 현재 Module Architecture / R&R이 더 최신이므로 이번 회의에서 다시 소유권을 정하지 않는다.

- 1.3의 과거 `평가·QA = 서어진` 역할표 → 현재 `search`와 `eval`을 별도 Owner로 나눈 역할 배정안을 따름
- 1.3의 예전 `agent/`, `tools/` 폴더 구조 → 현재 module architecture로 대체
- 1.3의 `docs/product-spec.md` 중심 단일 Source of Truth 제안 → 현재 분산된 책임별 docs 운영체계로 대체

> **`Evidence Rule / 신고요건 변경 = 평가·QA` 서명자 초안은 이 목록에서 빠졌다.** 소유권으로 갈음할지 별도 서명자를 둘지는 아직 팀이 정하지 않았으므로 **B-3 안건으로 되돌렸다.**

---

## 회의 종료 체크

- [ ] 모든 안건의 Primary/Consulted 결정 (A-1~A-3 / B-1~B-4 / C-1~C-4, 총 11건)
- [ ] **결정하지 못한 항목을 미결로 명시했는가** — 회의를 끝내려고 임의 확정하지 않았는지 확인
- [ ] **김준영 누적 부하 확인** — 현재 추천대로면 PM + `evidence` + 공통기반/운영 + Product Spec 승인 + 보안 coordinator + Product Validation + 발표 + 문서 일관성 + CLAUDE.md가 한 사람에게 모인다. 각 추천은 모듈 경계상 타당하지만 **총량은 회의에서 따로 확인해야 한다.** `ownership.md` §8 리스크 2가 이 누적까지는 다루지 않는다
- [ ] `ownership.md` 반영
- [ ] 필요 시 `module-architecture.md` 반영
- [ ] 각 담당 module spec/decisions에 배포
- [ ] Product/Management 문서에 governance 반영
- [ ] 이 문서는 `결정 완료` 상태로 변경하고 더 이상 authoritative 문서로 참조하지 않음
