# 전남대학교 2팀 서비스 기획안 제출 1.3

<aside>

이 워크북이 향하는 곳: 강의(하루) → 이 워크북 → 아이디어톤(1박 2일) → 2단계 프로젝트(약 10주)
워크북은 "강의 복습 노트"가 아니라 아이디어톤에 들고 갈 기획 초안 그 자체입니다.

</aside>

<aside>
💡

### 과제 작성법

| 표시 | 뜻 |
| --- | --- |
| ✅ 필수 | 과제당 3~5개로 이루어져있으며 반드시 작성합니다. |
| ⭕ 선택 | 팀 내에서 선택적으로 작성하며 평가에 반영하지 않습니다. 다만 앞으로의 2단계 프로젝트를 위해 작성하는 것을 권장합니다. |

⚠ 필수부터 끝내고 선택으로 가세요. 선택 항목을 채우느라 필수가 비면 순서가 거꾸로입니다.

② 제출 방식

- 과제 1만 개인 트랙 / 팀 트랙 둘 다 가능합니다. 권장: 개인이 각자 채운 뒤 → 「1-5 팀 통합」에서 하나로
- 과제 2부터는 팀 트랙입니다. **제출은 팀장 명의로 한 팀당 하나의 문서**
- 특정 툴을 강제하지 않습니다. 문서·손그림·화면 캡처 자유롭게

**③ 🎤 표시는 심사위원이 실제로 물어볼 질문입니다. 그 칸을 채우면 그게 답이 됩니다.**

**팀명:** 대신고(대신 신고 해드립니다)

**팀원:** 김대원, 김준영, 서어진, 신유민, 유소연, 정철원

**제출자:** 김준영

**주제(택1):** ☐ 사람 연결 ☐ 지역 문제 ☑ 더 나은 일상

</aside>

---

# 🎯 최종 원페이지 캔버스 (제출용)

## [문제]

### 1. ⭐ 주제 / 문제 / 타깃 ＋ 지금 어떻게 버티고 있나

> **더 나은 일상 / 이미 교통위반을 신고하려고 마음먹은 블랙박스 운전자 / 사건 영상 재탐색 → 증거구간 준비·용량 조정 → 시간·장소·차량번호·신고요건 확인 → 안전신문고 제출**
>
> 신고 의향이 생겨도 사후 **Evidence Preparation**의 마찰 때문에 실제 제출까지 이어지지 않을 수 있다.

### 2. 핵심 가치 제안 한 문장

> **기억나는 시간·차량·상황 단서만 말하면 AI가 장시간 블랙박스에서 사건 후보와 전후 증거구간을 먼저 구성하고, 사용자는 구조화된 확인·수정만 거쳐 신고 준비를 끝낸다.**
>
> 제품 목표는 평균 처리시간을 임의로 확정하는 것이 아니라, 박신고 Proto-persona의 약 20분짜리 수동 준비 시나리오를 기준으로 **사용자의 직접 작업시간을 약 3분 수준까지 줄일 수 있는지 검증**하는 것이다.

### 3. 뻔하지 않은 이유 ＋ 우리만 아는 진실

> 신고콕 등 기존 도구는 **사용자가 이미 위반 장면을 찾았다는 전제**에서 편집·시각·번호판·신고요건·신고문 같은 후반부를 줄인다.
>
> 대신고는 **장시간·다중 블랙박스 파일에서 사건을 찾고, 위반 전후의 Evidence Interval 자체를 구성하는 앞단부터 시작한다.**
>
> 정성 조사에서 영상 탐색·편집·용량 조정의 반복 불편은 확인됐다. 다만 **이 중 사건 재탐색이 최우선 pain인지, 실제 몇 분이 드는지, 이 때문에 포기하는 비율이 얼마인지는 사용자 조사로 추가 검증한다.**

## [설계]

### 4. AI 쓰는 곳 / 규칙 쓰는 곳 ＋ 우리 제약조건

> **Agentic Orchestrator:** 사용자 자연어 단서·수정 요청 이해, Case State 관리, 필요한 도구만 재실행
>
> **AI Tools:** Gemini Cheap Coarse Candidate Generation → Gemini Fine Evidence Verification → 조건부 Plate Pipeline(Target association → Detection → Best Frame/Multi-frame → PaddleOCR baseline)
>
> **규칙/도구:** Timestamp Resolver(metadata/filename/overlay OCR + provenance)·GPS parser·reverse geocoding·Evidence State Builder·FFmpeg·130MB 검사·신고기한·Evidence Rule·신고문 템플릿·handoff
>
> **제약:** 장시간 원본에서 사건을 높은 Recall로 찾되 법적 위반 판정과 시각적 사건 탐색을 분리하고, 실제 비용·지연·개인정보 처리 범위도 함께 통제해야 한다.

### 5. ⭐ 루프 한 줄 ＋ “왜 챗봇이 아닌가”

> **자연어 단서 → Main Agent가 Case State 구성 → Coarse 후보 탐색 → Fine 시각근거 검증 → Top-3 사용자 선택 → 번호판·시간·위치 등 Evidence 보강 → 규칙검사·파생영상 생성 → 신고 패키지 → 안전신문고 handoff → 사용자 보정 시 필요한 단계만 재실행**
>
> UI는 순수 채팅창이 아니라 **Conversational Agent UI**다. 대화는 탐색·수정의 navigation으로 쓰고, Top-K 비교·번호판·시간출처·위치단서·신고요건은 구조화된 카드/폼으로 검증한다.

### 6. ⭐ 핵심 시나리오 1개의 화면 흐름

> **인식:** 블랙박스 폴더 + “6시 반쯤 흰 SUV가 실선을 넘었어요”
>
> → **계획:** Agent가 이해한 시간·차량·상황 단서와 현재 실행단계 표시
>
> → **행동:** Top-3 후보 + timestamp + 관찰근거 카드, 사용자가 사건 선택
>
> → **반영:** Fine Evidence, 번호판 Best Frame/Multi-frame OCR, Timestamp Resolver의 시각·출처, 위치 단서/GPS 후보, 신고영상·요건 확인
>
> → **핸드오프:** 신고용 영상·복사 가능한 정보 제공 → 안전신문고에서 최종 위치 핀·내용 확인 후 제출

### 7. 네 가지

- 모델 계층: **Main Agent(대화/오케스트레이션) + 핵심 영상 AI 2단계(Coarse/Fine) + 조건부 Plate OCR/CV** — 시간은 별도 LLM이 아니라 Timestamp Resolver로 처리
- 사람: 사건 후보·추천유형·번호판·시각/위치 단서를 확인·수정하고 실제 제출 수행
- 되돌릴 수 없는 칸: 서비스 내부 **0 / 외부 안전신문고 제출 1**
- 통과 판정: **Final Event Recall@3 + Fine/Hard-negative 지표 + Tool Trajectory + 사용자 검토부담·직접 작업시간**

### 8. 확신이 낮을 때의 문구와 경로

> `"이 범위에서 확실한 후보를 찾지 못했습니다."`
>
> `[시간범위 넓히기] [기억 단서 추가] [직접 타임라인 보기]`
>
> 번호판·timestamp·위치가 불확실하면 값을 만들어내지 않고 **출처와 `확인 필요` 상태**를 보여준다.

## [검증]

### 9. 성공 정의

> **제품 AI Primary:** locked real long-dashcam에서 **Final Event Recall@3**를 중심으로 보고, Candidate Recall@K·timestamp error·FP/hour·Fine hard-negative FPR·Precision과 비용/지연을 함께 측정한다.
>
> **제품 E2E:** 사용자가 신고 준비 완료·안전신문고 handoff까지 도달하는 비율, 검토 후보 수, 직접 작업시간을 기존 수동 방식과 비교한다. `20분→3분`은 제품 목표 시나리오이며 실측값으로 검증한다.

### 10. 테스트 케이스를 어떻게 만들었나

> **초기 4종 visual event(신호위반·중앙선 침범·진로변경·이륜차 안전모 미착용) + 사건 없음·Hard Negative·야간/우천·파일경계·시간 기억 오류·GPS 없음·번호판 불명확·지원범위 밖 등을 event/case 단위로 구성한다.**
>
> Synthetic long-video는 개발용, 최종 성능 주장은 **locked real long-dashcam test**에서만 한다.

### 11. 안전·개인정보 ＋ 보안 체크 완료

- [ ] 실제 배포코드 보안점검 전
- Source video를 실수로 덮어쓰지 않고, 원본/분석용/신고용 파생파일을 구분한다.
- 얼굴 모자이크는 **안전신문고 필수 제출 요건으로 확인되지 않아 MVP Must에 넣지 않는다.**
- 대신 업로드 범위 최소화·보관기간·자동 파기·외부 AI API 제공 여부·학습 데이터 재사용 여부를 MVP부터 설계한다.
- 얼굴·전화번호 블러는 외부 공유·데모·학습 데이터 구축·개인정보 보호 강화가 필요할 때 **선택적 파생영상 기능**으로 검토한다.
- Metadata 기반 timestamp 삽입은 공식적으로 항상 인정된다고 단정하지 않고, 사용자에게 **사후 각인과 출처를 명시하는 선택 기능**으로만 제공한다.

## [지속]

### 12. ⭐ 3개월 뒤 남는 것

> **데이터 해자:** 실제 long-dashcam event/case eval + Positive/Hard-negative + Failure/Correction 데이터
>
> **책임 있는 workflow:** 자연어 보정이 가능한 Agentic Orchestration과 deterministic Coarse→Fine·Evidence Rule을 결합한 Raw Video → Event → Evidence → Handoff 파이프라인

### 13. 10주 동안 쌓일 것 3개

1. **Long-video Traffic Event Evaluation Harness + locked real test set**
2. **Failure taxonomy / Positive / Hard-negative / 사용자 correction 데이터**
3. **Main Agent + Coarse/Fine + Evidence State + 신고 준비 E2E Pipeline**

### 14. ⭐ 첫 100명 채널 1개

> **보배드림 교통사고/블랙박스 게시판 — 실제 신고 경험자 인터뷰 → Concierge/Prototype 테스트 → 같은 채널에서 확대**

### 15. 3단 계획

> **1단계:** Evaluation Harness + Gemini Coarse/Fine baseline + Structured/Reference A/B
>
> → **2단계:** Main Agent·Evidence State·Plate/Timestamp/Location/FFmpeg/Rule/handoff를 실제 Desktop Web E2E로 연결
>
> → **3단계:** Failure taxonomy가 증명한 병목에만 VideoChat3·SentrySearch·ADAS/CV·fine-tuning 등 Challenger를 추가

## [팀]

### 16. 역할 4개 ＋ 결정 방식 ＋ 가장 위험한 한 곳

- PM: **김준영**
- 평가·QA: **서어진**
- 통합: **유소연**
- 발표·스토리: **김준영**

> 기준으로 4개 후보를 떨어뜨리고 레드팀 후 팀 전체가 최종 수렴.
>
> 가장 위험한 한 곳은 **실제 장시간 블랙박스에서 초기 4종 visual event를 사용자가 기다릴 수 있는 비용·시간 안에 높은 Final Recall@3로 찾는 것**이다.

---

# 📌 과제 1 — 문제 정의와 아이디어

## ✅ 필수 1-1. 타깃 페르소나 + 문제·포지셔닝 문장

**🎤 "이 서비스가 꼭 필요한 딱 한 사람을 설명해줄래요?"**

### 페르소나 — 딱 1명

- **이름 / 나이:** 박신고(가명) / 32세 — 실제 신고 경험의 행동 흐름을 바탕으로 만든 **Proto-persona**
- **상황(직업·생활·환경):** 매일 자가용으로 출퇴근하는 직장인이라는 세부 설정은 스토리용 가정이다. 핵심 행동 속성은 **위험한 교통위반을 목격했고 이미 신고할 의향이 생겼지만, 운전 중 정확한 사건 시각·위치를 별도로 기록하지 못한 운전자**라는 점이다.
- **하루 중 문제가 터지는 순간:** 집에 돌아와 블랙박스 SD카드를 연결하면 수분 단위로 나뉜 여러 파일 중 사건 장면부터 다시 찾아야 한다. 장면을 찾은 뒤에도 필요한 구간·용량·차량번호·시각·장소·신고요건을 맞춰야 한다.
- **제품이 지키는 관점:** 신고할 마음이 없던 사람을 자극하는 것이 아니라, **이미 생긴 신고 의향이 준비 과정의 마찰 때문에 사라지지 않도록 한다.**

### 문제 한 문장

<aside>

[누가]는 [어떤 상황]에서 [무엇] 때문에 [어떻게] 괴롭다.

</aside>

> **[교통위반을 이미 신고하려고 마음먹은 운전자]는 [운전 중 순식간에 지나간 사건을 사후 신고하려 할 때] [블랙박스에서 사건을 다시 찾고 증거구간·시간·장소·차량번호·신고요건을 재구성해야 하기 때문에] [신고 의향이 있어도 실제 제출 전 준비 단계에서 이탈할 수 있다].**

### 포지셔닝 한 문장

<aside>

우리는 [특정 대상]이 [특정 반복 워크플로]를 [현재의 비용·시간]에서 [더 나은 결과]로 줄이도록 돕는다 — AI + 사람 리뷰로

</aside>

> **우리는 [이미 교통위반 신고 의향이 생긴 블랙박스 운전자]가 [기억나는 시간·차량·상황 단서만 말하면] [장시간 영상에서 사건 후보와 전후 증거구간을 먼저 찾고 구조화된 확인·수정만 거쳐] [신고 준비 완료 상태]까지 도달하도록 돕는다 — Agentic Orchestration + Coarse/Fine AI + deterministic Evidence 처리 + 사람 최종 확인으로.**

