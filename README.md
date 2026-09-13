# 대신고 (Daesingo)

**블랙박스 영상에서 교통위반 신고 자료를 준비해 주는 제품.**

위험한 위반을 목격했고 신고할 마음도 생겼지만, 운전 중이라 **정확한 시각과 장소를 적어두지 못한 운전자**가 타깃이다. 몇 시간짜리 영상을 손으로 훑는 대신, 기억나는 단서를 자연어로 말하면(대충 언제 · 어떤 차 · 무슨 일 · 어디쯤) 제품이 사건 구간 후보와 그 전후 증거를 찾아온다. **사용자는 확인하고 고치기만 한다.**

목표는 신고할 마음이 없던 사람을 유도하는 게 아니라, **이미 생긴 신고 의향이 준비 과정의 마찰 때문에 사라지지 않게 하는 것**이다.

> **현재 상태:** 설계와 문서가 정리된 단계다. 실행되는 것은 `apps/prototype`의 흐름 프로토타입 하나뿐이고, **백엔드·영상 파이프라인·AI 호출이 없는 목데이터 UI 습작**이다. `src/`와 `eval/`은 폴더와 README만 있고 코드가 없다.

## 무엇을 하고, 무엇을 하지 않는가

제품이 약속하는 것과 명시적으로 하지 않는 것은 **[`docs/product/product-spec.md`](docs/product/product-spec.md) §5**가 소유한다. 요약하면:

**한다** — 자연어 기억 단서를 시간·차량·상황 정보로 구조화 · 1차 탐색(Coarse)으로 상위 후보 생성 후 정밀 검증 · Top-3 구조화 카드와 사용자 보정 · 사건 전후 증거 구간 구성(**영상 파일 경계에 걸친 사건 포함**) · 번호판 best frame과 OCR · 시각을 **출처와 함께**(화면 표시 / 파일명 / 메타데이터 / 사용자 / Unknown) 관리 · GPS가 있으면 위치 보강, 없으면 사용자 단서 유지 · 신고요건 점검과 안전신문고 handoff

**하지 않는다** — AI가 법적 위반 여부를 최종 확정 · 사용자 승인 없는 무인 자동신고 · 신뢰 가능한 출처 없는 시각을 임의 생성 · 자체 지도 UI · 모든 도로교통법 위반 유형 지원

### 초기 지원 사건 4종

신호위반 · 중앙선 침범 · 진로변경(백색 실선 침범) · 이륜차 안전모 미착용

4종으로 좁힌 이유는 시간 순서 판단(신호 → 정지선 → 통과)과 객체 속성 판단(안전모)처럼 **서로 다른 인식 능력을 함께 검증**할 수 있기 때문이다. 자세한 근거는 product-spec §6.

### 넘지 않는 선

[`product-spec.md`](docs/product/product-spec.md) **§7**이 제품 수준 불변 경계를 소유한다. 그중 셋만 옮기면:

- **원본 영상을 덮어쓰지 않는다.**
- 번호판·시각·위치가 불확실하면 **값을 만들어내지 않고** 출처와 `확인 필요`/`UNKNOWN` 상태를 보여준다.
- **실제 안전신문고 제출은 사용자가 직접 한다.**

## 사용자 흐름

영상 업로드 → 영상에서 읽은 정보 확인(촬영 시간 · 화면 시각 유무 · GPS 유무) → 사용자가 기억을 말함 → 단서 구조화와 탐색 범위 확인 → 분석 → 사건 후보 비교·검증 → 사용자 보정 → 번호판·시각·위치 확정 → 신고요건 점검 → 안전신문고로 handoff.

화면 단위 흐름과 **실패했을 때 무엇을 보여주는지**는 [`docs/product/core-user-flow.md`](docs/product/core-user-flow.md)가 소유한다. 채팅 인터페이스가 아니라 **단계형 화면**이고, 자연어 입력은 단서 입력 한 곳에만 있다.

## 구조

모듈 7개로 나눈다. 기준은 팀원 수가 아니라 **서로 다른 변경 이유**다 — 무엇이 바뀌면 어디를 고치게 되는가.

| 모듈 | 다루는 사실 |
| --- | --- |
| `recording` | 블랙박스 파일·stream이라는 현실. Source가 말해주는 것과 픽셀 접근 경계 |
| `search` | 넓은 영상 범위의 픽셀이 말해주는 것 — 사건 구간 후보 탐색 |
| `readout` | 좁은 화면 영역의 값 — 번호판·화면 시각이 어떻게 보이는지 |
| `evidence` | 확정 Evidence + 신고 규정 + Package 정책 |
| `case` | 진행 상태·사용자 선택·부분 재실행·작업 발주 의도 |
| `web` | 도메인 상태를 갖지 않고 `CaseView`를 표현하는 작업공간 |
| `eval` | 제품 런타임과 분리된 채점 도구 |

두 가지가 이 구조의 핵심이다. **관찰(`search`·`readout`)과 확정(`evidence`)을 분리한다** — "AI가 그렇게 봤다"와 "이 값이 맞다"는 다른 사실이다. 그리고 **`eval`은 제품 런타임이 아니다** — `search`와 `readout`은 `eval`의 존재를 모른다.