- **입력 가정**
    - 시간대: `18:30쯤`, `퇴근길 7시 전후`
    - 위반/상황 단서: `신호가 빨간데 직진`, `중앙선을 넘어옴`, `흰색 실선을 넘어 끼어듦`, `오토바이 운전자가 안전모를 안 썼어요`
    - 차량 특징: `흰색 SUV`
    - 위치 단서: `미금역 근처`, `경부고속도로 서울방향 ○○IC 지난 뒤`
    - 사용자가 정확한 값을 몰라도 자연어로 시작할 수 있으며, Agent가 구조화한 해석을 다시 보여주고 수정 가능하게 한다.

---

## ✅ 필수 1-2. “지금 어떻게 버티고 있나” ＋ 그 근거 ⭐가장 중요

**🎤 "그 사람은 지금 이걸 어떻게 버티고 있나요?”**

### 이 사람이 현재 이 문제를 우회하는 방법:

**A. 완전 수동**

```text
교통위반 목격·신고 결심
→ 차량에서 SD카드 제거 / 앱에서 원본 확인
→ 노트북·리더기에 연결
→ 수분 단위 파일을 하나씩 열어 사건 순간 탐색
→ 필요한 구간 자르기
→ 130MB 등 첨부규격에 맞게 필요 시 압축
→ 영상 내 시각·차량번호 확인
→ 안전신문고에서 유형 선택
→ 위치 검색·지도 핀 세부조정
→ 날짜·시간·차량번호·신고내용 입력
→ 본인인증·인적사항
→ 제출
```

**B. 신고콕 같은 신고 보조도구 사용**

```text
사용자가 위반 장면을 먼저 찾음
→ 영상 선택
→ metadata 촬영시각/위치 확인
→ 구간 자르기
→ 번호판 추출
→ 신고 4요건 확인
→ 신고문/법령 안내
→ 안전신문고 이동
→ 신고기록·기한·처리결과 관리
```

> **두 경로 모두 공통적으로 사용자가 먼저 “어느 파일의 어느 순간이 신고할 사건인지” 알아야 후반부 자동화를 시작할 수 있다.**
>
> 신고콕은 대신고와 완전히 같은 제품이라기보다 **전체 workflow의 후반부가 실제 제품화 가능하다는 Proven Reference이자 경쟁 서비스**다.

### 거기에 드는 시간 / 돈 / 수고 :

- 여러 분할 파일·긴 타임라인에서 사건 순간을 다시 찾는 시간
- 필요한 전후 구간 결정·자르기·재인코딩·130MB 맞추기
- 번호판이 선명한 순간 확인
- 영상 내 실제 위반 시각 확인
- 운전 중 지나친 사건 장소를 안전신문고 지도에서 다시 특정
- 신고유형·요건·내용·본인인증 확인
- **박신고 20분:** 통계 평균이 아니라 `영상 찾기 10~15분 + 편집/용량 + 위치 재확인 + 정보입력`의 현실적인 Proto-persona 시나리오
- **3분:** 전체 처리 지연을 3분으로 단정하지 않고, **사용자의 직접 작업시간을 약 20분→3분으로 줄일 수 있는지 검증하는 제품 목표값**

### 사용자 동기 / 저항

**주요 신고 동기 — 커뮤니티 관찰 기반**

- 사고위험을 직접 경험했거나 위험행위를 목격함
- 얌체운전·규칙위반에 대한 불공정감
- 반복되는 생활권 문제를 개선하고 싶음
- 신고 수용·처리 결과에서 오는 완료감·성취감

**주요 저항**

- `“굳이 신고까지 해야 하나?”`
- 직접적 보상 없음
- 신고자에 대한 부정적 낙인 부담
- `나도 신고당할 수 있다`는 심리적 부담
- 불수용·처리지연 이후의 허탈감

> UX는 `참교육·벌금·도파민`을 전면에 내세우지 않고 **안전·공정·신고 준비 완료·처리 결과** 중심으로 보상감을 설계한다.

### 실제 근거 및 현재 확인 상태

- `실제_신고_과정.pdf` 사례에서 **SD카드 → 폴더 영상 탐색 → 편집 파일 첨부 → 위치 검색/핀 조정 → 신고내용·차량번호·날짜·시간 → 본인인증** workflow 확인
- 커뮤니티 조사에서 블랙박스 영상 탐색·편집·용량 조정이 반복적인 불편으로 관찰됨
- 따라서 **“긴 영상에서 사건 순간을 찾는 문제가 실제 존재하는가”는 정성적으로 확인됨**
- 다만 아직 모르는 것:
    - 이 단계가 신고 과정의 **핵심/최우선 pain**인지
    - 실제 탐색·전체 준비에 **얼마의 시간이 소요되는지**
    - 이 과정 때문에 **신고를 포기하는 비율**이 어느 정도인지
- 사용자 조사 질문은 미래 의향보다 **“지난번 실제 신고에서 영상을 어떻게 찾았고, 얼마나 걸렸으며, 어느 단계가 가장 귀찮았는가?”**를 중심으로 한다.

### 시장/Impact 숫자의 사용 규칙

- 2023년 교통법규 위반 공익신고 처리 규모: **약 366만 건**
- 그중 신호위반·중앙선침범·진로변경/방법위반·지정차로위반 등 **전후 맥락·차량 움직임 확인이 중요한 대표 유형 약 203만 건**
- **203만 건을 “동영상 신고 203만 건”이라고 주장하지 않는다.**
- `약 200만 건 × 20분 → 3분`은 **시장 통계가 아니라 가정 기반 잠재 impact estimation**이다.
- 전부에 적용된다고 가정할 때 잠재 절감은 약 **57만 시간/년**이며, 실제 적용률·작업시간은 사용자 실측이 필요하다.

### “고통이 진짜다”의 증거 체크 :

- ☑ 실제 신고자가 영상 탐색·편집·용량·위치·정보입력 단계를 수행함
- ☑ 커뮤니티에서 긴 영상 탐색·편집·용량 조정의 반복 불편이 관찰됨
- ☑ 후반부를 줄이는 신고콕 같은 실제 제품이 존재함
- [ ] 사건 재탐색이 **가장 큰 pain**인지 직접 비교
- [ ] 실제 탐색/준비시간 분포 실측
- [ ] 준비마찰 때문에 실제 제출을 포기한 비율 확인
- [ ] 자동 준비된 상태가 실제 신고 전환을 높이는지 사용자 테스트

---

## ✅ 필수 1-3. 증명할 가설 1개 ＋ Must / Won’t

**🎤 "2단계 끝까지 이걸 다 만들 수 있어요? 하나만 남긴다면?" ← 스코프 질문은 3개월 기준으로 옵니다.**

### 2단계에서 증명할 핵심 가설

> **이미 신고 의향이 있는 운전자에게 기억 단서만으로 장시간 블랙박스에서 사건 후보와 전후 증거구간을 먼저 구성하고 신고정보를 구조화해 제공하면, 기존 수동 workflow보다 사용자 직접 작업시간·검토부담이 줄고 실제 신고 준비 완료/제출 전환이 증가한다.**

- **기술 하위가설:** 초기 4종 visual event를 real long-dashcam에서 충분한 Final Recall@3와 현실적인 비용/지연으로 찾을 수 있다.
- **제품 하위가설:** 위반 장면과 신고자료가 자동 준비된 상태라면 기존 방식보다 실제 신고 완료 의향/행동이 증가한다.

### Must / Won’t

| ✅ Must — 2단계까지 반드시 만든다 | 🚫 Won’t — 이번에는 만들지 않는다 |
| --- | --- |
| 자연어 기억 단서 → Main Agent가 시간/차량/상황 Case State 구성·수정 | 신고할 의향이 없는 사용자를 게임화·보상으로 적극 유도 |
| 초기 4종: 신호위반 / 중앙선 침범 / 진로변경 / 이륜차 안전모 미착용 visual event 탐색 | 모든 도로교통법 위반 유형 지원 |
| Gemini Cheap Coarse로 Top-K candidate 생성 + Gemini Fine Evidence Verification | AI가 법적 위반 여부를 최종 확정 |
| 사건 전후 Evidence Interval 자동 구성 + 파일 경계에 걸린 사건 처리 | 사용자 승인 없는 무인 자동신고 |
| Top-3 구조화 카드 + 사용자 `맞음/아님/다른 후보/조금 전·후` 보정 | 자율 multi-agent video exploration |
| 대상 차량 번호판 best frame/OCR + 사용자 수정 | ADAS/CV Candidate Generator를 baseline 전에 선행 구축 |
| timestamp 값 + 출처(Video overlay / Metadata / User / Unknown) 관리 | metadata 없는 시각을 AI가 임의 생성 |
| GPS가 있으면 사건 시각 위치 후보·주소/POI/search keyword 보강, 없으면 user hint 유지 | 자체 지도 UI / GPS 없는 영상을 간판 등으로 완전자동 위치확정 |
| 130MB 등 파일규격 검사 + 파생 신고영상 생성 + 신고요건 점검 + handoff | 얼굴 모자이크를 신고 필수 Must로 구현 |
| Source video/Derived Evidence 구분, 개인정보 처리·삭제정책 설계 | 신고콕의 신고기록·CSV·통계 등 모든 후반 기능을 10주 핵심으로 복제 |

### 초기 지원 4종을 고른 이유

> **신호위반 / 중앙선 침범 / 진로변경 / 이륜차 안전모 미착용**을 10주 MVP의 초기 지원 범위로 고정한다. 모든 신고유형을 넓게 지원하기보다, 실제 신고에서 체감 중요도가 있고 장시간 영상 탐색의 기술가설을 대표할 수 있는 유형을 먼저 검증한다.

1. **신고 빈도·사용자 체감 중요성** — 신호·중앙선·진로변경처럼 실제 주행 중 위험·불공정을 체감하기 쉬운 유형을 포함한다.
2. **Long-video reasoning 대표성** — 신호위반은 신호 상태→정지선→차량 통과의 temporal order, 중앙선·진로변경은 선 종류와 차량 trajectory/crossing을 요구해 Coarse/Fine 구조의 핵심 난점을 검증할 수 있다.
3. **서로 다른 perception primitive** — 신호/정지선, 차선·trajectory, 이륜차·사람·안전모 attribute처럼 서로 다른 시각 primitive를 포함해 한 종류의 패턴에만 맞는 데모를 피한다.
4. **평가·학습 데이터 확보 가능성** — AI-Hub 등에서 관련 교통 데이터와 annotation을 평가·Reference·향후 학습에 활용할 수 있다. 특히 이륜차 안전모 미착용은 관련 데이터가 있고, 팀 논의에서 상대적으로 구현 난도가 과도하지 않을 것으로 판단해 추가했다.
5. **10주 MVP 스코프** — 법적 위반 전체를 다루지 않고 4종에서 Event Recall·Hard-negative·비용·지연을 먼저 검증한 뒤 failure taxonomy가 필요성을 증명할 때만 범위를 넓힌다.

> 여기서 AI가 찾는 것은 **법적 최종 위반 판정이 아니라 신고 가능성이 있는 visual event/candidate**이며, 최종 신고유형은 Evidence Rule과 사용자 확인을 거친다.

---

## ✅ 필수 1-4. 가장 위험한 한 곳

**🎤 "기술적으로 제일 겁나는 부분은 어디예요?”**

### 가장 위험한 한 곳 :

**실제 장시간·다중 블랙박스 파일에서 초기 4종 visual event가 몇 초만 존재하는 상황에서도, 사용자가 기다릴 수 있는 비용·지연 안에서 목표 사건을 Final Top-3 안에 안정적으로 포함시키는가.**

### 왜 위험한가

- 긴 영상 대부분은 정상주행이고 target event는 몇 초에 불과함
- 신호 상태·정지선·차선·차량 trajectory 같은 **시간적 관계**와, 이륜차·운전자·안전모 attribute 같은 객체 관계를 함께 봐야 함
- 야간·우천·역광·번호판 반사·가림 등 영상 품질 편차
- 사건이 분할 파일 경계에 걸릴 수 있음
- 사용자의 시간 기억이 틀리거나 차량 특징이 불완전할 수 있음
- 장시간 원본의 업로드·API 비용·latency·privacy가 제품 UX를 동시에 제한
- 법적 위반과 visual event를 섞으면 평가 자체가 불안정해질 수 있음

### 언제 먼저 확인할 것인가

> **2단계 1~4주차 최우선 — UI보다 Evaluation Harness와 baseline부터**

1. event/case 단위 Evaluation Harness 구축
2. Gemini Cheap Coarse + Gemini Fine baseline
3. Candidate: Recall@1/@3/@10, timestamp error, FP/hour
4. Fine: Recall, Hard-negative FPR, Precision
5. E2E: Final Recall@3, 사용자 검토 후보 수
6. Efficiency: source-video-hour당 비용, latency, tokens, Fine exposure
7. 동일 candidate clip으로 `Gemini Direct / Structured Evidence / Structured + Positive·Hard-negative Reference` A/B
8. `300개`, `90%` 같은 임의 숫자를 stage gate로 쓰지 않고 Pilot disagreement·confidence interval을 보고 최종 규모 결정
9. Synthetic long-video는 architecture 개발용, 최종 주장은 locked real long-dashcam에서
10. 실패 taxonomy에 따라 Challenger만 연다.

```text
SEARCH_FAILURE          → VideoChat3 / SentrySearch / retrieval challenger
TEMPORAL_ORDER_FAILURE  → temporal verifier / TrafficRAG-inspired 확장
PRIMITIVE_FAILURE       → ADAS/CV perception 조사
TARGET_ASSOCIATION      → tracking / lane-signal association / stronger VLM
FINE_FALSE_NEGATIVE     → Fine model/prompt/reference 개선
COST                    → Local SLM/CV/self-host/fine-tuning 검토
```

- 사용자 측에서는 신고 경험자의 **실제 탐색시간·가장 귀찮은 단계·포기 경험·자동준비 후 실제 제출 행동**을 함께 확인한다.

---

## ✅ 필수 1-5. 팀 통합 — 수렴 기록

**🎤 "이 결정은 팀에서 누가, 어떻게 정했나요?”**

- **후보가 몇 개였나:** 4개
- **어떤 기준으로 떨어뜨렸나:** 문제 정의·타깃의 구체성, Agent가 필요한 다단계 workflow인지, 범용 ChatGPT만으로 대체하기 어려운지, AI 결과를 사용자가 직접 검증할 수 있는지를 기준으로 검토했다. 레드팀 크리틱을 통해 실시간 데이터 확보가 어려운 가게 상태 서비스, AI 오류를 타깃이 직접 검증하기 어려운 시각장애인 접근성 서비스, 타깃의 문제 절실함이 아직 불명확한 특허 도면 서비스의 우선순위를 낮췄다.
- **누가 어떻게 최종 결정했나:** 후보마다 팀원이 실패 가능성을 공격한 뒤 팀 전체가 기준과 크리틱 결과를 비교했다. 그 결과 실제 블랙박스 원본으로 사용자가 결과를 검증할 수 있고, `기억 단서 → 장시간 사건 탐색 → Evidence 확인·수정 → 신고 준비 → 안전신문고 handoff`라는 상태 있는 E2E workflow가 명확한 **대신고**를 최종안으로 선정했다.

---

## ⭕ 선택 — 채점하지 않습니다

### 먼저 완전히 장악할 최소 시장

> **PC에서 전방 1채널 블랙박스 영상을 직접 확인해 안전신문고 교통위반 신고를 준비하는 운전자 — 특히 신고 의향은 있지만 사건 시각을 정확히 기록하지 못한 사람**

### Real Trend 체크  - 🎤 "이게 해결되면 그 사람의 하루가 어떻게 달라지나요?”

- **다음에도 열어볼 이유:** 신고 의향이 생겼을 때 SD카드의 여러 파일을 직접 뒤져 사건부터 다시 찾고 싶지 않아서 사용
- **유저가 바꿔야 하는 자기 습관:** 운전 중 스마트폰 조작·수동저장 버튼을 필수로 요구하지 않고, 사후 자연어 기억 단서로 시작
- **보상감의 방향:** 처벌·참교육이 아니라 `안전/공정 → 신고 준비 완료 → 처리결과` 중심

### 리뷰 가능성 판정

> **높음.** Candidate는 원본 clip으로, Fine 결과는 관찰 근거로, 번호판은 best frame으로, timestamp·위치는 출처와 함께, 추천 신고유형은 사람이 직접 확인·수정할 수 있다.

---

# 📌 과제 2 — AI를 어디에 쓸 것인가

## ✅ 필수 2-1. AI 쓰는 곳 vs 규칙 쓰는 곳 ＋ 사람 승인 지점

**🎤 "AI가 어디까지 스스로 하고, 사람은 어디서 멈춰 세우나요?”**

### 경쟁·레퍼런스 — 신고콕

신고콕은 **사용자가 이미 확보한 교통위반 사진·영상을 안전신문고에 제출하기 좋은 형태로 후처리하는 신고 보조 앱**에 가깝다.

```text
위반 영상 선택
→ 촬영시각·위치 정리
→ 필요한 구간 자르기
→ 번호판 추출
→ 위반유형 선택
→ 신고 4요건 확인
→ 신고문 생성
→ 안전신문고 이동
→ 신고기록/기한/처리결과 관리
```

- metadata 촬영시각 확인·선택적 timestamp 렌더링
- 위치 주소변환/메모
- 번호판 인식
- 얼굴·전화번호 블러 등 선택적 개인정보 편집
- 신고 4요건·유형별 문구/법령
- 신고 기록·기한·처리 결과·통계·CSV
- 기기 내부 영상처리를 밝히고 있어 downstream local processing의 실제 제품 사례

> **차별점:** 신고콕은 `찾아놓은 위반영상 → 신고 가능한 형태로 후처리`, 대신고는 `장시간 블랙박스 → AI 사건 탐색 → 전후 증거구간 구성 → downstream 신고 준비`.
>
> downstream을 새로 발명하는 것보다, **이미 제품으로 검증된 패턴을 참고하되 앞단 Long Video → Event → Evidence에 개발 우선순위를 둔다.**

### 기능별 AI / 규칙 / 사람 확인

| 기능 | AI / 규칙 | 틀리면 얼마나 아픈가 | 사람 승인 필요? |
| --- | --- | --- | --- |
| 자연어 단서 이해·수정·필요 단계 재실행 | ☑ Main Agent/LLM | 중 | Agent 해석을 수정 가능하게 표시 |
| 장시간 영상 Candidate Generation | ☑ Gemini Cheap Coarse | **매우 높음** | Top-K 결과 확인 |
| 후보 clip Fine Evidence Verification | ☑ Gemini | 높음 | 관찰근거·추천유형 확인 |
| 대상차량 association → 번호판 Detection → Best Frame/Multi-frame OCR | ☑ AI/CV + PaddleOCR baseline | 높음 | **best frame/여러 crop + 문자열 직접 확인/수정** |
| visual event → 법적 신고유형 mapping | ☑ 규칙/Evidence Rule + 사용자 | 높음 | **사용자 최종 선택** |
| timestamp 값·출처 판정 | ☑ parser/규칙 | 높음 | 출처 표시, 불확실 시 확인 |
| Metadata 시각을 영상에 선택적 사후 표시 | ☑ FFmpeg/규칙 | 높음 | **사후 각인임을 안내하고 사용자 선택** |
| GPS 추출·사건시각 매칭 | ☑ parser/규칙 | 중 | 후보 위치로만 사용 |
| 좌표 → 주소/도로/POI/search keyword | ☑ geocoder/Local API | 중 | 최종 핀은 안전신문고에서 확인 |
| GPS 없는 위치 | 사용자 단서 유지 | 중 | AI 추측 금지, 안전신문고에서 직접 선택 |
| Evidence/Incident State 구성 | ☑ 코드 | 높음 | 별도 LLM 재요약 없이 provenance 유지 |
| 신고기한·필수항목·130MB 파일규격 | ☑ Evidence Rule/코드 | 높음 | 자동 검사 + 결과 확인 |
| 신고구간 자르기·압축·파생영상 생성 | ☑ FFmpeg/코드 | 중 | 결과 확인 |
| 신고문 초안 | ☑ 규칙/템플릿 | 낮~중 | 사용자 수정 |
| 안전신문고 handoff | ☑ 코드 | 중 | 사용자 이동 결과 확인 |
| **안전신문고 실제 제출** | 사람 | **매우 높음** | **사용자가 직접 수행** |

### AI의 실제 경계

**AI는 크게 다음 4개 역할로만 둔다.**

1. **Main Agent / Orchestration** — 사용자 모호한 기억·수정 요청 이해, Case State 관리, 필요한 도구 재실행
2. **Coarse Search AI** — 장시간 영상에서 Recall 우선 Candidate 생성
3. **Fine Evidence AI** — 후보에서 신호·선·차량·trajectory·temporal order 등 시각근거 확인
4. **Plate AI/CV** — 대상차량 association → 번호판 Detection/track → Best Frame + Multi-frame consensus → PaddleOCR baseline → confidence/abstention

> `날짜·시간·위치·차종·차량번호·clip 범위·추천유형`을 다시 한 번 LLM에 넣어 “정보 추출”하는 별도 AI 단계는 두지 않는다. **각 전문 도구 결과를 provenance와 함께 deterministic State Builder가 합친다.**

### Timestamp Resolver — metadata/filename 우선, Overlay OCR은 fallback·검증

Timestamp는 별도 LLM Agent가 추측하지 않고 **deterministic Resolver**가 여러 출처를 provenance와 함께 조합한다.

```text
후보 사건 + Source video
        ↓
① 원본 시각 source 탐색
   - container/stream metadata (ffprobe 등)
   - 제조사 custom/subtitle metadata가 있으면 parser
   - filename에 시각 규칙이 있으면 후보 source
        ↓
신뢰 가능한 Source 시작시각 확보?
 ├─ YES → Source 시작시각 + candidate offset으로 사건시각 계산
 │          ↓
 │       출처 간 일관성 확인
 │
 └─ NO / 출처 충돌 / 검증 필요
            ↓
② Video Overlay Timestamp OCR
   - timestamp 예상 영역 crop
   - 시작/종료 주변에서 시간적으로 떨어진 소수 frame sampling
   - PaddleOCR 등 범용 OCR baseline
   - 날짜/시간 format 검증
   - 시간 증가 방향 + video duration 일치 검증
            ↓
③ 신뢰 가능한 시각 없음
   → source = USER_INPUT / UNKNOWN
   → 자동 생성 금지, 사용자 확인
```

- `creation_time` 등 metadata가 존재한다는 이유만으로 실제 촬영시각이라고 단정하지 않는다. 가능하면 filename/overlay/custom metadata와 교차확인한다.
- 후보 clip을 새로 생성했다면 **파생파일의 creation_time이 아니라 Source video의 시작시각 + candidate offset**을 사용한다.
- overlay OCR은 한 프레임만 확정하지 않고, 예를 들어 시작/종료 주변의 시간적으로 떨어진 3개 안팎의 frame을 비교해 format·연속성·duration consistency를 검사한다.
- provenance 예: `VIDEO_OVERLAY_OCR / FILE_METADATA / FILENAME / USER_INPUT / UNKNOWN`.
- **화면 Timestamp가 없지만 신뢰 가능한 Metadata 시각이 있을 때** 사용자가 원하면 FFmpeg로 신고용 파생영상에 시각을 표시한다. 이는 원래 영상의 watermark가 아니라 **Metadata 기반 사후 각인**임을 명시하며, 공식적으로 항상 인정된다고 단정하지 않는다.

### Plate Pipeline — Detection과 Recognition을 분리

번호판은 단일 프레임 OCR 한 번으로 끝내지 않고, **대상차량 연결 → 번호판 검출 → 여러 실제 프레임 확보 → Best Frame/Multi-frame OCR → 사용자 확인**으로 처리한다.

```text
선택한 사건의 target vehicle
        ↓
Target association / tracking
        ↓
Plate Detection
        ↓
동일 차량의 여러 plate crop 확보
        ↓
Best Frame Selection
        ↓
PaddleOCR pretrained baseline
        ↓
Multi-frame OCR 결과 비교 / consensus
        ↓
confidence / abstention
        ↓
사용자 직접 확인·수정
```

- **Detection failure:** 번호판 영역 자체를 못 찾음.
- **Recognition failure:** crop은 맞지만 `12가3456 → 12가3458`처럼 문자열을 틀림.
- **Target association failure:** 위반 차량이 아닌 주변 차량의 번호판을 읽음.
- 초기에는 pretrained PaddleOCR을 그대로 평가하고, 실제 실패 데이터가 Recognition 병목을 보여줄 때만 한국 번호판 데이터로 fine-tuning한다.
- 저해상도·motion blur·glare에 대응해 한 장을 억지로 복원하기보다 먼저 **Best Frame + 실제 인접 프레임의 OCR consensus**를 사용한다.
- 더 강한 multi-frame restoration/alignment는 baseline failure가 필요성을 증명할 때 여는 Challenger로 둔다.
- 보이지 않는 문자를 생성형 모델로 복원해 확정하지 않는다. 읽을 수 없으면 `확인 필요`로 넘긴다.

### 장소 선택 MVP

```text
사용자 자연어 위치 단서
        +
사건시각 GPS 추출 가능 여부
        ↓
[GPS 가능]
좌표 → 주소/도로명/주변 POI → 안전신문고 검색어

[GPS 불가능]
사용자 위치 단서 유지
        ↓
최종 핀은 안전신문고 지도에서 사용자 확인·조정
```

- **우리 서비스 내 지도 UI는 MVP 제외**
- 카카오 Local API 등은 GPS 좌표를 사람이 이해할 주소/도로/랜드마크로 변환하는 backend enrichment 용도로만 검토
- `GPS 없음 ≠ 제품 실패`
- 위치도 `값 + 출처 + 불확실성 + 최종 확인 필요`로 관리

### 안전신문고 연계

```text
대신고
→ 신고용 파생영상 + 복사 가능한 신고정보 + 위치 검색어
→ 안전신문고 앱/웹
→ 사용자가 지도 핀·내용을 최종 검토
→ 사용자 직접 제출
```

---

## ✅ 필수 2-2. 우리 제약조건(병목)은 어디인가

### 우리 제품이 막히는 지점 한 문장 :

> **제품의 가장 큰 기술 병목은 장시간 정상주행 속 몇 초짜리 visual event를 낮은 비용·지연으로 놓치지 않고 Top-K에 넣는 것이며, 제품 병목은 그 결과가 실제 Evidence Preparation 비용을 줄여 신고 완료로 이어져야 한다는 점이다.**

- **우리는 AI를 거기에 배치했나?** ☑ 예
    - Agent는 모호한 자연어/상태전이를 담당
    - Coarse/Fine은 비정형 장시간 영상 이해에 집중
    - 나머지는 가능한 한 deterministic software로 이동
- **AI를 배치하지 않는 곳:** 130MB·기한·Evidence Rule·metadata/GPS parsing·geocoding·State Builder·FFmpeg·신고문 템플릿·실제 제출

### AI 경제성 4레버