경계·계약·각 모듈이 **알면 안 되는 것**은 [`docs/architecture/module-architecture.md`](docs/architecture/module-architecture.md)가 소유한다. 1,900줄이므로 전체를 읽지 않는다 — §1 → §2 → 자기 모듈 §4 → §5 순서로 읽는다.

### 기술 스택 (확정)

Python · FastAPI · **Modular Monolith**(API 1 + Worker 1) · MySQL 8.4 · DB Queue · ffmpeg/ffprobe · AWS · Desktop Web 우선(모바일 반응형은 MVP 제외). 안전신문고 자동 제출 API는 연동하지 않는다.

## 레포 구성

`apps/`에 실행 코드, `docs/`에 living document, `src/`·`eval/`에 코드 골격이 있다. 골격 폴더에는 README만 있고 코드가 없다 — 데이터 계약이 확정되면 각 Owner가 채운다.

| 경로 | 내용 |
| --- | --- |
| `apps/prototype/` | 흐름 프로토타입 (React 19 + Vite 6, 목데이터). **제품 코드 아님** |
| `apps/web/` | 실제 웹 앱 자리. README만 — 프로토타입을 확장할지 새로 만들지는 `web` Owner가 정한다 |
| `src/daesingo/` | Python 모듈형 모놀리스 골격 — 도메인 5개 + `common` runtime + `api`/`worker` composition root |
| `eval/` | 오프라인 채점 골격 — `datasets` / `manifests` / `runners` / `scorers` / `predictions` / `results` / `locked_test` |
| `scripts/`, `tests/` | 팀 스크립트와 테스트 자리 |
| `docs/product/` | 타깃·문제·제품 약속·지원 범위·사용자 흐름·검증 계획 |
| `docs/architecture/` | 모듈 경계(v4)와 계약 원칙 |
| `docs/modules/` | 모듈별 조사·실험·결정·계약 |
| `docs/management/` | 역할 배정·운영 계획·cross-cutting 결정·보안 검수 |
| `docs/design/` | 디자인 시스템·1단계 목업·프로토타입 스펙 |
| `docs/archive/` | 지난 제출물과 종료된 안건 — **현재 문서가 아니다** |

문서는 한국어로 쓰고 폴더·파일 이름은 영어로 쓴다.

## 문서를 읽는 순서

**전체를 읽지 않는다.** 자기 작업에 해당하는 것만 연다.

| 하려는 일 | 읽을 것 |
| --- | --- |
| 제품이 무엇을 약속하고 안 하는지 | `docs/product/product-spec.md` §5 · §7 |
| 화면 흐름 · 실패 UX | `docs/product/core-user-flow.md` |
| 내 모듈의 경계 · 계약 · 금지사항 | `docs/architecture/module-architecture.md` §1 → §2 → §4 내 모듈 → §5 |
| 내 모듈의 조사 · 실험 · 결정 | `docs/modules/<module>/` |
| 누가 무엇을 맡는지 | `docs/management/ownership.md` |
| 운영 결정(승인 경로 · 리뷰 담당) | `docs/management/cross-cutting-decisions.md` |
| 문서 폴더 규칙 · 문서가 서로 다른 말을 할 때 | `docs/README.md` |

문서가 충돌하면 우선순위는 **제품 약속 = `product-spec.md`** → **모듈 경계·계약 = `module-architecture.md`(v4)** → **화면 흐름 = `core-user-flow.md`** 이고, 셋이 어긋나면 혼자 고치지 않고 주간 회의 안건으로 올린다. 자세한 규칙은 [`docs/README.md`](docs/README.md).

**미결은 미결로 남긴다.** 업로드 전략 · timeout 수치 · correction 로그 재사용 설계 · overlay 존재 탐지 세부 · 실패 분류 이름 목록은 실측 전이라 `미결`로 표시돼 있다. 문서를 완성도 있게 보이려고 채우지 않는다.

## 실행

Node.js 20 이상. npm workspace라서 **레포 루트에서 한 번만** 설치한다(`apps/*` 안에서 하지 않는다).

```bash
npm install            # 루트에서 한 번
npm run dev:prototype  # Vite가 출력하는 URL 열기 (기본 http://localhost:5173)
```

```bash
npm run build              # build 스크립트가 있는 workspace 전부
npm run preview:prototype  # 프로토타입 프로덕션 빌드 서빙
```

`src/daesingo`와 `eval/`은 아직 실행할 것이 없다. `pyproject.toml`과 의존성은 코드를 시작하는 Owner가 만든다.

### 프로토타입에 대해

`apps/prototype`은 **흐름 프로토타입**이다. 목데이터로 도는 10화면이고 백엔드·영상 파이프라인·AI 호출이 없다. 결과 없음 · 탐색 실패 · 범위 확장처럼 **실패 상태로 바로 점프하는 `ScenarioBar` 데모 컨트롤**이 들어 있다.

실제 웹 앱이 이 코드를 확장할지 새로 시작할지는 **미결**이고 `web` Owner가 정한다. 판단에 필요한 사실은 [`apps/prototype/README.md`](apps/prototype/README.md)에 있다.

## 라이선스

[MIT](LICENSE).