| 레버 | 우리 제품에서는? | 여기에 AI가 있나 |
| --- | --- | --- |
| ① 획득 — 고객 수를 늘린다 | 신고/블랙박스 커뮤니티에서 실제 신고 경험자 확보 | ☐ |
| ② 전환 — 방문자→사용자 | 자연어 단서만으로 시작해 초기 입력 마찰을 줄임 | ☑ Agent |
| ③ 이행 — 가치를 더 빨리 배달 | **핵심.** Long Video → Event → Evidence를 자동화해 직접 작업시간·검토후보 수를 줄임 | ☑ Coarse/Fine/Plate |
| ④ 유지 — 고객 수명을 늘린다 | 처리결과/기한/기록은 신고콕에서 검증된 패턴이지만 10주 핵심은 아님 | △ 후속 |

---

## ✅ 필수 2-3. 성공 정의 ＋ 테스트 케이스 10개

**🎤 "이게 잘 됐다는 걸 뭘로 아나요?”**

### ① 성공 정의 한 문장

> **이게 잘 됐다는 걸 우리는 locked real long-dashcam에서 목표 event의 Final Recall@3를 중심으로 확인하고, 동시에 후보 검토수·사용자 직접 작업시간·신고 준비 완료율/실제 handoff 행동·비용·latency가 기존 방식보다 개선되는지로 안다.**

### Evaluation Harness — v1

| Stage | Primary Metrics |
| --- | --- |
| Candidate | Recall@1 / @3 / @10, timestamp error, FP/hour |
| Fine | Recall, Hard-negative FPR, Precision |
| Timestamp | source agreement, offset error, Overlay OCR format/continuity validation, UNKNOWN rate |
| Plate | **Exact Plate Accuracy, Wrong Accept Rate, Unreadable/Abstention Recall, 사용자 수정률·수정시간**; 진단용 Detection Recall/Target Association/CER/Best-frame vs Multi-frame/Latency |
| E2E | **Final Event Recall@3**, 사용자 검토 후보 수 |
| Efficiency | source-video-hour당 원가, latency, tokens, Fine exposure |
| Product | 사용자 직접 작업시간, 준비 완료율, handoff/실제 접수 행동 |

- `Top-3 Recall 90%`, `평가 300개` 같은 임의 숫자는 stage gate로 사용하지 않는다.
- Pilot을 동일 event에 수행한 뒤 모델 간 disagreement·confidence interval을 보고 평가 규모 결정
- `20분→3분`은 **제품 UX 목표 가설**, 실측 전 성과수치로 말하지 않음
- Synthetic long-video는 architecture 개발용
- 최종 제품 성능 주장은 **locked real long-dashcam test**에서만

### Fine Verifier 초기 A/B

동일 candidate clip을 사용해 아래 세 가지만 먼저 비교한다.

| 실험 | 목적 |
| --- | --- |
| Gemini Direct | 가장 단순한 baseline |
| Structured Evidence Prompt | “위반 상황 정의/근거 분해” 효과 검증 |
| Structured + Positive/Hard-negative Reference | TrafficRAG-inspired reference 효과 검증 |

TrafficRAG 전체 retrieval system은 바로 만들지 않고, 고정 reference 효과가 확인된 뒤 AI-Hub 사례 자동검색으로 확장한다.

### ② 테스트 케이스 10개

| # | 입력 | 기대한 답 | 실제 나온 답 | OK? |
| --- | --- | --- | --- | --- |
| 1 | 맑은 낮, 적색 신호 상태→정지선→차량 직진 통과 | 실제 사건을 Top-3 안에 반환하고 Fine에서 시간순 근거 제시 | 미실행 | ☐ |
| 2 | 정상주행만 있는 30~60분 | 확실한 후보 없음 또는 낮은 score, 과도한 confident false positive 억제 | 미실행 | ☐ |
| 3 | 황색 중앙선 crossing | 대상 차량 trajectory와 line crossing 전/후 근거 | 미실행 | ☐ |
| 4 | 백색 실선 진로변경 + 유사 점선 hard negative | 실선 crossing/trajectory 근거를 제시하고 점선 정상 차로변경과 구분 | 미실행 | ☐ |
| 5 | 이륜차 운전자 안전모 미착용 + 안전모 착용 hard negative | 이륜차·운전자·머리영역/안전모 attribute를 연결해 후보 제시, 착용 사례는 구분 | 미실행 | ☐ |
| 6 | 사건이 두 블랙박스 파일 경계에 걸림 | 인접 파일을 하나의 Evidence Interval로 구성 | 미실행 | ☐ |
| 7 | 야간·우천·역광, 번호판 불명확 | event는 찾되 plate는 `확인 필요`; 동일 차량 multi-frame/best frame 근거 제공 | 미실행 | ☐ |
| 8 | 사용자 시간 기억이 10~20분 틀림 | 보정/재탐색 경로 제안, 필요 단계만 재실행 | 미실행 | ☐ |
| 9 | 화면 timestamp 없음 + metadata 시각만 존재 | Source 시작시각+offset으로 계산하고 출처 FILE_METADATA 표시; 삽입은 선택·사후각인 안내 | 미실행 | ☐ |
| 10 | metadata/filename 시각 충돌 또는 GPS 없음/지원범위 밖 | 시각·위치를 만들어내지 않고 provenance 충돌/UNKNOWN 또는 직접 선택 경로 제시 | 미실행 | ☐ |

**이 케이스들을 어떻게 만들었나 (한 줄):**

> **초기 4종 visual event가 요구하는 signal/line/trajectory/helmet attribute·temporal order·target association을 중심으로 positive/hard-negative를 만들고, 실제 long-video 제품에서 흔한 파일경계·시간오류·GPS/번호판/시각 provenance·범위 밖 failure를 함께 넣는다.**

---

## ✅ 필수 2-4. AI가 틀렸을 때 사용자 화면

**🎤 "AI가 틀리게 행동하면 사용자에겐 어떻게 보이나요?"**

UI 원칙: **순수 챗봇이 아니라 Conversational Agent UI + Structured Cards**

| 상황 | 화면에 뭐가 보이나 |
| --- | --- |
| 결과 0개 | `"이 범위에서 확실한 후보를 찾지 못했습니다."` + `[범위 넓히기] [기억 추가] [직접 타임라인]` |
| 후보 여러 개 | Top-3 카드: thumbnail + timestamp + 차량/상황 단서 + 관찰근거 + `[이 장면 선택]` |
| 사건은 맞지만 조금 앞/뒤 | 채팅에서 `"조금 더 앞이었어"` → Main Agent가 범위/Coarse만 재실행 |
| Fine evidence 부족 | `관찰근거 일부 불확실` 표시, 법적 위반을 확정하지 않음 |
| 위반유형이 틀림 | `AI 추천 신고유형` + `[맞아요] [다른 유형]` |
| 번호판 OCR 불확실 | best frame + multi-frame crop/결과 + `12가 34?6` + `[확대] [번호판 수정]` |
| timestamp 출처가 metadata | `촬영시각: ... / 출처: Source 파일 Metadata + candidate offset / 영상 원래 표시는 아님` + 선택적 사후각인 |
| GPS 있음 | 주소/도로/POI 후보 + 안전신문고 검색어, **자체 지도 UI 없음** |
| GPS 없음 | user hint 유지 또는 `위치 미확인`; 안전신문고에서 직접 핀 선택 안내 |
| 신고요건 부족 | `신고 준비 4/5` + 부족 항목과 출처/확인상태 |

### 되돌리는 방법

`[다른 후보] [조금 전/후 다시 찾기] [유형 수정] [번호판 수정] [시간 확인] [위치 단서 수정] [원본 clip 보기]`

---

## ⭕ 선택 — 채점하지 않습니다

### 0단계 질문 통과 여부 — "이 일, 애초에 해야 하는 일인가?"에 걸린 기능이 있었나

- 영상 자르기·압축 → AI 불필요, FFmpeg/코드
- 신고기한·130MB·필수요건 → Rule
- 위치 → GPS parser/geocoder + user hint, **AI/지도 UI 불필요**
- timestamp → Timestamp Resolver(metadata/filename/overlay OCR + continuity validation), AI 추측 금지
- Incident/Evidence State 조립 → 코드
- 신고문 → 확인값 기반 템플릿
- 위반유형 → visual event + Rule + 사용자 선택
- **장시간 사건 후보 탐색 / Fine visual evidence 이해 → 핵심 AI 병목**
- 자연어 보정/필요 단계 재실행 → Agent layer

### 단일 출처(Source of Truth)— 팀원마다 다른 숫자를 들고 오는 걸 막는 문서/데이터 1개

> **Repo의 `docs/product-spec.md`를 의사결정 인덱스로 사용하고, AI 영상 파트는 `AI 영상탐색 Technical Spec v1`, 평가숫자는 버전 고정된 `eval/manifest + results`만 참조한다.**

### 서명자 지정 — 우리 제품의 출력에 대해 책임지는 사람 (영역별 1명)

- Evidence Rule / 신고요건 변경: **평가·QA 담당자**
- Candidate/Fine 평가 기준 변경: **평가·QA + AI 담당 Pair**
- 사건·추천유형·번호판·시간/위치 단서 최종 확인: **사용자**
- 실제 신고 제출: **사용자**

### Trajectory 점검 1건 — 데모를 돌릴 때 결과만 보지 말고 어떤 도구를 불렀는지 확인

```text
사용자 자연어
→ Main Agent: Case State 업데이트
→ 대상 영상 범위 구성
→ Gemini Cheap Coarse
→ Candidate ranking/merge
→ Gemini Fine Evidence
→ Top-3 사용자 사건 선택
→ [Plate Pipeline / Timestamp Resolver / GPS·geocoder] 병렬
→ Evidence State Builder
→ Evidence Rule
→ FFmpeg export + 130MB 검사
→ 신고문 템플릿/Package
→ 안전신문고 handoff
```

**실패 처리:**

- Coarse가 목표 event를 Top-K에서 놓침 → SEARCH_FAILURE
- 신호→정지선→차량 순서를 잘못 이해 → TEMPORAL_ORDER_FAILURE
- 선/신호 자체를 못 봄 → PRIMITIVE_FAILURE
- 다른 차량을 target으로 연결 → TARGET_ASSOCIATION_FAILURE
- Fine이 실제 후보를 제거 → FINE_FALSE_NEGATIVE
- 번호판이 안 보이는데 숫자를 임의 확정 → 실패
- GPS가 없는데 주소를 생성 → 실패
- 신뢰 가능한 source 없이 시각을 생성하거나 metadata/overlay 충돌을 숨김 → 실패
- visual event만 보고 법적 위반을 확정 → 실패
- 신고요건 Rule을 건너뛰고 완료 → 실패
- Source video를 덮어씀 → 실패

---

# 📌 과제 3 — 에이전트 설계 · 문서 · 화면

**🎤 "이거 그냥 챗봇으로 하면 왜 안 되나요?"**

## ✅ 필수 3-1. 루프 한 줄 ＋ “왜 챗봇이 아닌가”

### ① 자가진단 문장

<aside>

우리 제품은 ______________냐에 따라 다음에 할 일이 갈리고,
______________ 없이는 답을 못 내고,
____단계를 밟아야 하므로 챗봇으로는 안 됩니다.

</aside>

> **우리 제품은 사용자가 준 기억 단서·현재 Candidate·Fine 근거·Evidence 누락·사용자 correction 상태에 따라 다음에 실행할 도구가 갈리고, 실제 블랙박스 영상·VLM·OCR/CV·metadata/GPS parser·FFmpeg·Evidence Rule 없이는 답을 낼 수 없으며, 사건 탐색 → 시각근거 검증 → 사람 선택 → Evidence 보강 → 규칙검사 → 파생영상/Package → handoff 단계를 밟아야 하므로 텍스트 챗봇만으로는 안 됩니다.**

### 전체 구조 — Agentic Orchestrator + Specialized AI/Software Tools

```text
사용자 ↔ Conversational Agent UI
              │
              ▼
        [Main Agent]
- 자연어 단서/수정 이해
- Case State 관리
- 필요한 단계 선택·재실행
              │
      ┌───────┼─────────┬──────────┐
      ▼       ▼         ▼          ▼
 File/Meta  Coarse AI  Fine AI   Plate Pipeline
  Parser     Gemini     Gemini    Best/Multi-frame
      │       │         │          │
      └───────┴────┬────┴──────────┘
                   ▼
             Evidence State
                   │
       ┌───────────┼────────────┐
       ▼           ▼            ▼
 Timestamp      Location      FFmpeg
 Resolver       GPS/geocode   Export
       └───────────┼────────────┘
                   ▼
             Evidence Rule
                   ▼
            Structured Review
                   ▼
          SafetyReport Handoff
```

> **제품 상위층은 agentic**, 하지만 영상탐색 내부는 baseline 단계에서 **재현 가능한 deterministic Coarse → Fine pipeline**으로 제한한다. Planner가 자율적으로 영상을 반복 탐색하는 multi-agent 구조는 baseline failure가 필요성을 증명하기 전까지 넣지 않는다.

### ② 루프 한 줄

```text
자연어 기억 단서
→ Main Agent가 Case State 구성
→ 대상 영상 범위
→ Coarse Candidate Generation
→ Fine Evidence Verification
→ Top-3 사건 선택
→ [Plate Pipeline / Timestamp Resolver / Location / Export] 병렬 보강
→ Evidence State + Rule 검사
→ 신고 Package
→ SafetyReport handoff
→ 사용자 수정 시 필요한 단계만 재실행
```

### ③ 칸마다 색

- 🟣 **모델** — 모호한 자연어·비정형 영상 이해
- 🔵 **코드·도구** — 재현 가능한 parsing·변환·조회·검사·State 관리
- 🟠 **사람** — 중요한 Evidence 확인·수정·외부 제출

| 칸 | 무엇을 하나 | 색 | 도구 | 실패하면? |
| --- | --- | --- | --- | --- |
| 1 | 사용자의 자연어 기억을 시간/차량/상황/위치 hint로 구조화 | 🟣+🔵 | Main Agent + Case State | 해석값 수정 |
| 2 | 시간·파일 metadata로 대상 영상 범위 구성 | 🔵 | File API / metadata parser | 범위 재선택 |
| 3 | 장시간 영상에서 Recall 우선 Candidate Top-K 생성 | 🟣 | Gemini Cheap Coarse | 범위 확대 / SEARCH failure 기록 |
| 4 | 후보 clip에서 primitive·temporal evidence 검증 | 🟣 | Gemini Fine | 낮은 확신/다른 prompt/reference |
| 5 | Top-3 중 실제 찾던 사건 선택 | 🟠 | Candidate Cards | 다른 후보/조금 전·후 재탐색 |
| 6A | 대상차량 association→Plate Detection→Best Frame/Multi-frame OCR | 🟣/🔵 | tracking/detector + PaddleOCR baseline | `확인 필요` + 수정 |
| 6B | 사건시각 Resolver: metadata/filename + offset, 필요 시 overlay OCR/연속성 검증 | 🔵 | ffprobe/parser + OCR | 출처 충돌 표시 / User/Unknown 유지 |
| 6C | GPS 추출·주소/POI/search keyword 보강 | 🔵 | GPS parser + geocoder | user hint/unknown fallback |
| 6D | 사건 전후 파생영상 생성 | 🔵 | FFmpeg/ffprobe | Source 보존 후 재시도 |
| 7 | 결과를 provenance 포함 Evidence State로 병합 | 🔵 | State Builder | 누락 필드 표시 |
| 8 | 기한·필수요건·130MB 등 Rule 검사 | 🔵 | Evidence Rule | 부족 항목 표시 |
| 9 | 추천유형·번호판·시간·위치 단서 구조화 리뷰 | 🟠 | Evidence Review Card | 수정 후 해당 도구만 재실행 |
| 10 | 신고문·영상·복사값 Package | 🔵 | Template | 누락 시 완료 X |
| 11 | 안전신문고로 handoff | 🔵+🟠 | Link/Clipboard/Download | 사용자 최종 핀/내용 확인 |

### ④ 한 줄로 세우지 않기

<aside>

이 칸이 만든 데이터가 실제로 다음 칸으로 흘러가나?
예 → 화살표를 남깁니다. 진짜 의존성입니다
아니오 → 화살표를 지우고 둘을 나란히 놓습니다 (동시에 돌아갑니다)

</aside>

**나란히 놓을 수 있는 칸:** 사건 선택 이후 Plate Pipeline / Timestamp Resolver / GPS·위치보강 / 파생영상 준비

```text
Case State
→ Coarse
→ Fine
→ 사건 선택
→ 병렬 Evidence 보강
→ Evidence State
→ Rule
→ 사람 Review
→ Package
→ Handoff
```

---

## ✅ 필수 3-2. 네 가지를 셉니다

**🎤 "AI가 어디까지 스스로 하고, 사람은 어디서 멈춰 세우나요?”**

| # | 무엇을 세나 | 우리 답 |
| --- | --- | --- |
| 1 | 모델 호출이 몇 번인가 | **고정 숫자 2회로 보지 않는다.** 핵심 영상판단은 `Coarse/Fine 2단계`, Main Agent는 대화/재실행 때 조건부, Plate OCR/CV도 조건부. 실제 API 호출 수는 chunk/K 구현에 따라 eval에서 기록 |
| 2 | 사람이 서는 칸이 있는가 | **있음** — Top-3 사건 선택, 추천유형·번호판·시간/위치 단서 확인, 실제 제출 |
| 3 | 되돌릴 수 없는 칸이 있는가 | **서비스 내부 0 / 안전신문고 실제 제출 1** |
| 4 | 통과했는지 무엇으로 아는가 | **결과 eval + Tool Trajectory + 사용자 검토부담/E2E 행동** |

✅ 되돌릴 수 없는 외부 제출 앞에 사람이 서 있음: ☑ 확인함

### 통과 판정

- [ ] **결과가 맞나**
    - locked real test에서 목표 event가 Final Top-3 안에 있는가
    - 사건 없음/Hard Negative에서 과도한 confident FP가 없는가
    - Fine Evidence가 primitive·temporal order·target을 맞게 연결했는가
    - 번호판·시간·위치가 불명확할 때 추측하지 않았는가
    - 신고요건 누락을 표시했는가
- [ ] **거쳐온 경로가 맞나**
    - Main Agent가 수정 요청에 필요한 단계만 재실행했는가
    - Fine을 건너뛰고 법적유형을 확정하지 않았는가
    - Plate OCR 결과에 target vehicle·plate detection·best/multi-frame 근거가 연결됐고 불확실하면 abstain했는가
    - GPS 없을 때 주소를 생성하지 않았는가
    - Timestamp Resolver가 source+offset/provenance를 보존하고 metadata timestamp 삽입 시 사후각인 표시가 있었는가
    - Evidence Rule을 실제 통과했는가
    - Source video를 덮어쓰지 않았는가

---

## ✅ 필수 3-3. PRD 초안 — A4 한 장

**① 이미 갖고 있는 여섯 칸 — 옮겨 적으면 끝입니다**

| 항목 | 내용 |
| --- | --- |
| **배경** | 2023년 교통법규 위반 공익신고는 약 366만 건 규모이며, 신호위반·중앙선침범·진로변경/방법위반·지정차로위반 등 전후 맥락이 중요한 대표유형만 약 203만 건이다. 실제 신고자는 SD카드 영상 탐색·편집/용량·시간·위치·차량번호·내용 입력을 수행한다. 신고콕은 이 workflow 후반을 줄이지만 사건장면을 사용자가 먼저 찾아야 한다. |
| **문제** | 이미 신고 의향이 있는 운전자도 사후 Evidence Preparation 비용 때문에 실제 제출 전 이탈할 수 있다. 긴 영상 사건 재탐색은 정성적으로 존재가 확인됐지만 최우선 pain·실제 시간·포기율은 추가 실측이 필요하다. |
| **목표** | 자연어 기억 단서만으로 Main Agent가 Case State를 만들고, Gemini Coarse/Fine이 장시간 영상에서 초기 4종 visual event와 전후 Evidence Interval을 찾아 Top-3로 제공한다. 사용자는 구조화된 Evidence를 확인한 뒤 신고 준비와 안전신문고 handoff까지 간다. |
| **비목표** | 모든 위반유형, AI 법적 최종판정, 무인 자동신고, 자체 지도 UI, GPS 없는 위치 완전자동추정, 얼굴 모자이크 Must, baseline 전 ADAS/SentrySearch/fine-tuning, 자율 multi-agent video exploration은 하지 않는다. |
| **성공 지표** | AI: locked real long-dashcam Final Event Recall@3 + Candidate/Fine/Hard-negative/비용·latency. 제품: 검토 후보 수·직접 작업시간·준비 완료율·handoff/실제 제출 행동. 20분→3분은 실측할 목표 시나리오다. |
| **유저 스토리** | “나는 위험한 교통위반을 신고하려는 운전자로서 사건 시각을 정확히 기억하지 못해도 블랙박스에서 그 장면과 신고 근거를 빠르게 찾고 싶다. 이미 신고할 마음은 있지만 준비 과정 때문에 포기하고 싶지 않기 때문이다.” |

**② 나머지 네 칸**

| 항목 | 내용 |
| --- | --- |
| **범위 (Must / Won’t)** | Must: Agent natural-language/correction, 초기 4종 Coarse/Fine, Top-3, Evidence Interval, file-boundary, Plate Pipeline(PaddleOCR baseline + Best/Multi-frame + abstention), Timestamp Resolver(metadata/filename/overlay OCR provenance), GPS optional enrichment, Evidence Rule, 130MB export, handoff. Won’t: 모든 유형·법적확정·무인신고·자체지도·얼굴모자이크 필수·baseline 전 고비용 challenger. |
| **엣지 케이스** | 사건 없음 / Hard Negative / 야간·우천 / 파일경계 / 잘못 기억한 시간 / 유사 차량 / 이륜차 안전모 착용 hard negative / 번호판 저해상도·blur·glare / target association 오류 / 화면 timestamp 없음 / metadata·filename·overlay 충돌 / GPS 없음 / codec 문제 / 범위 밖 유형. |
| **가드레일** | visual event와 legal status 분리. 보이지 않는 번호판·위치·시각 추측 금지. Plate는 잘못 읽고 확정하는 것보다 abstain/사용자 확인을 우선. Timestamp는 source+offset/provenance와 출처 충돌을 보존. Source video 덮어쓰기 금지. 파생영상의 timestamp 삽입은 provenance와 사후각인 고지. 실제 제출은 사용자. 개인정보 업로드 최소화·TTL/삭제·외부 AI API/학습 재사용 정책 검토. |
| **열린 질문** | ① 사건 재탐색이 Evidence Preparation의 최우선 pain인가? ② 자동준비가 실제 신고완료 행동을 높이는가? ③ Gemini Coarse/Fine의 real long-dashcam 실패 taxonomy와 비용은? ④ H.265/대용량 처리·proxy 전략은? ⑤ metadata timestamp 사후삽입의 제출 실무 허용범위는? ⑥ 외부 AI API에 원본/파생영상을 어느 범위까지 보낼 것인가? ⑦ 파생영상 압축·편집과 증거요건은 어떻게 공존하는가? |

**③ 자율성 경계**

| # | 무엇을 세나 | 우리 답 |
| --- | --- | --- |
| 1 | 모델 호출 | Main Agent + Coarse/Fine + conditional Plate. 실제 호출수는 eval 기록 |
| 2 | 사람 | 사건·추천유형·번호판·시간/위치 단서·제출 확인 |
| 3 | 되돌릴 수 없는 칸 | 서비스 내부 0 / 외부 제출 1 |
| 4 | 통과 기준 | 결과 eval + trajectory + 사용자 E2E |

---

## ✅ 필수 3-4. CLAUDE.md ＋ 붙일 도구

### CLAUDE.md 실제 작성

- [ ] 실제 프로젝트 저장소 반영 전

### CLAUDE.md 초안

```markdown
# 제품 불변 규칙

## Evidence / 판단 경계
- AI는 교통법규 위반을 법적으로 최종 확정하지 않는다.
- Visual event와 legal status를 분리한다.
- 초기 지원 visual event는 SIGNAL / CENTER_LINE_CROSSING / LANE_CHANGE / MOTORCYCLE_HELMET_NON_USE 4종이다.
- Fine 결과는 가능하면 primitive, target, temporal order, timestamp 근거를 구조화한다.
- 보이지 않는 번호판·위치·시각은 추측하지 않고 `확인 필요` 또는 UNKNOWN으로 반환한다. Plate OCR은 target association/detection/recognition failure를 구분하고 불확실하면 abstain한다.

## Agent / workflow
- 제품 상위층은 Main Agent가 Case State와 tool routing을 관리한다.
- Coarse→Fine 영상 탐색은 재현 가능한 pipeline으로 유지한다.
- 사용자의 수정 요청에는 필요한 단계만 재실행한다.
- Evidence Rule, 130MB 검사, 기한, state merge를 LLM의 기억으로 처리하지 않는다.

## Video / provenance
- 사용자가 선택한 Source video를 덮어쓰지 않는다.
- Source / analysis proxy / derived evidence 파일을 구분한다.
- timestamp는 VIDEO_OVERLAY_OCR / FILE_METADATA / FILENAME / USER_INPUT / UNKNOWN 출처와 Source offset을 보존한다.
- Timestamp Resolver는 metadata를 무조건 신뢰하지 않고 가능한 source를 교차확인하며, Metadata timestamp를 파생영상에 표시할 때는 사후각인임을 명확히 한다.
- GPS가 없으면 위치를 생성하지 않는다. user hint 또는 UNKNOWN으로 유지한다.
- 우리 서비스에서 최종 지도 핀을 확정하지 않는다. SafetyReport에서 사용자가 최종 확인한다.

## Privacy / security
- 얼굴 모자이크를 안전신문고 제출 필수요건으로 가정하지 않는다.
- 업로드 범위, 보관기간, 자동삭제, 외부 AI API 전송, 학습 재사용 정책을 명시한다.
- 실제 사용자 영상·차량번호·정확한 위치를 불필요하게 로그에 남기지 않는다.
- API Key/secret을 frontend에 포함하지 않는다.

## Action boundary
- 실제 안전신문고 제출은 사용자 승인 없이 실행하지 않는다.
```

### 붙일 도구 2~3개

| 도구 | 무엇을 하나 | 하지 않는 일 |
| --- | --- | --- |
| **Main Agent / Case State Orchestrator** | 자연어 단서·수정 이해, tool routing, state update | 영상 자체 판단을 독자적으로 재생성 / 외부 제출 |
| **Gemini Video Pipeline wrapper** | Cheap Coarse Candidate + Fine Evidence A/B + structured contract | 법적 최종판정 / Evidence Rule 대체 |
| **Evidence Toolkit** | Plate Pipeline(PaddleOCR baseline, Best/Multi-frame, abstention), Timestamp Resolver(metadata/filename/overlay OCR + offset/provenance), GPS/geocoder, State Builder, FFmpeg, 130MB/기한/Rule, Package | 불확실 정보 추측 / 사용자 승인 없는 제출 |

### 스킬 후보 1개

- **이름:** `[미정 — 실제 작업 1회 완료 후 반복 패턴을 추출]`
- **Description:** `[미정]`
- **한 번 당해봐야 아는 것(gotcha):** `[codec/GPS metadata/timestamp provenance/특정 위반유형 evidence 분해 등 구현 후 기록]`

---

## ✅ 필수 3-5. 핵심 시나리오 1개의 화면 흐름

**🎤 "처음 들어와서 핵심 경험까지 한 번 따라가 볼까요?"**

## **① 루프의 한 단계 = 화면 하나 또는 상태 하나**

UI는 **Conversational Workspace / Conversational Agent UI**로 구성한다.

- **대화:** 기억 단서 입력·보정·재탐색 요청·진행 설명
- **구조화 카드:** Top-3 비교·Evidence 근거·번호판·timestamp provenance·위치단서·신고요건·Package
- “모든 것을 채팅으로” 만들지 않는다. 중요한 판단은 사용자가 원본/근거와 함께 직접 확인한다.

| 칸 | 무엇이 보이나 | 우리 화면 |
| --- | --- | --- |
| **① 인식** | attachment + 자연어 | 블랙박스 폴더/파일 정보 + “6시 반쯤 흰 SUV가 실선을 넘었어요” |
| **② 계획 ⭐** | Agent가 이해한 것 + 진행 | 시간/차량/상황/위치 hint 요약 + `대상영상 → Coarse → Fine` 상태 |
| **③ 행동** | Top-3 Candidate Cards | thumbnail·timestamp·차량/상황·관찰근거 + `[이 장면 선택]` |
| **④ 반영** | Evidence Review Card | 사건 clip, 추천 신고유형, 번호판 best frame, timestamp 출처, 위치후보/search keyword, 파일/요건 |
| **⑤ 핸드오프 ⭐** | Package | 신고영상 다운로드·전체복사·안전신문고 이동. 최종 지도 핀·제출은 안전신문고에서 사용자 확인 |

## **② 끊김 점검 — 이 순서대로 이어지나요?**

### ① 인식

```text
[ 블랙박스 폴더 선택 완료 · 42개 · 18:03~19:21 ]

사용자:
"6시 반쯤 흰 SUV가 실선을 넘어왔어요.
미금역 근처였던 것 같아요."
```

Agent:

```text
이렇게 이해했어요.
시간 단서   18:30 전후
차량 단서   흰색 SUV
사건 단서   백색 실선 crossing 가능성
위치 단서   미금역 근처

[수정] [영상에서 찾아보기]
```

### ② 계획

```text
✓ 대상 영상 범위 구성
● Recall 우선 후보 탐색
○ 후보 시각근거 정밀 확인
```

### ③ 행동 — Top-3 Candidate Cards

```text
후보 1 — 18:31:48
관찰: 백색 실선 + 흰 SUV가 선을 넘어 인접차로 진입
[근거 보기] [이 장면 선택]

후보 2 — 18:36:04
관찰: 흰 SUV 차로변경, 선 종류 불확실
[근거 보기] [이 장면 선택]

후보 3 — 18:42:11
관찰: 백색 실선 crossing, 차량색은 검정
[근거 보기] [이 장면 선택]

[다른 장면으로 다시 찾기]
```

사용자 자연어 correction:

```text
"이거보다 조금 전이었어"
→ Main Agent가 시간 범위 / Candidate Search만 재실행
```

### ④ 반영 — Evidence Review

```text
선택한 사건
18:31:42 ~ 18:31:57

AI가 확인한 시각근거
✓ 백색 실선 존재
✓ 대상 흰 SUV
✓ crossing 전 우측 영역
✓ line crossing
✓ crossing 후 인접차로 진입

AI 추천 신고유형
백색 실선 진로변경 관련
[맞아요] [다른 유형]
```

**번호판**

```text
[target vehicle의 best frame 확대 이미지]
12가 34?6
출처: PaddleOCR baseline / best frame + multi-frame 결과 비교
상태: 일부 문자 불확실 → 사용자 확인 필요
[다른 프레임 보기] [확대해서 확인] [번호판 수정]
```

**발생시각**

```text
2026-08-24 18:31:48
출처: VIDEO_OVERLAY_OCR
검증: 주변 frame 시간 연속성 일치
```

또는

```text
2026-08-24 18:31:48
출처: Source 파일 Metadata + candidate offset
⚠ 영상 화면에 원래 표시된 시각은 아닙니다.
[파생영상에 촬영시각 표시]  ← 선택 기능 / 사후 각인 고지
```

**위치**

GPS 있음:

```text
위치 후보: 미금역 사거리 인근
출처: 블랙박스 GPS
안전신문고 검색어: [미금역 사거리] [복사]
※ 최종 핀은 안전신문고 지도에서 확인해주세요.
```

GPS 없음:

```text
위치 단서: 미금역 근처
출처: 사용자 기억
안전신문고 검색어: [미금역] [복사]
※ 최종 핀은 안전신문고 지도에서 선택해주세요.
```

> **MVP에서는 자체 지도/핀 조정 화면을 만들지 않는다.** 기존 프로토타입의 지도 패널과 `[위치 지도에서 조정]` 버튼은 제거한다.

### ⑤ 핸드오프

```text
신고 준비 완료
✓ 사건영상 20초 · 84MB
✓ 발생일시 + 출처
△ 위치 후보/검색어 · SafetyReport 최종확인 필요
✓ 차량번호 · 사용자 확인
✓ 추천 신고유형 · 사용자 확인
✓ 신고내용 템플릿

[영상 다운로드] [전체 복사] [안전신문고로 이동]
```

**실제 접수 제출은 사용자가 직접 수행한다.**

## **③ "안 될 때" 화면 — 두 종류입니다**

| 상황 | 화면 |
| --- | --- |
| 빈 결과 | `이 범위에서 확실한 후보를 찾지 못했습니다.` + 범위 넓히기/기억추가/직접타임라인 |
| 낮은 Fine 확신 | `시각적 근거 일부가 불명확합니다.` + 후보 clip 직접 확인 |
| 범위 밖 | `현재 자동탐색 지원 범위를 벗어났습니다.` + 직접 구간 선택/안전신문고 이동 |
| GPS 없음 | 오류가 아니라 `사용자 위치단서/UNKNOWN` 정상 상태 |
| timestamp 없음 | `시각 확인 필요`; 자동 생성 금지 |
| Plate 불확실 | best/multi-frame 근거 + 물음표 문자열 + abstain/직접 수정 |
| Agent 오해 | 자연어/버튼으로 Case State 수정, 필요한 단계만 재실행 |

---

## ⭕ 선택 — 채점하지 않습니다

### 탈출구 3종

- **반복 상한:** 사용자 correction에 따른 자동 재탐색은 비용/latency 실측 후 상한 설정. 무한 agent loop 금지
- **타임아웃:** 일정 시간 초과 시 현재 Candidate + `[직접 타임라인]` 제공 — baseline 실측 후 결정
- **완료 조건:** 사건 선택 + 필수 Evidence 상태 확인 + Rule 검사 + 신고용 파생영상/Package + SafetyReport handoff 가능

### CLAUDE.md에 넣을 것 / 뺄 것

| 항상 지킬 것 (CLAUDE.md) | 가끔 필요한 것 (스킬로) |
| --- | --- |
| visual event / legal status 분리 | 특정 위반유형 Fine evidence decomposition |
| 불확실한 plate/location/time 추측 금지 | 특정 블랙박스 codec/GPS parser |
| Source video 덮어쓰기 금지 | 특정 metadata timestamp 처리 |
| Evidence Rule을 LLM 기억으로 대체 금지 | 특정 신고문 템플릿 |
| 사용자 없는 자동신고 금지 | Hard-negative debugging |
| privacy/secret/log 원칙 | 제조사별 파일경계 처리 |

### 폴더 구조

```text
repo/
├── CLAUDE.md
├── docs/
│   ├── product-spec.md
│   ├── ai-video-tech-spec-v1.md
│   └── evidence-policy.md
├── agent/
│   ├── orchestrator/
│   └── case_state/
├── tools/
│   ├── candidate_generator/
│   ├── fine_verifier/
│   ├── plate_pipeline/
│   ├── timestamp_resolver/
│   ├── gps_location/
│   ├── ffmpeg_export/
│   └── evidence_rule/
└── eval/
    ├── manifest/
    ├── cases/
    ├── references/
    ├── locked_test/
    └── results/
```

- [ ] 실제 저장소에 생성 전

---

# 📌 과제 4 — 3개월 뒤에 남는 것

## ✅ 필수 4-1. 래퍼 자가진단 ＋ “쓸수록 못 따라오는 지점”

**🎤 "이거 ChatGPT에 물어보면 나오는 거랑 뭐가 달라요?”**

- 판정: ☐ 80% 이상 나온다 ☑ **그대로는 안 나온다**

### 나머지 20%는 무엇인가 :

범용 VLM에 이미 잘라낸 짧은 영상을 넣고 “무슨 일인가?” 묻는 것은 가능하다. 우리 제품은 그 앞뒤를 포함한다.

```text
자연어 기억 단서
→ 여러 블랙박스 파일/시간축 구성
→ Cheap Coarse Candidate Search
→ Structured Fine Evidence
→ Top-3 user correction
→ 사건 전후 Evidence Interval
→ Plate Pipeline (target association → Best/Multi-frame OCR)
→ Timestamp Resolver + provenance
→ GPS/user hint 위치보강
→ FFmpeg / 130MB / Evidence Rule
→ Package
→ SafetyReport handoff
```

> 핵심은 프롬프트 자체가 아니라 **Long Video → Event → Evidence → Action-ready Package를 Case State로 연결하고, 사용자 correction에 필요한 단계만 재실행하는 Agentic workflow**다.

신고콕은 이 전체 workflow의 **후반부가 제품으로 성립함을 보여주는 reference**이지만, 장시간에서 사건 자체를 찾는 앞단은 사용자가 수행한다.

### 🎤 “쓸수록 남들이 못 따라오게 되는 지점”

> **실제 long-dashcam에서 초기 4종 visual event를 어떤 조건에서 놓치고, 어떤 Hard-negative에 속고, 사용자가 어떤 후보/번호판/유형을 수정하는지 event/case 단위로 축적한 eval/failure/correction 데이터와 평가 harness**다. Plate에서는 Detection/Recognition/Target Association/Abstention을, Timestamp에서는 source 충돌/OCR 연속성 실패를 별도 failure로 남긴다.

AI-Hub 경찰청 원천 데이터도 단순 fine-tuning용이 아니라:

```text
AI-Hub
├─ Evaluation source
├─ Positive / Hard-negative Reference source
└─ Future Training source
```

로 활용한다. 같은 case의 연속 frame이 train/test에 섞이지 않도록 event/case 단위로 관리한다.

---

## ✅ 필수 4-2. 남는 것 — 네 가지 중 우리 것 2개

| 판정 질문 | 무엇인가 | 우리 것 |
| --- | --- | --- |
| ① 유저 락인 | 쓸수록 떠나기 어려워지나 | △ 현재 핵심 아님. 신고기록/기한/처리결과는 신고콕에서 검증된 retention pattern으로 후속 검토 |
| **② 데이터 해자** | 옆 팀은 오늘 시작해도 못 따라잡나 | **☑ 핵심 — locked real long-video eval + Positive/Hard-negative + failure/correction + harness** |
| ③ 월등한 UX | 같은 모델로 다른 경험을 만드나 | ○ Conversational Agent UI + Structured Evidence Cards + 필요한 단계만 재실행 |
| **④ 아무나 못 들어오는 것** | 막는 게 기술이 아니라 책임인가 | **☑ Human-in-the-Loop evidence workflow — 차량번호·위치·timestamp·외부신고를 provenance와 함께 책임있게 연결** |

### 🎤 “3개월 뒤에 여러분 손에 남는 게 뭐예요?”

> **특정 모델 이름이 아니라, 실제 long-dashcam에서 무엇을 왜 놓치는지 재현할 수 있는 평가체계와, 그 결과를 사용자가 검증 가능한 Evidence State·신고 준비까지 연결하는 Agentic workflow가 남는다.**

---

## ✅ 필수 4-3. 순풍 / 역풍 ＋ 3단 계획

- 판정: ☑ **순풍** ☐ 역풍

### 근거 한 문장 :

> **범용 VLM이 좋아지고 싸질수록 장시간 Candidate/Fine 성능과 비용은 개선되지만, 우리 eval/failure data·Evidence provenance·Rule·Case State·사용자 correction·SafetyReport handoff는 그대로 남고 더 강해진다.**

### 모델이 10배 좋아지면 없어도 되는 기능 :

- 일부 low-resolution/sparse workaround
- 반복 Fine retry
- 사용자가 상세한 검색힌트를 많이 입력해야 하는 UX
- 특정 primitive detector 보조
- 일부 challenger routing 복잡도

### 모델이 10배 좋아지면 새로 가능해지는 기능 :

- 시간대를 거의 몰라도 수시간/SD카드 전체 탐색
- 여러 사건 자동 후보화
- 전방/후방 다채널 통합
- 애매한 temporal event의 높은 Recall
- 사고·보험·분쟁 등 다른 Long Video → Evidence workflow 확장

### 3단 계획 - 🎤 심사가 보는 게 정확히 "앞으로 3개월의 방향"입니다

| 단계 | 시점 | 무엇을 보여주나 |
| --- | --- | --- |
| 1단계 | 초반 | Evaluation Harness → Gemini Coarse/Fine baseline → Structured Prompt A/B → Fixed Reference A/B |
| 2단계 | 중반 | Main Agent + Case State + Plate Pipeline + Timestamp Resolver + Location/FFmpeg/Rule + Conversational Workspace E2E |
| 3단계 | 후반 | locked real test + 사용자 기존방식 비교 + failure taxonomy 기반 필요한 Challenger만 추가 |

> ADAS/CV Candidate Generator, SentrySearch, 자체 VLM fine-tuning, 상시 GPU VM, 자율 multi-agent exploration은 **폐기하지 않았지만 baseline failure가 필요성을 증명할 때만 연다.**

---

## ✅ 필수 4-4. 첫 100명을 데려올 채널 딱 1개

- 타깃: ☑ **개인(B2C)**
- **우리 채널 딱 1개:** 보배드림 교통사고/블랙박스 게시판

### 왜 그 채널인가:

우리에게 필요한 사람은 단순 운전자가 아니라 **실제 블랙박스 영상을 찾아 교통위반 신고를 준비하거나 포기해본 사람**이다.

### 거기서 30명을 어떻게 확보하나

1. **실제 행동 인터뷰 10명**
    - `지난번 신고에서 영상을 어떻게 찾았나?`
    - `탐색/편집/위치/작성 각각 몇 분?`
    - `가장 귀찮았던 단계?`
    - `중간에 포기한 적? 왜?`
    - 동기: 위험경험/불공정/생활권/처리결과
    - 저항: 굳이 신고/보상 없음/낙인/불수용·지연
2. **Concierge 10명** — 과거 영상으로 사건/증거 준비를 대신해주고 실제 가치 확인
3. **Prototype 30명** — 기존 방식 vs 대신고에서 직접 작업시간·후보검토수·준비완료/handoff/실제 제출행동 비교

### 아이디어톤 전에 한 번 올려봤다

- [ ] 미실행
- **올린 곳 / 반응:** `[게시 후 실제 결과 입력]`

---

## ⭕ 선택 — 채점하지 않습니다

### 냅킨 계산

금액을 임의로 먼저 정하지 않는다. Technical Spec v1의 Efficiency를 동일 eval에서 측정한다.

```text
source-video-hour당 비용
= Coarse 분석
+ Fine exposure
+ Plate Pipeline/OCR
+ Timestamp Resolver/OCR fallback
+ storage/transfer
+ optional geocoder
```

기록값:

- latency
- tokens
- Fine exposure ratio
- source-video-hour당 원가
- 사용자 1건당 평균 탐색범위/재탐색 횟수

### 비용을 설계로 줄이는 방법

- ☑ 기억 단서로 시간범위 우선 축소
- ☑ Gemini Cheap Coarse로 Recall 우선 routing
- ☑ 후보 clip만 Fine
- ☑ proxy/index/cache 가능성 검토
- ☑ Agent 반복상한
- ☑ Failure가 COST일 때만 Local SLM/CV/self-host/fine-tuning Challenger

### 임시방편 vs 구조적

| 임시방편 | 구조적 |
| --- | --- |
| sparse sampling / proxy 파라미터 조정 | locked real eval/failure set |
| 특정 prompt workaround | structured evidence schema |
| 반복 Fine | Positive/Hard-negative reference harness |
| 검색 hint 많이 받기 | natural-language correction + Case State |
| 특정 model routing | 모델 독립 Candidate/Fine I/O contract |
|  | Timestamp Resolver + location + plate provenance/abstention |
|  | Evidence Rule + SafetyReport handoff |

### 공개 정책

- **공개해도 되는 것:** 문제정의, 비식별 Demo, 평가방법, aggregate benchmark, Before/After
- **출시 후/비공개:** 실제 사용자 원본, 차량번호·정확한 위치, 세부 failure/hard-negative corpus, abuse 대응, 민감 routing 정보

### 가격 가설

- 우리가 파는 것: ☐ 기능 ☑ **결과**
- 결과: **장시간 영상에서 찾던 사건과 신고준비 자료가 이미 정리된 상태**
- 가격: `[미정 — 실제 pain·사용빈도·시간가치 확인 후]`

### 재방문을 제품 형태로

신고콕에서 신고기록·기한·처리결과·통계가 실제 기능으로 존재하므로 retention pattern 자체는 참고할 가치가 있다. 다만 10주 핵심은 아니다.

**왕복 핵심**

> AI가 Candidate/Evidence 제시 → 사용자가 사건·유형·번호판 등을 correction → failure/eval에 반영 → 다음 모델/프롬프트/Reference 비교에 사용

### 지금 희망으로 버티는 것 한 줄

> **영상 재탐색·편집 등의 불편이 존재한다는 것은 정성적으로 확인했지만, 이것이 최우선 pain이고 자동 준비가 실제 신고 완료 행동을 유의미하게 높인다는 점은 아직 검증해야 한다.**

### 우리가 그대로 베낄 Proven 3개

- **신고콕** — 사건을 찾은 이후의 metadata·트림·번호판·신고요건·신고문·기한/기록 UX
- **안전신문고** — 최종 위치 검색/핀 조정·본인인증·실제 제출 workflow
- **AI-Hub 경찰청 데이터 구조** — 신호·차선/진로변경·이륜차 안전모 등 지원 유형의 annotation을 평가·Reference·향후 학습 source로 활용

### 남의 제품에 묻혀 있는 것

> 신고콕에는 downstream 자동화가 충분히 존재한다. 대신고가 새로 해결해야 하는 핵심은 그 앞의 **“사용자가 사건 위치를 아직 모르는 장시간 블랙박스 → Candidate → Evidence Interval”**이다.

---

# 📌 과제 5 — 차별화와 10주 운영

## ✅ 필수 5-1. 차별화 한 문장 ＋ “우리만 아는 진실”

### ① 차별화 한 문장

<aside>

우리 아이디어는 [흔한 버전]과 달리 [차별점] 때문에 다르다.

</aside>

> **우리 아이디어는 [신고콕처럼 사용자가 위반 순간을 이미 찾은 뒤 영상·시각·번호판·신고요건을 정리하는 서비스]와 달리, [사용자가 기억나는 단서만 말하면 장시간·다중 블랙박스에서 AI가 사건 후보와 전후 Evidence Interval 자체를 먼저 구성하고, Main Agent가 사용자 correction에 맞춰 필요한 도구만 재실행한 뒤 downstream 신고 준비까지 연결한다는 점]에서 다르다.**

### ② “남들이 동의하지 않는, 우리만 아는 진실”

> **교통위반 신고의 문제는 ‘사람들이 신고할 마음이 없다’가 아니라, 이미 생긴 신고 의향이 사후 Evidence Preparation의 마찰로 실제 제출 전에 사라지는 데 있을 수 있다.**
>
> 긴 영상 탐색·편집·용량 조정의 불편 자체는 정성적으로 확인됐다. **그중 사건 재탐색이 최우선 pain인지와 자동 준비가 실제 신고전환을 높이는지는 검증 가설**이다.

---

## ✅ 필수 5-2. 역할 4개 배정

| 역할 | 누가 | 소유하는 것 | 연결 |
| --- | --- | --- | --- |
| **PM** | **김준영** | Product Spec · Must/Won’t · Agent boundary · 수렴 최종 결정 | Part 1 |
| **평가·QA** | **서어진** | Evaluation Harness · locked test · Failure taxonomy · 믿을 수 있는 숫자 | Part 2-3 |
| **통합** | **유소연** | Main Agent/BE/AI/영상처리/외부도구 E2E 통합 · 머지 | Part 5 |
| **발표·스토리** | **김준영** | 박신고 Proto-persona · 20→3 가설 · Demo · Q&A · 문서 일관성 | 클로징 |

### 나머지 팀원 구현 주축

- **김대원:** Video FE / Candidate Cards / Timeline / AI 기술 Spike
- **신유민:** Conversational Workspace / 진행·실패·Evidence Review UI / FE-AI 연결

### 핵심 Pair

- Long-video AI / Eval → **서어진 + 김대원**
- Backend / Agent / FFmpeg → **김준영 + 유소연**
- Conversational Video UX → **김대원 + 신유민**
- Evidence Rule / QA 문서 → **서어진 + 정철원**
- 최종 E2E 통합 → **유소연 중심 + 전원**

### 첫 모임과 첫 커밋

- [ ] 첫 모임: Problem / Proto-persona / Technical Spec v1 / Must-Won’t / 역할 한 화면
- [ ] 저장소 첫 커밋: `CLAUDE.md · docs/product-spec.md · eval/`

---

## ✅ 필수 5-3. 지뢰 8개 체크리스트

| # | 지뢰 | 어디서 했나 | 우리는? | 대응 |
| --- | --- | --- | --- | --- |
| ① | AI를 위한 AI | 2-1·2-2 | ☐ 핵심에는 해당 안 됨 | Agent/Coarse/Fine/Plate만 AI, State/Rule/FFmpeg/GPS는 SW |
| ② | 뻔한 래퍼 | 4-1·5-1 | ☑ 위험 있음 | Long Video→Event→Evidence Interval + correction + eval/failure moat |
| ③ | 개인정보·안전 | 2-1·5-3 | **☑ 매우 해당** | 최소업로드·보관/자동삭제·외부AI전송·학습재사용·민감로그 정책 |
| ④ | 콜드 스타트 | 4-4 | ☐ 비교적 낮음 | 자신의 과거 블랙박스만으로 즉시 가치. 대신 실제 long-video eval corpus는 구축 필요 |
| ⑤ | 데모만 되고 실제로 안 됨 | 2-3 | **☑ 매우 해당** | Hard-negative/locked real/failure taxonomy + 실제 H.265 E2E |
| ⑥ | 빌드 인 퍼블릭 역풍 | 4-4 | ☑ 해당 | 비식별 Demo, 실제 원본/plate/location/failure corpus 보호 |
| ⑦ | 마지막 20% | 3-5 | **☑ 매우 해당** | “장면 찾음”이 아니라 provenance+Rule+130MB+Package+handoff까지 |
| ⑧ | 바이브코딩 보안 ⭐ | 아래 | 실제 코드 후 확인 | Key·Endpoint·Storage·로그·FFmpeg·파일 접근·AI provider 전송 점검 |

### ⑧ 보안 — 실제 확인

현재 초안 단계이므로 완료로 체크하지 않는다.

- [ ] `.gitignore`에 `.env`
- [ ] API 키가 Frontend에 없음
- [ ] 인증 없이 열린 API endpoint 없음
- [ ] DB/Object Storage 접근 규칙
- [ ] 사용자 간 영상 IDOR 방지
- [ ] 업로드할 원본/파생영상 범위 정의
- [ ] 외부 AI API에 보내는 영상범위·provider 명시
- [ ] 보관기간/TTL/자동삭제 구현
- [ ] 학습 데이터 재사용 default 정책 명시
- [ ] raw video 로그 미기록
- [ ] 차량번호·정확한 위치 로그 masking
- [ ] FFmpeg/파일명 입력 validation

### 얼굴 모자이크 관련

- **안전신문고 교통위반 신고의 필수 제출 요건으로 확인되지 않았으므로 MVP Must에 포함하지 않는다.**
- 다만 블랙박스 업로드·분석은 개인영상정보 처리에 해당할 수 있으므로 privacy architecture는 MVP부터 검토한다.
- **외부 공유·데모:** 실제 영상 사용 시 비식별 처리
- **실제 신고 제출용:** 자동 얼굴 모자이크를 기본 적용한다고 확정하지 않음
- **후속 선택 기능:** 외부공유·데모·학습데이터 구축·privacy 강화가 필요할 때 파생영상 blur 추가

### Source video / 파생영상 정책

- 소프트웨어 안전원칙: **사용자 Source video를 실수로 덮어쓰지 않는다.**
- 별도 열린 질문: 신고용 Derived Evidence에서 압축·timestamp 삽입·블러·재인코딩 등 어떤 변환을 허용할지는 Evidence Policy와 공식 제출요건 확인 후 결정

### 배포 전 AI 보안 리뷰

```text
배포 전에 이 프로젝트를 보안·개인정보 관점에서 검토해줘. 특히:

① frontend secret/API key
② 인증 없는 endpoint / IDOR
③ DB/Object Storage 접근규칙
④ source/proxy/derived video 저장 위치와 TTL
⑤ 외부 AI provider에 전송하는 파일/clip 범위
⑥ 차량번호·GPS·주소·영상 metadata 로그
⑦ 학습/평가 데이터 재사용 동의와 비식별
⑧ FFmpeg/file parser 사용자 입력 validation
⑨ 삭제 요청/자동파기
⑩ 불필요하게 수집하는 개인정보

발견한 것마다
[위험도 / 무슨 일이 일어날 수 있나 / 고치는 법]
형식으로.
확실하지 않으면 추측하지 말고 "확인 필요"로 표시해.
```

- [ ] 돌렸다
- 나온 것 중 고친 것: `[실제 배포 전 입력]`

---

## ✅ 필수 5-4. 프로젝트 관리안 ＋ 피봇 규칙

### ① 10주 마일스톤 — 불확실성 제거 순서

| 주차 | 제거할 불확실성 | 확인 방법 |
| --- | --- | --- |
| **1~2주** | **평가체계 + Problem 우선순위 + Gemini baseline** | Evaluation Harness/event schema/real long-video 준비 + 실제 신고자 행동 인터뷰 + Gemini Cheap Coarse/Fine baseline + source-video-hour 비용/latency |
| **3~4주** | **Fine reasoning / Reference가 실제로 필요한가** | 동일 clip에서 Direct vs Structured Evidence vs Structured+Positive/Hard-negative Reference A/B + failure taxonomy 분석 |
| **5~6주** | **Agentic workflow와 Evidence State가 E2E로 닫히는가** | Main Agent correction/routing + Candidate Cards + Plate Pipeline(PaddleOCR baseline/Best/Multi-frame) + Timestamp Resolver(source+offset/overlay OCR) + GPS optional enrichment + FFmpeg/130MB/Rule + Package |
| **7~8주** | **사용자가 실제로 더 적게 일하고 신고 완료로 가는가** | 기존 수동 방식 vs Prototype: 직접 작업시간·검토후보수·수정횟수·준비완료·handoff/실제제출 행동 관찰 |
| **9~10주** | **locked real 성능·privacy/security·통합·발표** | locked test + regression + cost/CI + privacy/security review + H.265/대용량 E2E + Demo/Q&A |

### 1~2주차에 하지 않는 것

- 예쁜 UI부터 완성
- 모든 위반유형
- 자체 지도 UI
- 얼굴 모자이크 Must
- VideoChat3/SentrySearch/ADAS 인프라부터 구축
- 자체 VLM fine-tuning
- 상시 GPU VM
- 자율 multi-agent video exploration
- 신고기록/통계 대시보드

### 기술 확장 규칙 — Failure decides the challenger

```text
SEARCH_FAILURE          → VideoChat3 / SentrySearch / retrieval challenger
TEMPORAL_ORDER_FAILURE  → TrafficRAG-inspired / temporal verifier
PRIMITIVE_FAILURE       → ADAS/CV perception
TARGET_ASSOCIATION      → tracking / lane-signal association / stronger VLM
FINE_FALSE_NEGATIVE     → Fine model/prompt/reference
COST                    → Local SLM/CV/self-host/fine-tuning
```

- **Gemini baseline이 충분하면** model hunting보다 E2E 제품 완성에 집중
- **부족하더라도** “더 좋아 보이는 모델”을 무작정 비교하지 않고 failure category가 설명하는 Challenger만 추가
- TrafficRAG도 전체 retrieval부터 구현하지 않고 **고정 Positive/Hard-negative Reference A/B → 효과 확인 후 자동 retrieval** 순서

### ② 주간 리듬

- [ ] 정렬 미팅 주 1회 — 지난주 배운 것 / 이번주 가장 위험한 것 / 막힌 것
- [ ] `product-spec` 주 1회 — 합의·규칙·Won’t·Evidence Policy
- [ ] `eval` 주 1회 — Candidate/Fine/E2E/Cost/Failure regression
- [ ] 실제 사용자 learning 주 1회 — 과거 행동/직접 작업시간/가장 귀찮은 단계
- [ ] Won’t 격주 — 지도·모자이크·모든 유형·challenger scope creep
- [ ] 정기 통합 최소 주 1회

**우리 팀 요일/시간:** 매주 금요일 오후 2시 - 5시

### ③ 피봇 규칙

**피봇/재수렴 신호 — 2개 이상이면 재검토**

- [ ] 실제 신고 경험자에게서 Evidence Preparation의 불편은 있으나 **제품이 줄이려는 단계가 우선순위가 매우 낮음**
- [ ] 자동 준비된 Prototype이 직접 작업시간/검토부담을 줄여도 **실제 신고 완료 행동에 거의 영향이 없음**
- [ ] locked real long-video의 Final Recall@3가 실사용에 부족하고 failure별 개선 경로가 없음
- [ ] source-video-hour 비용/latency가 공익 B2C 사용에서 감당 불가능하고 최적화 경로가 없음
- [ ] 범용 VLM 단일제품이 Long Video→Evidence→Handoff까지 사실상 동일 UX를 매우 저렴하게 제공
- [ ] 개인정보/외부 AI API/증거 파생처리 제약으로 실사용 가능한 workflow를 만들 수 없음

### 피봇 전에 묻는 질문

> **“Problem hypothesis가 틀린 건가, AI/구현 방식만 부족한 건가?”**

- pain/전환효과 강함 + Gemini search 부족 → 피봇 아님, failure 기반 challenger
- search 됨 + GPS 없음 → 피봇 아님, user hint + SafetyReport final pin
- event 찾음 + plate 불확실 → 피봇 아님, 사용자 확인 fallback
- 기술 됨 + 자동준비가 신고행동을 바꾸지 않음 → product hypothesis 재검토

### 피봇 금지 구간

> **6주차까지 Problem·AI baseline·E2E 가능성을 확인한 뒤에는 새로운 아이디어로의 전면 피봇을 원칙적으로 금지하고 기능 축소·품질개선·failure 기반 구현 변경만 허용한다.**

### 재수렴 방법

> 발산·수렴 분리 → 침묵 브레인라이팅 → 치명적 기준으로 떨어뜨리기 → 레드팀 → PM 최종 결정

---

## ⭕ 선택 — 채점하지 않습니다

### #실험 채널

```text
[CASE]
real / synthetic
visual event type
positive / hard-negative
source duration

[INPUT]
user hint / ground-truth interval

[PIPELINE]
Coarse model/settings
Fine: Direct / Structured / +Reference

[RESULT]
Recall@K / timestamp error / FP-hour
Fine Recall / HN-FPR / Precision
Final Recall@3
latency / tokens / cost / Fine exposure

[FAILURE]
SEARCH / PRIMITIVE / TEMPORAL / TARGET / FINE_FN / OTHER

[LEARNING]
다음 실험에서 바꿀 한 가지
```

### 버린 것 / 보류한 것 기록

| 안 | 상태 | 이유 |
| --- | --- | --- |
| 사진 1장 기반 신고 Agent | 버림 | Long-video problem/Agent workflow가 약하고 영역 중복 |
| 신고콕과 동일한 편집·압축 중심 제품 | 버림 | downstream에 실제 경쟁서비스 존재, 차별점 부족 |
| 상세한 사건설명 필수입력 | 버림 | 자연어 기억 단서와 correction으로 시작 |
| AI 법적 최종판정 | 버림 | visual event + Evidence + 사용자 확인으로 분리 |
| 우리 서비스 자체 지도 UI | 버림(MVP) | SafetyReport에 검색/핀조정 존재, 이중작업 |
| GPS 없는 위치 완전자동추정 | 버림(MVP) | 위험 대비 가치 낮음, user hint fallback |
| 얼굴 모자이크 신고 Must | 버림(MVP) | 필수 제출요건으로 확인 안 됨. privacy architecture는 별도 필수 |
| 2시간 원본을 무조건 전체 서버 업로드 | 버림 | 전송·비용·privacy 부담, 범위축소/proxy/clip 전략 필요 |
| VideoChat3 처음부터 필수 | 보류 | SEARCH/TEMPORAL failure가 필요성 증명 시 challenger |
| SentrySearch 처음부터 필수 | 보류 | SEARCH failure 시 challenger |
| ADAS/CV Candidate Generator | 보류 | PRIMITIVE/TARGET failure 시 재검토 |
| TrafficRAG 전체 시스템 | 보류 | Fixed Reference A/B 효과 확인 후 자동 retrieval |
| 자체 VLM fine-tuning / GPU VM | 보류 | COST/성능 failure가 필요성 증명 시 |
| 자율 multi-agent video exploration | 보류 | deterministic Coarse→Fine baseline이 먼저 |
| 사용자 승인 없는 자동신고 | 버림 | 외부 irreversible action |
| 참교육/벌금/신고 게임화 | 버림 | 안전·공정·완료·처리결과 중심 UX |

---

# 🎤 발표 전 마지막 체크

## 2분 피치 골격

- 누구의 어떤 문제 → 실제 어떻게 준비하는지 → 기존 대안(신고콕)과 남은 gap → 우리 흐름 → 왜 Agent인지 → 3개월 뒤 남는 것 → 첫 사용자 채널

### 누구의 어떤 문제

> 박신고 씨는 위험한 교통위반을 봤고 **이미 신고하려고 마음먹었습니다.** 하지만 집에 돌아와 SD카드를 연결한 뒤 사건 파일부터 다시 찾고, 구간·용량·시간·위치·차량번호를 맞춰야 합니다.

### 지금 어떻게 버티는지

> 실제 신고 workflow에서도 SD카드 영상탐색 → 편집파일 첨부 → 안전신문고 위치 검색/핀조정 → 차량번호·날짜·시간·내용 → 본인인증을 거칩니다. 신고콕은 이 후반부를 줄이지만 사용자가 사건을 먼저 찾아야 합니다.

### 우리 흐름 하나

> `“6시 반쯤 흰 SUV가 실선을 넘었어요”`라고 말하면 Main Agent가 기억단서를 정리하고, Gemini Coarse/Fine이 장시간 영상에서 Top-3와 시각적 근거를 찾습니다. 사용자가 사건을 고르면 번호판·시각출처·위치단서·신고영상을 구조화해 SafetyReport handoff까지 준비합니다.

### 왜 챗봇이 아닌지

> 대화는 navigation일 뿐입니다. 실제로는 Long-video VLM·OCR·metadata/GPS·FFmpeg·Evidence Rule을 Case State에 따라 호출하고, 중요한 결과는 structured card에서 사람이 검증합니다.

### 3개월 뒤 남는 것

> 특정 모델이 아니라 **locked real long-dashcam eval/failure/correction data와 Agentic Evidence workflow**가 남습니다.

### 첫 100명

> 보배드림 교통사고/블랙박스 게시판에서 실제 신고 행동 인터뷰부터 Prototype 비교까지 이어갑니다.

### 심사위원 머리에 남길 한 장면

> **수십 개 블랙박스 파일 + “6시 반쯤 흰 SUV가 실선을 넘었어” → Top-3 Candidate → 사용자가 한 장면 선택 → 20초 Evidence clip + plate best frame + time/location provenance가 한 카드로 정리되는 순간**

---

## ⭐ 숫자를 말할 때의 규율

### 사실/조사값

- `2023년 교통법규 위반 공익신고 약 366만 건`
- `대표 동적 위반유형 약 203만 건`
- `안전신문고 동영상 한 파일 최대 130MB`
- `교통법규 위반 공익신고의 2일 이내 신고 urgency`

### 가설/시나리오

- `박신고 씨 20분` → 평균 아님, Proto-persona workflow scenario
- `20분 → 3분` → **사용자 직접 작업시간 목표**, total processing latency 보장 아님
- `약 57만 시간 절감` → 대표유형 약 200만 건 전체에 17분 절감이 적용된다는 **potential impact estimation**

실측 전에는:

- ❌ “모든 203만 건이 영상 신고입니다.”
- ❌ “평균 20분이 듭니다.”
- ❌ “정확도 90%입니다.”
- ❌ “무조건 3분이면 끝납니다.”

대신:

- ✅ “실제 신고 workflow에서 이 단계들이 존재함을 확인했습니다.”
- ✅ “20→3분은 사용자 테스트로 검증할 제품 목표입니다.”
- ✅ “최종 성능은 locked real long-dashcam의 Final Recall@3와 CI/비용을 함께 보고합니다.”

---

## ⭐ 마지막 문장 — 지금 가장 불확실한 부분

<aside>

저희가 가장 모르는 것은 ________________입니다.
2단계 ____주차에 ________________ 방법으로 확인할 계획입니다.

</aside>

> **저희가 가장 모르는 것은 Evidence Preparation 중 사건 재탐색이 실제 신고자의 최우선 pain인지, 자동으로 사건·증거를 준비한 상태가 실제 신고 완료 행동을 얼마나 높이는지, 그리고 real long-dashcam에서 Gemini Coarse/Fine이 초기 4종 event를 감당 가능한 비용·지연으로 Final Top-3 안에 안정적으로 넣을 수 있는가입니다.**
>
> **초반에는 실제 신고자 행동 인터뷰와 기존방식 시간측정, 동시에 Evaluation Harness + Gemini baseline + Structured/Reference A/B를 수행해 제품가설과 기술가설을 같이 확인합니다.**

---

# 심사 예상 질문 최종 점검

| 질문 | 답할 수 있나 | 어디에 있나 |
| --- | --- | --- |
| 이 서비스가 꼭 필요한 딱 한 사람은? | ☑ | 1-1 — 박신고 Proto-persona |
| 신고를 왜 하나 / 왜 포기하나? | ☑/검증중 | 1-2 동기·저항 |
| 지금 어떻게 버티고 있나? | ☑ | 1-2 실제 workflow + 신고콕 |
| 신고콕이 있는데 왜 필요한가? | ☑ | 1-2 · 2-1 · 5-1 |
| 기술적으로 제일 겁나는 부분은? | ☑ | 1-4 |
| AI가 어디까지 하고 사람은 어디서 멈추나? | ☑ | 2-1 · 3-2 |
| 왜 법적 위반을 AI가 확정하지 않나? | ☑ | Technical boundary / 2-1 |
| 이게 잘 됐다는 걸 뭘로 아나? | ☑ | 2-3 — Final Recall@3 + Product E2E |
| 왜 300개/90%가 아니냐? | ☑ | 2-3 — Pilot/CI/locked real |
| AI가 틀리면 사용자에게 어떻게 보이나? | ☑ | 2-4 · 3-5 |
| 이거 그냥 챗봇으로 하면 왜 안 되나? | ☑ | 3-1 — Agentic Orchestrator + Tools |
| 왜 UI가 채팅형인가? | ☑ | 3-5 — 자연어 correction + structured cards |
| 위치를 왜 서비스에서 핀으로 확정하지 않나? | ☑ | 2-1 장소 MVP / 3-5 |
| timestamp를 사후 삽입해도 되나? | △ | provenance/선택기능으로 설계, 공식 상시 인정은 열린 질문 |
| 얼굴 모자이크는 왜 없나? | ☑ | 5-3 — 제출 Must 아님, privacy는 별도 |
| ChatGPT/Gemini에 그냥 영상 넣으면? | ☑ | 4-1 — E2E stateful workflow + eval/data |
| 쓸수록 남들이 못 따라오는 지점은? | ☑ | 4-1·4-2 |
| 모델이 더 좋아지면 없어지는가? | ☑ | 4-3 |
| 첫 100명은 어떻게 모을 것인가? | ☑ | 4-4 |
| 지금 가장 불확실한 부분은? | ☑ | 발표 마지막 문장 |
| API 키/원본영상/외부 AI 전송은? | △ | 5-3 — 실제 저장소·privacy architecture 구현 후 체크 |
